# Diccionario de métricas v1

Herramienta de pago para dueños y líderes de bares, discotecas, colectivos y organizadores. Convierte boletería y covers de Discover en números para decidir: ¿cuánto se vendió, se llenó el local, a qué ritmo y con qué mezcla de audiencia?

Las definiciones canónicas en código están en [`app/domain/metric_definitions.py`](../app/domain/metric_definitions.py). Este documento es la versión ejecutiva.

## Convenciones

| Campo | Significado |
|---|---|
| Definición | Qué mira el dueño, en lenguaje de negocio |
| Grano | Nivel de corte (noche, evento, venue, periodo, tier) |
| Fórmula | Cálculo. `COUNT(tickets)` — nunca `sold_quantity` |
| Fuente Discover | Columnas operativas |
| Vista / hecho | Objeto que implementa la métrica |
| Limitaciones | Sesgos, huecos y calidad |

**Tenant:** toda consulta de negocio filtra `account_id` (JWT). Las vistas exponen la columna; el repositorio vuelve a filtrar.

**Dinero:** en Discover los montos van en **pesos COP** (`price_paid_cop`, `price_cop`, `orders.total_amount`). Las vistas guardan `revenue_cents = pesos * 100` para alinearlas con `fact_sales_by_night`. Un cover de 85 000 COP no es 850.

**Estados de venta:** órdenes pagadas = `COMPLETED`, `CONFIRMED_FREE`, `APPROVED`. Un `INITIAL_TRANSACTION` es carrito, no venta. Boletos cancelados (`canceled` / `cancelled` / `cancelado`) no cuentan. El enum de tickets en DEV mezcla inglés y español (`active`, `inactive`, `activo`).

**Privacidad:** nunca PII ni filas individuales. Perfil de compradores solo agregado y **fail-closed**: si hay menos de **10** compradores distintos, la vista no emite la fila. Invitados (`user_id` NULL) no entran al mix.

**Fase A vs B:** `DATA_SOURCE=seed` lee hechos (`fact_sales_by_night`, `fact_nightly_attendance`). `DATA_SOURCE=discover` lee `analytics.v_*`. No hay conexión a bases reales en este carril; las vistas se aplican sobre la Postgres de Discover cuando otro agente active Fase B.

## Modelo estrella (grano)

Alineado a [dev-data-inventory.md](dev-data-inventory.md) §3, con Discover como fuente:

| Hecho conceptual | Grano | Vista agregada (lo que se expone) |
|---|---|---|
| fact_ticket | 1 boleto vendido | `v_ticket_sales_by_night`, `v_event_metrics`, `v_sellthrough_by_tier`, `v_sales_velocity` |
| fact_order | 1 orden pagada | `v_sales_by_night` (puente) |
| fact_redemption | 1 check-in | `v_nightly_attendance`, ocupación en `v_event_metrics` |
| dim_venue | 1 venue | `v_venues_normalized` (ciudad limpia, aforo) |
| dim_event / dim_tier | 1 evento / lista | `v_event_metrics`, `v_sellthrough_by_tier` |
| dim_date | noche / hora / weekday | `v_purchase_hours`, `v_activity_by_weekday` |
| dim_buyer (anónimo) | no se materializa | solo conteos en `v_buyer_mix_*` |

No se publica un `fact_ticket` fila a fila: sería PII operacional.

Columnas Discover usadas (repo `Proyecto-Discover`, `backend/app/models.py`): `venues.aforo`, `venues.account_id`, `events.price_cop`, `events.capacity`, `events.date`, `ticket_tiers` (`price_cop`, `capacity`), `tickets.price_paid_cop`, `tickets.purchased_at`, `tickets.tier`, `tickets.redemption_date`, `users.rol` (no se usa en v1).

---

## Métricas v1

### Ingresos

**Definición.** Dinero recaudado por boletos vendidos en una noche, evento, venue o periodo.

**Grano.** Noche + venue; evento; venue + periodo; periodo.

**Fórmula.** `SUM(COALESCE(price_paid_cop, tier.price_cop, event.price_cop, 0))`; en vista `* 100` → `revenue_cents`.

**Fuente.** `tickets.price_paid_cop`, `ticket_tiers.price_cop`, `events.price_cop`.

**Vista.** `analytics.v_ticket_sales_by_night`, `analytics.v_event_metrics`. En seed: `fact_sales_by_night`.

**Limitaciones.** No mezclar `transactions.status = 'APPROVED'` (en DEV hay txs huérfanas). Eventos gratis = 0. El puente `v_sales_by_night` usa `orders.total_amount` y solo estados pagados; preferir la vista de tickets cuando exista `price_paid_cop`.

