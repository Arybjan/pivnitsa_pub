import enum

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, Numeric, String, Text, func, text
from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


# Статусы, при которых бронь считается занятой платежом: второй такой платёж
# на ту же бронь запрещён уникальным индексом в БД (а не asyncio.Lock в памяти).
ACTIVE_STATUSES_SQL = "status IN ('PENDING', 'SUCCEEDED', 'REFUND_PENDING')"

PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    booking_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="KGS", nullable=False)
    status = Column(String(30), default=PaymentStatus.PENDING.value, nullable=False)
    provider = Column(String(50), default="STRIPE", nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    provider_payment_id = Column(String(255), nullable=True, index=True)
    # Секрет страницы оплаты (аналог Stripe client_secret): знает только владелец
    client_secret = Column(String(255), nullable=True)
    receipt_url = Column(String(500), nullable=True)
    refund_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_payments_active_booking",
            "booking_id",
            unique=True,
            postgresql_where=text(ACTIVE_STATUSES_SQL),
            sqlite_where=text(ACTIVE_STATUSES_SQL),
        ),
    )


class OutboxEvent(Base):
    """
    Transactional outbox: событие пишется в той же транзакции, что и смена статуса
    платежа, а в RabbitMQ его отправляет фоновый воркер. Если брокер недоступен,
    событие дождётся отправки, а не потеряется после списания денег.
    """

    __tablename__ = "outbox_events"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    routing_key = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    attempts = Column(Integer, default=0, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
