"""Shared fixtures for DB-backed functional tests.

These fixtures let the functional suite run for real in CI (where a Postgres
service is provided and migrated) while self-skipping for developers who run
`pytest` without a reachable database. The no-DB unit tests are unaffected.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.core.config import get_settings


def _sync_url() -> URL:
    """Return a synchronous (psycopg) URL derived from DATABASE_URL.

    A URL object is returned (not a string) so the real password reaches the
    driver; ``str(URL)`` masks the password as ``***``.
    """
    url = make_url(get_settings().database_url)
    return url.set(drivername="postgresql+psycopg")


@pytest.fixture(scope="session")
def require_db() -> None:
    """Skip the test when no database is reachable at DATABASE_URL."""
    try:
        engine = create_engine(_sync_url(), connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 - any connection failure means skip
        pytest.skip(f"Sin base de datos disponible para tests funcionales: {exc}")


@pytest.fixture
def client(require_db: None) -> Iterator[TestClient]:
    """FastAPI TestClient bound to the migrated+seeded test database."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