### Ticket promedio

**Definición.** Precio medio pagado por boleto (o por orden en el puente de orders).

**Grano.** El mismo que ingresos.

**Fórmula.** `revenue_cents / tickets_sold`. Si no hay unidades, la métrica queda vacía (no se inventa 0).

**Fuente.** Derivada.

**Vista.** Capa de dominio sobre las vistas/hechos diarios.

**Limitaciones.** Órdenes gratis bajan el promedio. El puente por orden no ve mix de tiers dentro de la misma compra.

### Boletos vendidos

**Definición.** Boletos emitidos y no cancelados. Volumen de venta, no aforo ni puerta.

**Grano.** Noche, evento, venue, tier, periodo.

**Fórmula.** `COUNT(tickets.id)` con status no cancelado.

**Fuente.** `tickets` + `tickets.tier` / `event_id`.

**Vista.** `v_ticket_sales_by_night`, `v_event_metrics`, `v_sellthrough_by_tier`.

**Limitaciones.** **Nunca** `sold_quantity` (en DEV está en 0). Enum sucio EN/ES. Covers sin evento se agrupan por `venue_id`. No disponible en seed.

### Ocupación

**Definición.** Porcentaje del aforo físico que sí entró.

**Grano.** Evento (y asistencia diaria por venue).

**Fórmula.** `boletos redimidos / venues.aforo * 100`.

**Fuente.** `tickets.redemption_date`, `venues.aforo`.

**Vista.** `v_event_metrics.occupancy_pct`; puerta diaria en `v_nightly_attendance`.

**Limitaciones.** Sin aforo o aforo 0 → vacía. Sin scanner, `redemption_date` nulo subestima la puerta. No incluye walk-in sin ticket. No está en seed (el hecho de asistencia no trae aforo).

### Sell-through del evento

**Definición.** Qué parte del cupo del evento ya se vendió.

**Grano.** Evento.

**Fórmula.** `COUNT(tickets) / events.capacity * 100`.

**Fuente.** `events.capacity`, conteo de tickets.

**Vista.** `v_event_metrics.sellthrough_pct`.

**Limitaciones.** Si `capacity` es NULL no se usa el aforo como sustituto (son cosas distintas: inventario vs sala). Puede superar 100% si hubo over-sale.

### Sell-through por etapa / tier

**Definición.** Qué tan vendida está cada lista (early bird, general, VIP).

**Grano.** `ticket_tier` dentro del evento.

**Fórmula.** `COUNT(tickets del tier) / ticket_tiers.capacity * 100`.

**Fuente.** `tickets.tier`, `ticket_tiers.capacity`, `ticket_tiers.price_cop`.

**Vista.** `analytics.v_sellthrough_by_tier`.

**Limitaciones.** No usar `ticket_batches` ni `sold_quantity`. Cupo NULL → porcentaje vacío.

### Ritmo de venta antes del evento

**Definición.** Cuánto se vendió con tiempo vs de último minuto.

**Grano.** Evento + ventana.

**Fórmula.** Ventanas sobre `event.date - purchased_at::date` (Bogotá):

| Ventana | Días antes |
|---|---|
| `early_bird` | más de 7 |
| `week_before` | 3 a 7 |
| `last_days` | 1 a 2 |
| `same_day` | 0 o posterior |

**Fuente.** `tickets.purchased_at`, `events.date`.

**Vista.** `analytics.v_sales_velocity`.

**Limitaciones.** Sin `purchased_at` no hay ritmo. Compras después de la fecha caen en `same_day`.

### Comparativo entre eventos

**Definición.** Ranking de eventos del tenant por ingreso, boletos, sell-through u ocupación.

**Grano.** Lista de eventos.

**Fórmula.** Las mismas de arriba, ordenadas.

**Fuente / vista.** `analytics.v_event_metrics`.

**Limitaciones.** Comparar un rooftop de 200 con una discoteca de 1 200 en pesos crudos engaña; usar % de sell-through u ocupación.

### Comparativo entre periodos

**Definición.** Variación frente al periodo anterior (semana o mes equivalente).

**Grano.** Dos rangos de fechas del mismo tenant.

**Fórmula.** `(actual − anterior) / anterior * 100`. Si anterior = 0, indefinido.

**Fuente.** Hechos/vistas diarias.

**Vista.** Repositorio (`compare_periods`).

**Limitaciones.** Festivos y mix vie-sáb sesgan WoW. DEV no es proxy de producción.

### Comparativo entre venues

**Definición.** Mismo periodo, distintos locales del tenant.

**Grano.** Venue.

**Fórmula.** Suma de ingreso y unidades por `venue_id`.

