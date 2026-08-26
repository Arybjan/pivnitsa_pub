from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.core.database import get_db
from app.models.notification import Notification
from app.schemas.notification import BigIntId, BigIntPath, NotificationCreate, NotificationResponse, UnreadCountResponse, SendSMSRequest, SendSMSResponse
from app.services.sms_service import send_sms_via_nikita

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(data: NotificationCreate, db: AsyncSession = Depends(get_db)):
    notification = Notification(**data.model_dump())
    db.add(notification)
    await db.commit()
    return notification


@router.get("/", response_model=list[NotificationResponse])
async def get_user_notifications(user_id: BigIntId, unread_only: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(user_id: BigIntId, db: AsyncSession = Depends(get_db)):
    query = select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read == False)
    result = await db.execute(query)
    count = result.scalar() or 0
    return UnreadCountResponse(user_id=user_id, unread_count=count)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification_by_id(notification_id: BigIntPath, db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.patch("/{notification_id}/read")
async def mark_as_read(notification_id: BigIntPath, db: AsyncSession = Depends(get_db)):
    stmt = update(Notification).where(Notification.id == notification_id).values(is_read=True)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"status": "ok", "message": "Notification marked as read"}


@router.patch("/read-all")
async def mark_all_as_read(user_id: BigIntId, db: AsyncSession = Depends(get_db)):
    stmt = update(Notification).where(Notification.user_id == user_id, Notification.is_read == False).values(is_read=True)
    result = await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "user_id": user_id, "updated_count": result.rowcount}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: BigIntPath, db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.delete(notification)
    await db.commit()
    return {"status": "ok", "message": "Notification deleted"}


@router.post("/sms", response_model=SendSMSResponse)
async def send_sms(data: SendSMSRequest, bg_tasks: BackgroundTasks):
    bg_tasks.add_task(send_sms_via_nikita, data.phone_number, data.message)
    return SendSMSResponse(status="success", message=f"SMS queued for {data.phone_number}")