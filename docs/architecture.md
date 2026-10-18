# Arquitectura de la API

## Relación con la plataforma de Fundación

La app de Fundación (`analytics-platform`) aportó el patrón: FastAPI + SQLAlchemy + Alembic + dashboards con contrato de visuales + RBAC. **No se copia el monorepo.** Este backend es una variante para consultoría sobre vida nocturna Discover.

| Grupo | Qué era en Fundación | Decisión aquí |
|---|---|---|
| A | FastAPI, sesiones, Alembic, auth, errores, health, caché, contrato visual, export, cross-filter, KPI/tabla/gráfica genéricos, Docker, CI | Reutilizar el **patrón**, código nuevo sin nombres FUA |
| B | Shells de dashboard, registro, medidas, catálogo semántico, reportes, presentaciones, auditoría, preferencias, nav, tokens | Desacoplar: medidas y catálogo propios; tokens en el front |
| C | `apps/agents`, Azure AI Foundry, chat Miguel, RAG, loaders Odoo/SharePoint/Sheets, fallbacks JSON/Excel, dominios FUA, Nexus Glass | **Prohibido** |

Inventario archivo-a-archivo de Fundación: pendiente de abrir ese repo (no está en `Discover_cambios`).

## Capas

```
HTTP  →  api/v1 (Pydantic, RBAC)
         →  domain (métricas, reglas, ciclo de consultoría)
            →  data (repositorios, SQL parametrizado)
               →  infra (engine, settings, JWT, logging)
```

- **Infrastructure:** dos URLs cuando `DATA_SOURCE=discover` (app vs Discover read-only), pool async, timeout de consulta, health/ready, JWT. Credenciales solo por entorno.
- **Data access:** repos. Prohibido interpolar SQL con input de usuario. Lectura de Discover vía vistas `analytics.v_*`. Escritura solo tablas `analytics.*` en la base propia.
- **Domain:** medidas con unidad, formato, definición y `as_of`. Hallazgos/recomendaciones son metadatos, no copias de `orders`.
- **API:** `/api/v1`, errores sin internals (sin DSN, host ni PII), alcance por `account_id`.

## Una base de app, puente opcional a Discover

**Fase A (actual):** Postgres `discover_analytics`. Schema `analytics` con auth, consultoría y facts seed. `DATA_SOURCE=seed`.

**Fase B:** misma API; `DATA_SOURCE=discover`; métricas leen vistas sobre tablas `public` de Discover mediante conexión de **solo lectura separada**. Ver [phase-b-discover.md](phase-b-discover.md), ADR 0005 y ADR 0006.

Discover (`public`) no se migra desde este repo.

### Dos pools de conexión

- **`database_url`:** escritura Analytics (auth, consultoría, engagements)
- **`discover_database_url`:** solo lectura Discover (métricas cuando `DATA_SOURCE=discover`)

Pool de Discover:
- Size 3 + overflow 2 (menor que app para no saturar Discover)
- `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` a nivel Postgres
- TLS requerido en producción (`sslmode=require`)
- Timeout 10s
- Usuario `analytics_readonly` con `GRANT SELECT` únicamente sobre vistas `analytics.v_*`

Dependencia FastAPI `MetricsDbSession` usa el factory correcto según `data_source`.

La configuración se valida al arrancar (`Settings.validate_startup()`). Fallos típicos (sin revelar el DSN): falta `DISCOVER_DATABASE_URL`, driver distinto de asyncpg, DSN igual a `DATABASE_URL`, o `sslmode` ausente cuando `DISCOVER_REQUIRE_SSL=true`.

## Minimización de datos

Analytics **no** lee tablas `public` de Discover. Solo las 15 vistas agregadas de `sql/views` (allowlist en [`app/domain/discover_views.py`](../app/domain/discover_views.py)).

