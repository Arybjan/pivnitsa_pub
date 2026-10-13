import asyncio
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import async_session_maker
from app.messaging.publisher import EventPublisher, publisher
from app.models.payment import OutboxEvent
from app.services.payment_service import payment_service

logger = logging.getLogger(__name__)

OUTBOX_BATCH_SIZE = 50


async def relay_outbox_once(db: AsyncSession, event_publisher: EventPublisher = publisher) -> int:
    """Отправляет неотправленные события по порядку. Возвращает число отправленных."""
    if not event_publisher.is_connected:
        return 0

    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.id)
        .limit(OUTBOX_BATCH_SIZE)
        # Несколько экземпляров сервиса не отправят одно событие дважды
        .with_for_update(skip_locked=True)
    )
    events = list((await db.execute(stmt)).scalars().all())

    sent = 0
    for event in events:
        try:
            await event_publisher.publish(event.routing_key, json.loads(event.payload))
        except Exception:
            # Порядок важен: при сбое останавливаемся и повторим с этого же события
            event.attempts += 1
            logger.exception("Failed to publish outbox event %s", event.id)
            break
        event.published_at = datetime.now(timezone.utc)
        sent += 1

    await db.commit()
    return sent


async def outbox_relay_loop() -> None:
    while True:
        try:
            async with async_session_maker() as session:
                await relay_outbox_once(session)
        except Exception:
            logger.exception("Outbox relay iteration failed")
        await asyncio.sleep(settings.OUTBOX_POLL_SECONDS)


async def refund_retry_loop() -> None:
    while True:
        await asyncio.sleep(settings.REFUND_RETRY_SECONDS)
        try:
            async with async_session_maker() as session:
                refunded = await payment_service.retry_pending_refunds(session)
            if refunded:
                logger.info("Retried refunds completed: %s", refunded)
        except Exception:
            logger.exception("Refund retry iteration failed")
