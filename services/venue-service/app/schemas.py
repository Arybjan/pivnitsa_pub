from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

from app.models import TableStatus

PositiveInt = Annotated[int, Field(gt=0, le=2_147_483_647, strict=True)]
Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Rotation = Annotated[float, Field(ge=0, lt=360, allow_inf_nan=False)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=2000)]
ImageUrl = Annotated[HttpUrl, Field(max_length=2048)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Patch(Input):
    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field")
        for field in self.model_fields_set - {"map_image_url"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class HallCreate(Input):
    name: Name
    description: Description = ""
    map_image_url: ImageUrl | None = None
    map_width: Annotated[int, Field(gt=0, le=100000, strict=True)] = 1000
    map_height: Annotated[int, Field(gt=0, le=100000, strict=True)] = 700
    is_active: bool = True


class HallUpdate(Patch):
    name: Name | None = None
    description: Description | None = None
    map_image_url: ImageUrl | None = None
    map_width: Annotated[int, Field(gt=0, le=100000, strict=True)] | None = None
    map_height: Annotated[int, Field(gt=0, le=100000, strict=True)] | None = None
    is_active: bool | None = None


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HallRead(ReadModel):
    id: int
    name: str
    description: str
    map_image_url: str | None
    map_width: int
    map_height: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TableCreate(Input):
    hall_id: PositiveInt
    number: PositiveInt
    capacity: Annotated[int, Field(gt=0, le=1000, strict=True)]
    x: Coordinate
    y: Coordinate
    rotation: Rotation = 0
    description: Description = ""
    status: TableStatus = TableStatus.ACTIVE


class TableUpdate(Patch):
    number: PositiveInt | None = None
    capacity: Annotated[int, Field(gt=0, le=1000, strict=True)] | None = None
    x: Coordinate | None = None
    y: Coordinate | None = None
    rotation: Rotation | None = None
    description: Description | None = None
    status: TableStatus | None = None


class TableRead(ReadModel):
    id: int
    hall_id: int
    number: int
    capacity: int
    x: float
    y: float
    rotation: float
    description: str
    status: TableStatus
    created_at: datetime
    updated_at: datetime


class Interval(Input):
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class BlockCreate(Interval):
    reason: Annotated[str, Field(max_length=500)] = ""


class BlockRead(ReadModel):
    id: int
    table_id: int
    starts_at: datetime
    ends_at: datetime
    reason: str
    created_by: str
    created_at: datetime


class AvailabilityRequest(Interval):
    table_ids: Annotated[list[PositiveInt], Field(min_length=1, max_length=200)]
    guests: Annotated[int, Field(gt=0, le=1000, strict=True)] = 1


class UnavailableReason(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    HALL_INACTIVE = "HALL_INACTIVE"
    TABLE_UNAVAILABLE = "TABLE_UNAVAILABLE"
    ADMIN_BLOCK = "ADMIN_BLOCK"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"


class Availability(ReadModel):
    table_id: int
    physically_available: bool
    reason: UnavailableReason | None = None


class MapTable(TableRead):
    physically_available: bool
    reason: UnavailableReason | None = None


class HallMap(BaseModel):
    hall: HallRead
    starts_at: datetime | None
    ends_at: datetime | None
    checked_at: datetime
    tables: list[MapTable]
