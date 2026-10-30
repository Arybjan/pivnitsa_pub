"""align bookings with specification

Revision ID: b4e8d2a6c1f3
Revises: 7c3e9a1f2b4d

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b4e8d2a6c1f3'
down_revision: Union[str, Sequence[str], None] = '7c3e9a1f2b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ID_COLUMNS = ("id", "user_id", "table_id", "event_id")


def upgrade() -> None:
    # Переименование значения сохраняет его OID, поэтому частичный индекс
    # uq_active_booking_table_event продолжает работать без пересоздания.
    op.execute(
        "ALTER TYPE bookingstatus RENAME VALUE 'PENDING' TO 'PENDING_PAYMENT'"
    )

    for column in ID_COLUMNS:
        op.alter_column(
            "bookings",
            column,
            type_=sa.BigInteger(),
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    op.execute("ALTER SEQUENCE bookings_id_seq AS BIGINT")

    op.add_column(
        "bookings",
        sa.Column("phone", sa.String(length=20), nullable=True),
    )

    # Раньше подтверждение обнуляло expires_at; по спецификации поле обязательное.
    op.execute(
        "UPDATE bookings SET expires_at = created_at WHERE expires_at IS NULL"
    )
    op.alter_column(
        "bookings",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "bookings",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    op.drop_column("bookings", "phone")

    op.execute("ALTER SEQUENCE bookings_id_seq AS INTEGER")

    for column in ID_COLUMNS:
        op.alter_column(
            "bookings",
            column,
            type_=sa.Integer(),
            existing_type=sa.BigInteger(),
            existing_nullable=False,
        )

    op.execute(
        "ALTER TYPE bookingstatus RENAME VALUE 'PENDING_PAYMENT' TO 'PENDING'"
    )
