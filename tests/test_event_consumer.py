import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.event_consumer import process_event_message
from app.core.config import settings


@pytest.mark.asyncio
async def test_process_event_published():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "event_id": 42,
        "title": "Jazz Night Live",
        "start_datetime": "2026-10-15T20:00:00",
        "send_notifications": True,
        "timestamp": "2026-09-17T22:00:00",
    }

    result = await process_event_message("event.published", payload, mock_session)

    assert len(result) == 1
    notification = result[0]
    assert notification.related_event_id == 42
    assert "Jazz Night Live" in notification.title
    assert "15.10.2026" in notification.message
    assert notification.type == "event_published"
    assert notification.user_id == settings.EVENT_NOTIFICATION_DEFAULT_USER_ID
    assert notification.is_read is False

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_event_published_skip_when_disabled():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "event_id": 43,
        "title": "Private Party",
        "start_datetime": "2026-10-15T20:00:00",
        "send_notifications": False,
    }

    result = await process_event_message("event.published", payload, mock_session)
    assert len(result) == 0
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_process_event_cancelled():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "event_id": 42,
        "title": "Jazz Night Live",
        "timestamp": "2026-09-17T22:00:00",
    }

    result = await process_event_message("event.cancelled", payload, mock_session)

    assert len(result) == 1
    notification = result[0]
    assert notification.related_event_id == 42
    assert "Отмена" in notification.title
    assert notification.type == "event_cancelled"
    assert notification.user_id == settings.EVENT_NOTIFICATION_DEFAULT_USER_ID

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_event_updated():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "event_id": 42,
        "title": "Jazz Night Live - New Time",
        "changes": {"start_datetime": "2026-10-15T21:00:00"},
        "timestamp": "2026-09-17T22:00:00",
    }

    result = await process_event_message("event.updated", payload, mock_session)

    assert len(result) == 1
    notification = result[0]
    assert notification.related_event_id == 42
    assert "Обновление" in notification.title
    assert notification.type == "event_updated"

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_event_with_target_users():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    payload = {
        "event_id": 99,
        "title": "VIP Tasting",
        "start_datetime": "2026-11-01T19:00:00",
        "send_notifications": True,
        "target_user_ids": [10, 20, 30],
    }

    result = await process_event_message("event.published", payload, mock_session)

    assert len(result) == 3
    assert [n.user_id for n in result] == [10, 20, 30]
    assert mock_session.add.call_count == 3
    mock_session.commit.assert_called_once()
