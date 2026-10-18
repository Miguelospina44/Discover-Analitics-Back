# Diccionario de métricas v1

Discover Analytics es una herramienta de pago para dueños de bares, discotecas, colectivos y organizadores. **Su valor crece con el tiempo**: a más usuarios y noches, más finas las tendencias propias y las del mercado.

Ayuda a tres decisiones:

| Línea | Pregunta del dueño |
|---|---|
| **Público objetivo** | ¿Quién me compra y vuelve? |
| **Patrones de operación** | ¿Qué días, horas y etapas funcionan? ¿Se llena el local? |
| **Ventas y tendencia** | ¿Cuánto vendí, hacia dónde va y cómo está el mercado? |

Los planes (básico / intermedio / premium) **refinan la información**. El nivel que aparece aquí es una **sugerencia**; el dueño del producto puede mover cualquier métrica de plan.

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

### Compradores nuevos vs recurrentes — premium

**Definición.** Qué parte de la audiencia compra por primera vez en el tenant.

**Grano.** Evento o mes.

**Fórmula.** Primera compra del `user_id` en el tenant = nuevo; el resto = recurrente.

**Fuente / vista.** `tickets.user_id`, `MIN(purchased_at)` → `v_buyer_mix_by_event`, `v_buyer_mix_by_month`.

**Limitaciones.** Invitados fuera. Con poco histórico casi todos son “nuevos”. No es LTV.

**Privacidad.** Se omite la fila si hay menos de 10 compradores distintos.

### Mix de género (agregado) — premium

**Definición.** Distribución de sala woman / man / other / undisclosed.

**Grano.** Account / venue / periodo.

**Fuente.** `fact_attendance_detail` (seed). Discover v1 no lee `users` fila a fila.

**Limitaciones.** En Fase B no hay género en tickets.

---

## 2. Patrones de operación

Cómo se comporta la casa: puerta, inventario, timing.

### Asistencia por noche — básico

Check-ins por venue y noche. `COUNT(tickets)` con `redemption_date`. `v_nightly_attendance` / `fact_nightly_attendance`. Sin scanner, no hay señal de puerta.

### Ocupación — intermedio

Redimidos / `venues.aforo` × 100. `v_event_metrics.occupancy_pct`. Vacía si aforo es NULL o 0.

### Sell-through del evento — intermedio

Vendidos / `events.capacity` × 100. No se sustituye capacity por aforo (inventario ≠ sala).

### Sell-through por etapa / tier — premium

Vendidos del tier / `ticket_tiers.capacity`. **Nunca** `sold_quantity`. `v_sellthrough_by_tier`.

### Ritmo de venta antes del evento — premium

Ventanas sobre `event.date − purchased_at`: `early_bird` (>7d), `week_before` (3–7), `last_days` (1–2), `same_day`. `v_sales_velocity`.

### Horas pico de compra — intermedio

Hora 0–23 en Bogotá. `v_purchase_hours`.

### Actividad por día de semana — intermedio

Lunes=1 … domingo=7. Vista Discover o hechos seed.

### Comparativo entre eventos — premium

Ranking propio por ingreso, boletos, sell-through u ocupación. Normalizar por aforo.

### Tendencia de mercado por tipo de local — premium

Bar vs discoteca vs rooftop, **anónimo**. Ver §4.

### Tendencia de mercado por día de semana — premium

Si el viernes flojo es de la casa o del mercado. Ver §4.

---

## 3. Ventas y tendencia

Monitoreo de plata y volumen; luego comparación en el tiempo y contra el mercado.

### Ingresos — básico

`SUM(COALESCE(price_paid_cop, tier.price_cop, event.price_cop, 0))`; vista `* 100` → `revenue_cents`. `v_ticket_sales_by_night`, `v_event_metrics`. Seed: `fact_sales_by_night`. No mezclar `transactions` huérfanas.

### Ticket promedio — básico

`revenue_cents / tickets_sold`. Vacío si no hay unidades.

### Boletos vendidos — básico

`COUNT(tickets)` no cancelados. Nunca `sold_quantity`.

### Ventas por noche (órdenes) — básico

Puente de orders pagadas. Complementa tickets; no los sustituye. `v_sales_by_night`.

### Comparativo entre periodos — intermedio

`(actual − anterior) / anterior`. Indefinido si anterior = 0.

### Comparativo entre venues — intermedio

Mismo tenant, varios locales. Un solo venue no tiene contraste.

### Tendencia de mercado por ciudad — premium

Ticket medio y volumen por local en la ciudad, sin vecinos nombrados. Ver §4.

### Tendencia de mercado por rango de precio — premium

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

En la Postgres de Discover, schema `analytics`, archivos `sql/views/001`–`015` en orden. Sin DDL sobre `public`. Otro agente gestiona secretos; este carril no lee `.env`.
