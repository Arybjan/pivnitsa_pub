"""add booking comment

Revision ID: e7b3c9d1f4a6
Revises: d5f1a7c9e2b8

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7b3c9d1f4a6'
down_revision: Union[str, Sequence[str], None] = 'd5f1a7c9e2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Колонка необязательная: у существующих броней комментарий остаётся NULL
    op.add_column("bookings", sa.Column("comment", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "comment")
