# Fase B — Puente a Discover

Estado: **conexión de solo lectura cableada**; smoke contra un Discover real queda pendiente de ops (este repo no usa secretos ni hosts reales).

## Qué ya está listo

| Pieza | Ubicación |
|---|---|
| Switch `DATA_SOURCE` | [`app/core/config.py`](../app/core/config.py) |
| Validación fail-closed al arrancar | `Settings.validate_startup()` |
| Pool read-only separado | [`app/infra/db.py`](../app/infra/db.py) |
| Sesión de métricas | `MetricsDbSession` en [`app/api/deps.py`](../app/api/deps.py) |
| Attendance seed vs vista | [`app/data/attendance_repository.py`](../app/data/attendance_repository.py) |
| Sales seed vs vista | [`app/data/sales_repository.py`](../app/data/sales_repository.py) |
| Métricas v1 (eventos, tiers, ritmo, mix, horas) | [`app/data/metrics_repository.py`](../app/data/metrics_repository.py) |
| Definiciones | [`app/domain/metric_definitions.py`](../app/domain/metric_definitions.py), [`docs/metrics-dictionary.md`](metrics-dictionary.md) |
| Vistas 001–015 | [`sql/views/`](../sql/views/) (propias + mercado anónimo) |
| Allowlist + GRANTs | [`app/domain/discover_views.py`](../app/domain/discover_views.py), [discover-readonly-setup.sql](discover-readonly-setup.sql) |
| Tenant / planes | [adr/0007-tenant-hierarchy-and-entitlements.md](adr/0007-tenant-hierarchy-and-entitlements.md) |
| Usuario SELECT-only | [`docs/discover-readonly-setup.sql`](discover-readonly-setup.sql) |
| Columnas permitidas | [architecture.md](architecture.md#minimizaci%C3%B3n-de-datos) |
| ADR | [adr/0006-secure-discover-connection.md](adr/0006-secure-discover-connection.md) |

## Pasos para activar (cuando toque)

1. En la Postgres de Discover (nunca desde este repo con credenciales reales):
   - Aplicar `sql/views/001`–`015` en orden. `001`/`002` son el puente de asistencia y órdenes; `003`–`011` usan `ticket_tiers`, `price_paid_cop` y `purchased_at`; `012`–`015` son tendencias de mercado (sin IDs, umbral de locales y de cohorte).
   - Crear rol `analytics_readonly` con `GRANT SELECT` solo sobre esas vistas. Ver `docs/discover-readonly-setup.sql`.
2. En la Postgres **propia** de Analytics (`discover_analytics`):
   - `alembic upgrade head` (auth, consultoría, facts seed).
   - **No** apuntar `DATABASE_URL` / `ALEMBIC_DATABASE_URL` a Discover.
3. `.env` local (ignorado por git):
   - `DATA_SOURCE=discover`
   - `DISCOVER_DATABASE_URL` → DSN de solo lectura, distinta de `DATABASE_URL`, con `sslmode=require` (o verify-full)
   - `DISCOVER_REQUIRE_SSL=true`
   - `BOOTSTRAP_ACCOUNT_ID` = un `accounts.id` real con venues/tickets (solo no-producción)
4. Reiniciar API; si falta URL, driver, TLS o el DSN coincide con la base de la app, **no arranca**.
5. Métricas deben devolver `data_source: discover`.
6. Smoke: login → métricas con periodo donde haya redenciones → finding.

## Reglas

- No DDL sobre tablas `public` de Discover/Pary desde Analytics.
- `GRANT SELECT` solo sobre vistas `analytics.v_*` al rol de la app.
- No copiar `orders`/`tickets` a facts en producción; los facts seed son solo Fase A.
- No leer `users.password` / `password_hash`, emails, teléfonos ni otros PII.
- No registrar ni devolver DSN, hosts, credenciales ni PII.

## Contrato pendiente con el frontend

Anotado en [metrics-dictionary.md](metrics-dictionary.md#contrato-pendiente-con-el-frontend). Resumen: `revenue_cents` mezcla centavos (vistas Discover `* 100`) y magnitud de pesos en el seed; `gremial-benchmarks` no expone promedio de ingresos; `sales-by-night` no recorta por audiencia. No se inventan campos en este PR.
