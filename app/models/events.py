from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Index
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class EventStatus(str, enum.Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    CANCELLED = 'cancelled'
    ARCHIVED = 'archived'

class Event(Base):
    __tablename__ = 'events'

    id = Column(BigInteger, primary_key= True, index= True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    poster_url = Column(String(500), nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    status = Column(Enum(EventStatus), nullable=False, default = EventStatus.DRAFT)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())



    __table_args__ = (
        Index('idx_events_status', 'status'),
        Index('idx_events_start_datetime', 'start_datetime'),
        Index('idx_events_created_by', 'created_by'),
        Index('idx_events_status_start', 'status', 'start_datetime')
    )
