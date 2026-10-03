from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus


class BookingRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.flush()
        self.db.refresh(booking)

        return booking

    def get_by_id(
        self,
        booking_id: int,
        for_update: bool = False,
    ) -> Booking | None:
        stmt = select(Booking).where(
            Booking.id == booking_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        return self.db.scalar(stmt)

    def get_by_user_id(self, user_id: int) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )

        return list(self.db.scalars(stmt).all())

    def get_active_by_event_id(self, event_id: int) -> list[Booking]:
        stmt = select(Booking).where(
            Booking.event_id == event_id,
            Booking.status.in_(
                [BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED]
            ),
        ).with_for_update()

        return list(self.db.scalars(stmt).all())

    def get_expired_pending(self) -> list[Booking]:
        # skip_locked: бронь, которую прямо сейчас подтверждает оплата,
        # пропускаем — её статус решит та транзакция.
        stmt = select(Booking).where(
            Booking.status == BookingStatus.PENDING_PAYMENT,
            Booking.expires_at <= datetime.now(timezone.utc),
        ).with_for_update(skip_locked=True)

        return list(self.db.scalars(stmt).all())
