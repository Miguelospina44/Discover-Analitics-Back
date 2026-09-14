# Fase B — Puente a Discover

Estado: **cableado en código y validado end-to-end contra una Postgres MOCK de Discover**
(ver "Validación mecánica" abajo). El puente contra la Postgres **real** de Discover queda
**bloqueado** hasta tener credenciales reales (ver "Bloqueo").

## Qué ya está listo

| Pieza | Ubicación |
|---|---|
| Switch `DATA_SOURCE` (`seed` \| `discover`) | [`app/core/config.py`](../app/core/config.py) |
| Attendance seed vs vista | [`app/data/attendance_repository.py`](../app/data/attendance_repository.py) |
| Sales seed vs vista | [`app/data/sales_repository.py`](../app/data/sales_repository.py) |
| Benchmarks gremiales seed vs vista | [`app/data/benchmark_repository.py`](../app/data/benchmark_repository.py) |
| Vista asistencia | [`sql/views/001_v_nightly_attendance.sql`](../sql/views/001_v_nightly_attendance.sql) |
| Vista ventas | [`sql/views/002_v_sales_by_night.sql`](../sql/views/002_v_sales_by_night.sql) |
| MOCK de tablas `public` de Discover (solo pruebas) | [`sql/mock/001_discover_mock.sql`](../sql/mock/001_discover_mock.sql) |

## Pasos para activar (verificados contra mock)

1. En la Postgres de Discover (una sola base; escrituras solo en schema `analytics`):
   - `alembic upgrade head` → crea el schema de escritura `analytics`
     (auth/consulting/facts + `accounts` + FKs/CHECK de integridad 0006).
   - Aplicar las vistas de solo lectura sobre `public`:
     `psql "$DB" -f sql/views/001_v_nightly_attendance.sql`
     `psql "$DB" -f sql/views/002_v_sales_by_night.sql`
   - Recomendado: `GRANT SELECT` solo sobre `analytics.v_*` al rol de la app.
2. Variables de entorno / `.env`:
   - `DATA_SOURCE=discover`
   - `DATABASE_URL` (asyncpg) y `ALEMBIC_DATABASE_URL` (psycopg) → esa Postgres de Discover
   - `BOOTSTRAP_ACCOUNT_ID` = un `analytics.accounts.id` real que además exista como
     `public.venues.account_id` con `tickets`/`orders`.
   - Sembrar al menos un `analytics.users` para ese account (o reusar el bootstrap admin
     de development).
3. Reiniciar la API. Las métricas deben devolver `data_source: discover`.
4. Smoke: `login` → `GET /api/v1/metrics/{nightly-attendance,sales-by-night,gremial-benchmarks}`
   con un periodo donde haya redenciones/órdenes.

## Validación mecánica (MOCK de Discover)

Ejecutada contra una base aislada `discover_bridge_test` (Postgres 16), sin tocar
`discover_analytics` ni la Postgres real de Discover:

1. `alembic upgrade head` (hasta `0006_account_fks_role_check`).
2. `psql -f sql/mock/001_discover_mock.sql` crea `public.venues/tickets/orders` con datos
   de septiembre 2026 para el account Demo (`a1111111-1111-4111-8111-111111111111`) y uno
   de Miguel's Club; incluye tickets sin redimir y órdenes `canceled` para probar los filtros.
3. `psql -f sql/views/001_*.sql` y `002_*.sql`; las vistas devuelven filas uniendo las tablas
   `public` mock (redenciones NULL y órdenes `canceled` quedan excluidas).
4. `DATA_SOURCE=discover`, API en puerto 8010, login con el bootstrap admin.
5. Resultado (periodo `2026-09-01..2026-09-10`):
   - `nightly-attendance` y `sales-by-night` → `data_source: discover`, `venue_id`
     de las tablas mock (`d4444444-...`), fechas de septiembre → derivan de las vistas,
     no de los facts seed (que son de agosto).
   - `gremial-benchmarks` → `data_source: discover`, `accounts_in_sample=2`,
     `nights_in_sample=30`, promedios calculados sobre las vistas.

## Bloqueo (conexión real a Discover)

En este entorno **no existen credenciales reales de Discover**. El `.env` y las variables de
entorno apuntan solo a la base local de Fase A (`discover_analytics`). Para conectar de verdad
se necesitan (como secretos, sin commitear):

- `DATABASE_URL` → `postgresql+asyncpg://…@<host-discover>/<db>` de la Postgres real de Discover.
- `ALEMBIC_DATABASE_URL` → `postgresql+psycopg://…@<host-discover>/<db>` (mismo host, driver sync).
- `BOOTSTRAP_ACCOUNT_ID` → un `accounts.id` real con `venues`/`tickets`/`orders`.

## Brechas conocidas (path `discover`)

- **`gremial-benchmarks` sin breakdown de género:** las vistas `v_*` no exponen género, así
  que `share_woman/man/other/undisclosed` salen `null` en modo `discover`. Los promedios de
  tickets/órdenes sí provienen de las vistas.
- **`attendance-by-gender` no tiene path `discover`:** `gender_repository` siempre lee
  `analytics.fact_attendance_detail` (facts seed). Requiere una vista con dimensión de género
  en `public` para funcionar en Fase B.
- **`nightly-attendance` ignora el filtro `gender`** en modo `discover` (la vista no lo soporta)
  y el filtro `venue_id` se aplica del lado del cliente tras el fetch.

## Reglas

- No DDL sobre tablas `public` de Pary desde Analytics (solo `CREATE VIEW` en `analytics`).
  El script `sql/mock/001_discover_mock.sql` crea tablas `public` **solo para pruebas locales**:
  no ejecutar contra la Postgres real de Discover.
- Preferir `GRANT SELECT` solo sobre vistas `analytics.v_*` al rol de la app.
- No copiar `orders`/`tickets` a facts en producción; los facts seed son solo Fase A.
