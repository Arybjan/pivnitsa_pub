from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Index, Uuid, JSON, Integer
from sqlalchemy.sql import func
from app.core.database import Base
import enum
import uuid

class EventStatus(str, enum.Enum):
    DRAFT = 'DRAFT'
    PUBLISHED = 'PUBLISHED'
    CANCELLED = 'CANCELLED'
    FINISHED = 'FINISHED'

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            return cls.__members__.get(value.upper())

class Event(Base):
    __tablename__ = 'events'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key= True, index= True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    poster_url = Column(String(500), nullable=True)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(EventStatus), nullable=False, default = EventStatus.DRAFT)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())



    __table_args__ = (
        Index('idx_events_status', 'status'),
        Index('idx_events_start_datetime', 'start_datetime'),
        Index('idx_events_created_by', 'created_by'),
        Index('idx_events_status_start', 'status', 'start_datetime')
    )


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    routing_key = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
