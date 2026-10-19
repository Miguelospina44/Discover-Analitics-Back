# Diccionario de métricas v1

Discover Analytics es una herramienta de pago para dueños de bares, discotecas, colectivos y organizadores. **Su valor crece con el tiempo**: a más usuarios y noches, más finas las tendencias propias y las del mercado.

Ayuda a tres decisiones:

| Línea | Pregunta del dueño |
|---|---|
| **Público objetivo** | ¿Quién me compra y vuelve? |
| **Patrones de operación** | ¿Qué días, horas y etapas funcionan? ¿Se llena el local? |
| **Ventas y tendencia** | ¿Cuánto vendí, hacia dónde va y cómo está el mercado? |

Los planes (básico / intermedio / premium) **refinan la información**. El nivel que aparece aquí es una **sugerencia**; el dueño del producto puede mover cualquier métrica de plan.

## Quién ve qué: local vs colectivo/organizador

Regla de Miguel: un **colectivo u organizador** ve los datos de **sus eventos** y de **sus clientes en esos eventos** (siempre agregados, sin PII) y las **tendencias generales del ecosistema**. **Nunca** ve la operación del local donde hace el evento. Su corte es **evento puntual**, no una casa que abre todas las semanas.

| Actor | Corte | Qué ve | Qué no ve |
|---|---|---|---|
| Local / grupo | `account_id` (operación continua) | Noches, venues, ocupación, weekday, mix de sala | Eventos de terceros |
| Colectivo / organizador | `event_ids` propios | Ingresos y boletos del evento, etapas, ritmo, horas de compra, público agregado, comparativo entre **sus** eventos, mercado anónimo | El venue anfitrión (aforo, ocupación, noches del local), eventos ajenos |
| Ambos | celdas de mercado | Promedios de ciudad / tipo / weekday / precio | Identidad de otro cliente |

El repositorio aplica `event_id IN (:event_ids)` para el organizador. Sin `event_ids` no hay filas (fail-closed). Las filas de evento **no incluyen** `venue_id`, aforo ni ocupación.

Las definiciones canónicas están en [`app/domain/metric_definitions.py`](../app/domain/metric_definitions.py).

## Privacidad (fail-closed)

- Ningún cliente ve datos particulares de clientes ajenos ni de compradores.
- El propio tenant ve **solo agregados** de su `account_id`.
- El **mercado** es tendencia general: promedios y medianas entre muchos locales. La celda se **omite** si no hay al menos **5 locales distintos**, **3 tenants** y **20 boletos**.
- No se publican totales de mercado (evitar restas para inferir a un vecino).
- Mix de compradores del tenant: n ≥ **10**. Sin PII (`user_id`, email, teléfono, nombre).

## Planes sugeridos (ajustables)

| Plan | Enfoque | Ejemplos |
|---|---|---|
| Básico | Monitorear la casa: vendí, entré, ticket | ingresos, boletos, asistencia, ticket promedio |
| Intermedio | Mejorar la operación y ver tendencia propia | ocupación, sell-through evento, weekday, horas, WoW |
| Premium | Público + refinamiento + mercado anónimo | mix nuevos/recurrentes, tiers, ritmo, benchmarks |

## Convenciones de cálculo

- **Tenant:** toda métrica propia filtra `account_id`. El mercado no expone IDs.
- **Dinero:** Discover guarda **pesos COP**. Las vistas usan `revenue_cents = pesos * 100`. 85 000 COP no es 850.
- **Venta:** órdenes `COMPLETED` / `CONFIRMED_FREE` / `APPROVED`. Carritos `INITIAL_TRANSACTION` fuera. Tickets cancelados (`canceled` / `cancelled` / `cancelado`) fuera.
- **Volumen:** `COUNT(tickets)` — nunca `sold_quantity`.
- Seed (`DATA_SOURCE=seed`) vs Discover (`analytics.v_*`). Este carril no usa bases reales ni `.env`.

## Modelo estrella (agregado)

| Hecho | Grano interno | Lo que se publica |
|---|---|---|
| fact_ticket | 1 boleto | vistas por noche/evento/tier/ventana |
| fact_order | 1 orden pagada | `v_sales_by_night` |
| fact_redemption | 1 check-in | `v_nightly_attendance`, ocupación |
| dim_venue / event / date | atributos de negocio | ciudad y tipo normalizados |
| dim_buyer | no se materializa | solo conteos `v_buyer_mix_*` |
| mercado | celda ciudad / tipo / weekday / banda | `v_market_by_*` sin IDs |

Fuente Discover: `venues.aforo`, `events.price_cop` / `capacity`, `ticket_tiers`, `tickets.price_paid_cop` / `purchased_at` / `tier`.

---

## 1. Público objetivo

Retrato agregado de **quién** compra. Nunca una persona.

### Compradores nuevos vs recurrentes — premium · local y colectivo (por evento)

**Definición.** Qué parte de la audiencia compra por primera vez en el tenant.

**Grano.** Evento o mes.

**Fórmula.** Primera compra del `user_id` en el tenant = nuevo; el resto = recurrente.

**Fuente / vista.** `tickets.user_id`, `MIN(purchased_at)` → `v_buyer_mix_by_event`, `v_buyer_mix_by_month`.

**Limitaciones.** Invitados fuera. Con poco histórico casi todos son “nuevos”. No es LTV.

**Privacidad.** Se omite la fila si hay menos de 10 compradores distintos.

### Mix de género (agregado) — premium · solo local (sala continua)

**Definición.** Distribución de sala woman / man / other / undisclosed.

**Grano.** Account / venue / periodo.

**Fuente.** `fact_attendance_detail` (seed). Discover v1 no lee `users` fila a fila.

**Limitaciones.** En Fase B no hay género en tickets.

### Audiencia por género y rango de edad — intermedio · local y colectivo (el colectivo solo sus eventos)

**Definición.** Compradores distintos por género declarado y banda de edad. Gráfica de público, nunca una persona.

**Grano.** `gender` × `age_band` en el periodo y alcance autenticado.

**Fórmula.** `COUNT(DISTINCT tickets.user_id)`. Edad = años a `events.date`. Bandas: `18-24`, `25-34`, `35-44`, `45-54`, `55+`. Género o edad nulos / no parseables → `sin_dato`. No se inventan valores.

**Fuente / vista.** Seed: celdas de ejemplo con `is_demo=true`. Discover: `analytics.v_audience_by_gender_age` (rol `analytics_readonly`).

**Privacidad.** Si el total del alcance es &lt; 10, no hay puntos. Cada celda &lt; 10 se agrupa en `otros`/`otros` solo si ese residual llega a 10; si no, se omite. Sin `user_id`, email, nombre ni fecha de nacimiento en la respuesta.

**Columnas Discover asumidas (verificar en la base real):** `users.gender` (text), `users.birth_date` (date), `tickets.user_id`, `events.date`. Alternativas no usadas en el SQL: `users.birthdate`, `users.date_of_birth`, `users.age`, `users.sexo`.

**Endpoint.** `GET /api/v1/metrics/audience-by-gender-age`

**JSON de ejemplo (seed, `is_demo=true`):**

```json
{
  "name": "audience_by_gender_age",
  "title": "Audiencia por género y rango de edad",
  "unit": "headcount",
  "definition": "Compradores distintos por género declarado y rango de edad (18-24 … 55+). Celdas con menos de 10 personas se agrupan en otros o se omiten. Género o edad nulos van a sin_dato. No expone user_id ni filas individuales.",
  "as_of": "2026-10-19",
  "data_quality": "ok",
  "data_source": "seed",
  "is_demo": true,
  "demo_label": "Datos de ejemplo (DATA_SOURCE=seed). No son filas de Discover.",
  "scope": "account",
  "k_anonymity": 10,
  "suppressed": false,
  "points": [
    {"gender": "woman", "age_band": "18-24", "headcount": 28, "share": 0.1186},
    {"gender": "woman", "age_band": "25-34", "headcount": 41, "share": 0.1737},
    {"gender": "woman", "age_band": "35-44", "headcount": 22, "share": 0.0932},
    {"gender": "woman", "age_band": "45-54", "headcount": 14, "share": 0.0593},
    {"gender": "man", "age_band": "18-24", "headcount": 19, "share": 0.0805},
    {"gender": "man", "age_band": "25-34", "headcount": 36, "share": 0.1525},
    {"gender": "man", "age_band": "35-44", "headcount": 24, "share": 0.1017},
    {"gender": "man", "age_band": "45-54", "headcount": 12, "share": 0.0508},
    {"gender": "man", "age_band": "55+", "headcount": 11, "share": 0.0466},
    {"gender": "other", "age_band": "25-34", "headcount": 11, "share": 0.0466},
    {"gender": "sin_dato", "age_band": "sin_dato", "headcount": 18, "share": 0.0763}
  ]
}
```

