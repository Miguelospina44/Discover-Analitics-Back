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

Analytics **no** lee tablas `public` de Discover. Solo vistas agregadas. Columnas permitidas:

| Vista | Columnas | Grano |
|---|---|---|
| `analytics.v_nightly_attendance` | `account_id`, `venue_id`, `night_date`, `redeemed_tickets` | cuenta por tenant / venue / noche |
| `analytics.v_sales_by_night` | `account_id`, `venue_id`, `night_date`, `order_count`, `revenue_cents` | suma por tenant / venue / noche |

**Prohibido** (ni en vistas, ni en SELECT, ni en logs/respuestas):

- `users.password`, `users.password_hash`, tokens, JWT
- `users.email`, `users.phone`, documento, nombre, IP
- filas de `tickets` / `orders` / `transactions` con comprador o medio de pago
- DSN, host, puerto, usuario o password de cualquier base

Toda query de métricas añade `account_id` del JWT (multi-tenant fail-closed). Un admin gremial puede omitir el filtro de cuenta en una fase posterior; no se acepta un `account_id` ajeno mandado por el cliente.

Checklist y rotación: [security-checklist.md](security-checklist.md). Setup del rol: [discover-readonly-setup.sql](discover-readonly-setup.sql). ADR: [adr/0006-secure-discover-connection.md](adr/0006-secure-discover-connection.md).

## Flujo de un corte vertical

```
tickets.redemption_date
  → vista analytics.v_nightly_attendance
  → NightlyAttendanceRepository
  → medida nightly_attendance
  → GET /api/v1/metrics/nightly-attendance
  → (front) KPI + hallazgo opcional
```

## Auth y tenant

Roles de **esta** app (no los de Pary): `admin`, `consultant`, `viewer`.

- Token JWT propio. No se confía en un rol mandado por el cliente.
- Toda consulta de negocio filtra `account_id` del token (o lista explícita para un admin gremial, fase posterior).
- `APP_ENV=production` ignora el usuario bootstrap.

## Lo que no vive aquí

Módulo de recaudo NFC, tags 3D y rutas `/r/:slug` → `pary_backend` / `pary_frontend`.
