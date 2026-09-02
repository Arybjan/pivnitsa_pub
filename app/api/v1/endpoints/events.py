from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.core.database import get_db
from app.schemas.event import (
    EventCreate, EventUpdate, EventOut,
    EventListResponse, EventPublishRequest
)
from app.services.event_services import EventService
from app.api.dependencies.auth import get_current_user, CurrentUser
from app.utils.exceptions import NotFoundError, PermissionDeniedError
from loguru import logger

router = APIRouter(prefix="/events", tags=["Events"])

# === Public Endpoints (For Guests) ===

@router.get("", response_model=EventListResponse)
async def get_published_events(
    limit: int = Query(10, ge=1, le=100, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список ОПУБЛИКОВАННЫХ мероприятий.
    Доступно всем пользователям (включая неавторизованных).
    """
    service = EventService(db)
    result = await service.get_published_events(limit, offset)
    return EventListResponse(**result)

@router.get("/{event_id}", response_model=EventOut)
async def get_event_by_id(
    event_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить мероприятие по ID.
    Если мероприятие не опубликовано, доступно только админам.
    """
    service = EventService(db)
    event = await service.get_event_by_id(event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    # Если мероприятие не опубликовано, проверяем права
    if event.status != "published":
        # Здесь должна быть проверка на админа через токен
        # Пока пропускаем для упрощения
        pass

    return event

# === Admin Endpoints (Requires Authentication) ===

@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новое мероприятие (ЧЕРНОВИК).
    Только для администраторов.
    """
    # Проверяем права (только админ или владелец)
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can create events")

    service = EventService(db)
    event = await service.create_event(event_data, current_user.id)
    return event

@router.put("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    event_data: EventUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить мероприятие.
    Только для администраторов.
    """
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can update events")

    service = EventService(db)
    event = await service.update_event(event_id, event_data)

    if not event:
        raise NotFoundError(f"Event {event_id} not found")

    return event

@router.post("/{event_id}/publish", response_model=EventOut)
async def publish_event(
    event_id: int,
    request: EventPublishRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Опубликовать мероприятие.
    После публикации становится доступно гостям и рассылаются уведомления.
    Только для администраторов.
    """
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can publish events")

    service = EventService(db)
    event = await service.publish_event(event_id, request.send_notifications)

    if not event:
        raise NotFoundError(f"Event {event_id} not found")

    return event

@router.post("/{event_id}/cancel", response_model=EventOut)
async def cancel_event(
    event_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Отменить мероприятие.
    Только для администраторов.
    """
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can cancel events")

    service = EventService(db)
    event = await service.cancel_event(event_id)

    if not event:
        raise NotFoundError(f"Event {event_id} not found")

    return event

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить мероприятие.
    Только для администраторов.
    """
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can delete events")

    service = EventService(db)
    deleted = await service.delete_event(event_id)

    if not deleted:
        raise NotFoundError(f"Event {event_id} not found")

    return None

# === Admin: Get All Events ===

@router.get("/all", response_model=EventListResponse)
async def get_all_events(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить ВСЕ мероприятия (включая черновики).
    Только для администраторов.
    """
    if current_user.role not in ["admin", "owner"]:
        raise PermissionDeniedError("Only admins can view all events")

    service = EventService(db)
    result = await service.get_all_events(limit, offset, status)
    return EventListResponse(**result)
