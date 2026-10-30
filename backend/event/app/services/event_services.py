from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import Event, EventStatus
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    def __init__(self, db: AsyncSession):
        self.repository = EventRepository(db)

    @staticmethod
    def _page(events: list[Event], total: int, limit: int, offset: int) -> dict:
        return {
            "items": events,
            "total": total,
            "page": offset // limit + 1,
            "per_page": limit,
            "has_next": offset + len(events) < total,
        }

    async def get_published_events(self, limit: int, offset: int) -> dict:
        events, total = await self.repository.published(limit, offset)
        return self._page(events, total, limit, offset)

    async def get_all_events(
        self, limit: int, offset: int, status: Optional[str] = None
    ) -> dict:
        event_status = EventStatus(status) if status else None
        events, total = await self.repository.get_all(limit, offset, event_status)
        return self._page(events, total, limit, offset)

    async def get_event_by_id(self, event_id: int) -> Optional[Event]:
        return await self.repository.get_by_id(event_id)

    async def create_event(self, event_data: EventCreate, created_by: int) -> Event:
        return await self.repository.create(event_data, created_by)

    async def update_event(
        self, event_id: int, event_data: EventUpdate
    ) -> Optional[Event]:
        return await self.repository.update(event_id, event_data)

    async def publish_event(
        self, event_id: int, send_notifications: bool = True,
        recipient_ids: list[int] | None = None,
    ) -> Optional[Event]:
        return await self.repository.update_status(event_id, EventStatus.PUBLISHED, send_notifications, recipient_ids)

    async def unpublish_event(self, event_id: int) -> Optional[Event]:
        return await self.repository.update_status(event_id, EventStatus.DRAFT)

    async def cancel_event(self, event_id: int) -> Optional[Event]:
        return await self.repository.update_status(event_id, EventStatus.CANCELLED)

    async def delete_event(self, event_id: int) -> bool:
        return await self.repository.delete(event_id)
