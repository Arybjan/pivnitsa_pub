import os

# Настройки читаются при импорте app — окружение задаём до него
TEST_DB_FILE = "test_payments.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["PAYMENT_GATEWAY_ENV"] = "sandbox"
os.environ["DEPOSIT_PER_GUEST"] = "1000.00"

import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import async_session_maker
from app.main import app
from app.messaging.workers import relay_outbox_once
from app.models.payment import OutboxEvent, Payment
from app.services.booking_client import BookingServiceClient
from app.services.payment_service import payment_service


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    # Схема создаётся миграциями, как в Docker: расхождение модели и миграции уронит тесты
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    command.upgrade(Config("alembic.ini"), "head")
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


def make_token(user_id: int, role: str = "guest", exp: bool = True) -> str:
    claims = {"sub": str(user_id), "role": role, "phone": "+996700111222"}
    if exp:
        claims["exp"] = int(time.time()) + 3600
    return jwt.encode(claims, "test-secret", algorithm="HS256")


def auth(user_id: int, role: str = "guest") -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, role)}"}


class FakeBookingService:
    """Имитирует HTTP API Booking Service: GET /api/v1/bookings/{id}."""

    def __init__(self):
        self.bookings: dict[int, dict] = {}
        self.unavailable = False

    def add(self, booking_id: int, user_id: int, guests: int = 2, status: str = "PENDING_PAYMENT", minutes_left: int = 15):
        self.bookings[booking_id] = {
            "id": booking_id,
            "user_id": user_id,
            "table_id": 1,
            "event_id": 1,
            "guests": guests,
            "phone": "+996700111222",
            "status": status,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=minutes_left)).isoformat(),
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.unavailable:
            raise httpx.ConnectError("booking-service is down", request=request)
        token = request.headers["Authorization"].removeprefix("Bearer ")
        user_id = int(jwt.decode(token, "test-secret", algorithms=["HS256"])["sub"])
        booking_id = int(request.url.path.rsplit("/", 1)[-1])
        booking = self.bookings.get(booking_id)
        if booking is None:
            return httpx.Response(404, json={"detail": "Booking not found"})
        if booking["user_id"] != user_id:
            return httpx.Response(403, json={"detail": "You do not have access to this booking"})
        return httpx.Response(200, json=booking)


class FakePublisher:
    def __init__(self, connected: bool = True, fail: bool = False):
        self.is_connected = connected
        self.fail = fail
        self.published: list[dict] = []

    async def publish(self, routing_key, payload):
        if self.fail:
            raise RuntimeError("broker is down")
        self.published.append({"routing_key": routing_key, "payload": payload})


@pytest.fixture
def bookings(monkeypatch) -> FakeBookingService:
    fake = FakeBookingService()
    client = BookingServiceClient(transport=httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_service, "bookings", client)
    return fake


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with async_session_maker() as session:
        await session.execute(delete(OutboxEvent))
        await session.execute(delete(Payment))
        await session.commit()


@pytest_asyncio.fixture
async def client(bookings):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def outbox_events() -> list[dict]:
    async with async_session_maker() as session:
        rows = (await session.execute(select(OutboxEvent).order_by(OutboxEvent.id))).scalars().all()
        return [
            {"routing_key": r.routing_key, "payload": json.loads(r.payload), "published": r.published_at is not None}
            for r in rows
        ]


async def relay(publisher) -> int:
    async with async_session_maker() as session:
        return await relay_outbox_once(session, publisher)