**Fuente.** `v_ticket_sales_by_night` o `fact_sales_by_night`.

**Limitaciones.** Un solo venue no tiene contraste. Normalizar por aforo cuando exista.

### Compradores nuevos vs recurrentes

**Definición.** Qué parte de la audiencia compra por primera vez en el tenant.

**Grano.** Evento o mes.

**Fórmula.** Primera compra del `user_id` en el tenant = nuevo; el resto = recurrente.

**Fuente.** `tickets.user_id`, `MIN(purchased_at)`.

**Vista.** `v_buyer_mix_by_event`, `v_buyer_mix_by_month`.

**Limitaciones.** Invitados fuera. Con poco histórico casi todos son “nuevos”. No es LTV.

**Privacidad.** La vista **omite** la fila si hay menos de 10 compradores distintos. El repositorio vuelve a aplicar el umbral. No se selecciona `user_id`, email, teléfono ni nombre.

### Horas pico de compra

**Definición.** Hora del día (0–23, Bogotá) en la que se concentran las compras.

**Grano.** Account + hora.

**Fórmula.** `COUNT(tickets) GROUP BY EXTRACT(HOUR FROM purchased_at AT TIME ZONE 'America/Bogota')`.

**Fuente.** `tickets.purchased_at`.

**Vista.** `analytics.v_purchase_hours`.

**Limitaciones.** No separa laboral vs fin de semana (ver día de semana). Poco volumen = patrón inestable.

### Actividad por día de semana

**Definición.** Ventas según lunes=1 … domingo=7.

**Grano.** Account + `iso_weekday`.

**Fórmula.** Conteo e ingreso por `ISODOW`.

**Fuente.** `purchased_at` (Discover) o `night_date` de hechos (seed).

**Vista.** `v_activity_by_weekday` / agregación en repositorio.

### Asistencia por noche (ya existía)

**Definición.** Tickets redimidos por venue y noche.

**Fórmula.** `COUNT(*)` donde `redemption_date IS NOT NULL`.

**Vista / hecho.** `v_nightly_attendance` / `fact_nightly_attendance`.

### Ventas por noche — órdenes (puente)

**Definición.** Órdenes pagadas e ingreso por venue-noche. Complementa la vista de tickets; no la sustituye.

**Fórmula.** `COUNT(orders)` y `SUM(total_amount)*100` con estados pagados.

**Vista.** `v_sales_by_night`.

### Mix de género (ya existía, solo seed)

**Definición.** Distribución agregada woman / man / other / undisclosed.

**Fuente.** `fact_attendance_detail`. En Discover v1 no hay género en tickets; no se lee `users` fila a fila.

---

## Riesgos que las vistas ya contemplan

Documentados en [dev-data-inventory.md](dev-data-inventory.md):

1. **COP en pesos**, no centavos — conversión explícita `* 100`.
2. **Estados inconsistentes** — whitelist de órdenes pagadas; tickets cancelados fuera.
3. **Ciudades sucias** — `v_venues_normalized` (Medellín / medellin / Medellin).
4. **Integridad referencial** — métricas v1 de tickets no dependen de `orders`↔`transactions`.
5. **`sold_quantity` no confiable** — solo `COUNT(tickets)`.
6. **Unix vs timestamptz** — `redemption_date` / `order_date` como unix (`to_timestamp`); `purchased_at` como timestamptz. Si Discover cambia el tipo, hay que ajustar la vista.
7. **DEV ≠ prod** — sandbox, volumen bajo, no usar como verdad de negocio.

## Métricas v2 (priorizadas)

Requieren datos que hoy no están en Discover o no son usables. Orden de valor para el dueño:

| # | Métrica | Por qué espera |
|---|---|---|
| 1 | ROI de pauta | No hay gasto Meta/Google; UTM en DEV es residual |
| 2 | Proyección vs real | El organizador no carga forecast |
| 3 | Tasa de cancelación / refund | No hay tabla de devoluciones |
| 4 | LTV de comprador | Hace falta ≥12 meses y umbral ≥20 |
| 5 | Margen de contribución | No hay costos del evento |
| 6 | NPS post-evento | No hay encuestas |
| 7 | Interacciones en redes | Fuera de Postgres |
| 8 | Tiempo de check-in | Solo existe `redemption_date` |
| 9 | Sell-through predicho | v1 es descriptivo; sandbox no entrena |
| 10 | Origen geográfico del comprador | PII / compliance; no va en v1 |

## Cómo aplicar las vistas

En la Postgres de Discover, con schema `analytics` creado, aplicar en orden los archivos de `sql/views/`. La app no hace DDL sobre `public`. Otro agente gestiona conexión y secretos; este carril no lee `.env` ni bases reales.
