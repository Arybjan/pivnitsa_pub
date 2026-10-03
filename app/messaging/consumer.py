import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation

from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from app.database import SessionLocal
from app.messaging.publisher import EXCHANGE_NAME
from app.services.booking_service import BookingService


logger = logging.getLogger(__name__)

# Свои очереди: у других сервисов свои, и каждый получит копию события.
EVENT_CANCELLED_QUEUE = "booking-service.event.cancelled"
PAYMENT_SUCCEEDED_QUEUE = "booking-service.payment.succeeded"


def cancel_event_bookings_once(event_id: int) -> int:
    db = SessionLocal()

    try:
        service = BookingService(db)
        return service.cancel_event_bookings(event_id)

    finally:
        db.close()


def confirm_paid_booking_once(
    booking_id: int,
    user_id: int,
    amount: Decimal | None,
) -> str:
    db = SessionLocal()

    try:
        service = BookingService(db)
        return service.confirm_paid_booking(booking_id, user_id, amount)

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


async def on_payment_succeeded(message: AbstractIncomingMessage) -> None:
    # Формат из specification.json: { booking_id, user_id, amount }
    try:
        data = json.loads(message.body)
        booking_id = int(data["booking_id"])
        user_id = int(data["user_id"])
        amount = Decimal(str(data["amount"])) if data.get("amount") is not None else None

    except (ValueError, KeyError, TypeError, InvalidOperation):
        logger.error("Invalid payment.succeeded message: %r", message.body)
        await message.ack()
        return

    async with message.process(requeue=True):
        result = await asyncio.to_thread(
            confirm_paid_booking_once,
            booking_id,
            user_id,
            amount,
        )

        logger.info("Payment for booking %s: %s", booking_id, result)


async def setup_consumer(connection: AbstractRobustConnection) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        "topic",
        durable=True,
    )

    bindings = (
        (EVENT_CANCELLED_QUEUE, "event.cancelled", on_event_cancelled),
        (PAYMENT_SUCCEEDED_QUEUE, "payment.succeeded", on_payment_succeeded),
    )

    for queue_name, routing_key, handler in bindings:
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, routing_key=routing_key)
        await queue.consume(handler)
