import asyncio
import logging
import os

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from dotenv import load_dotenv

from app.messaging.consumer import setup_consumer
from app.messaging.publisher import publisher


load_dotenv()

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
RETRY_DELAY_SECONDS = 5

_connection: AbstractRobustConnection | None = None


async def start_messaging() -> None:
    global _connection

    publisher.bind_loop(asyncio.get_running_loop())

    # Сервис стартует и без брокера; подключаемся в фоне, пока не получится.
    # После первого подключения connect_robust сам восстанавливает соединение.
    while _connection is None:
        connection: AbstractRobustConnection | None = None

        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)

            await publisher.setup(connection)
            await setup_consumer(connection)

            _connection = connection
            logger.info("Connected to RabbitMQ")

        except Exception as exc:
            publisher.reset()

            if connection is not None:
                await connection.close()

            logger.warning(
                "RabbitMQ connection failed: %s. Retrying in %ss",
                exc,
                RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)


async def stop_messaging() -> None:
    global _connection

    publisher.reset()

    if _connection is not None:
        await _connection.close()
        _connection = None
