import os

# Настройки задаются до импорта приложения
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    REDIS_URL="redis://localhost:6379/15",
    JWT_SECRET="test-secret-key-that-is-long-enough-for-hs256",
    SMS_PROVIDER="console",
    OTP_EXPOSE_IN_RESPONSE="true",
)

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app

PASSWORD = "secret123"


@pytest.fixture
async def redis():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def client(redis, session_maker):
    async def _get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def get_verification_token(client, phone: str, purpose: str = "register") -> str:
    sent = await client.post("/api/v1/auth/otp/send", json={"phone": phone, "purpose": purpose})
    assert sent.status_code == 200, sent.text
    code = sent.json()["debug_code"]
    verified = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code, "purpose": purpose})
    assert verified.status_code == 200, verified.text
    return verified.json()["verification_token"]


async def register_user(client, phone: str = "+996555123456", password: str = PASSWORD, **extra) -> dict:
    token = await get_verification_token(client, phone)
    response = await client.post(
        "/api/v1/auth/register", json={"verification_token": token, "password": password, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}
