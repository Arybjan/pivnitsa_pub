from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_, and_

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user, require_service_or_admin
from app.models.notification import Notification, NotificationSettings
from app.schemas.notification import (
    BigIntId, BigIntPath, NotificationCreate, NotificationResponse,
    UnreadCountResponse, SendSMSRequest, SendSMSResponse,
    NotificationSettingsUpdate, NotificationSettingsResponse
)
from app.services.sms_service import send_sms_via_nikita

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(data: NotificationCreate, auth: AuthenticatedUser = Depends(require_service_or_admin), db: AsyncSession = Depends(get_db)):
    notification = Notification(**data.model_dump())
    db.add(notification)
    await db.commit()
    return notification


@router.get("/", response_model=list[NotificationResponse])
async def get_user_notifications(user_id: BigIntId, current_user: AuthenticatedUser = Depends(get_current_user), unread_only: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    if not current_user.is_admin_or_service and user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    settings = await db.get(NotificationSettings, user_id)
    events_enabled = settings.events_enabled if settings else True
    booking_enabled = settings.booking_enabled if settings else True

    conditions = []
    if events_enabled:
        conditions.append(Notification.user_id.is_(None))
    
    user_filters = [Notification.user_id == user_id]
    if not events_enabled:
        user_filters.append(~Notification.type.startswith("event"))
    if not booking_enabled:
        user_filters.append(~Notification.type.startswith("booking"))
    
    conditions.append(and_(*user_filters))
    query = select(Notification).where(or_(*conditions))
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(user_id: BigIntId, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.is_admin_or_service and user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    settings = await db.get(NotificationSettings, user_id)
    events_enabled = settings.events_enabled if settings else True
    booking_enabled = settings.booking_enabled if settings else True

    conditions = []
    if events_enabled:
        conditions.append(Notification.user_id.is_(None))
    
    user_filters = [Notification.user_id == user_id]
    if not events_enabled:
        user_filters.append(~Notification.type.startswith("event"))
    if not booking_enabled:
        user_filters.append(~Notification.type.startswith("booking"))
    
    conditions.append(and_(*user_filters))
    query = select(func.count(Notification.id)).where(or_(*conditions), Notification.is_read == False)
    result = await db.execute(query)
    count = result.scalar() or 0
    return UnreadCountResponse(user_id=user_id, unread_count=count)


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(user_id: BigIntId | None = None, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user_id = user_id if (user_id and current_user.is_admin_or_service) else current_user.user_id
    settings = await db.get(NotificationSettings, target_user_id)
    if not settings:
        settings = NotificationSettings(user_id=target_user_id, events_enabled=True, booking_enabled=True, sms_enabled=True)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.patch("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(data: NotificationSettingsUpdate, user_id: BigIntId | None = None, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user_id = user_id if (user_id and current_user.is_admin_or_service) else current_user.user_id
    settings = await db.get(NotificationSettings, target_user_id)
    if not settings:
        settings = NotificationSettings(
            user_id=target_user_id,
            events_enabled=True if data.events_enabled is None else data.events_enabled,
            booking_enabled=True if data.booking_enabled is None else data.booking_enabled,
            sms_enabled=True if data.sms_enabled is None else data.sms_enabled
        )
        db.add(settings)
    else:
        if data.events_enabled is not None:
            settings.events_enabled = data.events_enabled
        if data.booking_enabled is not None:
            settings.booking_enabled = data.booking_enabled
        if data.sms_enabled is not None:
            settings.sms_enabled = data.sms_enabled
    await db.commit()
    await db.refresh(settings)
    return settings


@router.get("/dev/token")
async def get_dev_token(role: str = "admin", user_id: int = 1, phone: str = "+996555123456"):
    import time
    import jwt
    from app.core.config import settings

    payload = {
        "sub": str(user_id),
        "role": role,
        "phone": phone,
        "is_active": True,
        "token_type": "access",
        "exp": int(time.time()) + 86400 * 7,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "user_id": user_id,
        "header_example": f"Authorization: Bearer {token}"
    }


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification_by_id(notification_id: BigIntPath, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not current_user.is_admin_or_service and notification.user_id is not None and notification.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.patch("/{notification_id}/read")
async def mark_as_read(notification_id: BigIntPath, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not current_user.is_admin_or_service and notification.user_id is not None and notification.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    await db.commit()
    return {"status": "ok", "message": "Notification marked as read"}


@router.patch("/read-all")
async def mark_all_as_read(user_id: BigIntId, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.is_admin_or_service and user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    stmt = update(Notification).where(or_(Notification.user_id == user_id, Notification.user_id.is_(None)), Notification.is_read == False).values(is_read=True)
    result = await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "user_id": user_id, "updated_count": result.rowcount}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: BigIntPath, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id is None and not current_user.is_admin_or_service:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete broadcast notification")
    if not current_user.is_admin_or_service and notification.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.delete(notification)
    await db.commit()
    return {"status": "ok", "message": "Notification deleted"}


@router.post("/sms", response_model=SendSMSResponse)
async def send_sms(data: SendSMSRequest, bg_tasks: BackgroundTasks, auth: AuthenticatedUser = Depends(require_service_or_admin)):
    bg_tasks.add_task(send_sms_via_nikita, data.phone_number, data.message)
    return SendSMSResponse(status="success", message=f"SMS queued for {data.phone_number}")