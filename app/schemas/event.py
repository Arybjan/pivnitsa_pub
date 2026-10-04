from pydantic import BaseModel, Field, ConfigDict, AliasChoices, field_validator
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from app.models.events import EventStatus

# === Request Schemas ===

class EventDates(BaseModel):
    @field_validator("start_datetime", "end_datetime", check_fields=False)
    @classmethod
    def normalize_datetime(cls, value):
        if value is None:
            return value
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class EventCreate(EventDates):
    title: str = Field(..., min_length=1, max_length=255, description="Название мероприятия")
    description: Optional[str] = Field(None, description="Описание мероприятия")
    poster_url: Optional[str] = Field(None, max_length=500, description="Ссылка на афишу")
    start_datetime: datetime = Field(..., validation_alias=AliasChoices("starts_at", "start_datetime"), serialization_alias="starts_at", description="Дата и время начала")
    end_datetime: Optional[datetime] = Field(None, validation_alias=AliasChoices("ends_at", "end_datetime"), serialization_alias="ends_at", description="Дата и время окончания (опционально)")

class EventUpdate(EventDates):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Название мероприятия")
    description: Optional[str] = Field(None, description="Описание мероприятия")
    poster_url: Optional[str] = Field(None, max_length=500, description="Ссылка на афишу")
    start_datetime: Optional[datetime] = Field(None, validation_alias=AliasChoices("starts_at", "start_datetime"), serialization_alias="starts_at", description="Дата и время начала")
    end_datetime: Optional[datetime] = Field(None, validation_alias=AliasChoices("ends_at", "end_datetime"), serialization_alias="ends_at", description="Дата и время окончания")

    status: Optional[EventStatus] = None

    @field_validator("status")
    @classmethod
    def terminal_status_only(cls, value):
        if value != EventStatus.FINISHED:
            raise ValueError("Use publish, unpublish or cancel endpoints for other status transitions")
        return value

class EventPublishRequest(BaseModel):
    send_notifications: bool = Field(True, description="Отправлять ли уведомления гостям")
    recipient_ids: list[UUID] | None = Field(None, description="Explicit recipients; otherwise all active guests")

# === Response Schemas ===

class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    poster_url: Optional[str]
    start_datetime: datetime = Field(validation_alias=AliasChoices("starts_at", "start_datetime"), serialization_alias="starts_at")
    end_datetime: Optional[datetime] = Field(validation_alias=AliasChoices("ends_at", "end_datetime"), serialization_alias="ends_at")
    status: EventStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    per_page: int
    has_next: bool
