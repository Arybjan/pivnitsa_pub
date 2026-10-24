import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

load_dotenv()
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


ADMIN_ROLES = ("admin", "owner")


def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            # Срок действия проверяется всегда, а токен без exp не принимаем вовсе.
            options={"require_exp": True},
        )

        user_id = payload.get("sub")

        # Тем же секретом Auth подписывает и служебные токены:
        # пользователем считаем только владельца access token
        token_type = payload.get("token_type", payload.get("type"))

        if user_id is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        int(user_id)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("is_active", True) is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return payload


def get_current_user(
    payload: dict = Depends(get_token_payload),
) -> int:

    return int(payload["sub"])


def require_admin(
    payload: dict = Depends(get_token_payload),
) -> int:

    if payload.get("role") not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    return int(payload["sub"])