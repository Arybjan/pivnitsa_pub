import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.messaging.publisher import BookingEventPublisher, booking_payload, publisher
from app.models.booking import ACTIVE_STATUSES, Booking, BookingSource, BookingStatus
from app.repositories.booking_repository import BookingRepository
from app.services.event_client import get_bookable_event_start, EventNotBookable
from app.schemas.booking import (
    AdminBookingCreate,
    AdminBookingUpdate,
    BookingCreate,
    check_prepayment,
)


logger = logging.getLogger(__name__)

# Сколько минут стол держится за гостем до оплаты
BOOKING_HOLD_MINUTES = int(os.getenv("BOOKING_HOLD_MINUTES", "15"))

# Часовой пояс заведения: по нему считается дата брони
VENUE_TIMEZONE = ZoneInfo(os.getenv("VENUE_TIMEZONE", "Asia/Bishkek"))


def local_date(moment: datetime) -> date:
    return moment.astimezone(VENUE_TIMEZONE).date()


def default_slot() -> datetime:
    now_local = datetime.now(VENUE_TIMEZONE)
    target_today = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
    if now_local >= target_today:
        target_today += timedelta(days=1)
    return target_today.astimezone(timezone.utc)


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

        event_id = data.event_id
        starts_at = None

        if event_id is not None:
            try:
                starts_at = get_bookable_event_start(event_id)
            except EventNotBookable:
                event_id = None
                starts_at = data.starts_at or default_slot()
        elif data.starts_at:
            if data.starts_at <= datetime.now(timezone.utc):
                raise ValueError("starts_at must be in the future")
            starts_at = data.starts_at
        else:
            starts_at = default_slot()

        booking = Booking(
            user_id=user_id,
            phone=phone,
            table_id=data.table_id,
            event_id=event_id,
            starts_at=starts_at,
            booking_date=local_date(starts_at) if starts_at else None,
            guests=data.guests,
            comment=data.comment,
            status=BookingStatus.PENDING_PAYMENT,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=BOOKING_HOLD_MINUTES),
        )
        self.db.add(booking)
        self._save_checked(booking)

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

        # Онлайн-оплата из приложения - это предоплата брони (нужна для отчётов)
        if amount is not None:
            booking.prepayment = amount
            booking.prepayment_paid = True

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

    def list_bookings(self, **filters) -> list[Booking]:
        return self.repository.list_filtered(**filters)

    def _save_checked(self, booking: Booking, exclude_id: int | None = None) -> None:
        """Проверка двойной брони и commit под блокировкой стола."""
        self.repository.lock_table(booking.table_id)

        conflict = self.repository.find_conflict(
            booking.table_id,
            booking.event_id,
            booking.booking_date,
            exclude_id=exclude_id,
        )
        if conflict:
            self.db.rollback()
            raise ValueError(conflict)

        try:
            self.db.flush()
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Table is already booked")

        self.db.refresh(booking)

    def create_admin_booking(
        self,
        admin_id: int,
        data: AdminBookingCreate,
    ) -> Booking:
        # Бронь от администратора сразу подтверждена: оплата не через приложение
        booking = Booking(
            user_id=admin_id,
            phone=data.guest_phone,
            guest_name=data.guest_name,
            table_id=data.table_id,
            event_id=data.event_id,
            starts_at=data.starts_at,
            booking_date=local_date(data.starts_at),
            guests=data.guests,
            total_amount=data.total_amount,
            prepayment=data.prepayment,
            prepayment_paid=data.prepayment_paid,
            source=BookingSource.ADMIN.value,
            status=BookingStatus.CONFIRMED,
            expires_at=datetime.now(timezone.utc),
        )
        self.db.add(booking)
        self._save_checked(booking)

        self.publisher.publish_threadsafe(
            "booking.confirmed",
            booking_payload(booking, confirmed_by="admin"),
        )

        return booking

    def update_admin_booking(
        self,
        booking_id: int,
        data: AdminBookingUpdate,
    ) -> Booking | None:
        booking = self.repository.get_by_id(booking_id, for_update=True)

        if booking is None:
            self.db.rollback()
            return None

        if booking.status not in ACTIVE_STATUSES:
            self.db.rollback()
            raise ValueError("Only active bookings can be changed")

        changes = data.model_dump(exclude_unset=True)

        if "guest_phone" in changes:
            changes["phone"] = changes.pop("guest_phone")
        if "starts_at" in changes:
            changes["booking_date"] = local_date(changes["starts_at"])

        for field, value in changes.items():
            setattr(booking, field, value)

        if booking.event_id is None and booking.starts_at is None:
            self.db.rollback()
            raise ValueError("Booking needs an event or a start time")

        try:
            check_prepayment(booking.total_amount, booking.prepayment)
        except ValueError:
            self.db.rollback()
            raise

        self._save_checked(booking, exclude_id=booking.id)

        return booking

    def cancel_booking(
        self,
        booking_id: int,
        user_id: int,
        is_admin: bool = False,
        reason: str | None = None,
    ) -> Booking | None:

        booking = self.repository.get_by_id(booking_id, for_update=True)

        if booking is None:
            return None

        # Гость отменяет только свою бронь, администратор - любую
        if booking.user_id != user_id and not is_admin:
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
        booking.cancel_reason = reason

        self.db.commit()
        self.db.refresh(booking)

        self.publisher.publish_threadsafe(
            "booking.cancelled",
            booking_payload(
                booking,
                reason="admin" if is_admin and booking.user_id != user_id else "user",
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
