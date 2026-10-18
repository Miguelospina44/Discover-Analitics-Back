# Fase B — Puente a Discover

Estado: **diseñado y cableado en código**; smoke contra DEV queda pendiente de apuntar `.env` a la Postgres de Discover.

## Qué ya está listo

| Pieza | Ubicación |
|---|---|
| Switch `DATA_SOURCE` | [`app/core/config.py`](../app/core/config.py) |
| Attendance seed vs vista | [`app/data/attendance_repository.py`](../app/data/attendance_repository.py) |
| Sales seed vs vista | [`app/data/sales_repository.py`](../app/data/sales_repository.py) |
| Métricas v1 (eventos, tiers, ritmo, mix, horas) | [`app/data/metrics_repository.py`](../app/data/metrics_repository.py) |
| Definiciones | [`app/domain/metric_definitions.py`](../app/domain/metric_definitions.py), [`docs/metrics-dictionary.md`](metrics-dictionary.md) |
| Vistas | [`sql/views/`](../sql/views/) `001`–`011` |

## Pasos para activar (cuando toque)

1. En la Postgres de Discover (local `pary_db` o DEV `pary_db_test`):
   - `alembic upgrade head` (crea schema `analytics` de escritura).
   - Aplicar `sql/views/001`–`011` en orden. `001`/`002` son el puente de asistencia y órdenes; `003`+ usan `ticket_tiers`, `price_paid_cop` y `purchased_at` del modelo Discover.
2. `.env`:
   - `DATA_SOURCE=discover`
   - `DATABASE_URL` / `ALEMBIC_DATABASE_URL` → esa Postgres
   - `BOOTSTRAP_ACCOUNT_ID` = un `accounts.id` real con venues/tickets
3. Reiniciar API; métricas deben devolver `data_source: discover`.
4. Smoke: login → métricas con periodo donde haya redenciones → finding.

## Reglas

- No DDL sobre tablas `public` de Pary desde Analytics.
- Preferir `GRANT SELECT` solo sobre vistas `analytics.v_*` al rol de la app.
- No copiar `orders`/`tickets` a facts en producción; los facts seed son solo Fase A.
