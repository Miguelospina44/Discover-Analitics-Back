from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DataSource = Literal["seed", "discover"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "discover-analytics-api"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3001"
    data_source: DataSource = "seed"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/discover_analytics"
    )
    alembic_database_url: str = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/discover_analytics"
    )

    jwt_secret: str = "insecure-dev-secret"
    jwt_expires_minutes: int = 480
    jwt_algorithm: str = "HS256"

    bootstrap_admin_email: str = "analytics.admin@example.com"
    bootstrap_admin_password: str = "change-me-now"
    bootstrap_account_id: str = "a1111111-1111-4111-8111-111111111111"

    query_timeout_seconds: int = 15
    cache_ttl_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def uses_seed_facts(self) -> bool:
        return self.data_source == "seed"


@lru_cache
def get_settings() -> Settings:
    return Settings()
