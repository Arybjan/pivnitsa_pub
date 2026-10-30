import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

load_dotenv()
# auto_error=False: без заголовка отвечаем 401, а не 403 как HTTPBearer по умолчанию
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


ADMIN_ROLES = ("admin", "owner")


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Проверенный access token. Пользователь определяется только по его sub."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            # Срок действия проверяется всегда, а токен без exp не принимаем вовсе.
            options={"require_exp": True},
        )
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise unauthorized

    if user_id <= 0:
        raise unauthorized

    # Auth кладёт тип в оба поля; refresh и service-токены здесь не принимаем
    if payload.get("token_type", payload.get("type")) != "access":
        raise unauthorized

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