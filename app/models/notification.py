from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    related_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    related_booking_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)