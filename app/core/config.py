from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    NIKITA_API_URL: str = "https://smspro.nikita.kg/api/message"
    NIKITA_LOGIN: str = ""
    NIKITA_PASSWORD: str = ""
    NIKITA_SENDER: str = "TEST"
    NIKITA_TEST_MODE: bool = True
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    EVENT_NOTIFICATION_DEFAULT_USER_ID: int = 1

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()