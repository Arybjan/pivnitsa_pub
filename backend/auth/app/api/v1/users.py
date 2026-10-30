from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import AdminUser, CurrentUser, Users
from app.core.roles import Role
from app.schemas.user import (
    AdminUserUpdateRequest,
    PasswordChangeRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["Users"])

UserId = Annotated[int, Path(gt=0, le=2**63 - 1)]


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser):
    return UserResponse.from_user(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(data: UserUpdateRequest, user: CurrentUser, users: Users):
    return UserResponse.from_user(await users.update_profile(user, data))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: PasswordChangeRequest, user: CurrentUser, users: Users):
    """Смена пароля. Завершает все сессии — нужно войти заново."""
    await users.change_password(user, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, users: Users):
    """Удаление учётной записи (US-07): аккаунт деактивируется, все сессии завершаются."""
    await users.deactivate(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    _: AdminUser,
    users: Users,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    role: Role | None = None,
    is_active: bool | None = None,
    phone: Annotated[str | None, Query(max_length=20)] = None,
):
    items, total = await users.list(limit=limit, offset=offset, role=role, is_active=is_active, phone=phone)
    return UserListResponse(items=[UserResponse.from_user(u) for u in items], total=total, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UserId, _: AdminUser, users: Users):
    return UserResponse.from_user(await users.get(user_id))


@router.patch("/{user_id}", response_model=UserResponse)
async def admin_update_user(user_id: UserId, data: AdminUserUpdateRequest, admin: AdminUser, users: Users):
    """Блокировка/разблокировка пользователя (admin) и смена роли (только owner)."""
    return UserResponse.from_user(await users.admin_update(admin.id, admin.role, user_id, data))
