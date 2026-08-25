import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy.pool import NullPool
from unittest.mock import patch, AsyncMock
import httpx

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.notification import Notification
from app.services import sms_service

# Integration test engine with NullPool
test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def clean_database():
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.commit()
    yield
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.commit()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ==========================================
# 1. API Endpoints Functional Tests
# ==========================================

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_create_notification_success(client: AsyncClient):
    payload = {
        "user_id": 42,
        "title": "Новое бронирование",
        "message": "Ваш столик забронирован на 19:00",
        "type": "booking_confirmed",
        "related_event_id": 101,
        "related_booking_id": 202
    }
    response = await client.post("/api/v1/notifications/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == 42
    assert data["title"] == "Новое бронирование"
    assert data["message"] == "Ваш столик забронирован на 19:00"
    assert data["type"] == "booking_confirmed"
    assert data["related_event_id"] == 101
    assert data["related_booking_id"] == 202
    assert data["is_read"] is False
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_notification_optional_fields(client: AsyncClient):
    payload = {
        "user_id": 43,
        "title": "Простое уведомление",
        "message": "Без связанных событий",
        "type": "system"
    }
    response = await client.post("/api/v1/notifications/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["related_event_id"] is None
    assert data["related_booking_id"] is None
    assert data["is_read"] is False


@pytest.mark.asyncio
async def test_create_notification_validation(client: AsyncClient):
    # Missing fields
    res1 = await client.post("/api/v1/notifications/", json={"user_id": 1, "type": "info"})
    assert res1.status_code == 422

    # Title exceeds 255 chars
    res2 = await client.post("/api/v1/notifications/", json={
        "user_id": 1, "title": "A" * 300, "message": "msg", "type": "info"
    })
    assert res2.status_code == 422

    # Type exceeds 30 chars
    res3 = await client.post("/api/v1/notifications/", json={
        "user_id": 1, "title": "title", "message": "msg", "type": "T" * 50
    })
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_get_user_notifications_ordering_and_isolation(client: AsyncClient):
    for i in range(3):
        await client.post("/api/v1/notifications/", json={
            "user_id": 1,
            "title": f"Title {i}",
            "message": f"Message {i}",
            "type": "alert"
        })
        await asyncio.sleep(0.01)

    await client.post("/api/v1/notifications/", json={
        "user_id": 2,
        "title": "User 2 Title",
        "message": "User 2 Message",
        "type": "alert"
    })

    res1 = await client.get("/api/v1/notifications/?user_id=1")
    assert res1.status_code == 200
    items1 = res1.json()
    assert len(items1) == 3
    assert items1[0]["title"] == "Title 2"
    assert items1[1]["title"] == "Title 1"
    assert items1[2]["title"] == "Title 0"

    res2 = await client.get("/api/v1/notifications/?user_id=2")
    assert res2.status_code == 200
    items2 = res2.json()
    assert len(items2) == 1
    assert items2[0]["title"] == "User 2 Title"


@pytest.mark.asyncio
async def test_get_user_notifications_pagination_and_validation(client: AsyncClient):
    for i in range(7):
        await client.post("/api/v1/notifications/", json={
            "user_id": 5,
            "title": f"Page {i}",
            "message": f"Content {i}",
            "type": "info"
        })

    # Normal pagination
    res_p1 = await client.get("/api/v1/notifications/?user_id=5&limit=3&offset=0")
    assert len(res_p1.json()) == 3

    res_p2 = await client.get("/api/v1/notifications/?user_id=5&limit=3&offset=3")
    assert len(res_p2.json()) == 3

    # Negative offset returns 422
    res_neg_offset = await client.get("/api/v1/notifications/?user_id=5&offset=-1")
    assert res_neg_offset.status_code == 422

    # Negative limit returns 422
    res_neg_limit = await client.get("/api/v1/notifications/?user_id=5&limit=0")
    assert res_neg_limit.status_code == 422


@pytest.mark.asyncio
async def test_unread_count_and_mark_read(client: AsyncClient):
    res_zero = await client.get("/api/v1/notifications/unread-count?user_id=999")
    assert res_zero.status_code == 200
    assert res_zero.json() == {"user_id": 999, "unread_count": 0}

    r1 = await client.post("/api/v1/notifications/", json={
        "user_id": 999, "title": "T1", "message": "M1", "type": "t"
    })
    r2 = await client.post("/api/v1/notifications/", json={
        "user_id": 999, "title": "T2", "message": "M2", "type": "t"
    })
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    res_two = await client.get("/api/v1/notifications/unread-count?user_id=999")
    assert res_two.json()["unread_count"] == 2

    patch_res = await client.patch(f"/api/v1/notifications/{id1}/read")
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "ok"

    res_one = await client.get("/api/v1/notifications/unread-count?user_id=999")
    assert res_one.json()["unread_count"] == 1

    unread_res = await client.get("/api/v1/notifications/?user_id=999&unread_only=true")
    assert len(unread_res.json()) == 1
    assert unread_res.json()[0]["id"] == id2


@pytest.mark.asyncio
async def test_mark_as_read_not_found(client: AsyncClient):
    response = await client.patch("/api/v1/notifications/88888888/read")
    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


@pytest.mark.asyncio
async def test_mark_all_as_read(client: AsyncClient):
    for i in range(5):
        await client.post("/api/v1/notifications/", json={
            "user_id": 777, "title": f"T{i}", "message": f"M{i}", "type": "t"
        })

    res = await client.patch("/api/v1/notifications/read-all?user_id=777")
    assert res.status_code == 200
    assert res.json()["updated_count"] == 5

    cnt_res = await client.get("/api/v1/notifications/unread-count?user_id=777")
    assert cnt_res.json()["unread_count"] == 0

    res_again = await client.patch("/api/v1/notifications/read-all?user_id=777")
    assert res_again.status_code == 200
    assert res_again.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_sms_endpoint_triggers_service(client: AsyncClient):
    with patch("app.api.v1.notifications.send_sms_via_nikita", new_callable=AsyncMock) as mock_nikita:
        mock_nikita.return_value = True
        payload = {"phone_number": "+996 (555) 11-22-33", "message": "Код подтверждения: 9876"}
        res = await client.post("/api/v1/notifications/sms", json=payload)
        assert res.status_code == 200
        assert res.json() == {
            "status": "success",
            "message": "SMS queued for +996 (555) 11-22-33"
        }


# ==========================================
# 2. SMS Service Unit Tests
# ==========================================

@pytest.mark.asyncio
async def test_nikita_xml_payload_generation_and_cleaning():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.text = "<response><status>0</status></response>"
        mock_post.return_value = mock_response

        # Test phone with parens and dots
        res = await sms_service.send_sms_via_nikita("+996 (700) 99.88-77", "Hello <&> Test")
        assert res is True

        called_args, called_kwargs = mock_post.call_args
        xml_content = called_kwargs["content"].decode("utf-8")

        assert "<login>test_login</login>" in xml_content
        assert "<pwd>test_password</pwd>" in xml_content
        assert "<phone>996700998877</phone>" in xml_content
        assert "<text>Hello &lt;&amp;&gt; Test</text>" in xml_content
        assert "<test>1</test>" in xml_content


@pytest.mark.asyncio
async def test_nikita_service_non_zero_status():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.text = "<response><status>1</status><message>Auth error</message></response>"
        mock_post.return_value = mock_response

        res = await sms_service.send_sms_via_nikita("+996555111111", "Some message")
        assert res is False


@pytest.mark.asyncio
async def test_nikita_service_http_failure():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError("500 Server Error", request=AsyncMock(), response=AsyncMock(status_code=500))
        res = await sms_service.send_sms_via_nikita("+996555111111", "Fail text")
        assert res is False


@pytest.mark.asyncio
async def test_nikita_service_timeout():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Connection timed out")
        res = await sms_service.send_sms_via_nikita("+996555111111", "Timeout text")
        assert res is False
