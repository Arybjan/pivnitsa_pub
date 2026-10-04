import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Column, DateTime, Integer, Numeric, String, func
from app.core.database import Base

class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    booking_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="KGS", nullable=False)
    status = Column(String(30), default=PaymentStatus.PENDING.value, nullable=False)
    provider = Column(String(50), default="STRIPE", nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    provider_payment_id = Column(String(255), nullable=True, index=True)
    receipt_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
