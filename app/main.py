from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.messaging.publisher import publisher
from app.messaging.consumer import consumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema if running with SQLite or auto-create
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.warning("Could not auto-create database tables: %s", e)

    # Initialize RabbitMQ connections
    await publisher.connect()
    await consumer.start()

    yield

    await consumer.close()
    await publisher.close()
    await engine.dispose()

app = FastAPI(
    title="Pivnitsa Pub Payment Service",
    description="PCI-DSS compliant payment processing service for table reservations (US-24, US-25, US-26)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
