import uuid

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    phone: str
    first_name: str | None
    last_name: str | None
    email: EmailStr | None

    model_config = {
        "from_attributes": True,
    }


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None