import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import async_session_maker, engine
from app.messaging.connection import start_messaging, stop_messaging
from app.messaging.publisher import publisher
from app.messaging.workers import outbox_relay_loop, refund_retry_loop
from app.models.payment import OutboxEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схему БД создают только миграции (alembic upgrade head в Dockerfile):
    # create_all здесь скрывал расхождения между моделью и миграцией.
    tasks = [
        asyncio.create_task(start_messaging()),
        asyncio.create_task(outbox_relay_loop()),
        asyncio.create_task(refund_retry_loop()),
    ]

    yield

    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass

    await stop_messaging()
    await engine.dispose()


app = FastAPI(
    title="Pivnitsa Pub Payment Service",
    description="PCI-DSS compliant payment processing service for table reservations (US-24, US-25, US-26)",
    version="2.0.0",
    lifespan=lifespan,
)

# Токен передаётся в заголовке Authorization, cookie не нужны — allow_credentials выключен
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "service": "payment-service",
        "environment": settings.PAYMENT_GATEWAY_ENV,
    }


@app.get("/health/ready", tags=["system"])
async def readiness_check():
    checks = {"database": False, "rabbitmq": publisher.is_connected, "outbox_backlog": None}
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            checks["outbox_backlog"] = (
                await session.execute(
                    select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
                )
            ).scalar_one()
        checks["database"] = True
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)

    ready = checks["database"] and checks["rabbitmq"]
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
