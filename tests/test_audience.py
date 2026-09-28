"""Fase D: pruebas de la segmentación ANÓNIMA de audiencia.

Dos capas:
- Metadata (sin DB): el modelo declara el FK account_id -> accounts RESTRICT y la
  MeasureMeta/quality existen.
- Funcionales (con DB, self-skip vía tests/conftest.py): el endpoint devuelve
  segmentos, respeta el aislamiento de tenant, los shares por dimensión suman ~1
  y —lo más importante— la respuesta NO contiene ningún dato personal (PII).
"""

from fastapi.testclient import TestClient

from app.domain.measures import (
    AUDIENCE_PROFILE,
    AudienceSegment,
    quality_for_audience,
)
from app.infra import orm

SUPERADMIN_EMAIL = "superadmin@discover.example.com"
MIGUEL_EMAIL = "miguel@miguelsclub.example.com"
SEED_PASSWORD = "change-me-now"

ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"

PERIOD = {"period_start": "2026-08-01", "period_end": "2026-08-14"}
DIMENSIONS = {"gender", "age_band", "zone", "recurrence"}

# Nombres de columna de contacto que NUNCA deben existir en la tabla anónima.
PII_FIELDS = {"name", "email", "phone", "birth_date", "first_name", "last_name"}
# Términos de PII que no deben filtrarse en el payload. Se excluye "name" a
# propósito: es un campo legítimo de metadata de la medida ("audience_profile"),
# no un nombre de persona.
PII_LEAK_TERMS = {"email", "phone", "birth_date", "first_name", "last_name"}


# --- Metadata (sin base de datos) -------------------------------------------


def test_audience_account_id_has_fk_restrict() -> None:
    fks = list(orm.FactAudienceProfile.__table__.c.account_id.foreign_keys)
    targets = {fk.target_fullname for fk in fks}
    assert "analytics.accounts.id" in targets
    for fk in fks:
        if fk.target_fullname == "analytics.accounts.id":
            assert fk.ondelete == "RESTRICT"


def test_audience_table_has_no_pii_columns() -> None:
    columns = set(orm.FactAudienceProfile.__table__.c.keys())
    assert columns == {
        "account_id",
        "night_date",
        "gender",
        "age_band",
        "zone",
        "recurrence",
        "headcount",
    }
    assert not (columns & PII_FIELDS)


def test_audience_measure_meta_exists() -> None:
    assert AUDIENCE_PROFILE.name == "audience_profile"
    assert AUDIENCE_PROFILE.title == "Tu público"


def test_audience_quality() -> None:
    assert quality_for_audience([]) == "missing"
    ok = [
        AudienceSegment("gender", "woman", 10, 0.5),
        AudienceSegment("gender", "man", 10, 0.5),
    ]
    assert quality_for_audience(ok) == "ok"
    partial = [AudienceSegment("zone", "Laureles", 0, 0.0)]
    assert quality_for_audience(partial) == "partial"


# --- Funcionales (con base de datos) ----------------------------------------


def _login(client: TestClient, email: str, password: str = SEED_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fetch(client: TestClient, token: str, params: dict) -> dict:
    response = client.get(
        "/api/v1/metrics/audience",
        params=params,
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_audience_returns_segments_for_each_dimension(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    body = _fetch(client, token, PERIOD)
    assert body["name"] == "audience_profile"
    assert body["scope"] == "global"
    dims = {segment["dimension"] for segment in body["segments"]}
    assert DIMENSIONS <= dims


def test_audience_shares_sum_to_one_per_dimension(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    body = _fetch(client, token, PERIOD)
    for dimension in DIMENSIONS:
        shares = [s["share"] for s in body["segments"] if s["dimension"] == dimension]
        assert shares, f"faltan segmentos para {dimension}"
        assert abs(sum(shares) - 1.0) < 1e-6


def test_audience_has_no_pii(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    response = client.get("/api/v1/metrics/audience", params=PERIOD, headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    # La respuesta solo trae agregados: cada segmento tiene exactamente estos campos.
    for segment in body["segments"]:
        assert set(segment.keys()) == {"dimension", "key", "headcount", "share"}
    # Y ningún término de contacto debe filtrarse en todo el payload.
    raw = response.text.lower()
    for term in PII_LEAK_TERMS:
        assert term not in raw


def test_audience_tenant_isolation_client_restricted(client: TestClient) -> None:
    """Un admin de cliente no puede pedir la audiencia de otra cuenta -> 403."""
    token = _login(client, MIGUEL_EMAIL)
    response = client.get(
        "/api/v1/metrics/audience",
        params={**PERIOD, "account_id": ACCOUNT_DEMO},
        headers=_auth(token),
    )
    assert response.status_code == 403, response.text


def test_audience_client_sees_own_scope(client: TestClient) -> None:
    token = _login(client, MIGUEL_EMAIL)
    body = _fetch(client, token, PERIOD)
    assert body["scope"] == "account"
    assert body["segments"], "el cliente debe ver su propia audiencia"


def test_audience_super_admin_can_scope_to_account(client: TestClient) -> None:
    token = _login(client, SUPERADMIN_EMAIL)
    body = _fetch(client, token, {**PERIOD, "account_id": ACCOUNT_MIGUEL})
    assert body["scope"] == "account"
    dims = {segment["dimension"] for segment in body["segments"]}
    assert DIMENSIONS <= dims
