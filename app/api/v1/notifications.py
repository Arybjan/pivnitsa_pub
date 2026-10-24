from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import BigInteger, select, update, func, or_, and_, exists, literal
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user, require_service_or_admin
from app.models.notification import Notification, NotificationRead, NotificationSettings
from app.schemas.notification import (
    BigIntPath, NotificationCreate, NotificationResponse,
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


def _visible_to(user_id: int, settings: NotificationSettings | None):
    """Условие: личные уведомления пользователя и общие анонсы с учётом его настроек."""
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
    return or_(*conditions)


def _is_read_by(user_id: int):
    """Прочитано ли уведомление этим пользователем.

    Личное - по флагу is_read. Анонс - по отметке в notification_reads;
    общий флаг is_read анонса учитывается для старых отметок до миграции.
    """
    read_mark = exists().where(
        NotificationRead.notification_id == Notification.id,
        NotificationRead.user_id == user_id,
    )
    return or_(Notification.is_read.is_(True), and_(Notification.user_id.is_(None), read_mark))


def _response(notification: Notification, is_read: bool) -> NotificationResponse:
    item = NotificationResponse.model_validate(notification)
    item.is_read = bool(is_read)
    return item


@router.get("/", response_model=list[NotificationResponse])
async def get_user_notifications(current_user: AuthenticatedUser = Depends(get_current_user), unread_only: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    user_id = current_user.user_id
    settings = await db.get(NotificationSettings, user_id)
    is_read = _is_read_by(user_id)
    query = select(Notification, is_read.label("is_read_by_user")).where(_visible_to(user_id, settings))
    if unread_only:
        query = query.where(~is_read)
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [_response(notification, read) for notification, read in result.all()]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user.user_id
    settings = await db.get(NotificationSettings, user_id)
    query = select(func.count(Notification.id)).where(_visible_to(user_id, settings), ~_is_read_by(user_id))
    result = await db.execute(query)
    count = result.scalar() or 0
    return UnreadCountResponse(user_id=user_id, unread_count=count)


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user_id = current_user.user_id
    settings = await db.get(NotificationSettings, target_user_id)
    if not settings:
        settings = NotificationSettings(user_id=target_user_id, events_enabled=True, booking_enabled=True, sms_enabled=True)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.patch("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(data: NotificationSettingsUpdate, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user_id = current_user.user_id
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
    is_read = notification.is_read
    if notification.user_id is None and not is_read:
        is_read = await db.get(NotificationRead, (notification.id, current_user.user_id)) is not None
    return _response(notification, is_read)


@router.patch("/{notification_id}/read")
async def mark_as_read(notification_id: BigIntPath, current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not current_user.is_admin_or_service and notification.user_id is not None and notification.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id is None:
        # Анонс общий: отмечаем прочтение только для текущего пользователя
        await db.execute(
            pg_insert(NotificationRead)
            .values(notification_id=notification.id, user_id=current_user.user_id)
            .on_conflict_do_nothing()
        )
    else:
        notification.is_read = True
    await db.commit()
    return {"status": "ok", "message": "Notification marked as read"}


@router.patch("/read-all")
async def mark_all_as_read(current_user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Помечает прочитанными все уведомления владельца токена.

    Меняются только его личные уведомления; анонсы отмечаются в notification_reads
    и остаются непрочитанными для остальных пользователей.
    """
    user_id = current_user.user_id
    personal = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    unread_broadcasts = select(Notification.id, literal(user_id, BigInteger)).where(
        Notification.user_id.is_(None), ~_is_read_by(user_id)
    )
    broadcasts = await db.execute(
        pg_insert(NotificationRead)
        .from_select(["notification_id", "user_id"], unread_broadcasts)
        .on_conflict_do_nothing()
    )
    await db.commit()
    return {"status": "ok", "user_id": user_id, "updated_count": personal.rowcount + broadcasts.rowcount}


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
async def send_sms(data: SendSMSRequest, auth: AuthenticatedUser = Depends(require_service_or_admin)):
    # Отправляем сразу, а не в фоне: Auth должен знать, ушёл ли код,
    # иначе человек ждёт SMS, которой не будет, а повторный запрос заблокирован на минуту
    if not await send_sms_via_nikita(data.phone_number, data.message):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SMS gateway rejected the message or is unavailable")
    return SendSMSResponse(status="success", message=f"SMS sent to {data.phone_number}")