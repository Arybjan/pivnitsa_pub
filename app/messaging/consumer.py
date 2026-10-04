import json
import logging
from typing import Optional
import aio_pika
from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session_maker
from app.models.payment import Payment, PaymentStatus
from app.services.stripe_gateway import gateway

logger = logging.getLogger(__name__)

QUEUE_NAME = "payment-service.booking-events"

class BookingEventConsumer:
    def __init__(self):
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None

    async def start(self):
        try:
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)

            exchange = await self.channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            queue = await self.channel.declare_queue(QUEUE_NAME, durable=True)
            await queue.bind(exchange, routing_key="booking.payment_rejected")
            await queue.bind(exchange, routing_key="booking.cancelled")

            await queue.consume(self.process_message)
            logger.info("Payment consumer listening on queue '%s'", QUEUE_NAME)
        except Exception as e:
            logger.warning("RabbitMQ consumer not started: %s", e)

    async def process_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process():
            try:
                payload = json.loads(message.body.decode("utf-8"))
                routing_key = message.routing_key
                logger.info("Received booking event '%s': %s", routing_key, payload)

                booking_id = payload.get("booking_id") or payload.get("id")
                if not booking_id:
                    return

                # If booking was cancelled with previous_status == CONFIRMED, or payment was rejected:
                prev_status = payload.get("previous_status")
                should_refund = (
                    routing_key == "booking.payment_rejected"
                    or (routing_key == "booking.cancelled" and prev_status == "CONFIRMED")
                )

                if not should_refund:
                    return

                async with async_session_maker() as session:
                    stmt = select(Payment).where(
                        Payment.booking_id == int(booking_id),
                        Payment.status == PaymentStatus.SUCCEEDED.value,
                    )
                    result = await session.execute(stmt)
                    payment = result.scalars().first()

                    if payment:
                        logger.info("Refunding payment %s for booking %s", payment.id, booking_id)
                        if payment.provider_payment_id:
                            await gateway.refund(payment.provider_payment_id, amount=payment.amount)
                        payment.status = PaymentStatus.REFUNDED.value
                        await session.commit()
                        logger.info("Payment %s marked as REFUNDED", payment.id)
            except Exception as e:
                logger.error("Error processing booking event: %s", e)

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

consumer = BookingEventConsumer()
