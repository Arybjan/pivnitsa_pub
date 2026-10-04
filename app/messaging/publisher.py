import json
import logging
from typing import Any, Dict, Optional
import aio_pika
from app.core.config import settings

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self):
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.exchange: Optional[aio_pika.RobustExchange] = None

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("Connected to RabbitMQ exchange '%s'", settings.RABBITMQ_EXCHANGE)
        except Exception as e:
            logger.warning("RabbitMQ connection skipped or failed: %s", e)

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    async def publish(self, routing_key: str, payload: Dict[str, Any]):
        if not self.exchange:
            logger.warning("Cannot publish event '%s': RabbitMQ exchange not connected", routing_key)
            return

        body = json.dumps(payload).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=routing_key)
        logger.info("Published '%s' event: %s", routing_key, payload)

publisher = EventPublisher()
