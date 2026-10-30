from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    # Только бронь: пользователь берётся из токена, сумма — из брони на сервере
    booking_id: int = Field(..., gt=0, description="Target booking identifier")


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    user_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    provider: str
    provider_payment_id: Optional[str] = None
    receipt_url: Optional[str] = None
    refund_reason: Optional[str] = None
    # Заполняются только для владельца платежа
    client_secret: Optional[str] = None
    checkout_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefundRequest(BaseModel):
    reason: Optional[str] = Field("admin_refund", max_length=255, description="Reason for the refund")


class PaymentConfirmRequest(BaseModel):
    payment_method_id: Optional[str] = Field("pm_card_visa", description="Test or tokenized payment method (PCI-DSS compliant)")
