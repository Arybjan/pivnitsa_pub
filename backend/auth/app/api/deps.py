from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.roles import ADMIN_ROLES
from app.core.security import TokenError, decode_token
from app.models import User
from app.services.auth_service import AuthService
from app.services.errors import ServiceError
from app.services.user_service import UserService

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]


def get_auth_service(db: DbSession, redis: RedisClient) -> AuthService:
    return AuthService(db, redis)


def get_user_service(db: DbSession, redis: RedisClient) -> UserService:
    return UserService(db, redis)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    users: Annotated[UserService, Depends(get_user_service)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = int(payload["sub"])
    except (TokenError, ValueError):
        raise unauthorized from None
    # Сам Auth Service всегда сверяется с БД: деактивация и смена роли действуют сразу
    try:
        return await users.get_active(user_id)
    except ServiceError:
        raise unauthorized from None


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
Auth = Annotated[AuthService, Depends(get_auth_service)]
Users = Annotated[UserService, Depends(get_user_service)]
