import re

_DSN_RE = re.compile(r"(postgresql(?:\+\w+)?://)([^:/@]+):([^@/]+)@", re.IGNORECASE)
_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(password|secret|dsn|database_url|alembic_database_url|"
    r"discover_database_url|jwt_secret|jwt_token|access_token)\b\s*[=:]\s*\S+"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_secrets(text: str) -> str:
    """Remove credentials, DSN hosts and emails from a log or error string."""
    redacted = _DSN_RE.sub(r"\1***:***@", text)
    redacted = _SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)}=***", redacted)
    redacted = _EMAIL_RE.sub("[redacted-email]", redacted)
    return redacted


def contains_sensitive_token(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "password=",
        "postgresql://",
        "postgresql+",
        "jwt_secret",
        "discover_database_url",
        "database_url",
    )
    return any(marker in lowered for marker in markers)
