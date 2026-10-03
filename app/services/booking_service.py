import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.messaging.publisher import BookingEventPublisher, booking_payload, publisher
from app.models.booking import Booking, BookingStatus
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import BookingCreate


logger = logging.getLogger(__name__)

# Сколько минут стол держится за гостем до оплаты
BOOKING_HOLD_MINUTES = int(os.getenv("BOOKING_HOLD_MINUTES", "15"))


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
        phone: str | None,
        data: BookingCreate,
    ) -> Booking:

        booking = Booking(
            user_id=user_id,
            phone=phone,
            table_id=data.table_id,
            event_id=data.event_id,
            guests=data.guests,
            status=BookingStatus.PENDING_PAYMENT,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=BOOKING_HOLD_MINUTES),
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

        booking = self.repository.get_by_id(booking_id, for_update=True)

        if booking is None:
            return None

        if booking.status != BookingStatus.PENDING_PAYMENT:
            self.db.rollback()
            raise ValueError("Only pending bookings can be confirmed")

        booking.status = BookingStatus.CONFIRMED

        self.db.commit()
        self.db.refresh(booking)

        self.publisher.publish_threadsafe(
            "booking.confirmed",
            booking_payload(booking, confirmed_by="admin"),
        )

        return booking

    def confirm_paid_booking(
        self,
        booking_id: int,
        user_id: int,
        amount: Decimal | None,
    ) -> str:
        # Строка заблокирована до commit: задача истечения броней
        # не переведёт её в EXPIRED, пока мы решаем её судьбу.
        booking = self.repository.get_by_id(booking_id, for_update=True)

        if booking is None:
            self.db.rollback()
            logger.warning("Payment for unknown booking %s", booking_id)
            return "not_found"

        if booking.user_id != user_id:
            self.db.rollback()
            logger.warning(
                "Payment user %s does not match booking %s owner %s",
                user_id,
                booking_id,
                booking.user_id,
            )
            return "user_mismatch"

        if booking.status == BookingStatus.CONFIRMED:
            # Повторная доставка того же события — ничего не делаем.
            self.db.rollback()
            return "already_confirmed"

        if booking.status != BookingStatus.PENDING_PAYMENT:
            status = booking.status.value
            payload = booking_payload(
                booking,
                amount=str(amount) if amount is not None else None,
                reason=f"booking_{status.lower()}",
            )
            self.db.rollback()

            # Деньги списаны, а бронь уже сгорела или отменена —
            # payment-service должен вернуть оплату.
            self.publisher.publish_threadsafe(
                "booking.payment_rejected",
                payload,
            )
            return "rejected"

        booking.status = BookingStatus.CONFIRMED

        self.db.commit()
        self.db.refresh(booking)

        self.publisher.publish_threadsafe(
            "booking.confirmed",
            booking_payload(
                booking,
                confirmed_by="payment",
                amount=str(amount) if amount is not None else None,
            ),
        )

        return "confirmed"

    def cancel_booking(
        self,
        booking_id: int,
        user_id: int,
    ) -> Booking | None:

        booking = self.repository.get_by_id(booking_id, for_update=True)

        if booking is None:
            return None

        if booking.user_id != user_id:
            self.db.rollback()
            return None

        if booking.status in (
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
        ):
            self.db.rollback()
            raise ValueError("Booking cannot be cancelled")

        # CONFIRMED означает, что бронь оплачена — payment-service вернёт деньги
        previous_status = booking.status.value
        booking.status = BookingStatus.CANCELLED

        self.db.commit()
        self.db.refresh(booking)

        self.publisher.publish_threadsafe(
            "booking.cancelled",
            booking_payload(
                booking,
                reason="user",
                previous_status=previous_status,
            ),
        )

        return booking

    def cancel_event_bookings(self, event_id: int) -> int:
        bookings = self.repository.get_active_by_event_id(event_id)
        previous_statuses = {
            booking.id: booking.status.value for booking in bookings
        }

        for booking in bookings:
            booking.status = BookingStatus.CANCELLED

        if bookings:
            self.db.commit()

        for booking in bookings:
            self.publisher.publish_threadsafe(
                "booking.cancelled",
                booking_payload(
                    booking,
                    reason="event_cancelled",
                    previous_status=previous_statuses[booking.id],
                ),
            )

        return len(bookings)

    def expire_bookings(self) -> int:
        bookings = self.repository.get_expired_pending()

        for booking in bookings:
            booking.status = BookingStatus.EXPIRED

        # commit и при пустом списке — чтобы снять блокировку SELECT FOR UPDATE
        self.db.commit()

        for booking in bookings:
            self.publisher.publish_threadsafe(
                "booking.expired",
                booking_payload(booking),
            )

        return len(bookings)
