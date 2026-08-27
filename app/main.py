from fastapi import FastAPI
from app.api.v1.notifications import router as notifications_router

app = FastAPI(title="Notification Microservice")

app.include_router(notifications_router, prefix="/api/v1")


# Проверка работоспособности сервиса
@app.get("/health")
async def health_check():
    return {"status": "healthy"}