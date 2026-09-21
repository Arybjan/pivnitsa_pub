import asyncio

from app.database import SessionLocal
from app.services.booking_service import BookingService


async def expire_bookings_loop():
    while True:
        db = SessionLocal()

        try:
            service = BookingService(db)
            expired_count = service.expire_bookings()

            if expired_count:
                print(f"Expired bookings: {expired_count}")

        finally:
            db.close()

        await asyncio.sleep(30)