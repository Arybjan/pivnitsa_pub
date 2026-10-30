from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# Активные брони занимают стол
ACTIVE_STATUSES = (BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED)


class BookingSource(str, Enum):
    APP = "APP"      # гость сам через приложение
    ADMIN = "ADMIN"  # администратор (гость позвонил, пришёл без брони)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # Бронь либо на мероприятие, либо на дату и время
        CheckConstraint(
            "event_id IS NOT NULL OR starts_at IS NOT NULL",
            name="ck_booking_event_or_time",
        ),
        # Обычный вечер без мероприятия: одна активная бронь стола на день
        Index(
            "uq_active_booking_table_date",
            "table_id",
            "booking_date",
            unique=True,
            postgresql_where=text(
                "event_id IS NULL AND status IN ('PENDING_PAYMENT', 'CONFIRMED')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    table_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    event_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    # Время прихода гостей. Для брони из приложения на мероприятие может быть пустым
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Дата брони по местному времени заведения (VENUE_TIMEZONE)
    booking_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True
    )

    guests: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Телефон гостя из JWT: нужен notification-service для SMS
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    guest_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    prepayment: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    # Предоплата внесена (иначе оплата при входе)
    prepayment_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False
    )

    # Комментарий гостя к брони из приложения
    comment: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    cancel_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    source: Mapped[str] = mapped_column(
        String(10),
        default=BookingSource.APP.value,
        server_default=BookingSource.APP.value,
        nullable=False
    )

    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus),
        default=BookingStatus.PENDING_PAYMENT,
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )