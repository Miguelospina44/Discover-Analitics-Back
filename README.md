# Discover Analytics Back

API de la aplicación de analítica y consultoría de Discover. **No es Pary** y **no es la plataforma FUA**.

Remote: https://github.com/Miguelospina44/Discover-Analitics-Back.git

## Qué hace

Trata datos operativos de Discover (misma Postgres) y metadatos de un estudio de consultoría: contexto, diagnóstico, hallazgos y recomendaciones.

El recaudo NFC y la venta de covers siguen en Discover.

## Arranque local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Ajusta `DATABASE_URL` / `ALEMBIC_DATABASE_URL` al Postgres de Discover (`pary_db` local o DEV). Pon un `BOOTSTRAP_ACCOUNT_ID` UUID de un `accounts.id` real.

```bash
alembic upgrade head
psql %DATABASE% -f sql/views/001_v_nightly_attendance.sql
uvicorn app.main:app --reload --port 8000
```

- Health: `GET /health`
- Docs: `http://localhost:8000/docs`
- Login: `POST /api/v1/auth/login`

## Contrato principal (`/api/v1`)

| Método | Ruta | Notas |
|---|---|---|
| POST | `/auth/login` | JWT propio |
| GET/POST | `/engagements` | Estudios; filtro por `account_id` del token |
| GET | `/metrics/nightly-attendance` | Vista `analytics.v_nightly_attendance` |
| GET/POST | `/findings` | Hallazgos del estudio |
| POST | `/recommendations` | Acción que pide decisión |

Autorización fail-closed. El rol no se toma del body.

## Documentación

- [docs/architecture.md](docs/architecture.md)
- [docs/data-model.md](docs/data-model.md)
- [docs/adr/](docs/adr/)
- [AGENTS.md](AGENTS.md)

## Infra

Un contenedor (`Dockerfile` / `docker-compose.yml`). Sin warehouse, sin agentes, sin loaders. CI en `.github/workflows/ci.yml`.
