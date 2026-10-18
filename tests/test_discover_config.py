from app.core.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_seed_source_does_not_require_discover_url() -> None:
    settings = _settings(data_source="seed", discover_database_url=None)
    assert settings.validate_discover_config() == []
    assert settings.validate_startup() == []


def test_discover_source_requires_discover_url() -> None:
    settings = _settings(data_source="discover", discover_database_url=None)
    errors = settings.validate_discover_config()
    assert errors == ["DISCOVER_DATABASE_URL requerido cuando DATA_SOURCE=discover"]


def test_blank_discover_url_is_treated_as_missing() -> None:
    settings = _settings(data_source="discover", discover_database_url="   ")
    errors = settings.validate_discover_config()
    assert errors == ["DISCOVER_DATABASE_URL requerido cuando DATA_SOURCE=discover"]


def test_discover_url_must_use_asyncpg() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql://user:pass@127.0.0.1:5432/db?sslmode=require",
    )
    errors = settings.validate_discover_config()
    assert any("asyncpg" in err for err in errors)


def test_discover_require_ssl_needs_sslmode_in_url() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db",
        discover_require_ssl=True,
    )
    errors = settings.validate_discover_config()
    assert any("sslmode" in err for err in errors)


def test_valid_discover_config_with_ssl() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db?sslmode=require",
        discover_require_ssl=True,
    )
    assert settings.validate_discover_config() == []


def test_valid_discover_config_without_ssl_requirement() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db",
        discover_require_ssl=False,
    )
    assert settings.validate_discover_config() == []


def test_discover_url_must_differ_from_app_database() -> None:
    shared = "postgresql+asyncpg://user:pass@127.0.0.1:5432/same?sslmode=require"
    settings = _settings(
        data_source="discover",
        database_url=shared,
        discover_database_url=shared,
        discover_require_ssl=True,
    )
    errors = settings.validate_discover_config()
    assert any("distinta de DATABASE_URL" in err for err in errors)


def test_validation_errors_do_not_include_dsn_or_password() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql://owner:super-secret@db-internal:5432/pary_db",
    )
    blob = " ".join(settings.validate_startup())
    assert "super-secret" not in blob
    assert "db-internal" not in blob
    assert "pary_db" not in blob
    assert "owner" not in blob


def test_production_rejects_dev_jwt_secret() -> None:
    settings = _settings(app_env="production", jwt_secret="insecure-dev-secret")
    errors = settings.validate_startup()
    assert any("JWT_SECRET" in err for err in errors)
    assert "insecure-dev-secret" not in " ".join(errors)


def test_production_requires_discover_ssl() -> None:
    settings = _settings(
        app_env="production",
        jwt_secret="a-long-random-production-secret",
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db",
        discover_require_ssl=False,
    )
    errors = settings.validate_startup()
    assert any("DISCOVER_REQUIRE_SSL" in err for err in errors)


def test_uses_seed_facts_property() -> None:
    settings = _settings(data_source="seed")
    assert settings.uses_seed_facts is True
    assert settings.uses_discover_source is False


def test_uses_discover_source_property() -> None:
    settings = _settings(
        data_source="discover",
        discover_database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db",
        discover_require_ssl=False,
    )
    assert settings.uses_seed_facts is False
    assert settings.uses_discover_source is True


def test_discover_pool_defaults() -> None:
    settings = _settings()
    assert settings.discover_pool_size == 3
    assert settings.discover_max_overflow == 2
    assert settings.discover_pool_timeout == 10
    assert settings.discover_require_ssl is True
    assert settings.default_plan == "growth"
    assert settings.default_tenant_kind == "venue"


def test_invalid_default_plan_fails_startup() -> None:
    settings = _settings(default_plan="unlimited")
    errors = settings.validate_startup()
    assert any("DEFAULT_PLAN" in err for err in errors)


def test_invalid_default_tenant_kind_fails_startup() -> None:
    settings = _settings(default_tenant_kind="franchise")
    errors = settings.validate_startup()
    assert any("DEFAULT_TENANT_KIND" in err for err in errors)
