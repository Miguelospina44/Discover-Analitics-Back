from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "discover-analytics-api"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3001"

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/pary_db"
    alembic_database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/pary_db"

    jwt_secret: str = "insecure-dev-secret"
    jwt_expires_minutes: int = 480
    jwt_algorithm: str = "HS256"

    bootstrap_admin_email: str = "analytics.admin@localhost"
    bootstrap_admin_password: str = "change-me-now"
    bootstrap_account_id: str = ""

    query_timeout_seconds: int = 15
    cache_ttl_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
