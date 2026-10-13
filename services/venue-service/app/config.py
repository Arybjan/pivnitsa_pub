from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./venue.db"
    jwt_secret_key: SecretStr = Field(
        min_length=32,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"),
    )
    # Адреса фронтенда через запятую; "*" — разрешить всем (для разработки)
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
