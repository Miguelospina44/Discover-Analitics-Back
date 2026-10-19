from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import register_error_handlers


def test_sqlalchemy_errors_are_generic() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise SQLAlchemyError(
            "connection to postgresql://owner:super-secret@db-prod:5432/pary_db failed"
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "Error al procesar la solicitud. Intenta de nuevo más tarde."
    assert "super-secret" not in detail
    assert "db-prod" not in detail
    assert "pary_db" not in detail
    assert "postgresql" not in detail.lower()


def test_unexpected_errors_are_generic() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("jwt_secret=real-token host=db-prod")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "Error interno del servidor"
    assert "jwt_secret" not in detail
    assert "db-prod" not in detail
