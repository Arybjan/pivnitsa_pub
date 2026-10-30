"""Пользователь определяется только по access token, user_id в query не используется."""
import pytest
from sqlalchemy import select

from app.models.notification import Notification, NotificationRead
from tests.test_broadcast_and_templates import auth_client  # noqa: F401
from tests.test_security import create_token, TestSessionLocal


def bearer(sub: str, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(sub=sub, role=role)}"}


async def add(*notifications: Notification) -> list[int]:
    async with TestSessionLocal() as session:
        session.add_all(notifications)
        await session.commit()
        return [n.id for n in notifications]


async def is_read(notification_id: int) -> bool:
    async with TestSessionLocal() as session:
        return (await session.get(Notification, notification_id)).is_read


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/notifications/"),
    ("GET", "/api/v1/notifications/unread-count"),
    ("PATCH", "/api/v1/notifications/read-all"),
    ("GET", "/api/v1/notifications/settings"),
    ("PATCH", "/api/v1/notifications/settings"),
])
async def test_user_endpoints_require_token(auth_client, method, path):  # noqa: F811
    async with auth_client as ac:
        res = await ac.request(method, path, json={} if method == "PATCH" else None)
        assert res.status_code == 401
        res = await ac.request(method, f"{path}?user_id=1", headers={"Authorization": "Bearer garbage"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_read_all_without_token_changes_nothing(auth_client):  # noqa: F811
    [own] = await add(Notification(user_id=10, title="T", message="M", type="info"))
    async with auth_client as ac:
        res = await ac.patch("/api/v1/notifications/read-all?user_id=10")
    assert res.status_code == 401
    assert await is_read(own) is False


@pytest.mark.asyncio
async def test_read_all_marks_only_own_notifications(auth_client):  # noqa: F811
    own_a, own_b, foreign = await add(
        Notification(user_id=10, title="A", message="M", type="info"),
        Notification(user_id=10, title="B", message="M", type="info"),
        Notification(user_id=20, title="Foreign", message="M", type="info"),
    )
    async with auth_client as ac:
        # Чужой user_id в query игнорируется - отмечаются уведомления владельца токена
        res = await ac.patch("/api/v1/notifications/read-all?user_id=20", headers=bearer("10"))
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "user_id": 10, "updated_count": 2}

        cnt = await ac.get("/api/v1/notifications/unread-count", headers=bearer("10"))
        assert cnt.json() == {"user_id": 10, "unread_count": 0}
        cnt = await ac.get("/api/v1/notifications/unread-count", headers=bearer("20"))
        assert cnt.json() == {"user_id": 20, "unread_count": 1}

    assert await is_read(own_a) and await is_read(own_b)
    assert await is_read(foreign) is False


@pytest.mark.asyncio
async def test_read_all_marks_broadcast_only_for_current_user(auth_client):  # noqa: F811
    [broadcast] = await add(Notification(user_id=None, title="Анонс", message="M", type="event_published"))
    async with auth_client as ac:
        res = await ac.patch("/api/v1/notifications/read-all", headers=bearer("10"))
        assert res.json()["updated_count"] == 1
        res = await ac.patch("/api/v1/notifications/read-all", headers=bearer("10"))
        assert res.json()["updated_count"] == 0

        mine = (await ac.get("/api/v1/notifications/", headers=bearer("10"))).json()
        assert [(n["id"], n["is_read"]) for n in mine] == [(broadcast, True)]
        single = await ac.get(f"/api/v1/notifications/{broadcast}", headers=bearer("10"))
        assert single.json()["is_read"] is True

        # Для другого пользователя анонс по-прежнему не прочитан
        other = (await ac.get("/api/v1/notifications/?unread_only=true", headers=bearer("20"))).json()
        assert [(n["id"], n["is_read"]) for n in other] == [(broadcast, False)]
        cnt = await ac.get("/api/v1/notifications/unread-count", headers=bearer("20"))
        assert cnt.json()["unread_count"] == 1

    assert await is_read(broadcast) is False


@pytest.mark.asyncio
async def test_mark_broadcast_as_read_is_per_user(auth_client):  # noqa: F811
    [broadcast] = await add(Notification(user_id=None, title="Анонс", message="M", type="event_published"))
    async with auth_client as ac:
        for _ in range(2):  # повторная отметка не падает на первичном ключе
            res = await ac.patch(f"/api/v1/notifications/{broadcast}/read", headers=bearer("10"))
            assert res.status_code == 200
        cnt10 = await ac.get("/api/v1/notifications/unread-count", headers=bearer("10"))
        cnt20 = await ac.get("/api/v1/notifications/unread-count", headers=bearer("20"))
    assert cnt10.json()["unread_count"] == 0
    assert cnt20.json()["unread_count"] == 1

    async with TestSessionLocal() as session:
        marks = (await session.execute(select(NotificationRead.user_id))).scalars().all()
    assert marks == [10]


@pytest.mark.asyncio
async def test_legacy_shared_read_flag_is_kept(auth_client):  # noqa: F811
    """Анонсы, отмеченные общим флагом до миграции, остаются прочитанными."""
    await add(Notification(user_id=None, title="Старый", message="M", type="event_published", is_read=True))
    async with auth_client as ac:
        cnt = await ac.get("/api/v1/notifications/unread-count", headers=bearer("10"))
        res = await ac.patch("/api/v1/notifications/read-all", headers=bearer("10"))
    assert cnt.json()["unread_count"] == 0
    assert res.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_settings_use_token_owner(auth_client):  # noqa: F811
    async with auth_client as ac:
        res = await ac.patch(
            "/api/v1/notifications/settings?user_id=20",
            json={"sms_enabled": False},
            headers=bearer("10", role="admin"),
        )
        assert res.json()["user_id"] == 10
        other = await ac.get("/api/v1/notifications/settings", headers=bearer("20"))
    assert other.json()["user_id"] == 20
    assert other.json()["sms_enabled"] is True
