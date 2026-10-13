from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Payment Service"
    PORT: int = 8004
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "events_exchange"

    # Сумма считается на сервере: депозит за каждого гостя брони.
    # Клиент больше не передаёт amount — иначе стол можно оплатить за 0.01.
    DEPOSIT_PER_GUEST: Decimal = Decimal("1000.00")
    CURRENCY: str = "KGS"

    # Payment Service читает бронь из Booking Service, чтобы проверить владельца,
    # статус PENDING_PAYMENT и число гостей.
    BOOKING_SERVICE_URL: str = "http://booking-service:8000"
    BOOKING_SERVICE_TIMEOUT: float = 5.0

    STRIPE_SECRET_KEY: str = "sk_test_placeholder_for_dev"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_placeholder_for_dev"
    STRIPE_WEBHOOK_SECRET: str = "whsec_placeholder_for_dev"
    PAYMENT_GATEWAY_ENV: str = "sandbox"

    # Без значения по умолчанию: секрет общий для всех сервисов и задаётся только через окружение.
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Фоновые воркеры
    OUTBOX_POLL_SECONDS: float = 2.0
    REFUND_RETRY_SECONDS: float = 30.0
    RABBITMQ_RETRY_SECONDS: float = 5.0

    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
