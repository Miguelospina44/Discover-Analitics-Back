from fastapi.testclient import TestClient

from app.main import app


def test_health_does_not_require_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_fail_closed_without_token() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/metrics/nightly-attendance",
            params={"period_start": "2026-08-01", "period_end": "2026-08-31"},
        )
    assert response.status_code == 401
