import asyncio
import json
import logging
from datetime import datetime
from typing import Any
import aio_pika
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.templates import render_notification, render_sms
from app.models.notification import Notification
from app.services.sms_service import send_sms_via_nikita

logger = logging.getLogger(__name__)

_is_running = False
_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def process_event_message(routing_key: str, data: dict[str, Any], session: AsyncSession) -> list[Notification]:
    event_id = data.get("event_id")
    booking_id = data.get("booking_id") or data.get("id")
    title = data.get("title", "Без названия")
    table_id = data.get("table_id")
    send_notifications = data.get("send_notifications", True)

    if routing_key == "event.published" and not send_notifications:
        logger.info(f"Skipping event.published for event_id={event_id}: send_notifications is False")
        return []

    notif_title = ""
    notif_message = ""
    notif_type = ""
    related_event_id = event_id
    related_booking_id = None
    formatted_date = ""

    if routing_key == "event.published":
        start_datetime = data.get("start_datetime", "")
        formatted_date = start_datetime
        try:
            dt = datetime.fromisoformat(start_datetime)
            formatted_date = dt.strftime("%d.%m.%Y в %H:%M")
        except Exception:
            pass

        notif_type = "event_published"
        notif_title, notif_message = render_notification(
            notif_type, title=title, date=formatted_date
        )

    elif routing_key == "event.cancelled":
        notif_type = "event_cancelled"
        notif_title, notif_message = render_notification(notif_type, title=title)

    elif routing_key == "event.updated":
        notif_type = "event_updated"
        notif_title, notif_message = render_notification(notif_type, title=title)

    elif routing_key == "booking.created":
        notif_type = "booking_created"
        related_booking_id = booking_id
        notif_title, notif_message = render_notification(notif_type, table_number=table_id)

    elif routing_key == "booking.confirmed":
        notif_type = "booking_confirmed"
        related_booking_id = booking_id
        notif_title, notif_message = render_notification(notif_type, table_number=table_id)

    elif routing_key == "booking.cancelled":
        notif_type = "booking_cancelled"
        related_booking_id = booking_id
        notif_title, notif_message = render_notification(notif_type, table_number=table_id)

    elif routing_key == "booking.expired":
        notif_type = "booking_expired"
        related_booking_id = booking_id
        notif_title, notif_message = render_notification(notif_type, table_number=table_id)

    else:
        logger.warning(f"Unknown routing key: {routing_key}")
        return []

    target_user_ids: list[int | None] = []
    if "user_id" in data and data["user_id"] is not None:
        target_user_ids.append(int(data["user_id"]))
    elif "target_user_ids" in data and isinstance(data["target_user_ids"], list):
        target_user_ids.extend([int(uid) for uid in data["target_user_ids"]])
    else:
        target_user_ids.append(settings.EVENT_NOTIFICATION_DEFAULT_USER_ID)

    created_notifications: list[Notification] = []
    for user_id in target_user_ids:
        query = select(Notification).where(
            Notification.type == notif_type
        )
        if user_id is None:
            query = query.where(Notification.user_id.is_(None))
        else:
            query = query.where(Notification.user_id == user_id)

        if related_event_id is not None:
            query = query.where(Notification.related_event_id == related_event_id)
        if related_booking_id is not None:
            query = query.where(Notification.related_booking_id == related_booking_id)

        existing = await session.execute(query)
        if existing.scalars().first():
            continue

        notification = Notification(
            user_id=user_id,
            title=notif_title,
            message=notif_message,
            type=notif_type,
            related_event_id=related_event_id,
            related_booking_id=related_booking_id,
            is_read=False,
        )
        session.add(notification)
        created_notifications.append(notification)

    if created_notifications:
        await session.commit()
    logger.info(
        f"Saved {len(created_notifications)} notification(s) (type={notif_type})"
    )

    phone = data.get("phone") or data.get("phone_number")
    if phone:
        sms_text = render_sms(
            notif_type,
            title=title,
            date=formatted_date,
            table_number=table_id,
        )
        if sms_text:
            asyncio.create_task(send_sms_via_nikita(str(phone), sms_text))

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
            bookings_exchange = await channel.declare_exchange(
                "bookings_exchange",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            service_queue = await channel.declare_queue("notifications_service_queue", durable=True)

            event_keys = ["event.published", "event.cancelled", "event.updated"]
            booking_keys = ["booking.created", "booking.confirmed", "booking.cancelled", "booking.expired"]

            for r_key in event_keys:
                await service_queue.bind(events_exchange, routing_key=r_key)
                await service_queue.bind(channel.default_exchange, routing_key=r_key)

            for b_key in booking_keys:
                await service_queue.bind(bookings_exchange, routing_key=b_key)
                await service_queue.bind(channel.default_exchange, routing_key=b_key)

            await service_queue.consume(_on_message)

            logger.info("Successfully subscribed to RabbitMQ event and booking queues.")

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
