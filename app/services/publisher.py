import json

import aio_pika
from app.core.config import settings


class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url, timeout=10)
            self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
            self.exchange = await self.channel.declare_exchange(
                "events_exchange", aio_pika.ExchangeType.TOPIC, durable=True,
            )

    async def publish(self, routing_key: str, payload: dict):
        await self.connect()
        await self.exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(), message_id=payload["message_id"],
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ), routing_key=routing_key, mandatory=True, timeout=10,
        )

    async def close(self):
        if self.connection:
            await self.connection.close()
