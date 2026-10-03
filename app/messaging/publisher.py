import asyncio
import json
import logging
from datetime import datetime, timezone

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection

from app.models.booking import Booking


logger = logging.getLogger(__name__)

EXCHANGE_NAME = "events_exchange"


def booking_payload(booking: Booking, **extra) -> dict:
    return {
        "booking_id": booking.id,
        "user_id": booking.user_id,
        "phone": booking.phone,
        "event_id": booking.event_id,
        "table_id": booking.table_id,
        "guests": booking.guests,
        "status": booking.status.value,
        "expires_at": booking.expires_at.isoformat() if booking.expires_at else None,
        **extra,
    }


class BookingEventPublisher:

    def __init__(self):
        self._exchange: AbstractExchange | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def setup(self, connection: AbstractRobustConnection) -> None:
        channel = await connection.channel()

        self._exchange = await channel.declare_exchange(
            EXCHANGE_NAME,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    def reset(self) -> None:
        self._exchange = None

    async def publish(self, routing_key: str, payload: dict) -> None:
        if self._exchange is None:
            logger.warning(
                "RabbitMQ is not connected, dropped %s: %s",
                routing_key,
                payload,
            )
            return

        body = {
            **payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await self._exchange.publish(
                aio_pika.Message(
                    body=json.dumps(body).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
            )

            logger.info("Published %s: booking_id=%s", routing_key, payload.get("booking_id"))

        except Exception:
            # Бронь уже сохранена в БД — сбой брокера не должен её ломать.
            logger.exception("Failed to publish %s", routing_key)

    def publish_threadsafe(self, routing_key: str, payload: dict) -> None:
        # Эндпоинты и задача истечения броней синхронные и работают в потоках,
        # а соединение с RabbitMQ живёт в event loop приложения.
        if self._loop is None or self._loop.is_closed():
            logger.warning("Event loop is not available, dropped %s", routing_key)
            return

        asyncio.run_coroutine_threadsafe(
            self.publish(routing_key, payload),
            self._loop,
        )


publisher = BookingEventPublisher()
