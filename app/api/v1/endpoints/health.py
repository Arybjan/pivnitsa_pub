from fastapi import APIRouter, status
from app.core.database import engine
from app.core.redis import redis_client
import asyncio

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def health_check():
    """
    Проверка состояния сервиса.
    """
    return {
        "status": "healthy",
        "service": "event-service",
        "version": "1.0.0"
    }

@router.get("/ready")
async def readiness_check():
    """
    Проверка готовности сервиса (зависимости).
    """
    checks = {
        "database": False,
        "redis": False
    }

    # Проверка БД
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        checks["database"] = False

    # Проверка Redis
    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception as e:
        checks["redis"] = False

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        return {"status": "not ready", "checks": checks}
