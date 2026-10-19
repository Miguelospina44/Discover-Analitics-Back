from app.core.config import Settings
from app.infra.db import (
    create_discover_session_factory,
    create_session_factory,
    discover_connect_args,
)


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_discover_factory_is_none_on_seed() -> None:
    settings = _settings(data_source="seed")
    assert create_discover_session_factory(settings) is None


def test_discover_factory_is_none_without_url() -> None:
    settings = _settings(data_source="discover", discover_database_url=None)
    assert create_discover_session_factory(settings) is None


def test_discover_connect_args_are_readonly_with_timeouts_and_ssl() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db?sslmode=require",
        discover_require_ssl=True,
        discover_pool_timeout=10,
        query_timeout_seconds=15,
    )
    args = discover_connect_args(settings)
    assert args["ssl"] is True
    assert args["timeout"] == 10
    assert args["command_timeout"] == 15
    assert args["server_settings"]["default_transaction_read_only"] == "on"
    assert args["server_settings"]["statement_timeout"] == "15000"
    assert args["server_settings"]["application_name"] == "discover-analytics-readonly"


def test_discover_factory_builds_without_connecting() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db?sslmode=require",
        discover_require_ssl=True,
        discover_pool_size=3,
    )
    factory = create_discover_session_factory(settings)
    assert factory is not None


def test_app_factory_builds_without_connecting() -> None:
    settings = _settings()
    factory = create_session_factory(settings)
    assert factory is not None
