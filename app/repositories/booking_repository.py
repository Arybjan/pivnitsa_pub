from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking


class BookingRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.flush()
        self.db.refresh(booking)

        return booking

    def get_by_id(self, booking_id: int) -> Booking | None:
        stmt = select(Booking).where(
            Booking.id == booking_id
        )

        return self.db.scalar(stmt)

    def get_by_user_id(self, user_id: int) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )

        return list(self.db.scalars(stmt).all())

    def get_expired_pending(self) -> list[Booking]:
        stmt = select(Booking).where(
            Booking.status == "PENDING",
            Booking.expires_at <= datetime.now(timezone.utc),
        )

        return list(self.db.scalars(stmt).all())
