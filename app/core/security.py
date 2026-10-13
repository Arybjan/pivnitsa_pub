from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

ADMIN_ROLES = ("admin", "owner")

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str
    # Исходный токен — пробрасывается в Booking Service при проверке брони
    token: str

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES


def decode_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            # Токен без exp не принимаем вовсе — как в Booking Service
            options={"require": ["exp", "sub"]},
        )
        return CurrentUser(
            id=int(payload["sub"]),
            role=str(payload.get("role", "guest")),
            token=token,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> CurrentUser | None:
    if credentials is None:
        return None
    return decode_token(credentials.credentials)


def get_current_user(user: CurrentUser | None = Depends(get_optional_user)) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
