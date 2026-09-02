from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple
from app.models.events import Event, EventStatus
from app.schemas.event import EventCreate, EventUpdate

class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event_data: EventCreate, created_by: int) -> Event:
        """Create a new Event"""

        event = Event(
            title = event_data.title,
            description = event_data.description,
            poster_url = event_data.poster_url,
            start_datetime = event_data.start_datetime,
            end_datetime = event_data.end_datetime,
            created_by = created_by,
            status = EventStatus.DRAFT
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_by_id(self, event_id: int) -> Optional[Event]:
        """Get Event by ID"""
        query = select(Event).where(Event.id == event_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def published(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Event], int]:
        """Get published events with pagination"""
        # First, count all published events
        count_query = select(func.count()).where(
            Event.status == EventStatus.PUBLISHED,
            Event.start_datetime >= func.now()
        )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        query = select(Event).where(
            Event.status == EventStatus.PUBLISHED,
            Event.start_datetime >= func.now()
        ).order_by(Event.start_datetime).limit(limit).offset(offset)
        result = await self.db.execute(query)
        events = result.scalars().all()
        return events, total


    async def get_all(
        self,
        limit: int = 10,
        offset: int = 0,
        status: Optional[EventStatus] = None,
    ) -> Tuple[List[Event], int]:
        """Get all events with pagination (for admin)"""
        conditions = []
        if status:
            conditions.append(Event.status == status)


        # Count all general events
        count_query = select(func.count()).where(*conditions)
        if conditions:
            count_query = count_query.where(*conditions)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()


        # Get List
        query = select(Event).order_by(
            Event.start_datetime.desc()
        ).limit(limit).offset(offset)

        if conditions:
            query = query.where(*conditions)

        result = await self.db.execute(query)
        events = result.scalars().all()


        return events, total


    async def update(self, event_id: int, event_data: EventUpdate) -> Optional[Event]:
        # Update Event
        event = await self.get_by_id(event_id)
        if not event:
            return None

        for field, value in event_data.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def update_status(self, event_id: int, status: EventStatus) -> Optional[Event]:
        event = await self.get_by_id(event_id)
        if not event:
            return None


        event.status = status
        await self.db.commit()
        await self.db.refresh(event)
        return event


    async def delete(self, event_id: int) -> bool:
        """Delete event"""
        event = await self.get_by_id(event_id)
        if not event:
            return False

        await self.db.delete(event)
        await self.db.commit()
        return True


    async def get_by_ids(self, event_ids: List[int]) -> List[Event]:
        query = select(Event).where(Event.id.in_(event_ids))
        result = await self.db.execute(query)
        return result.scalars().all()