En `DATA_SOURCE=discover` el mismo contrato trae `is_demo: false`, `demo_label: null` y los conteos de la vista.

---

## 2. Patrones de operación

Cómo se comporta la casa: puerta, inventario, timing.

### Asistencia por noche — básico · solo local

Check-ins por venue y noche. `COUNT(tickets)` con `redemption_date`. `v_nightly_attendance` / `fact_nightly_attendance`. Sin scanner, no hay señal de puerta.

### Ocupación — intermedio · solo local (aforo del venue)

Redimidos / `venues.aforo` × 100. `v_event_metrics.occupancy_pct`. Vacía si aforo es NULL o 0.

### Sell-through del evento — intermedio · local y colectivo

Vendidos / `events.capacity` × 100. No se sustituye capacity por aforo (inventario ≠ sala).

### Sell-through por etapa / tier — premium · local y colectivo

Vendidos del tier / `ticket_tiers.capacity`. **Nunca** `sold_quantity`. `v_sellthrough_by_tier`.

### Ritmo de venta antes del evento — premium · local y colectivo

Ventanas sobre `event.date − purchased_at`: `early_bird` (>7d), `week_before` (3–7), `last_days` (1–2), `same_day`. `v_sales_velocity`.

### Horas pico de compra — intermedio · local y colectivo (filtrado por evento)

Hora 0–23 en Bogotá. `v_purchase_hours`.

### Actividad por día de semana — intermedio · solo local

Lunes=1 … domingo=7. Vista Discover o hechos seed.

### Comparativo entre eventos — premium · local y colectivo (solo sus event_ids)

Ranking propio por ingreso, boletos, sell-through u ocupación. Normalizar por aforo.

### Tendencia de mercado por tipo de local — premium · ecosistema (local y colectivo)

Bar vs discoteca vs rooftop, **anónimo**. Ver §4.

### Tendencia de mercado por día de semana — premium · ecosistema (local y colectivo)

Si el viernes flojo es de la casa o del mercado. Ver §4.

---

## 3. Ventas y tendencia

Monitoreo de plata y volumen; luego comparación en el tiempo y contra el mercado.

### Ingresos — básico · local y colectivo (el colectivo solo a grano evento)

`SUM(COALESCE(price_paid_cop, tier.price_cop, event.price_cop, 0))`; vista `* 100` → `revenue_cents`. `v_ticket_sales_by_night`, `v_event_metrics`. Seed: `fact_sales_by_night`. No mezclar `transactions` huérfanas.

### Ticket promedio — básico · local y colectivo

`revenue_cents / tickets_sold`. Vacío si no hay unidades.

### Boletos vendidos — básico · local y colectivo

`COUNT(tickets)` no cancelados. Nunca `sold_quantity`.

### Ventas por noche (órdenes) — básico · solo local

Puente de orders pagadas. Complementa tickets; no los sustituye. `v_sales_by_night`.

### Comparativo entre periodos — intermedio · solo local (operación continua)

`(actual − anterior) / anterior`. Indefinido si anterior = 0.

### Comparativo entre venues — intermedio · solo local

Mismo tenant, varios locales. Un solo venue no tiene contraste.

### Tendencia de mercado por ciudad — premium · ecosistema (local y colectivo)

Ticket medio y volumen por local en la ciudad, sin vecinos nombrados. Ver §4.

### Tendencia de mercado por rango de precio — premium · ecosistema (local y colectivo)

Bandas en pesos COP: `free` 0; `entry` ≤40 000; `standard` ≤80 000; `high` ≤150 000; `premium_cover` >150 000. Ver §4.

---

## 4. Benchmarks de mercado (anónimos)

Cualquier cliente puede ver **tendencias generales**, nunca la cifra de otro tenant.

| Vista | Corte | Métricas publicadas |
|---|---|---|
| `v_market_by_city` | ciudad normalizada | promedio/mediana de boletos e ingreso **por local**, ticket medio |
| `v_market_by_venue_type` | bar / discoteca / club / rooftop | igual |
| `v_market_by_weekday` | ISODOW | igual |
| `v_market_by_price_band` | banda de cover | igual |

Reglas:

1. Salida **sin** `account_id`, `venue_id`, `event_id`, PII.
2. Solo promedio y mediana (no `SUM` de ingreso ni de boletos).
3. `HAVING` fail-closed: ≥5 locales, ≥3 accounts, ≥20 boletos.
4. El repositorio vuelve a aplicar el umbral. Si el mercado global (`gremial`) no llega, se ocultan promedios y no se filtra el n chico.
5. En seed actual (2–3 locales) las celdas salen vacías: es correcto.

