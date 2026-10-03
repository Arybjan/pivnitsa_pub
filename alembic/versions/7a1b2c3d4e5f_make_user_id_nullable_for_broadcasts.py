"""make_user_id_nullable_for_broadcasts

Revision ID: 7a1b2c3d4e5f
Revises: 2821b4c59e88
Create Date: 2026-10-03 13:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '7a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '2821b4c59e88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('notifications', 'user_id', existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column('notifications', 'user_id', existing_type=sa.BigInteger(), nullable=False)
