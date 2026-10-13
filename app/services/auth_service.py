from datetime import timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenError, decode_token, encode_token, hash_password, verify_password
from app.models import Profile, User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    OtpPurpose,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.errors import ServiceError
from app.services.otp_service import OtpService
from app.services.session_store import SessionStore

_INVALID_CREDENTIALS = "Invalid phone or password"


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.otp = OtpService(redis)
        self.sessions = SessionStore(redis)

    async def get_user_by_phone(self, phone: str) -> User | None:
        return await self.db.scalar(select(User).where(User.phone == phone))

    async def send_otp(self, phone: str, purpose: OtpPurpose):
        user = await self.get_user_by_phone(phone)
        if purpose == OtpPurpose.REGISTER and user is not None:
            raise ServiceError(409, "Phone number is already registered")
        # Для входа и сброса пароля не раскрываем, есть ли такой номер: ответ одинаковый, SMS не уходит
        deliver = purpose == OtpPurpose.REGISTER or (user is not None and user.is_active)
        return await self.otp.issue(phone, purpose, deliver=deliver)

    async def register(self, data: RegisterRequest) -> AuthResponse:
        phone = await self.otp.consume_verification(data.verification_token, OtpPurpose.REGISTER)
        user = User(phone=phone, email=data.email, password_hash=hash_password(data.password))
        user.profile = Profile(first_name=data.first_name, last_name=data.last_name)
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            if await self.get_user_by_phone(phone):
                raise ServiceError(409, "Phone number is already registered") from None
            raise ServiceError(409, "Email is already in use") from None
        await self.db.refresh(user, ["profile", "created_at"])
        return await self._auth_response(user)

    async def login(self, data: LoginRequest) -> AuthResponse:
        if data.verification_token is not None:
            phone = await self.otp.consume_verification(data.verification_token, OtpPurpose.LOGIN)
            user = await self.get_user_by_phone(phone)
            if user is None:
                raise ServiceError(401, "User not found")
        else:
            user = await self._check_password(data.phone, data.password)
        if not user.is_active:
            raise ServiceError(403, "Account is deactivated")
        return await self._auth_response(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        user_id, jti = self._decode_refresh(refresh_token)
        if not await self.sessions.consume(user_id, jti):
            # Повторное использование уже обменянного токена — признак кражи: завершаем все сессии
            await self.sessions.revoke_all(user_id)
            raise ServiceError(401, "Refresh token is no longer valid")
        user = await self.db.get(User, user_id)
        if user is None or not user.is_active:
            await self.sessions.revoke_all(user_id)
            raise ServiceError(401, "Refresh token is no longer valid")
        return await self.issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        try:
            user_id, jti = self._decode_refresh(refresh_token)
        except ServiceError:
            return  # выход идемпотентен
        await self.sessions.revoke(user_id, jti)

    async def reset_password(self, data: PasswordResetRequest) -> None:
        phone = await self.otp.consume_verification(data.verification_token, OtpPurpose.RESET_PASSWORD)
        user = await self.get_user_by_phone(phone)
        if user is None or not user.is_active:
            raise ServiceError(401, "User not found")
        user.password_hash = hash_password(data.new_password)
        await self.db.commit()
        await self.sessions.revoke_all(user.id)
        await self.redis.delete(_login_failures_key(phone))

    async def issue_tokens(self, user: User) -> TokenResponse:
        access_ttl = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Клеймы под контракт остальных сервисов: sub=int, role, phone, is_active
        access, _, _ = encode_token(
            "access", str(user.id), access_ttl, role=user.role, phone=user.phone, is_active=user.is_active
        )
        refresh, jti, _ = encode_token("refresh", str(user.id), timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
        await self.sessions.add(user.id, jti)
        return TokenResponse(access_token=access, refresh_token=refresh, expires_in=int(access_ttl.total_seconds()))

    async def _auth_response(self, user: User) -> AuthResponse:
        tokens = await self.issue_tokens(user)
        return AuthResponse(**tokens.model_dump(), user=UserResponse.from_user(user))

    async def _check_password(self, phone: str, password: str) -> User:
        failures_key = _login_failures_key(phone)
        failures = int(await self.redis.get(failures_key) or 0)
        if failures >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            retry_after = max(await self.redis.ttl(failures_key), 1)
            raise ServiceError(429, "Too many failed login attempts", headers={"Retry-After": str(retry_after)})

        user = await self.get_user_by_phone(phone)
        if not verify_password(password, user.password_hash if user else None):
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(failures_key)
                pipe.expire(failures_key, settings.LOGIN_LOCKOUT_SECONDS, nx=True)
                await pipe.execute()
            raise ServiceError(401, _INVALID_CREDENTIALS)

        await self.redis.delete(failures_key)
        return user

    @staticmethod
    def _decode_refresh(token: str) -> tuple[int, str]:
        try:
            payload = decode_token(token, "refresh")
            return int(payload["sub"]), payload["jti"]
        except (TokenError, ValueError):
            raise ServiceError(401, "Invalid refresh token") from None


def _login_failures_key(phone: str) -> str:
    return f"auth:login_failures:{phone}"
