from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Hall, Table, TableBlock, TableStatus, utc_now
from app.schemas import (
    Availability,
    BlockCreate,
    HallCreate,
    HallUpdate,
    TableCreate,
    TableUpdate,
    UnavailableReason,
)


class VenueService:
    def __init__(self, db: Session):
        self.db = db

    def save(self, entity):
        self.db.add(entity)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                409, "Conflicting hall name, table number or invalid data"
            ) from None
        self.db.refresh(entity)
        return entity

    def get_hall(self, hall_id: int, lock: bool = False) -> Hall:
        query = select(Hall).where(Hall.id == hall_id, Hall.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        hall = self.db.scalar(query)
        if hall is None:
            raise HTTPException(404, "Hall not found")
        return hall

    def list_halls(self, offset: int, limit: int) -> list[Hall]:
        return list(
            self.db.scalars(
                select(Hall)
                .where(Hall.deleted_at.is_(None))
                .order_by(Hall.id)
                .offset(offset)
                .limit(limit)
            )
        )

    def create_hall(self, data: HallCreate) -> Hall:
        return self.save(Hall(**data.model_dump(mode="json")))

    def update_hall(self, hall_id: int, data: HallUpdate) -> Hall:
        hall = self.get_hall(hall_id, lock=True)
        for key, value in data.model_dump(exclude_unset=True, mode="json").items():
            setattr(hall, key, value)
        return self.save(hall)

    def delete_hall(self, hall_id: int) -> None:
        hall = self.get_hall(hall_id, lock=True)
        table_id = self.db.scalar(
            select(Table.id)
            .where(Table.hall_id == hall_id, Table.deleted_at.is_(None))
            .limit(1)
        )
        if table_id is not None:
            raise HTTPException(409, "Remove the hall's tables first")
        hall.deleted_at = utc_now()
        self.save(hall)

    def get_table(self, table_id: int, lock: bool = False) -> Table:
        query = select(Table).where(Table.id == table_id, Table.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        table = self.db.scalar(query)
        if table is None:
            raise HTTPException(404, "Table not found")
        return table

    def list_tables(
        self,
        hall_id: int | None = None,
        min_capacity: int | None = None,
        offset: int = 0,
        limit: int | None = 100,
    ) -> list[Table]:
        query = select(Table).where(Table.deleted_at.is_(None))
        if hall_id is not None:
            self.get_hall(hall_id)
            query = query.where(Table.hall_id == hall_id)
        if min_capacity is not None:
            query = query.where(Table.capacity >= min_capacity)
        query = query.order_by(Table.hall_id, Table.number, Table.id).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return list(self.db.scalars(query))

    def create_table(self, data: TableCreate) -> Table:
        self.get_hall(data.hall_id, lock=True)
        return self.save(Table(**data.model_dump()))

    def update_table(self, table_id: int, data: TableUpdate) -> Table:
        table = self.get_table(table_id, lock=True)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(table, key, value)
        return self.save(table)

    def delete_table(self, table_id: int) -> None:
        table = self.get_table(table_id, lock=True)
        table.deleted_at = utc_now()
        self.save(table)

    def create_block(self, table_id: int, data: BlockCreate, actor: str) -> TableBlock:
        self.get_table(table_id, lock=True)
        return self.save(
            TableBlock(table_id=table_id, created_by=actor, **data.model_dump())
        )

    def list_blocks(self, table_id: int, offset: int, limit: int) -> list[TableBlock]:
        self.get_table(table_id)
        return list(
            self.db.scalars(
                select(TableBlock)
                .where(TableBlock.table_id == table_id)
                .order_by(TableBlock.starts_at, TableBlock.id)
                .offset(offset)
                .limit(limit)
            )
        )

    def delete_block(self, table_id: int, block_id: int) -> None:
        self.get_table(table_id, lock=True)
        block = self.db.scalar(
            select(TableBlock).where(
                TableBlock.id == block_id, TableBlock.table_id == table_id
            )
        )
        if block is None:
            raise HTTPException(404, "Table block not found")
        self.db.delete(block)
        self.db.commit()

    def availability(
        self,
        table_ids: list[int],
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        guests: int = 1,
        checked_at: datetime | None = None,
    ) -> list[Availability]:
        unique_ids = list(dict.fromkeys(table_ids))
        if not unique_ids:
            return []
        rows = self.db.execute(
            select(Table, Hall)
            .join(Hall)
            .where(
                Table.id.in_(unique_ids),
                Table.deleted_at.is_(None),
                Hall.deleted_at.is_(None),
            )
        ).all()
        tables = {table.id: (table, hall) for table, hall in rows}
        blocks = select(TableBlock.table_id).where(TableBlock.table_id.in_(unique_ids))
        if starts_at is not None and ends_at is not None:
            blocks = blocks.where(
                TableBlock.starts_at < ends_at, TableBlock.ends_at > starts_at
            )
        else:
            now = checked_at or utc_now()
            blocks = blocks.where(TableBlock.starts_at <= now, TableBlock.ends_at > now)
        blocked_ids = set(self.db.scalars(blocks))
        result = []
        for table_id in unique_ids:
            pair = tables.get(table_id)
            reason = None
            if pair is None:
                reason = UnavailableReason.NOT_FOUND
            else:
                table, hall = pair
                if not hall.is_active:
                    reason = UnavailableReason.HALL_INACTIVE
                elif table.status != TableStatus.ACTIVE:
                    reason = UnavailableReason.TABLE_UNAVAILABLE
                elif table_id in blocked_ids:
                    reason = UnavailableReason.ADMIN_BLOCK
                elif table.capacity < guests:
                    reason = UnavailableReason.INSUFFICIENT_CAPACITY
            result.append(
                Availability(
                    table_id=table_id,
                    physically_available=reason is None,
                    reason=reason,
                )
            )
        return result
