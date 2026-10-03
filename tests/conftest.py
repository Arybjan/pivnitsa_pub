import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.main import app
from app.core.config import settings
from app.core.security import AuthenticatedUser, get_current_user, require_service_or_admin
from app.models.notification import Notification, NotificationSettings

test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def clean_database():
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.execute(delete(NotificationSettings))
        await session.commit()
    yield
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.execute(delete(NotificationSettings))
        await session.commit()


@pytest.fixture(autouse=True)
def _default_test_auth_override():
    admin_user = AuthenticatedUser(user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_service_or_admin] = lambda: admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_service_or_admin, None)
