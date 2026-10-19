from app.core.redact import contains_sensitive_token, redact_secrets


def test_redact_dsn_password() -> None:
    raw = "failed postgresql+asyncpg://analytics_ro:hunter2@db.internal:5432/pary_db"
    redacted = redact_secrets(raw)
    assert "hunter2" not in redacted
    assert "analytics_ro" not in redacted
    assert "***:***@" in redacted


def test_redact_assignment_and_email() -> None:
    raw = "JWT_SECRET=abc123xyz DISCOVER_DATABASE_URL=foo admin@venue.com"
    redacted = redact_secrets(raw)
    assert "abc123xyz" not in redacted
    assert "admin@venue.com" not in redacted
    assert "[redacted-email]" in redacted


def test_contains_sensitive_token() -> None:
    assert contains_sensitive_token("postgresql://x")
    assert contains_sensitive_token("DATABASE_URL=x")
    assert not contains_sensitive_token("Error de base de datos: OperationalError")
