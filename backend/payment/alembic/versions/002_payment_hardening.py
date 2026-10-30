"""add missing payment columns, active payment uniqueness and outbox

Revision ID: 002_payment_hardening
Revises: 001_create_payments_table
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_payment_hardening'
down_revision: Union[str, None] = '001_create_payments_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_STATUSES_SQL = "status IN ('PENDING', 'SUCCEEDED', 'REFUND_PENDING')"


def upgrade() -> None:
    # Модель использовала idempotency_key, а миграция 001 его не создавала —
    # из-за этого POST /payments падал с 500 после alembic upgrade head.
    if op.get_bind().dialect.name == "sqlite":
        # В SQLite автоинкремент работает только у INTEGER PRIMARY KEY, а 001 создала BIGINT
        with op.batch_alter_table('payments', recreate='always') as batch:
            batch.alter_column('id', existing_type=sa.BigInteger(), type_=sa.Integer(), autoincrement=True)

    with op.batch_alter_table('payments') as batch:
        batch.add_column(sa.Column('idempotency_key', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('client_secret', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('refund_reason', sa.String(length=255), nullable=True))

    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)

    # Один активный платёж на бронь — гарантия БД, а не asyncio.Lock в памяти процесса
    op.create_index(
        'uq_payments_active_booking',
        'payments',
        ['booking_id'],
        unique=True,
        postgresql_where=sa.text(ACTIVE_STATUSES_SQL),
        sqlite_where=sa.text(ACTIVE_STATUSES_SQL),
    )

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('routing_key', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_events_published_at'), 'outbox_events', ['published_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outbox_events_published_at'), table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_index('uq_payments_active_booking', table_name='payments')
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    with op.batch_alter_table('payments') as batch:
        batch.drop_column('refund_reason')
        batch.drop_column('client_secret')
        batch.drop_column('idempotency_key')
