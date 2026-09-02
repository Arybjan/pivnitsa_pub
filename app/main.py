from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import router
from app.api.v1.endpoints import health
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.services.publisher import EventPublisher
from loguru import logger
import sys

# Настройка логов
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="DEBUG"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск
    logger.info("Starting Event Service...")

    # Создаем таблицы (в проде использовать миграции)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    # Проверка подключения к Redis
    try:
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    # Подключение к RabbitMQ
    publisher = EventPublisher()
    try:
        await publisher.connect()
        logger.info("RabbitMQ connected")
    except Exception as e:
        logger.error(f"RabbitMQ connection failed: {e}")

    yield  # Приложение запущено

    # Остановка
    logger.info("Shutting down Event Service...")
    await redis_client.close()
    await engine.dispose()

# Создаем приложение
app = FastAPI(
    title="Event Service",
    description="Микросервис для управления мероприятиями ночного клуба",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "service": "event-service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
