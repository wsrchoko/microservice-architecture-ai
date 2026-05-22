"""Auth Service configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class AuthServiceSettings(BaseSettings):
    """Auth service specific settings."""
    
    service_name: str = "auth-service"
    service_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    database_url: str = "postgresql+asyncpg://nexus_user:nexus_secure_password_2025@localhost:5432/nexusdb"
    redis_url: str = "redis://:nexus_redis_password@localhost:6379/0"
    rabbitmq_url: str = "amqp://nexus_user:nexus_rabbit_password@localhost:5672/"
    
    jwt_secret: str = "super-secret-jwt-key-change-in-production-2025"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = AuthServiceSettings()