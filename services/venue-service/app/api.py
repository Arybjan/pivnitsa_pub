from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import utc_now
from app.schemas import (
    Availability,
    AvailabilityRequest,
    BlockCreate,
    BlockRead,
    HallCreate,
    HallMap,
    HallRead,
    HallUpdate,
    MapTable,
    TableCreate,
    TableRead,
    TableUpdate,
)
from app.security import require_admin
from app.service import VenueService

router = APIRouter(prefix="/api/v1")
Database = Annotated[Session, Depends(get_db)]
Admin = Annotated[str, Depends(require_admin)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=200)]


def get_interval(
    starts_at: Annotated[AwareDatetime | None, Query()] = None,
    ends_at: Annotated[AwareDatetime | None, Query()] = None,
) -> tuple[datetime | None, datetime | None]:
    if (starts_at is None) != (ends_at is None):
        raise HTTPException(422, "Provide both starts_at and ends_at")
    if starts_at is not None and ends_at <= starts_at:
        raise HTTPException(422, "ends_at must be later than starts_at")
    return starts_at, ends_at


@router.get("/halls", response_model=list[HallRead], tags=["Halls"])
def list_halls(db: Database, offset: Offset = 0, limit: Limit = 100):
    return VenueService(db).list_halls(offset, limit)


@router.post("/halls", response_model=HallRead, status_code=201, tags=["Halls"])
def create_hall(data: HallCreate, db: Database, admin: Admin):
    return VenueService(db).create_hall(data)


@router.get("/halls/{hall_id}", response_model=HallRead, tags=["Halls"])
def get_hall(hall_id: int, db: Database):
    return VenueService(db).get_hall(hall_id)


@router.patch("/halls/{hall_id}", response_model=HallRead, tags=["Halls"])
def update_hall(hall_id: int, data: HallUpdate, db: Database, admin: Admin):
    return VenueService(db).update_hall(hall_id, data)


@router.delete("/halls/{hall_id}", status_code=204, tags=["Halls"])
def delete_hall(hall_id: int, db: Database, admin: Admin):
    VenueService(db).delete_hall(hall_id)
    return Response(status_code=204)


@router.get("/halls/{hall_id}/map", response_model=HallMap, tags=["Halls"])
def get_hall_map(
    hall_id: int,
    db: Database,
    interval: Annotated[tuple, Depends(get_interval)],
):
    service = VenueService(db)
    hall = service.get_hall(hall_id)
    tables = service.list_tables(hall_id=hall_id, limit=None)
    checked_at = utc_now()
    starts_at, ends_at = interval
    availability = {
        item.table_id: item
        for item in service.availability(
            [table.id for table in tables], starts_at, ends_at, checked_at=checked_at
        )
    }
    return HallMap(
        hall=HallRead.model_validate(hall),
        starts_at=starts_at,
        ends_at=ends_at,
        checked_at=checked_at,
        tables=[
            MapTable(
                **TableRead.model_validate(table).model_dump(),
                physically_available=availability[table.id].physically_available,
                reason=availability[table.id].reason,
            )
            for table in tables
        ],
    )


@router.get("/tables", response_model=list[TableRead], tags=["Tables"])
def list_tables(
    db: Database,
    hall_id: Annotated[int | None, Query(gt=0)] = None,
    min_capacity: Annotated[int | None, Query(gt=0)] = None,
    offset: Offset = 0,
    limit: Limit = 100,
):
    return VenueService(db).list_tables(hall_id, min_capacity, offset, limit)


@router.post("/tables", response_model=TableRead, status_code=201, tags=["Tables"])
def create_table(data: TableCreate, db: Database, admin: Admin):
    return VenueService(db).create_table(data)


@router.post(
    "/tables/availability", response_model=list[Availability], tags=["Availability"]
)
def check_availability(data: AvailabilityRequest, db: Database):
    return VenueService(db).availability(
        data.table_ids, data.starts_at, data.ends_at, data.guests
    )


@router.get("/tables/{table_id}", response_model=TableRead, tags=["Tables"])
def get_table(table_id: int, db: Database):
    return VenueService(db).get_table(table_id)


@router.patch("/tables/{table_id}", response_model=TableRead, tags=["Tables"])
def update_table(table_id: int, data: TableUpdate, db: Database, admin: Admin):
    return VenueService(db).update_table(table_id, data)


@router.delete("/tables/{table_id}", status_code=204, tags=["Tables"])
def delete_table(table_id: int, db: Database, admin: Admin):
    VenueService(db).delete_table(table_id)
    return Response(status_code=204)


@router.get(
    "/tables/{table_id}/blocks", response_model=list[BlockRead], tags=["Blocks"]
)
def list_blocks(
    table_id: int, db: Database, admin: Admin, offset: Offset = 0, limit: Limit = 100
):
    return VenueService(db).list_blocks(table_id, offset, limit)


@router.post(
    "/tables/{table_id}/blocks",
    response_model=BlockRead,
    status_code=201,
    tags=["Blocks"],
)
def create_block(table_id: int, data: BlockCreate, db: Database, admin: Admin):
    return VenueService(db).create_block(table_id, data, admin)


@router.delete("/tables/{table_id}/blocks/{block_id}", status_code=204, tags=["Blocks"])
def delete_block(table_id: int, block_id: int, db: Database, admin: Admin):
    VenueService(db).delete_block(table_id, block_id)
    return Response(status_code=204)
