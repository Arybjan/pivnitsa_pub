import aio_pika
import json
from datetime import datetime
from app.core.config import settings
from loguru import logger

class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def connect(self):
        """Подключиться к RabbitMQ"""
        if not self.connection:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self.channel = await self.connection.channel()
            # Объявляем обменник
            await self.channel.declare_exchange(
                'events_exchange',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info("Connected to RabbitMQ")

    async def publish_event_published(self, event_id: int, title: str, start_datetime: datetime, send_notifications: bool = True):
        """Опубликовать событие: мероприятие опубликовано"""
        await self.connect()

        message = {
            "event_id": event_id,
            "title": title,
            "start_datetime": start_datetime.isoformat(),
            "send_notifications": send_notifications,
            "timestamp": datetime.now().isoformat()
        }

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            ),
            routing_key="event.published"
        )
        logger.info(f"Published event.published: {event_id}")

    async def publish_event_cancelled(self, event_id: int, title: str):
        """Опубликовать событие: мероприятие отменено"""
        await self.connect()

        message = {
            "event_id": event_id,
            "title": title,
            "timestamp": datetime.now().isoformat()
        }

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            ),
            routing_key="event.cancelled"
        )
        logger.info(f"Published event.cancelled: {event_id}")

    async def publish_event_updated(self, event_id: int, title: str, changes: dict):
        """Опубликовать событие: мероприятие обновлено"""
        await self.connect()

        message = {
            "event_id": event_id,
            "title": title,
            "changes": changes,
            "timestamp": datetime.now().isoformat()
        }

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            ),
            routing_key="event.updated"
        )
        logger.info(f"Published event.updated: {event_id}")

    async def close(self):
        """Закрыть соединение"""
        if self.connection:
            await self.connection.close()
            logger.info("Closed RabbitMQ connection")
