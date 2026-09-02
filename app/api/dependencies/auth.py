from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from app.core.config import settings
from loguru import logger

security = HTTPBearer()

class CurrentUser(BaseModel):
    id: int
    phone_number: str
    role: str
    is_active: bool

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Расшифровывает JWT-токен и возвращает данные пользователя.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )

        user_id = payload.get("sub")
        phone_number = payload.get("phone")
        role = payload.get("role", "guest")
        is_active = payload.get("is_active", True)

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        return CurrentUser(
            id=int(user_id),
            phone_number=phone_number,
            role=role,
            is_active=is_active
        )

    except JWTError as e:
        logger.warning(f"Invalid JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
