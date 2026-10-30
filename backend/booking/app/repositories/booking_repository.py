from datetime import date, datetime, timezone
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models.booking import ACTIVE_STATUSES, Booking, BookingStatus


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

    def lock_table(self, table_id: int) -> None:
        # Брони одного стола создаются и меняются по очереди до commit:
        # уникальные индексы не покрывают пересечение брони на мероприятие
        # и брони на обычный вечер в тот же день.
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": table_id},
            )

    def find_conflict(
        self,
        table_id: int,
        event_id: int | None,
        booking_date: date | None,
        exclude_id: int | None = None,
    ) -> str | None:
        active = [
            Booking.table_id == table_id,
            Booking.status.in_(ACTIVE_STATUSES),
        ]
        if exclude_id is not None:
            active.append(Booking.id != exclude_id)

        if event_id is not None:
            stmt = select(Booking.id).where(*active, Booking.event_id == event_id)
            if self.db.scalar(stmt) is not None:
                return "Table is already booked for this event"

        if booking_date is not None:
            # Бронь на обычный вечер занимает стол на весь день.
            # Две брони на разные мероприятия в один день не конфликтуют.
            same_day = [*active, Booking.booking_date == booking_date]
            if event_id is not None:
                same_day.append(Booking.event_id.is_(None))
            if self.db.scalar(select(Booking.id).where(*same_day)) is not None:
                return "Table is already booked for this date"

        return None

    def list_filtered(
        self,
        event_ids: list[int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        table_id: int | None = None,
        active_only: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Booking]:
        conditions = []

        if event_ids:
            conditions.append(Booking.event_id.in_(event_ids))
        if date_from is not None:
            conditions.append(Booking.booking_date >= date_from)
        if date_to is not None:
            conditions.append(Booking.booking_date <= date_to)
        if table_id is not None:
            conditions.append(Booking.table_id == table_id)
        if active_only:
            conditions.append(Booking.status.in_(ACTIVE_STATUSES))

        stmt = (
            select(Booking)
            .where(*conditions)
            .order_by(Booking.starts_at.asc().nulls_last(), Booking.id)
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(stmt).all())
