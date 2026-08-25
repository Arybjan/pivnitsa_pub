from datetime import datetime
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.base import SafeBaseModel, BigIntId, BigIntPath


class NotificationCreate(SafeBaseModel):
    user_id: BigIntId
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=65535)
    type: str = Field(..., min_length=1, max_length=30)
    related_event_id: BigIntId | None = None
    related_booking_id: BigIntId | None = None


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    related_event_id: int | None = None
    related_booking_id: int | None = None
    is_read: bool | None = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    user_id: int
    unread_count: int


class SendSMSRequest(SafeBaseModel):
    phone_number: str = Field(..., min_length=5, max_length=30)
    message: str = Field(..., min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _validate_phone(self):
        if len(re.sub(r"\D", "", self.phone_number)) < 5:
            raise ValueError("Phone number must contain at least 5 digits")
        return self


class SendSMSResponse(BaseModel):
    status: str
    message: str