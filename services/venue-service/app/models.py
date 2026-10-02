from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Timezone is required")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class TableStatus(StrEnum):
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, onupdate=utc_now
    )


class Hall(TimestampMixin, Base):
    __tablename__ = "halls"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_hall_name"),
        CheckConstraint("map_width > 0 AND map_height > 0", name="ck_hall_dimensions"),
        Index(
            "uq_hall_active_name",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    map_image_url: Mapped[str | None] = mapped_column(String(2048))
    map_width: Mapped[int] = mapped_column(default=1000)
    map_height: Mapped[int] = mapped_column(default=700)
    is_active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Table(TimestampMixin, Base):
    __tablename__ = "venue_tables"
    __table_args__ = (
        CheckConstraint("number > 0", name="ck_table_number"),
        CheckConstraint("capacity > 0", name="ck_table_capacity"),
        CheckConstraint(
            "x >= 0 AND x <= 1 AND y >= 0 AND y <= 1", name="ck_table_position"
        ),
        CheckConstraint("rotation >= 0 AND rotation < 360", name="ck_table_rotation"),
        CheckConstraint("status IN ('ACTIVE', 'UNAVAILABLE')", name="ck_table_status"),
        Index(
            "uq_table_active_number",
            "hall_id",
            "number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hall_id: Mapped[int] = mapped_column(
        ForeignKey("halls.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[int]
    capacity: Mapped[int]
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    rotation: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=TableStatus.ACTIVE)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class TableBlock(TimestampMixin, Base):
    __tablename__ = "table_blocks"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_block_period"),
        Index("ix_block_table_period", "table_id", "starts_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("venue_tables.id", ondelete="RESTRICT")
    )
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[str] = mapped_column(String(128))
