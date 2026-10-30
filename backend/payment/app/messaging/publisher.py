import json
import logging
from typing import Any, Dict, Optional
import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection
from app.core.config import settings

logger = logging.getLogger(__name__)


class PublisherNotConnected(Exception):
    pass


class EventPublisher:
    def __init__(self):
        self.exchange: Optional[AbstractExchange] = None
        self._connection: Optional[AbstractRobustConnection] = None

    async def setup(self, connection: AbstractRobustConnection) -> None:
        # publisher_confirms (по умолчанию включены): publish ждёт подтверждения брокера
        self._connection = connection
        channel = await connection.channel()
        self.exchange = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    def reset(self) -> None:
        self.exchange = None
        self._connection = None

    @property
    def is_connected(self) -> bool:
        # У robust-соединения is_closed остаётся False и во время переподключения,
        # а событие connected сбрасывается при обрыве и взводится после восстановления.
        return (
            self.exchange is not None
            and self._connection is not None
            and self._connection.connected.is_set()
        )

    async def publish(self, routing_key: str, payload: Dict[str, Any]) -> None:
        # Исключения пробрасываются наружу: outbox-воркер повторит отправку
        if not self.is_connected:
            raise PublisherNotConnected(f"Cannot publish '{routing_key}': RabbitMQ is not connected")

        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=routing_key)
        logger.info("Published '%s' event: %s", routing_key, payload)


publisher = EventPublisher()
