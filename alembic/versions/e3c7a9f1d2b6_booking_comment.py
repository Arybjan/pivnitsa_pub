"""booking comment: guest's wishes for the booking

Revision ID: e3c7a9f1d2b6
Revises: d5f1a7c9e2b8

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e3c7a9f1d2b6'
down_revision: Union[str, Sequence[str], None] = 'd5f1a7c9e2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Существующие брони получают NULL - без комментария
    op.add_column("bookings", sa.Column("comment", sa.String(length=500)))


def downgrade() -> None:
    op.drop_column("bookings", "comment")
