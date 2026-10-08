"""DB-backed tests for the public lead-capture flow.

Self-skip when no database is reachable (see tests/conftest.py), so `pytest`
stays green without a DB. Leads carry PII and live in a separate table from the
anonymized analytics facts.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

VALID_PAYLOAD = {
    "name": "Prueba QA",
    "phone": "+57 300 000 0000",
    "birth_date": "1998-05-20",
    "email": "prueba.qa@example.com",
}


def _count_leads_by_email(email: str) -> int:
    sync_url = make_url(get_settings().database_url).set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM analytics.leads WHERE email = :email"),
                {"email": email},
            )
            return int(result.scalar_one())
    finally:
        engine.dispose()


def test_create_lead_returns_201_and_redirect_url(client: TestClient) -> None:
    response = client.post("/api/v1/leads", json=VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["redirect_url"] == "https://discover-co.com"
    assert body["id"]


def test_create_lead_persists_row(client: TestClient) -> None:
    email = "persisted.lead@example.com"
    payload = {**VALID_PAYLOAD, "email": email}
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201, response.text
    assert _count_leads_by_email(email) >= 1


def test_create_lead_invalid_email_is_422(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 422, response.text


def test_create_lead_is_public_no_auth_header(client: TestClient) -> None:
    """No Authorization header is required for the public capture flow."""
    response = client.post("/api/v1/leads", json=VALID_PAYLOAD)
    assert response.status_code == 201, response.text
