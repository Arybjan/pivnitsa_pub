from posix import environ

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    service_name: str = "event-service"
    service_port: int = 8001
    environment: str = 'development'
    log_level: str = 'INFO'

    #Datbase
    database_url: str

    #Redis
    redis_url: str

    #RobbitMQ
    rabbitmq_url: str

    #JWT
    jwt_secret: str
    jwt_algorithm: str = 'HS256'
    #Extermal Services
    auth_service_url: str

    #Cache TTL (seconds)
    event_cache_ttl: int = 300 #5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
