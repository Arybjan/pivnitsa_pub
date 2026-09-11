from datetime import datetime

from pydantic import BaseModel, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    table_id: int
    event_id: int
    guests: int = Field(gt=0)


class BookingResponse(BaseModel):
    id: int
    user_id: int
    table_id: int
    event_id: int
    guests: int
    status: BookingStatus
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }