from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import Role
from app.schemas.base import Password, StrictModel


class UserResponse(BaseModel):
    id: int
    phone: str
    email: EmailStr | None
    role: Role
    is_active: bool
    first_name: str | None
    last_name: str | None
    avatar_url: str | None
    created_at: datetime

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        profile = user.profile
        return cls(
            id=user.id,
            phone=user.phone,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            first_name=profile.first_name if profile else None,
            last_name=profile.last_name if profile else None,
            avatar_url=profile.avatar_url if profile else None,
            created_at=user.created_at,
        )


class UserUpdateRequest(StrictModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    avatar_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://\S+$")


class PasswordChangeRequest(StrictModel):
    current_password: str = Field(max_length=72)
    new_password: Password


class AdminUserUpdateRequest(StrictModel):
    role: Role | None = None
    is_active: bool | None = None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
