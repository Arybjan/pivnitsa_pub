from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    NIKITA_API_URL: str = "https://smspro.nikita.kg/api/message"
    NIKITA_LOGIN: str = ""
    NIKITA_PASSWORD: str = ""
    NIKITA_SENDER: str = "TEST"
    NIKITA_TEST_MODE: bool = True
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    EVENT_NOTIFICATION_DEFAULT_USER_ID: int | None = None
    JWT_SECRET: str = "supersecretkey_for_nightclub_pivnitsa_app_jwt_signing_secret_2026"
    JWT_ALGORITHM: str = "HS256"
    # Часовой пояс заведения: время в текстах уведомлений
    VENUE_TIMEZONE: str = "Asia/Bishkek"
    # Venue Service для номера стола в уведомлениях о бронях; пусто - показываем id стола
    VENUE_SERVICE_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()