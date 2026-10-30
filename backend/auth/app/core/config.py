import hashlib
import hmac
from functools import cached_property
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Pivnitsa Auth Service"
    ENVIRONMENT: Literal["dev", "test", "production"] = "dev"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # Общий секрет с Booking / Payment / Event / Notification — ими подписывается access-токен
    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 10

    # OTP-коды
    OTP_LENGTH: int = 6
    OTP_TTL_SECONDS: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5
    OTP_MAX_SENDS_PER_HOUR: int = 5
    # Только для разработки: код возвращается в ответе /otp/send (в production игнорируется)
    OTP_EXPOSE_IN_RESPONSE: bool = False

    # Защита от перебора пароля
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_SECONDS: int = 900

    # Отправка SMS: console — код пишется в лог, notification — через Notification Service
    SMS_PROVIDER: Literal["console", "notification"] = "console"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8000"
    # sub служебного токена для Notification Service (должен быть положительным int)
    SERVICE_TOKEN_SUBJECT: int = 1

    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @cached_property
    def internal_jwt_secret(self) -> str:
        """Секрет для refresh- и verification-токенов.

        Выводится из JWT_SECRET, но отличается от него — поэтому остальные сервисы
        (у которых есть только JWT_SECRET) не примут refresh-токен вместо access-токена.
        """
        return hmac.new(self.JWT_SECRET.encode(), b"pivnitsa-auth-internal", hashlib.sha256).hexdigest()

    @property
    def otp_exposed(self) -> bool:
        return self.OTP_EXPOSE_IN_RESPONSE and self.ENVIRONMENT != "production"


settings = Settings()
