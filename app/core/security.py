import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh", "phone_verification", "service"]

# Хеш для сравнения, когда пользователь не найден: время ответа не выдаёт, существует ли номер
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        bcrypt.checkpw(password.encode(), _DUMMY_HASH.encode())
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _secret_for(token_type: TokenType) -> str:
    # access и service проверяют другие сервисы, поэтому они подписаны общим JWT_SECRET
    return settings.JWT_SECRET if token_type in ("access", "service") else settings.internal_jwt_secret


def encode_token(token_type: TokenType, subject: str, expires_in: timedelta, **claims: Any) -> tuple[str, str, datetime]:
    """Возвращает (token, jti, expires_at)."""
    now = datetime.now(UTC)
    expires_at = now + expires_in
    jti = uuid.uuid4().hex
    payload = {
        "sub": subject,
        # Event Service читает "type", Notification — "token_type": кладём оба
        "type": token_type,
        "token_type": token_type,
        "iat": now,
        "exp": expires_at,
        "jti": jti,
        **claims,
    }
    return jwt.encode(payload, _secret_for(token_type), algorithm=settings.JWT_ALGORITHM), jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _secret_for(expected_type),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from None
    if payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload
