import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.bookings import router as bookings_router
from app.tasks import expire_bookings_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(expire_bookings_loop())

    yield

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Booking Service",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(bookings_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "booking-service",
    }