"""Shared configuration module for all microservices."""

from typing import Optional
from pydantic_settings import BaseSettings


class ServiceSettings(BaseSettings):
    """Base settings for all microservices."""
    
    # Service metadata
    service_name: str = "unknown-service"
    service_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database URLs
    database_url: Optional[str] = None
    mongodb_url: Optional[str] = None
    redis_url: Optional[str] = None
    rabbitmq_url: Optional[str] = "amqp://guest:guest@localhost:5672/"
    
    # JWT Configuration
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # External service URLs
    auth_service_url: Optional[str] = None
    user_service_url: Optional[str] = None
    role_service_url: Optional[str] = None
    
    # AI Service
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    qdrant_url: Optional[str] = "http://localhost:6333"
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = ServiceSettings()