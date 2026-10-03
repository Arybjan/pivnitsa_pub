import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.core.security import get_current_user, require_service_or_admin
from app.core.database import get_db
from app.core.templates import render_notification, render_sms
from app.services.event_consumer import process_event_message
from tests.test_security import create_token, TestSessionLocal


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


def test_templates_rendering():
    title, message = render_notification("event_published", title="Rock Fest", date="10.10.2026 в 20:00")
    assert "Rock Fest" in title
    assert "10.10.2026" in message

    sms = render_sms("booking_confirmed", table_number=5)
    assert sms is not None
    assert "#5" in sms
    assert "podtverzhdena" in sms


def test_templates_fallback():
    title, message = render_notification("unknown_type", title="Custom", message="Body")
    assert title == "Custom"
    assert message == "Body"

    sms = render_sms("unknown_type")
    assert sms is None


@pytest.mark.asyncio
async def test_broadcast_notification_visibility(auth_client):
    async with auth_client as ac:
        service_token = create_token(sub="999", role="service")
        post_res = await ac.post(
            "/api/v1/notifications/",
            json={
                "user_id": None,
                "title": "Общий анонс",
                "message": "Сегодня в пабе скидки на все крафтовое пиво!",
                "type": "event_published",
            },
            headers={"Authorization": f"Bearer {service_token}"}
        )
        assert post_res.status_code == 201
        notif_id = post_res.json()["id"]

        user_token = create_token(sub="12", role="user")
        get_res = await ac.get(
            "/api/v1/notifications/?user_id=12",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert get_res.status_code == 200
        items = get_res.json()
        assert any(n["id"] == notif_id for n in items)

        single_res = await ac.get(
            f"/api/v1/notifications/{notif_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert single_res.status_code == 200
        assert single_res.json()["title"] == "Общий анонс"

        del_res = await ac.delete(
            f"/api/v1/notifications/{notif_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert del_res.status_code == 403

        admin_del = await ac.delete(
            f"/api/v1/notifications/{notif_id}",
            headers={"Authorization": f"Bearer {service_token}"}
        )
        assert admin_del.status_code == 200


@pytest.mark.asyncio
async def test_event_consumer_with_phone_triggers_sms():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "booking_id": 100,
        "table_id": 4,
        "user_id": 15,
        "phone": "+996770123456",
    }

    with patch("app.services.event_consumer.send_sms_via_nikita", new_callable=AsyncMock) as mock_send_sms:
        notifications = await process_event_message("booking.confirmed", payload, mock_session)
        assert len(notifications) == 1
        assert notifications[0].user_id == 15
        assert notifications[0].type == "booking_confirmed"

        mock_send_sms.assert_called_once()
        called_phone, called_text = mock_send_sms.call_args[0]
        assert called_phone == "+996770123456"
        assert "#4" in called_text
