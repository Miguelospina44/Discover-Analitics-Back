"""DB-backed functional tests that guard core behavior.

They run against a real migrated + seeded database (see migrations 0002/0003,
which seed accounts, users, venues and facts). They self-skip when no database
is reachable (see tests/conftest.py), so `pytest` stays green without a DB.

Seed users (password ``change-me-now``):
- ``superadmin@discover.example.com`` -> role super_admin, account Demo Discover.
- ``miguel@miguelsclub.example.com``  -> role admin, account Miguel's Club.
"""

from fastapi.testclient import TestClient

SUPERADMIN_EMAIL = "superadmin@discover.example.com"
MIGUEL_EMAIL = "miguel@miguelsclub.example.com"
SEED_PASSWORD = "change-me-now"

ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"


def _login(client: TestClient, email: str, password: str = SEED_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    assert token
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_ready_reports_database_up(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_login_success_returns_token(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    assert isinstance(token, str) and token.count(".") == 2


def test_login_wrong_password_is_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SUPERADMIN_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401, response.text


def test_me_returns_the_right_account(client: TestClient) -> None:
    token = _login(client, MIGUEL_EMAIL)
    response = client.get("/api/v1/auth/me", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == MIGUEL_EMAIL
    assert body["role"] == "admin"
    assert body["account_id"] == ACCOUNT_MIGUEL
    assert body["account_name"] == "Miguel's Club"


def test_client_user_cannot_read_another_account(client: TestClient) -> None:
    """A client-scoped admin may not request another account's venues -> 403."""
    token = _login(client, MIGUEL_EMAIL)
    response = client.get(
        "/api/v1/venues",
        params={"account_id": ACCOUNT_DEMO},
        headers=_auth(token),
    )
    assert response.status_code == 403, response.text


def test_client_user_only_sees_own_venues(client: TestClient) -> None:
    token = _login(client, MIGUEL_EMAIL)
    response = client.get("/api/v1/venues", headers=_auth(token))
    assert response.status_code == 200, response.text
    venues = response.json()
    assert venues, "el usuario cliente debe ver sus propias sedes"
    assert {v["account_id"] for v in venues} == {ACCOUNT_MIGUEL}


def test_super_admin_sees_global_scope(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    response = client.get("/api/v1/venues", headers=_auth(token))
    assert response.status_code == 200, response.text
    account_ids = {v["account_id"] for v in response.json()}
    assert {ACCOUNT_DEMO, ACCOUNT_MIGUEL} <= account_ids