Tipo de local: `venues.venue_type` (texto). Si Discover solo tiene FK a catálogo, proyectar el nombre en `v_venues_normalized`.

---

## Riesgos ya cubiertos

COP en pesos; estados sucios; ciudades sucias (`v_venues_normalized`); integridad tickets↔orders (métricas v1 de ticket no dependen de tx); `sold_quantity` ignorado; unix vs timestamptz; DEV ≠ prod.

## Métricas v2 (priorizadas)

Más datos → más refinamiento de plan. Orden de valor:

| # | Métrica | Línea | Plan sugerido | Por qué espera |
|---|---|---|---|---|
| 1 | ROI de pauta | ventas | premium | No hay gasto Meta/Google |
| 2 | Proyección vs real | ventas | intermedio | El organizador no carga forecast |
| 3 | Tasa de cancelación / refund | ventas | intermedio | No hay tabla de devoluciones |
| 4 | LTV de comprador | público | premium | ≥12 meses y umbral ≥20 |
| 5 | Margen de contribución | ventas | premium | No hay costos |
| 6 | NPS post-evento | público | premium | No hay encuestas |
| 7 | Interacciones en redes | público | premium | Fuera de Postgres |
| 8 | Tiempo de check-in | operación | premium | Solo `redemption_date` |
| 9 | Sell-through predicho | operación | premium | v1 es descriptivo |
| 10 | Origen geográfico del comprador | público | premium | PII / compliance |

## Cómo aplicar las vistas

En la Postgres de Discover, schema `analytics`, archivos `sql/views/001`–`016` en orden. Sin DDL sobre `public`. Otro agente gestiona secretos; este carril no lee `.env`.

## Contrato pendiente con el frontend

Tres huecos abiertos. **No se inventa campo ni se cambia la API aquí**; solo se anota lo que hoy existe.

### Unidad de `revenue_cents` (pesos o centavos)

- Discover guarda montos operativos en **pesos COP** (`orders.total_amount`, `tickets.price_paid_cop`, `events.price_cop`, `ticket_tiers.price_cop`).
- Las vistas `analytics.v_*` hacen `pesos * 100` y publican `revenue_cents` (p. ej. `sql/views/002_v_sales_by_night.sql`, `003_v_ticket_sales_by_night.sql`).
- La API expone `SalesPointOut.revenue_cents`. La medida `sales_by_night` declara `unit: "orders_and_cents"`.
- El seed `analytics.fact_sales_by_night.revenue_cents` inserta valores del orden de 150 000–230 000 (`150000 + (DOY % 20) * 25000` en `alembic/versions/0002_fact_tables_seed.py`). Esa magnitud es de **pesos por noche**, no de centavos (150 000 centavos = 1 500 COP).

Pendiente de producto: si el front trata `revenue_cents` como centavos (÷ 100 → pesos) o como pesos con nombre heredado del seed. Hasta que se cierre, no se renombra la columna ni se “corrige” el seed en este PR.

### Promedio de ingresos del sector

No existe en el contrato HTTP gremial.

`GET /api/v1/metrics/gremial-benchmarks` serializa `GremialBenchmarksResponse`:

- `avg_tickets_per_venue_night` / `median_tickets_per_venue_night`
- `avg_orders_per_venue_night` / `median_orders_per_venue_night`
- `accounts_in_sample`, `nights_in_sample`
- `share_woman` / `share_man` / `share_other` / `share_undisclosed`
- `note`

No hay `avg_revenue_*`. El repositorio calcula `avg_revenue_cents_per_venue` para las vistas `v_market_by_*` (plan insight / `market_cross_tenant`); **no** lo incluye `GremialBenchmarksResponse`.

### Recorte de audiencia en ventas

No existe en la API de ventas.

`GET /api/v1/metrics/sales-by-night` acepta `period_start`, `period_end`, `account_id`, `venue_id`. Devuelve `SalesPointOut`: `venue_id`, `night_date`, `order_count`, `revenue_cents` (y `account_id` opcional).

No hay query de género, mix de compradores ni otro corte de audiencia. El filtro `gender` está en `nightly-attendance` y `attendance-by-gender`. El mix vive en `v_buyer_mix_*` (sin ruta HTTP de ventas por audiencia).
