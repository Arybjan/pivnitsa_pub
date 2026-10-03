import asyncio
import json
import logging

from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from app.database import SessionLocal
from app.messaging.publisher import EXCHANGE_NAME
from app.services.booking_service import BookingService


logger = logging.getLogger(__name__)

QUEUE_NAME = "booking-service.event.cancelled"


def cancel_event_bookings_once(event_id: int) -> int:
    db = SessionLocal()

    try:
        service = BookingService(db)
        return service.cancel_event_bookings(event_id)

    finally:
        db.close()


async def on_event_cancelled(message: AbstractIncomingMessage) -> None:
    try:
        data = json.loads(message.body)
        event_id = int(data["event_id"])

    except (ValueError, KeyError, TypeError):
        # Битое сообщение не исправится при повторе — подтверждаем и пропускаем.
        logger.error("Invalid event.cancelled message: %r", message.body)
        await message.ack()
        return

    # При ошибке БД сообщение вернётся в очередь, отмена броней не потеряется.
    async with message.process(requeue=True):
        cancelled_count = await asyncio.to_thread(
            cancel_event_bookings_once,
            event_id,
        )

        logger.info(
            "Event %s cancelled, cancelled bookings: %s",
            event_id,
            cancelled_count,
        )


async def setup_consumer(connection: AbstractRobustConnection) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        "topic",
        durable=True,
    )

    # Своя очередь: у notification-service своя, и каждый получит копию события.
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key="event.cancelled")
    await queue.consume(on_event_cancelled)
