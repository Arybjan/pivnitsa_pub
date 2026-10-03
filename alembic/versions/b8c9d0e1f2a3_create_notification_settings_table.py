"""create_notification_settings_table

Revision ID: b8c9d0e1f2a3
Revises: 7a1b2c3d4e5f
Create Date: 2026-10-04 01:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = '7a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_settings',
        sa.Column('user_id', sa.BigInteger(), primary_key=True, index=True, nullable=False),
        sa.Column('events_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('booking_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sms_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('notification_settings')
