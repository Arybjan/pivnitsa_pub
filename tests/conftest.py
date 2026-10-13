import os

os.environ.update(
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    REDIS_URL="redis://localhost:6380/0",
    RABBITMQ_URL="amqp://guest:guest@localhost:5673/",
    JWT_SECRET="test-secret-for-events",
    AUTH_SERVICE_URL="http://auth.test",
    ENVIRONMENT="test",
)

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import delete
from app.models.events import Event, EventOutbox
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

USER_ID = 1


@pytest.fixture
def token():
    def make(**overrides):
        payload = {
            "sub": str(USER_ID), "type": "access", "role": "admin", "is_active": True,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        payload.update(overrides)
        return {"Authorization": "Bearer " + jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)}
    return make


@pytest_asyncio.fixture
async def sessions():
    engine = create_async_engine(os.environ.get("EVENT_TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(delete(EventOutbox))
        await connection.execute(delete(Event))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(sessions):
    async def database():
        async with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def event_data():
    return {"title": "Concert", "starts_at": "2030-08-20T18:00:00Z", "ends_at": "2030-08-20T21:00:00+00:00"}
