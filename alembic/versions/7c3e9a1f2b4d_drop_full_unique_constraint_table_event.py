"""drop full unique constraint for table event

Revision ID: 7c3e9a1f2b4d
Revises: ca0d5a940874

"""

from typing import Sequence, Union

from alembic import op


revision: str = '7c3e9a1f2b4d'
down_revision: Union[str, Sequence[str], None] = 'ca0d5a940874'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The partial index uq_active_booking_table_event already guarantees
    # uniqueness for active bookings; the full constraint blocked rebooking
    # after cancellation or expiration.
    op.drop_constraint(
        "uq_booking_table_event",
        "bookings",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_booking_table_event",
        "bookings",
        ["table_id", "event_id"],
    )
