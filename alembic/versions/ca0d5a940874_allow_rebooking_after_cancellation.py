"""allow rebooking after cancellation

Revision ID: ca0d5a940874
Revises: f1b72b7d3d64

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ca0d5a940874'
down_revision: Union[str, Sequence[str], None] = 'f1b72b7d3d64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_active_booking_table_event",
        "bookings",
        ["table_id", "event_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('PENDING', 'CONFIRMED')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_booking_table_event",
        table_name="bookings",
    )
