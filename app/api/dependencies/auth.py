from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError
from app.core.config import settings

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: UUID
    phone_number: str | None = None
    role: str
    is_active: bool


def decode_user(credentials: HTTPAuthorizationCredentials) -> CurrentUser:
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True, "require_sub": True},
        )
        token_type = payload.get("type", payload.get("token_type"))
        if token_type != "access" or any(
            payload[key] != "access" for key in ("type", "token_type") if key in payload
        ):
            raise ValueError("Access token required")
        if payload.get("is_active") is not True:
            raise HTTPException(status_code=403, detail="Inactive user")
        return CurrentUser(
            id=payload["sub"], phone_number=payload.get("phone"),
            role=payload.get("role", "guest"), is_active=True,
        )
    except (JWTError, ValueError, ValidationError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    return decode_user(credentials) if credentials else None


async def get_current_user(
    user: CurrentUser | None = Depends(get_optional_user),
) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return user
