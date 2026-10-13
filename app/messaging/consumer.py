import json
import logging
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
import aio_pika
from app.core.config import settings
from app.core.database import async_session_maker
from app.services.payment_service import payment_service

logger = logging.getLogger(__name__)

QUEUE_NAME = "payment-service.booking-events"


def refund_reason_for(routing_key: str, payload: dict) -> str | None:
    """Возврат нужен, если бронь отвергла оплату или была отменена уже оплаченной."""
    if routing_key == "booking.payment_rejected":
        return str(payload.get("reason") or "booking_payment_rejected")
    if routing_key == "booking.cancelled" and payload.get("previous_status") == "CONFIRMED":
        return f"booking_cancelled:{payload.get('reason') or 'unknown'}"
    return None


async def handle_booking_event(routing_key: str, payload: dict) -> None:
    reason = refund_reason_for(routing_key, payload)
    if reason is None:
        return

    booking_id = int(payload["booking_id"])
    async with async_session_maker() as session:
        payment = await payment_service.refund_for_booking(session, booking_id, reason)

    if payment is None:
        logger.info("No paid payment for booking %s, nothing to refund", booking_id)
    else:
        logger.info("Booking %s: payment %s is %s", booking_id, payment.id, payment.status)


async def process_message(message: AbstractIncomingMessage) -> None:
    try:
        payload = json.loads(message.body.decode("utf-8"))
        int(payload["booking_id"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        # Битое сообщение не исправится при повторе — подтверждаем и пропускаем
        logger.error("Invalid booking event %s: %r", message.routing_key, message.body)
        await message.ack()
        return

    # Ошибка БД вернёт сообщение в очередь. Сбой шлюза сюда не доходит:
    # платёж остаётся в REFUND_PENDING и его добивает воркер повторных возвратов.
    async with message.process(requeue=True):
        logger.info("Received booking event '%s': %s", message.routing_key, payload)
        await handle_booking_event(message.routing_key or "", payload)


async def setup_consumer(connection: AbstractRobustConnection) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        settings.RABBITMQ_EXCHANGE,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key="booking.payment_rejected")
    await queue.bind(exchange, routing_key="booking.cancelled")
    await queue.consume(process_message)
    logger.info("Payment consumer listening on queue '%s'", QUEUE_NAME)
