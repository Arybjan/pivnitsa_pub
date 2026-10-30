"""create_notification_reads_table

Revision ID: c4d5e6f7a8b9
Revises: b8c9d0e1f2a3
Create Date: 2026-10-24 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Прочтение общих анонсов отдельно для каждого пользователя.
    # Существующие notifications не меняются: уже прочитанные анонсы остаются прочитанными.
    op.create_table(
        'notification_reads',
        sa.Column('notification_id', sa.BigInteger(), sa.ForeignKey('notifications.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_notification_reads_user_id', 'notification_reads', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_notification_reads_user_id', table_name='notification_reads')
    op.drop_table('notification_reads')
