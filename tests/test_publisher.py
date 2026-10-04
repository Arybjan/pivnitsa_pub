from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.publisher import EventPublisher


@pytest.mark.asyncio
async def test_publish_uses_declared_exchange_and_stable_id(monkeypatch):
    connection = MagicMock()
    connection.is_closed = False
    connection.close = AsyncMock()
    channel = AsyncMock()
    exchange = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)
    channel.declare_exchange.return_value = exchange
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr("app.services.publisher.aio_pika.connect_robust", connect)
    publisher = EventPublisher()
    await publisher.publish("event.published", {"message_id": "stable-id", "event_id": 1})
    connection.channel.assert_awaited_once_with(publisher_confirms=True, on_return_raises=True)
    message = exchange.publish.call_args.args[0]
    assert message.message_id == "stable-id"
    assert exchange.publish.call_args.kwargs["mandatory"] is True
    assert exchange.publish.call_args.kwargs["routing_key"] == "event.published"
    await publisher.close()
    connection.close.assert_awaited_once()
