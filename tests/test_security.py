import time
import jwt
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_service_or_admin
from app.models.notification import Notification

test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
def auth_client():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_service_or_admin, None)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def create_token(sub="10", role="user", is_active=True, token_type="access", exp_offset=3600, secret=None):
    payload = {
        "sub": str(sub),
        "role": role,
        "is_active": is_active,
        "token_type": token_type,
        "exp": int(time.time()) + exp_offset,
    }
    return jwt.encode(payload, secret or settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.mark.asyncio
async def test_unauthorized_request_rejected(auth_client):
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(auth_client):
    token = create_token(exp_offset=-100)
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rejected(auth_client):
    token = create_token(token_type="refresh")
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_rejected(auth_client):
    token = create_token(is_active=False)
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_forbidden_access_to_other_user(auth_client):
    token = create_token(sub="10", role="user")
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/?user_id=20", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_send_sms(auth_client):
    token = create_token(sub="10", role="user")
    async with auth_client as ac:
        res = await ac.post("/api/v1/notifications/sms", json={"phone_number": "996555123456", "message": "Test"}, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_service_role_can_send_sms(auth_client):
    token = create_token(sub="1", role="service")
    async with auth_client as ac:
        res = await ac.post("/api/v1/notifications/sms", json={"phone_number": "996555123456", "message": "Test"}, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_user_can_read_own_notifications(auth_client):
    async with TestSessionLocal() as session:
        session.add(Notification(user_id=50, title="Own Notice", message="Message", type="info", is_read=False))
        session.add(Notification(user_id=99, title="Foreign Notice", message="Message", type="info", is_read=False))
        await session.commit()

    token = create_token(sub="50", role="user")
    async with auth_client as ac:
        res = await ac.get("/api/v1/notifications/?user_id=50", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["title"] == "Own Notice"
