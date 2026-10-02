from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise unauthorized from None
    token_type = payload.get("token_type", payload.get("type"))
    subject = payload.get("sub")
    if (
        token_type != "access"
        or not isinstance(subject, str)
        or not 0 < len(subject) <= 128
    ):
        raise unauthorized
    if payload.get("is_active", True) is not True:
        raise HTTPException(status_code=403, detail="Account is inactive")
    permissions = payload.get("permissions", [])
    can_write = isinstance(permissions, list) and "venue:write" in permissions
    if payload.get("role") not in ("admin", "owner") and not can_write:
        raise HTTPException(
            status_code=403, detail="Venue management permission required"
        )
    return subject
