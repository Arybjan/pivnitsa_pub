import asyncio
import logging

from app.database import SessionLocal
from app.services.booking_service import BookingService


logger = logging.getLogger(__name__)


def expire_bookings_once() -> int:
    db = SessionLocal()

    try:
        service = BookingService(db)
        return service.expire_bookings()

    finally:
        db.close()


async def expire_bookings_loop():
    while True:
        try:
            # Sync DB work runs in a thread so it doesn't block the event loop.
            expired_count = await asyncio.to_thread(expire_bookings_once)

            if expired_count:
                logger.info("Expired bookings: %s", expired_count)

        except Exception:
            # Keep the loop alive on transient DB errors.
            logger.exception("Failed to expire bookings")

        await asyncio.sleep(30)
