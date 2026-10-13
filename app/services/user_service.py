from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.core.security import hash_password, verify_password
from app.models import Profile, User
from app.schemas.user import AdminUserUpdateRequest, PasswordChangeRequest, UserUpdateRequest
from app.services.errors import ServiceError
from app.services.session_store import SessionStore

_PROFILE_FIELDS = ("first_name", "last_name", "avatar_url")


class UserService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.sessions = SessionStore(redis)

    async def get(self, user_id: int) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise ServiceError(404, "User not found")
        return user

    async def get_active(self, user_id: int) -> User:
        user = await self.db.get(User, user_id)
        if user is None or not user.is_active:
            raise ServiceError(401, "User not found or deactivated")
        return user

    async def update_profile(self, user: User, data: UserUpdateRequest) -> User:
        changes = data.model_dump(exclude_unset=True)
        if "email" in changes:
            user.email = changes.pop("email")
        if user.profile is None:
            user.profile = Profile()
        for field in _PROFILE_FIELDS:
            if field in changes:
                setattr(user.profile, field, changes[field])
        await self._commit(user)
        return user

    async def change_password(self, user: User, data: PasswordChangeRequest) -> None:
        if not verify_password(data.current_password, user.password_hash):
            raise ServiceError(400, "Current password is incorrect")
        user.password_hash = hash_password(data.new_password)
        await self.db.commit()
        await self.sessions.revoke_all(user.id)

    async def deactivate(self, user: User) -> None:
        # Мягкое удаление: брони и платежи в других сервисах ссылаются на user_id
        user.is_active = False
        await self.db.commit()
        await self.sessions.revoke_all(user.id)

    async def list(self, *, limit: int, offset: int, role: Role | None, is_active: bool | None, phone: str | None):
        query = select(User)
        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if phone:
            query = query.where(User.phone.contains(phone))
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        users = (await self.db.scalars(query.order_by(User.id).limit(limit).offset(offset))).all()
        return users, total

    async def admin_update(self, actor_id: int, actor_role: str, user_id: int, data: AdminUserUpdateRequest) -> User:
        if user_id == actor_id:
            raise ServiceError(400, "Use /users/me to change your own account")
        user = await self.get(user_id)
        # Менять роли и трогать других админов может только владелец
        if actor_role != Role.OWNER and (data.role is not None or user.role != Role.USER):
            raise ServiceError(403, "Only owner can manage roles and administrators")
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        await self.db.commit()
        await self.db.refresh(user)
        # Старые токены несут прежнюю роль/статус — пусть пользователь войдёт заново
        await self.sessions.revoke_all(user.id)
        return user

    async def _commit(self, user: User) -> None:
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ServiceError(409, "Email is already in use") from None
        await self.db.refresh(user, ["profile", "updated_at"])
