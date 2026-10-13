import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.event_consumer import process_event_message
from app.core.config import settings


def _create_mock_session(existing_result=None):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = existing_result
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.mark.asyncio
async def test_process_event_published():
    mock_session = _create_mock_session()

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
    mock_session = _create_mock_session()

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
    mock_session = _create_mock_session()

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
    mock_session = _create_mock_session()

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
    mock_session = _create_mock_session()

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


@pytest.mark.asyncio
async def test_process_event_duplicate_ignored():
    mock_existing_notification = MagicMock()
    mock_session = _create_mock_session(existing_result=mock_existing_notification)

    payload = {
        "event_id": 42,
        "title": "Jazz Night Live",
        "start_datetime": "2026-10-15T20:00:00",
        "send_notifications": True,
        "timestamp": "2026-09-17T22:00:00",
    }

    result = await process_event_message("event.published", payload, mock_session)

    assert len(result) == 0
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_consumer_binds_only_named_exchanges(monkeypatch):
    """RabbitMQ отклоняет bind к default exchange - consumer не должен его делать."""
    from app.services import event_consumer

    channel = MagicMock()
    channel.set_qos = AsyncMock()
    channel.declare_exchange = AsyncMock(side_effect=lambda name, *a, **k: name)
    queue = MagicMock()
    queue.bind = AsyncMock()

    async def consume(callback):
        event_consumer._is_running = False

    queue.consume = consume
    channel.declare_queue = AsyncMock(return_value=queue)
    connection = MagicMock(is_closed=False)
    connection.channel = AsyncMock(return_value=channel)
    monkeypatch.setattr(event_consumer.aio_pika, "connect_robust", AsyncMock(return_value=connection))

    await event_consumer.start_event_consumer()

    bound = {call.args[0] for call in queue.bind.call_args_list}
    assert bound == {"events_exchange", "bookings_exchange"}


@pytest.mark.asyncio
async def test_event_time_shown_in_venue_timezone():
    payload = {"event_id": 7, "title": "Новый год", "start_datetime": "2026-12-31T16:00:00+00:00"}

    result = await process_event_message("event.published", payload, _create_mock_session())

    assert "31.12.2026 в 22:00" in result[0].message


@pytest.mark.asyncio
async def test_booking_notification_uses_table_number(monkeypatch):
    import httpx
    import respx

    monkeypatch.setattr(settings, "VENUE_SERVICE_URL", "http://venue.test")
    payload = {"booking_id": 1, "user_id": 5, "table_id": 4, "status": "CONFIRMED"}

    with respx.mock:
        respx.get("http://venue.test/api/v1/tables/4").mock(
            return_value=httpx.Response(200, json={"id": 4, "number": 8})
        )
        result = await process_event_message("booking.confirmed", payload, _create_mock_session())
    assert "№8" in result[0].message

    # Venue недоступен - уведомление всё равно создаётся, с id стола
    with respx.mock:
        respx.get("http://venue.test/api/v1/tables/4").mock(side_effect=httpx.ConnectError("down"))
        result = await process_event_message("booking.confirmed", payload, _create_mock_session())
    assert "№4" in result[0].message
