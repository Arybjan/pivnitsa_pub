import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=10,
)

class CacheService:
    @staticmethod
    async def get(key: str) -> str | None:
        return await redis_client.get(key)

    @staticmethod
    async def delete(key: str):
        await redis_client.delete(key)

    @staticmethod
    async def delete_pattern(pattern: str):
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
