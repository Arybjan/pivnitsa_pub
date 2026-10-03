from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.messaging.publisher import BookingEventPublisher, booking_payload, publisher
from app.models.booking import Booking, BookingStatus
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import BookingCreate


class BookingService:

    def __init__(
        self,
        db: Session,
        event_publisher: BookingEventPublisher = publisher,
    ):
        self.repository = BookingRepository(db)
        self.db = db
        self.publisher = event_publisher

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

        # События отправляем только после commit, чтобы не сообщить о брони,
        # которая откатилась.
        self.publisher.publish_threadsafe(
            "booking.created",
            booking_payload(booking),
        )

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

    def confirm_booking(
        self,
        booking_id: int,
    ) -> Booking | None:

        booking = self.repository.get_by_id(booking_id)

        if booking is None:
            return None

        if booking.status != BookingStatus.PENDING:
            raise ValueError("Only pending bookings can be confirmed")

        booking.status = BookingStatus.CONFIRMED
        booking.expires_at = None

        self.db.commit()
        self.db.refresh(booking)

        self.publisher.publish_threadsafe(
            "booking.confirmed",
            booking_payload(booking),
        )

        return booking

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

        self.publisher.publish_threadsafe(
            "booking.cancelled",
            booking_payload(booking, reason="user"),
        )

        return booking

    def cancel_event_bookings(self, event_id: int) -> int:
        bookings = self.repository.get_active_by_event_id(event_id)

        for booking in bookings:
            booking.status = BookingStatus.CANCELLED

        if bookings:
            self.db.commit()

        for booking in bookings:
            self.publisher.publish_threadsafe(
                "booking.cancelled",
                booking_payload(booking, reason="event_cancelled"),
            )

        return len(bookings)

    def expire_bookings(self) -> int:
        bookings = self.repository.get_expired_pending()

        for booking in bookings:
            booking.status = BookingStatus.EXPIRED

        if bookings:
            self.db.commit()

        for booking in bookings:
            self.publisher.publish_threadsafe(
                "booking.expired",
                booking_payload(booking),
            )

        return len(bookings)
