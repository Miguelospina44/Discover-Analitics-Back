# Discover Analytics Back

API de analítica y consultoría. **Fase A usa Postgres aislada `discover_analytics`** (sin Discover/Pary).

Remote: https://github.com/Miguelospina44/Discover-Analitics-Back.git

## Arranque local (Fase A — seed)

1. Tener Postgres local. Crear DB si no existe:

```sql
CREATE DATABASE discover_analytics;
```

2. Configurar entorno:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Ajusta usuario/password en `.env`. Debe quedar:

- `DATABASE_URL=.../discover_analytics`
- `DATA_SOURCE=seed`
- `BOOTSTRAP_ACCOUNT_ID=a1111111-1111-4111-8111-111111111111`

3. Migrar (schema + facts seed):

```bash
alembic upgrade head
```

4. Arrancar:

```bash
uvicorn app.main:app --reload --port 8000
```

- Health: `GET /health`
- Ready: `GET /ready`
- Docs: http://localhost:8000/docs
- Login: `POST /api/v1/auth/login` con `analytics.admin@example.com` / `change-me-now`

Re-seed opcional: `python -m scripts.seed_dev`

## Smoke checklist

1. `GET /health` → 200  
2. `GET /ready` → database up  
3. `POST /api/v1/auth/login` → JWT  
4. Sin token a `/metrics/...` → 401  
5. `POST /api/v1/engagements`  
6. `GET /api/v1/metrics/nightly-attendance?period_start=2026-08-01&period_end=2026-08-14` → points > 0, `data_source=seed`  
7. `GET /api/v1/metrics/sales-by-night?...` → points > 0  
8. `POST /api/v1/findings` + `POST /api/v1/recommendations`

## Visualizar el ER

No hay plugin Cursor de Postgres ER. Usa:

- [`docs/schema.dbml`](docs/schema.dbml) en [dbdiagram.io](https://dbdiagram.io)
- DBeaver conectado a `discover_analytics`
- Diagrama Mermaid en [`docs/data-model.md`](docs/data-model.md)

## Fase B (Discover)

Ver [`docs/phase-b-discover.md`](docs/phase-b-discover.md). Cambiar `DATA_SOURCE=discover` y aplicar vistas en `sql/views/`.

## Documentación

- [docs/architecture.md](docs/architecture.md)
- [docs/data-model.md](docs/data-model.md)
- [docs/adr/](docs/adr/)
- [AGENTS.md](AGENTS.md)
