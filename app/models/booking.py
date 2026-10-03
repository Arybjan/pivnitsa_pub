from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Integer, String
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


class Booking(Base):
    __tablename__ = "bookings"

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

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
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