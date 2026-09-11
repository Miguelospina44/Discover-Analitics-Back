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

- **Infrastructure:** una URL, pool async, timeout de consulta, health/ready, JWT.
- **Data access:** repos. Prohibido interpolar SQL con input de usuario. Lectura de Discover vía vistas `analytics.v_*`. Escritura solo tablas `analytics.*`.
- **Domain:** medidas con unidad, formato, definición y `as_of`. Hallazgos/recomendaciones son metadatos, no copias de `orders`.
- **API:** `/api/v1`, errores sin internals, alcance por `account_id`.

## Una base de app, puente opcional a Discover

**Fase A (actual):** Postgres `discover_analytics`. Schema `analytics` con auth, consultoría y facts seed. `DATA_SOURCE=seed`.

**Fase B:** misma API; `DATA_SOURCE=discover`; métricas leen vistas sobre tablas `public` de Discover. Ver [phase-b-discover.md](phase-b-discover.md) y ADR 0005.

Discover (`public`) no se migra desde este repo.

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
