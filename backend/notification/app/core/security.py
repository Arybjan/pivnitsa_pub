from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    def __init__(self, user_id: int, role: str = "user", permissions: list[str] | None = None):
        self.user_id = user_id
        self.role = role
        self.permissions = permissions or []

    @property
    def is_admin_or_service(self) -> bool:
        return self.role in ("admin", "service", "owner") or "notification:write" in self.permissions


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise unauthorized from None

    token_type = payload.get("token_type", payload.get("type"))
    if token_type != "access":
        raise unauthorized

    if payload.get("is_active", True) is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    subject = payload.get("sub")
    try:
        user_id = int(subject)
        if user_id <= 0:
            raise unauthorized
    except (ValueError, TypeError):
        raise unauthorized

    return AuthenticatedUser(
        user_id=user_id,
        role=payload.get("role", "user"),
        permissions=payload.get("permissions", [])
    )


def require_service_or_admin(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if not current_user.is_admin_or_service:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service or admin permission required")
    return current_user
