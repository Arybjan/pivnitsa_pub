from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    NIKITA_API_URL: str = "https://smspro.nikita.kg/api/message"
    NIKITA_LOGIN: str = ""
    NIKITA_PASSWORD: str = ""
    NIKITA_SENDER: str = "TEST"
    NIKITA_TEST_MODE: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()