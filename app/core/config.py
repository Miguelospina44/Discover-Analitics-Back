from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DataSource = Literal["seed", "discover"]

_DEV_JWT_SECRET = "insecure-dev-secret"
_SSL_MODES = ("sslmode=require", "sslmode=verify-ca", "sslmode=verify-full")


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

    discover_database_url: str | None = None
    discover_pool_size: int = 3
    discover_max_overflow: int = 2
    discover_pool_timeout: int = 10
    discover_require_ssl: bool = True

    jwt_secret: str = _DEV_JWT_SECRET
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

    @property
    def uses_discover_source(self) -> bool:
        return self.data_source == "discover"

    @property
    def discover_dsn(self) -> str | None:
        if not self.discover_database_url:
            return None
        stripped = self.discover_database_url.strip()
        return stripped or None

    def validate_discover_config(self) -> list[str]:
        errors: list[str] = []
        if not self.uses_discover_source:
            return errors

        dsn = self.discover_dsn
        if not dsn:
            errors.append("DISCOVER_DATABASE_URL requerido cuando DATA_SOURCE=discover")
            return errors

        if "asyncpg" not in dsn:
            errors.append("DISCOVER_DATABASE_URL debe usar driver asyncpg")
        if dsn == self.database_url.strip():
            errors.append("DISCOVER_DATABASE_URL debe ser distinta de DATABASE_URL")
        if self.discover_require_ssl and not any(mode in dsn.lower() for mode in _SSL_MODES):
            errors.append(
                "DISCOVER_REQUIRE_SSL=true requiere sslmode=require|verify-ca|verify-full"
            )
        if not 1 <= self.discover_pool_size <= 10:
            errors.append("DISCOVER_POOL_SIZE debe estar entre 1 y 10")
        if self.discover_pool_timeout < 1:
            errors.append("DISCOVER_POOL_TIMEOUT debe ser mayor que 0")
        if self.query_timeout_seconds < 1:
            errors.append("QUERY_TIMEOUT_SECONDS debe ser mayor que 0")
        return errors

    def validate_startup(self) -> list[str]:
        errors = self.validate_discover_config()
        if self.is_production:
            if self.jwt_secret == _DEV_JWT_SECRET:
                errors.append("JWT_SECRET de desarrollo no permitido en production")
            if self.uses_discover_source and not self.discover_require_ssl:
                errors.append("DISCOVER_REQUIRE_SSL debe ser true en production")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
