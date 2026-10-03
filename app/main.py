import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bookings import router as bookings_router
from app.messaging.connection import start_messaging, stop_messaging
from app.tasks import expire_bookings_loop


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(expire_bookings_loop()),
        asyncio.create_task(start_messaging()),
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


app = FastAPI(
    title="Booking Service",
    version="1.0.0",
    lifespan=lifespan,
)


# Список адресов фронтенда через запятую; "*" — разрешить всем (для разработки).
# allow_credentials не нужен: токен передаётся в заголовке Authorization, а не в cookie.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bookings_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "booking-service",
    }