| Vista | Columnas | Plan mín. |
|---|---|---|
| `v_nightly_attendance` | `account_id`, `venue_id`, `night_date`, `redeemed_tickets` | starter |
| `v_sales_by_night` | `account_id`, `venue_id`, `night_date`, `order_count`, `revenue_cents` | starter |
| `v_ticket_sales_by_night` | `account_id`, `venue_id`, `night_date`, `tickets_sold`, `revenue_cents` | growth |
| `v_event_metrics` | `account_id`, `event_id`, `venue_id`, `event_date`, `event_capacity`, `venue_aforo`, `tickets_sold`, `tickets_redeemed`, `revenue_cents`, `sellthrough_pct`, `occupancy_pct` | growth |
| `v_sellthrough_by_tier` | `account_id`, `event_id`, `venue_id`, `tier_id`, `tier_price_cop`, `tier_capacity`, `tickets_sold`, `sellthrough_pct` | growth |
| `v_sales_velocity` | `account_id`, `event_id`, `venue_id`, `event_date`, `window_key`, `tickets_sold`, `revenue_cents` | pro |
| `v_purchase_hours` | `account_id`, `hour_of_day`, `tickets_sold`, `revenue_cents` | pro |
| `v_activity_by_weekday` | `account_id`, `iso_weekday`, `tickets_sold`, `revenue_cents` | pro |
| `v_venues_normalized` | `account_id`, `venue_id`, `aforo`, `city_raw`, `city_normalized`, `venue_type_normalized` | pro |
| `v_buyer_mix_by_event` | `account_id`, `event_id`, `venue_id`, `buyer_count`, `new_buyers`, `returning_buyers` | insight |
| `v_buyer_mix_by_month` | `account_id`, `order_month`, `buyer_count`, `new_buyers`, `returning_buyers` | insight |
| `v_market_by_city` | `city_normalized`, `venues_in_sample`, `accounts_in_sample`, `avg_tickets_per_venue`, `median_tickets_per_venue`, `avg_revenue_cents_per_venue`, `median_avg_ticket_cents` | insight (premium) |
| `v_market_by_venue_type` | `venue_type_normalized` + mismos agregados | insight (premium) |
| `v_market_by_weekday` | `iso_weekday` + mismos agregados | insight (premium) |
| `v_market_by_price_band` | `price_band` + mismos agregados | insight (premium) |

Las `v_market_by_*` **no** tienen `account_id`. La capa de acceso no aplica filtro de tenant (`AccessScope.tenant_filter=False`); solo exige el entitlement `market_cross_tenant`. Nunca se exponen IDs ni PII. Un colectivo puede leerlas con el plan aunque no tenga eventos asignados.

**Prohibido** (ni en vistas, ni en SELECT, ni en logs/respuestas):

- `users.password`, `users.password_hash`, tokens, JWT
- `users.email`, `users.phone`, documento, nombre, IP, `user_id`
- filas de `tickets` / `orders` / `transactions` con comprador o medio de pago
- DSN, host, puerto, usuario o password de cualquier base

`GRANT SELECT` solo a esas 15 vistas: [discover-readonly-setup.sql](discover-readonly-setup.sql). ADR de conexión: [0006](adr/0006-secure-discover-connection.md). Acceso y planes: [0007](adr/0007-tenant-hierarchy-and-entitlements.md).

## Flujo de un corte vertical

```
tickets.redemption_date
  → vista analytics.v_nightly_attendance
  → NightlyAttendanceRepository
  → medida nightly_attendance
  → GET /api/v1/metrics/nightly-attendance
  → (front) KPI + hallazgo opcional
```

## Auth, tenant y planes

Roles de **esta** app (no los de Pary): `admin`, `consultant`, `viewer`, `super_admin` (staff). El rol no desbloquea métricas de un plan superior.

Jerarquía (ADR 0007):

- `venue` — un local / una cuenta.
- `group` — varios locales (p. ej. Grupo Belisario) vía la misma cuenta o `child_account_ids`.
- `collective` / `organizer` — solo `event_ids` propios; sin lista, 403.

Planes (`DEFAULT_PLAN`, hoy `growth` para no romper las rutas vivas): `starter` → `growth` → `pro` → `insight` (alias `premium` del diccionario). Cada uno suma entitlements. Un cliente nunca ve filas particulares de otro. `market_aggregates` (starter) es el gremial grueso; `market_cross_tenant` (insight/premium) son las `v_market_by_*` anónimas, sin filtro de tenant.

- Token JWT propio. El cliente no manda rol, plan ni membresía.
- `Principal.resolve_access_scope()` + `require_entitlement()`.
- `APP_ENV=production` ignora el usuario bootstrap.

## Lo que no vive aquí

Módulo de recaudo NFC, tags 3D y rutas `/r/:slug` → `pary_backend` / `pary_frontend`.
