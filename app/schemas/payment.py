from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.payment import PaymentStatus

class PaymentCreate(BaseModel):
    booking_id: int = Field(..., description="Target booking identifier")
    user_id: Optional[int] = Field(None, description="User identifier (auto-resolved from token if omitted)")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field("KGS", description="Currency code (e.g. KGS, USD, EUR)")
    provider: str = Field("STRIPE", description="Payment provider (STRIPE, CARD, MBANK)")

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
    client_secret: Optional[str] = None
    checkout_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RefundRequest(BaseModel):
    reason: Optional[str] = Field("user_cancellation", description="Reason for the refund")

class PaymentConfirmRequest(BaseModel):
    payment_method_id: Optional[str] = Field("pm_card_visa", description="Test or tokenized payment method (PCI-DSS compliant)")
