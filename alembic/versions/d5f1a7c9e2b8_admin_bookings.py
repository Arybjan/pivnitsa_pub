"""admin bookings: date/time bookings without event, guest and payment details

Revision ID: d5f1a7c9e2b8
Revises: b4e8d2a6c1f3

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd5f1a7c9e2b8'
down_revision: Union[str, Sequence[str], None] = 'b4e8d2a6c1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "bookings",
        "event_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    op.add_column("bookings", sa.Column("starts_at", sa.DateTime(timezone=True)))
    op.add_column("bookings", sa.Column("booking_date", sa.Date()))
    op.add_column("bookings", sa.Column("guest_name", sa.String(length=100)))
    op.add_column("bookings", sa.Column("total_amount", sa.Numeric(12, 2)))
    op.add_column("bookings", sa.Column("prepayment", sa.Numeric(12, 2)))
    op.add_column(
        "bookings",
        sa.Column(
            "prepayment_paid",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column("bookings", sa.Column("cancel_reason", sa.String(length=500)))
    op.add_column(
        "bookings",
        sa.Column(
            "source",
            sa.String(length=10),
            server_default="APP",
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_booking_event_or_time",
        "bookings",
        "event_id IS NOT NULL OR starts_at IS NOT NULL",
    )
    op.create_index("ix_bookings_booking_date", "bookings", ["booking_date"])
    op.create_index(
        "uq_active_booking_table_date",
        "bookings",
        ["table_id", "booking_date"],
        unique=True,
        postgresql_where=sa.text(
            "event_id IS NULL AND status IN ('PENDING_PAYMENT', 'CONFIRMED')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_active_booking_table_date", table_name="bookings")
    op.drop_index("ix_bookings_booking_date", table_name="bookings")
    op.drop_constraint("ck_booking_event_or_time", "bookings", type_="check")

    for column in (
        "source",
        "cancel_reason",
        "prepayment_paid",
        "prepayment",
        "total_amount",
        "guest_name",
        "booking_date",
        "starts_at",
    ):
        op.drop_column("bookings", column)

    # Брони без мероприятия в старой схеме не помещаются
    op.execute("DELETE FROM bookings WHERE event_id IS NULL")
    op.alter_column(
        "bookings",
        "event_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
