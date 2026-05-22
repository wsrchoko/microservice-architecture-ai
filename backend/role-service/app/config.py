"""Role Service configuration."""
from pydantic_settings import BaseSettings
class RoleServiceSettings(BaseSettings):
    service_name: str = "role-service"
    service_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://nexus_user:nexus_secure_password_2025@localhost:5432/nexusdb"
    rabbitmq_url: str = "amqp://nexus_user:nexus_rabbit_password@localhost:5672/"
    jwt_secret: str = "super-secret-jwt-key-change-in-production-2025"
    auth_service_url: str = "http://localhost:8001"
    class Config: env_file = ".env"; extra = "ignore"
settings = RoleServiceSettings()