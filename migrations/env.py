import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.core.database import Base
from app.models.events import Event, EventOutbox


def configure(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(configure)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(migrate())
