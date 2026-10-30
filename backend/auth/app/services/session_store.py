from datetime import timedelta

from redis.asyncio import Redis

from app.core.config import settings


def _session_key(jti: str) -> str:
    return f"auth:refresh:{jti}"


def _user_sessions_key(user_id: int) -> str:
    return f"auth:user_sessions:{user_id}"


class SessionStore:
    """Активные refresh-токены в Redis: refresh работает только пока его jti есть в хранилище."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def add(self, user_id: int, jti: str) -> None:
        ttl = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(_session_key(jti), user_id, ex=ttl)
            pipe.sadd(_user_sessions_key(user_id), jti)
            pipe.expire(_user_sessions_key(user_id), ttl)
            await pipe.execute()

    async def consume(self, user_id: int, jti: str) -> bool:
        """Атомарно забирает сессию. False — токен уже использован или отозван."""
        stored = await self.redis.getdel(_session_key(jti))
        await self.redis.srem(_user_sessions_key(user_id), jti)
        return stored is not None and int(stored) == user_id

    async def revoke(self, user_id: int, jti: str) -> None:
        await self.consume(user_id, jti)

    async def revoke_all(self, user_id: int) -> None:
        jtis = await self.redis.smembers(_user_sessions_key(user_id))
        keys = [_session_key(jti) for jti in jtis]
        await self.redis.delete(_user_sessions_key(user_id), *keys)
