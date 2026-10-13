import asyncio
import logging
from typing import Optional
import aio_pika
from aio_pika.abc import AbstractRobustConnection
from app.core.config import settings
from app.messaging.consumer import setup_consumer
from app.messaging.publisher import publisher

logger = logging.getLogger(__name__)

_connection: Optional[AbstractRobustConnection] = None


async def start_messaging() -> None:
    """
    Подключается к RabbitMQ в фоне, пока не получится. Сервис при этом уже
    принимает оплаты: события копятся в outbox и уйдут после подключения.
    """
    global _connection

    while _connection is None:
        connection: Optional[AbstractRobustConnection] = None
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            await publisher.setup(connection)
            await setup_consumer(connection)
            _connection = connection
            logger.info("Connected to RabbitMQ exchange '%s'", settings.RABBITMQ_EXCHANGE)
        except Exception as exc:
            publisher.reset()
            if connection is not None:
                await connection.close()
            logger.warning(
                "RabbitMQ connection failed: %s. Retrying in %ss",
                exc,
                settings.RABBITMQ_RETRY_SECONDS,
            )
            await asyncio.sleep(settings.RABBITMQ_RETRY_SECONDS)


async def stop_messaging() -> None:
    global _connection

    publisher.reset()
    if _connection is not None:
        await _connection.close()
        _connection = None
