from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    table_id: int
    event_id: int
    guests: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def empty_comment_to_none(cls, value: str | None) -> str | None:
        # Пустой комментарий не храним: "" и пробелы равнозначны его отсутствию
        return value or None


Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
GuestName = Annotated[str, Field(min_length=1, max_length=100)]
GuestPhone = Annotated[str, Field(min_length=5, max_length=20, pattern=r"^\+?[\d\s\-()]+$")]


def check_prepayment(total: Decimal | None, prepayment: Decimal | None) -> None:
    if total and prepayment and prepayment > total:
        raise ValueError("prepayment cannot exceed total_amount")


class AdminBookingCreate(BaseModel):
    """Бронь, которую администратор создаёт сам (звонок, гость у входа)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    table_id: int = Field(gt=0)
    # Без мероприятия - бронь на обычный вечер
    event_id: int | None = Field(default=None, gt=0)
    starts_at: AwareDatetime
    guests: int = Field(gt=0, le=1000)
    guest_name: GuestName
    guest_phone: GuestPhone
    total_amount: Money | None = None
    prepayment: Money | None = None
    prepayment_paid: bool = False

    @model_validator(mode="after")
    def validate_amounts(self) -> Self:
        check_prepayment(self.total_amount, self.prepayment)
        return self


class AdminBookingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    table_id: int | None = Field(default=None, gt=0)
    event_id: int | None = Field(default=None, gt=0)
    starts_at: AwareDatetime | None = None
    guests: int | None = Field(default=None, gt=0, le=1000)
    guest_name: GuestName | None = None
    guest_phone: GuestPhone | None = None
    total_amount: Money | None = None
    prepayment: Money | None = None
    prepayment_paid: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field")
        # event_id, суммы можно сбросить в null, остальное - нет
        nullable = {"event_id", "total_amount", "prepayment"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BookingCancel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


class BookingResponse(BaseModel):
    id: int
    user_id: int
    table_id: int
    # Номер стола из Venue Service; null, если стол не найден или Venue недоступен
    table_number: int | None = None
    event_id: int | None
    starts_at: datetime | None
    booking_date: date | None
    guests: int
    phone: str | None
    guest_name: str | None
    total_amount: Decimal | None
    prepayment: Decimal | None
    prepayment_paid: bool
    comment: str | None = None
    cancel_reason: str | None
    source: str
    status: BookingStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
