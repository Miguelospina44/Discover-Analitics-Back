# Fase B — Puente a Discover

Estado: **diseñado y cableado en código**; smoke contra DEV queda pendiente de apuntar `.env` a la Postgres de Discover.

## Qué ya está listo

| Pieza | Ubicación |
|---|---|
| Switch `DATA_SOURCE` | [`app/core/config.py`](../app/core/config.py) |
| Attendance seed vs vista | [`app/data/attendance_repository.py`](../app/data/attendance_repository.py) |
| Sales seed vs vista | [`app/data/sales_repository.py`](../app/data/sales_repository.py) |
| Vista asistencia | [`sql/views/001_v_nightly_attendance.sql`](../sql/views/001_v_nightly_attendance.sql) |
| Vista ventas | [`sql/views/002_v_sales_by_night.sql`](../sql/views/002_v_sales_by_night.sql) |

## Pasos para activar (cuando toque)

1. En la Postgres de Discover (local `pary_db` o DEV `pary_db_test`):
   - `alembic upgrade head` (crea schema `analytics` de escritura).
   - Aplicar `sql/views/001_*.sql` y `002_*.sql`.
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
