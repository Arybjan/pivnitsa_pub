from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from enum import Enum

class EventStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

# === Request Schemas ===

class EventCreate(BaseModel):
    title: str = Field(..., max_length=255, description="Название мероприятия")
    description: Optional[str] = Field(None, description="Описание мероприятия")
    poster_url: Optional[str] = Field(None, max_length=500, description="Ссылка на афишу")
    start_datetime: datetime = Field(..., description="Дата и время начала")
    end_datetime: Optional[datetime] = Field(None, description="Дата и время окончания (опционально)")

class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Название мероприятия")
    description: Optional[str] = Field(None, description="Описание мероприятия")
    poster_url: Optional[str] = Field(None, max_length=500, description="Ссылка на афишу")
    start_datetime: Optional[datetime] = Field(None, description="Дата и время начала")
    end_datetime: Optional[datetime] = Field(None, description="Дата и время окончания")
    status: Optional[EventStatus] = Field(None, description="Статус мероприятия")

class EventPublishRequest(BaseModel):
    send_notifications: bool = Field(True, description="Отправлять ли уведомления гостям")

# === Response Schemas ===

class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    poster_url: Optional[str]
    start_datetime: datetime
    end_datetime: Optional[datetime]
    status: EventStatus
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    per_page: int
    has_next: bool
