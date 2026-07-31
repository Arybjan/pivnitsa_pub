from pydantic_settings import BaseSettings
from typing import Union, List


class Settings(BaseSettings):
    app_name: str = "Pivnitsa Pub"
    debug: bool = True
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/pivnitsa_pub"
    )
    cors_origins: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    static_dir: str = "static"
    image_dir: str = "static/images"

    class Config:
        env_file = ".env"


settings = Settings()
