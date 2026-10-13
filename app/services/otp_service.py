import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import TokenError, decode_token, encode_token
from app.schemas.auth import OtpPurpose
from app.services.errors import ServiceError
from app.services.sms_sender import SmsDeliveryError, send_sms

# Атомарная проверка кода: сравнение хеша, счётчик попыток и удаление кода в одном Lua-скрипте,
# чтобы параллельные запросы не могли перебирать код сверх лимита.
_VERIFY_SCRIPT = """
local data = redis.call('HMGET', KEYS[1], 'hash', 'attempts')
if not data[1] then return -1 end
local attempts = tonumber(data[2]) + 1
if data[1] == ARGV[1] then
    redis.call('DEL', KEYS[1])
    return 1
end
if attempts >= tonumber(ARGV[2]) then
    redis.call('DEL', KEYS[1])
    return -2
end
redis.call('HSET', KEYS[1], 'attempts', attempts)
return 0
"""


@dataclass
class OtpIssued:
    code: str
    expires_in: int
    resend_after: int


def _hash_code(phone: str, purpose: OtpPurpose, code: str) -> str:
    message = f"{purpose}:{phone}:{code}".encode()
    return hmac.new(settings.internal_jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def _otp_key(phone: str, purpose: OtpPurpose) -> str:
    return f"auth:otp:{purpose}:{phone}"


class OtpService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def issue(self, phone: str, purpose: OtpPurpose, *, deliver: bool = True) -> OtpIssued:
        cooldown_key = f"auth:otp_cooldown:{purpose}:{phone}"
        hourly_key = f"auth:otp_hourly:{phone}"

        if not await self.redis.set(cooldown_key, "1", ex=settings.OTP_RESEND_COOLDOWN_SECONDS, nx=True):
            retry_after = max(await self.redis.ttl(cooldown_key), 1)
            raise ServiceError(429, "Code was sent recently, try again later", headers={"Retry-After": str(retry_after)})

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(hourly_key)
            pipe.expire(hourly_key, 3600, nx=True)
            sent, _ = await pipe.execute()
        if sent > settings.OTP_MAX_SENDS_PER_HOUR:
            retry_after = max(await self.redis.ttl(hourly_key), 1)
            raise ServiceError(429, "Too many codes requested, try again later", headers={"Retry-After": str(retry_after)})

        code = "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))
        key = _otp_key(phone, purpose)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            pipe.hset(key, mapping={"hash": _hash_code(phone, purpose, code), "attempts": 0})
            pipe.expire(key, settings.OTP_TTL_SECONDS)
            await pipe.execute()

        if deliver:
            try:
                await send_sms(phone, f"Pivnitsa: ваш код {code}. Никому его не сообщайте.")
            except SmsDeliveryError:
                await self.redis.delete(key, cooldown_key)
                await self.redis.decr(hourly_key)
                raise ServiceError(503, "SMS delivery is temporarily unavailable") from None

        return OtpIssued(code, settings.OTP_TTL_SECONDS, settings.OTP_RESEND_COOLDOWN_SECONDS)

    async def verify(self, phone: str, purpose: OtpPurpose, code: str) -> tuple[str, int]:
        """Проверяет код и выдаёт одноразовый verification_token."""
        result = await self.redis.eval(
            _VERIFY_SCRIPT, 1, _otp_key(phone, purpose), _hash_code(phone, purpose, code), settings.OTP_MAX_ATTEMPTS
        )
        if result == -1:
            raise ServiceError(400, "Code expired or not requested")
        if result == -2:
            raise ServiceError(429, "Too many invalid attempts, request a new code")
        if result != 1:
            raise ServiceError(400, "Invalid code")

        ttl = timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRE_MINUTES)
        token, jti, _ = encode_token("phone_verification", phone, ttl, purpose=str(purpose))
        await self.redis.set(f"auth:verification:{jti}", phone, ex=int(ttl.total_seconds()))
        return token, int(ttl.total_seconds())

    async def consume_verification(self, token: str, purpose: OtpPurpose) -> str:
        """Возвращает подтверждённый номер. Токен можно использовать только один раз."""
        try:
            payload = decode_token(token, "phone_verification")
        except TokenError:
            raise ServiceError(401, "Invalid or expired verification token") from None
        if payload.get("purpose") != purpose:
            raise ServiceError(401, "Verification token was issued for another action")
        if await self.redis.getdel(f"auth:verification:{payload['jti']}") is None:
            raise ServiceError(401, "Verification token already used")
        return payload["sub"]
