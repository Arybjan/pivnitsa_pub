import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db
from app.models.notification import Notification, NotificationSettings
from app.services.event_consumer import process_event_message
from tests.conftest import TestSessionLocal


@pytest.fixture
def client():
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_get_default_settings(client):
    async with client as ac:
        response = await ac.get("/api/v1/notifications/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 1
        assert data["events_enabled"] is True
        assert data["booking_enabled"] is True
        assert data["sms_enabled"] is True


@pytest.mark.asyncio
async def test_update_settings(client):
    async with client as ac:
        patch_res = await ac.patch(
            "/api/v1/notifications/settings",
            json={"events_enabled": False}
        )
        assert patch_res.status_code == 200
        data = patch_res.json()
        assert data["events_enabled"] is False
        assert data["booking_enabled"] is True
        assert data["sms_enabled"] is True

        get_res = await ac.get("/api/v1/notifications/settings")
        assert get_res.status_code == 200
        assert get_res.json()["events_enabled"] is False


@pytest.mark.asyncio
async def test_events_disabled_immediate_effect(client):
    async with client as ac:
        await ac.post(
            "/api/v1/notifications/",
            json={"user_id": None, "title": "Party", "message": "Big Party", "type": "event_published"}
        )
        await ac.post(
            "/api/v1/notifications/",
            json={"user_id": 1, "title": "Booking", "message": "Table 5", "type": "booking_created"}
        )

        res = await ac.get("/api/v1/notifications/?user_id=1")
        assert len(res.json()) == 2
        cnt = await ac.get("/api/v1/notifications/unread-count?user_id=1")
        assert cnt.json()["unread_count"] == 2

        await ac.patch("/api/v1/notifications/settings", json={"events_enabled": False})

        res_after = await ac.get("/api/v1/notifications/?user_id=1")
        items = res_after.json()
        assert len(items) == 1
        assert items[0]["type"] == "booking_created"

        cnt_after = await ac.get("/api/v1/notifications/unread-count?user_id=1")
        assert cnt_after.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_booking_disabled_immediate_effect(client):
    async with client as ac:
        await ac.post(
            "/api/v1/notifications/",
            json={"user_id": None, "title": "Party", "message": "Big Party", "type": "event_published"}
        )
        await ac.post(
            "/api/v1/notifications/",
            json={"user_id": 1, "title": "Booking", "message": "Table 5", "type": "booking_created"}
        )

        await ac.patch("/api/v1/notifications/settings", json={"booking_enabled": False})

        res = await ac.get("/api/v1/notifications/?user_id=1")
        items = res.json()
        assert len(items) == 1
        assert items[0]["type"] == "event_published"

        cnt = await ac.get("/api/v1/notifications/unread-count?user_id=1")
        assert cnt.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_event_consumer_respects_settings():
    async with TestSessionLocal() as session:
        settings = NotificationSettings(
            user_id=10,
            events_enabled=True,
            booking_enabled=False,
            sms_enabled=False
        )
        session.add(settings)
        await session.commit()

        payload = {
            "booking_id": 999,
            "user_id": 10,
            "table_id": 3,
            "phone": "+996555123456"
        }
        res = await process_event_message("booking.created", payload, session)
        assert len(res) == 0

        settings.booking_enabled = True
        await session.commit()

        res2 = await process_event_message("booking.confirmed", payload, session)
        assert len(res2) == 1
        assert res2[0].type == "booking_confirmed"
