from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import HTTPException
from typing import Optional, List, Tuple
from app.models.events import Event, EventStatus, EventOutbox
from app.schemas.event import EventCreate, EventUpdate

class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event_data: EventCreate, created_by: UUID) -> Event:
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

        self._validate_dates(event.start_datetime, event.end_datetime)
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
        count_query = select(func.count()).select_from(Event).where(*conditions)
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
        result = await self.db.execute(select(Event).where(Event.id == event_id).with_for_update())
        event = result.scalar_one_or_none()
        if not event:
            return None

        if event_data.status is not None and event.status != EventStatus.PUBLISHED:
            raise HTTPException(status_code=409, detail="Only published events can be finished")
        if event_data.start_datetime is None and "start_datetime" in event_data.model_fields_set:
            raise HTTPException(status_code=422, detail="starts_at cannot be null")
        if event_data.title is None and "title" in event_data.model_fields_set:
            raise HTTPException(status_code=422, detail="title cannot be null")
        for field, value in event_data.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
        self._validate_dates(event.start_datetime, event.end_datetime)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    @staticmethod
    def _validate_dates(start, end):
        if end is not None:
            start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
            end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end
            if end <= start:
                raise HTTPException(status_code=422, detail="ends_at must be after starts_at")

    async def update_status(
        self, event_id: int, status: EventStatus, send_notifications: bool = True,
        recipient_ids: list[UUID] | None = None,
    ) -> Optional[Event]:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if event is None or event.status == status:
            await self.db.commit()
            return event
        previous = event.status
        if status == EventStatus.PUBLISHED and previous != EventStatus.DRAFT:
            raise HTTPException(status_code=409, detail="Only drafts can be published")
        if status == EventStatus.CANCELLED and previous == EventStatus.FINISHED:
            raise HTTPException(status_code=409, detail="Finished events cannot be cancelled")
        if status == EventStatus.DRAFT and previous != EventStatus.PUBLISHED:
            raise HTTPException(status_code=409, detail="Only published events can be unpublished")
        event.status = status
        routing_key = {
            EventStatus.PUBLISHED: "event.published",
            EventStatus.CANCELLED: "event.cancelled",
        }.get(status)
        if routing_key and (status != EventStatus.PUBLISHED or send_notifications):
            message_id = uuid4()
            self.db.add(EventOutbox(
                id=message_id, routing_key=routing_key,
                payload={
                    "message_id": str(message_id), "event_id": event.id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "title": event.title, "starts_at": event.start_datetime.isoformat(),
                    "start_datetime": event.start_datetime.isoformat(),
                    "send_notifications": send_notifications,
                    "recipient_ids": [str(user_id) for user_id in dict.fromkeys(recipient_ids)] if recipient_ids is not None else None,
                    "audience": {"role": "guest", "is_active": True} if recipient_ids is None else None,
                },
            ))
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
