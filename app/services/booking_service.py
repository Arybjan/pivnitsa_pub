from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.booking import Booking, BookingStatus
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import BookingCreate


class BookingService:

    def __init__(self, db: Session):
        self.repository = BookingRepository(db)
        self.db = db

    def create_booking(
        self,
        user_id: int,
        data: BookingCreate,
    ) -> Booking:

        booking = Booking(
            user_id=user_id,
            table_id=data.table_id,
            event_id=data.event_id,
            guests=data.guests,
            status=BookingStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )

        try:
            booking = self.repository.create(booking)

            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Table is already booked for this event"
            )
        self.db.refresh(booking)

        return booking

    def get_booking(
        self,
        booking_id: int,
    ) -> Booking | None:

        return self.repository.get_by_id(booking_id)

    def get_user_bookings(
        self,
        user_id: int,
    ) -> list[Booking]:

        return self.repository.get_by_user_id(user_id)

    def cancel_booking(
        self,
        booking_id: int,
        user_id: int,
    ) -> Booking | None:

        booking = self.repository.get_by_id(booking_id)

        if booking is None:
            return None

        if booking.user_id != user_id:
            return None

        if booking.status in (
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
        ):
            raise ValueError("Booking cannot be cancelled")

        booking.status = BookingStatus.CANCELLED

        self.db.commit()
        self.db.refresh(booking)

        return booking

    def expire_bookings(self) -> int:
        bookings = self.repository.get_expired_pending()

        for booking in bookings:
            booking.status = BookingStatus.EXPIRED

        if bookings:
            self.db.commit()

        return len(bookings)