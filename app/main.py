import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.notifications import router as notifications_router
from app.services.event_consumer import start_event_consumer, stop_event_consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Фоновый запуск consumer RabbitMQ
    consumer_task = asyncio.create_task(start_event_consumer())
    yield
    # Остановка consumer при выключении сервера
    await stop_event_consumer()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Notification Microservice", lifespan=lifespan)

app.include_router(notifications_router, prefix="/api/v1")


# Проверка работоспособности сервиса
@app.get("/health")
async def health_check():
    return {"status": "healthy"}