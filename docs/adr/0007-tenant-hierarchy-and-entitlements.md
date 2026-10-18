# ADR 0007 — Jerarquía de tenant, roles y entitlements por plan

## Contexto

Los clientes de Discover Analytics son **locales**, **grupos de locales** (p. ej. Grupo Belisario), **colectivos** y **organizadores**. Pagan por **planes** con refinamiento creciente. Los datos personales de compradores son privados: un cliente no ve personas de otros clientes; sí puede ver **tendencias de mercado en agregado**.

Hasta ahora el alcance era un `account_id` plano más un rol de app (`admin` / `consultant` / `viewer` / `super_admin`). Eso no distingue grupo vs colectivo ni habilita/corta métricas por plan.

Este ADR complementa [0006](0006-secure-discover-connection.md) (conexión de solo lectura) y no cambia las fórmulas de negocio (carril de métricas).

## Decisión

### 1. Jerarquía de tenant (quién ve qué filas)

```
grupo (account)
  └── locales / venues
        └── eventos / noches

colectivo u organizador (account)
  └── solo SUS eventos  (no el venue completo ni eventos ajenos)
```

| `tenant_kind` | Alcance de filas propias | Ejemplo |
|---|---|---|
| `venue` | Un `account_id` y todos sus venues/eventos | Un bar independiente |
| `group` | La cuenta padre y, si existen, `child_account_ids` o `venue_ids` | Grupo Belisario |
| `collective` | Fail-closed a `event_ids` asignados | Colectivo que produce fechas |
| `organizer` | Igual que colectivo: solo sus eventos | Promotor / organizador |

Reglas fail-closed:

- Nadie (salvo `super_admin`) lee filas de **otra** cuenta. Un grupo solo baja a cuentas hijas listadas.
- Colectivo/organizador **sin** `event_ids` no ve métricas propias (403). No se infiere el venue entero.
- El cliente **nunca** manda el rol, el plan ni la membresía: salen del token emitido por esta API o de tablas propias (`analytics.*`). El query string `account_id` / `venue_id` / `event_id` solo **restringe** dentro del scope ya resuelto.
- Tendencias de mercado (`market_aggregates`, hoy `gremial-benchmarks`) no revelan filas de un tenant ajeno ni PII. Un colectivo **sí** puede ver ese agregado aunque no tenga eventos asignados.

`AccessScope` es el objeto que los repositorios deben aplicar (WHERE `account_id` / `venue_id` / `event_id`). En este PR se resuelve en dominio; el SQL de métricas sigue filtrando `account_id` como hoy.

### 2. Roles (qué puede **hacer** en esta app)

Roles de **esta** API, no los de Discover/Pary:

| Rol | Lectura en su scope | Escritura de estudios | Filas de otros tenants |
|---|---|---|---|
| `viewer` | Sí, según plan | No | No |
| `consultant` | Sí, según plan | Sí | No |
| `admin` | Sí, según plan | Sí | No |
| `super_admin` | Sí | Sí | Sí (staff interno) |

El rol **no** sustituye al plan: un `admin` en Esencial no desbloquea Insight.

### 3. Entitlements por plan (qué vistas/métricas)

Planes técnicos (copy de producto en español). Cada plan **incluye** el anterior. Costo creciente = más refinamiento.

| Plan | Título | Qué habilita |
|---|---|---|
| `starter` | Esencial | Puerta diaria, ventas diarias, venues del tenant, tendencias de mercado agregadas |
| `growth` | Crecimiento | + boletos/noche, métricas por evento, sell-through por lista, mix de género agregado |
| `pro` | Pro | + ritmo de venta, hora de compra, weekday, venues normalizados, comparativos de venues |
| `insight` | Insight | + mix nuevos/recurrentes (solo cohortes ≥ 10) |

Claves de entitlement (código) y medidas actuales:

| Medida / vista | Entitlement | Plan mínimo |
|---|---|---|
| `nightly_attendance` | `nightly_attendance` | starter |
| `sales_by_night` | `sales_by_night` | starter |
| `gremial_benchmarks` | `market_aggregates` | starter |
| `attendance_by_gender` | `attendance_by_gender` | growth |
| `ticket_sales_by_night` | `ticket_sales_by_night` | growth |
| `event_metrics` | `event_metrics` | growth |
| `sellthrough_by_tier` | `sellthrough_by_tier` | growth |
| `sales_velocity` | `sales_velocity` | pro |
| `purchase_hours` | `purchase_hours` | pro |
| `activity_by_weekday` | `activity_by_weekday` | pro |
| `venues_normalized` | `venues_normalized` | pro |
| `buyer_mix_by_*` | `buyer_mix` | insight |

Plan desconocido → **cero** entitlements. `super_admin` bypasea el plan (ops interno).

Hasta que exista una tabla de suscripción, `DEFAULT_PLAN` (hoy `growth`) es el piso para no romper las métricas ya expuestas. El front no elige el plan.

### 4. Privacidad

- Analytics no lee `public.users` ni columnas PII. Las vistas `v_buyer_mix_*` pueden usar `user_id` **dentro** del SQL y **no** lo exponen; además omiten la fila si hay menos de 10 compradores distintos.
- Un cliente no ve compradores, emails, teléfonos ni tickets de otro cliente.
- El mercado se ve solo como agregado (sin `account_id` ajeno en la respuesta de benchmarks).

### 5. Modelo futuro (escritura en `analytics`, no ahora)

Sin migración en este PR (evita pelear con el schema de consultoría):

- `analytics.accounts.kind` + `parent_account_id`
- `analytics.account_venues` / `account_events` (membresía)
- `analytics.account_subscriptions (account_id, plan, valid_from, valid_to)`

El login cargará kind/plan/membresía desde esas tablas y las meterá en el `Principal`. El JWT no es la fuente de verdad del plan.

## Consecuencias

- El default `tenant_kind=venue` + `plan=growth` mantiene el comportamiento actual de las rutas vivas.
- Colectivos y grupos quedan diseñados; hace falta persistir membresías para activarlos en producción.
- Los repositorios de métricas deben, en el siguiente corte, aplicar `AccessScope.event_ids` / `venue_ids` (no solo `account_id`).
- Catálogo de vistas permitidas: [`app/domain/discover_views.py`](../../app/domain/discover_views.py) y [`docs/discover-readonly-setup.sql`](../discover-readonly-setup.sql).

## Alternativas descartadas

1. **Un solo `account_id` para grupos y colectivos:** un colectivo vería todo el venue.
2. **Plan mandado por el front:** viola fail-closed y “el frontend no define roles”.
3. **RLS en Discover para cada cliente:** el usuario de BD es uno solo (`analytics_readonly`); el aislamiento es en la app.
