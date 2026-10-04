from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Payment Service"
    PORT: int = 8004
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "events_exchange"

    STRIPE_SECRET_KEY: str = "sk_test_placeholder_for_dev"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_placeholder_for_dev"
    STRIPE_WEBHOOK_SECRET: str = "whsec_placeholder_for_dev"
    PAYMENT_GATEWAY_ENV: str = "sandbox"

    JWT_SECRET: str = "supersecretjwtkey_pivnitsa_pub_2026"
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
