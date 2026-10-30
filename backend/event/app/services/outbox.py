import asyncio
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.events import EventOutbox
from app.services.publisher import EventPublisher


async def deliver_pending(publisher: EventPublisher, session_factory=AsyncSessionLocal):
    async with session_factory() as db:
        async with db.begin():
            messages = (await db.execute(
                select(EventOutbox).where(EventOutbox.delivered_at.is_(None))
                .order_by(EventOutbox.created_at).limit(100)
                .with_for_update(skip_locked=True)
            )).scalars().all()
            for message in messages:
                await publisher.publish(message.routing_key, message.payload)
                message.delivered_at = datetime.now(timezone.utc)


async def run_outbox(publisher: EventPublisher):
    while True:
        try:
            await deliver_pending(publisher)
        except Exception:
            logger.exception("Outbox delivery failed; pending messages will be retried")
        await asyncio.sleep(5)
