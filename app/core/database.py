from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session