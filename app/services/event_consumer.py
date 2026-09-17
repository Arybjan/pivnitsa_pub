import asyncio
import json
import logging
from datetime import datetime
from typing import Any
import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import async_session_maker
from app.models.notification import Notification

logger = logging.getLogger(__name__)

_is_running = False
_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def process_event_message(routing_key: str, data: dict[str, Any], session: AsyncSession) -> list[Notification]:
    event_id = data.get("event_id")
    title = data.get("title", "Без названия")
    send_notifications = data.get("send_notifications", True)

    if routing_key == "event.published" and not send_notifications:
        logger.info(f"Skipping event.published for event_id={event_id}: send_notifications is False")
        return []

    if routing_key == "event.published":
        start_datetime = data.get("start_datetime", "")
        formatted_date = start_datetime
        try:
            dt = datetime.fromisoformat(start_datetime)
            formatted_date = dt.strftime("%d.%m.%Y в %H:%M")
        except Exception:
            pass

        notif_title = f"Анонс: {title}"
        notif_message = (
            f"Мероприятие «{title}» запланировано на {formatted_date}. "
            f"Бронируйте столики заранее!"
        )
        notif_type = "event_published"

    elif routing_key == "event.cancelled":
        notif_title = f"Отмена мероприятия: {title}"
        notif_message = f"К сожалению, мероприятие «{title}» было отменено."
        notif_type = "event_cancelled"

    elif routing_key == "event.updated":
        notif_title = f"Обновление мероприятия: {title}"
        notif_message = f"Информация о мероприятии «{title}» была обновлена. Проверьте детали в афише."
        notif_type = "event_updated"

    else:
        logger.warning(f"Unknown routing key: {routing_key}")
        return []

    
    target_user_ids: list[int] = []
    if "user_id" in data and data["user_id"]:
        target_user_ids.append(int(data["user_id"]))
    elif "target_user_ids" in data and isinstance(data["target_user_ids"], list):
        target_user_ids.extend([int(uid) for uid in data["target_user_ids"]])
    else:
        target_user_ids.append(settings.EVENT_NOTIFICATION_DEFAULT_USER_ID)

    created_notifications: list[Notification] = []
    for user_id in target_user_ids:
        notification = Notification(
            user_id=user_id,
            title=notif_title,
            message=notif_message,
            type=notif_type,
            related_event_id=event_id,
            related_booking_id=None,
            is_read=False,
        )
        session.add(notification)
        created_notifications.append(notification)

    await session.commit()
    logger.info(
        f"Saved {len(created_notifications)} notification(s) for event_id={event_id} (type={notif_type})"
    )
    return created_notifications


async def _on_message(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process():
        try:
            body = message.body.decode("utf-8")
            data = json.loads(body)
            routing_key = message.routing_key or ""
            logger.info(f"Received RabbitMQ message [{routing_key}]: {data}")

            async with async_session_maker() as session:
                await process_event_message(routing_key, data, session)

        except Exception as e:
            logger.error(f"Error processing RabbitMQ message: {e}", exc_info=True)


async def start_event_consumer():
    global _is_running, _connection
    _is_running = True

    retry_delay = 3
    while _is_running:
        try:
            logger.info(f"Connecting to RabbitMQ at {settings.RABBITMQ_URL}...")
            _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            channel = await _connection.channel()
            await channel.set_qos(prefetch_count=10)

            events_exchange = await channel.declare_exchange(
                "events_exchange",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            routing_keys = ["event.published", "event.cancelled", "event.updated"]

            for r_key in routing_keys:
                queue = await channel.declare_queue(r_key, durable=True)
                await queue.bind(events_exchange, routing_key=r_key)
                await queue.consume(_on_message)

            logger.info("Successfully subscribed to RabbitMQ event queues (published, cancelled, updated).")

            while _is_running and not _connection.is_closed:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("RabbitMQ consumer task cancelled.")
            break
        except Exception as e:
            if not _is_running:
                break
            logger.warning(
                f"RabbitMQ connection failed: {e}. Retrying in {retry_delay}s... (FastAPI remains healthy)"
            )
            await asyncio.sleep(retry_delay)


async def stop_event_consumer():
    global _is_running, _connection
    _is_running = False
    if _connection and not _connection.is_closed:
        try:
            await _connection.close()
            logger.info("Closed RabbitMQ connection.")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")
