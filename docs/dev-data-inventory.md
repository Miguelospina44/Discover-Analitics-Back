# Inventario DEV `pary_db_test` (solo lectura)

Fecha de corte: 2026-08-30. Host DEV `148.113.203.168`, database `pary_db_test`.  
**Conclusión:** hay señal útil para prototipar analítica, pero el volumen es de sandbox y hay **quiebre de integridad** entre `transactions`/`tickets` y `orders` actuales. No usar DEV como proxy de prod.

## 1. Inventario

| Tabla | Filas | Notas |
|---|---:|---|
| tracking_events | 516 | Más densa; funnel |
| tracking_sessions | 120 | `user_id` siempre NULL |
| transactions | 110 | 100 huérfanas vs `orders` actuales |
| tickets | 63 | 37 con check-in; 7 compradores |
| promoters | 12 | Ninguno enlazado a órdenes actuales |
| venues | 15 | 4 “ciudades” con casing inconsistente |
| ticket_batches | 14 | `sold_quantity` = 0 en todos |
| users | 17 | 8 customer, 4 admin, 5 super_admin |
| order-lines | 10 | |
| orders | 10 | Solo `INITIAL_TRANSACTION` (8) y `COMPLETED` (2 free) |
| utm_campaigns | 9 | Poca atribución en sesiones |
| events | 5 | Jun–ago 2026 |
| accounts | 4 | |
| venue-types | 2 | `bar`, `discotk` |
| promotional_codes | 1 | |
| promotional_codes_usages | 1 | |
| music_genres | 0 | Tabla no existe en este schema |

### Rangos de fechas

| Señal | Min | Max |
|---|---|---|
| orders.order_date (unix→ts) | 2026-07-08 | 2026-08-21 |
| users.registration_date | 2025-05-27 | 2026-07-08 |
| events.date | 2026-06-19 | 2026-08-26 |
| tracking_events.created_at | 2026-04-26 | 2026-08-23 |
| tracking_sessions.created_at | 2026-04-22 | 2026-08-26 |
| transactions.created_at (APPROVED sample) | ~2026-02 | 2026-05 |

`pg_stat_user_tables` estaba **desactualizado** (mostraba 0 users/venues). Usar siempre `COUNT(*)`.

## 2. Calidad

| Check | Resultado | Implicación |
|---|---|---|
| orders APPROVED | **0** de 10 | No hay GMV “APPROVED” en `orders` hoy |
| orders INITIAL_TRANSACTION | 8/10 | Carritos / pagos no finalizados en tabla viva |
| orders COMPLETED (free) | 2/10 | Eventos gratis |
| tx APPROVED | 50 | Pero **0** con `order_id` existente |
| tx huérfanas | **100/110** | Histórico borrado o cascade incompleto |
| tickets con order vivo | **3/63** | Misma quiebra |
| orders.tracking_session_id NULL | **0/10** | Bien en muestra chica |
| orders.promoter_id NULL | **10/10** | Cero atribución promotor |
| tracking_sessions.user_id | **0** con user | No cierra identidad |
| UTM en sesiones | 3/120 | Atribución débil |
| ticket_batches.sold_quantity | todo 0 | No confiar; preferir COUNT tickets |
| tickets.status | `inactive` 37, `active` 24, `activo` 2 | Enum sucio (ES/EN) |
| city | Medellín / medellin / Medellin | Normalizar |
| Unidad amount | order_total == tx.amount (80k–160k); batch 0–85k; cover hasta 100k | **COP pesos**, no centavos (85 000 COP es cover/ticket creíble; 850 COP no) |
| Currency | COP 110/110 | OK |

**Regla de ventas en DEV (pragmática):**  
- Para “órdenes vivas”: `order_status IN ('COMPLETED','CONFIRMED_FREE','APPROVED')` + free aparte.  
- Para “pagos históricos”: `transactions.status = 'APPROVED'` sabiendo que muchos no joinean a `orders`.  
- No mezclar ambos sin documentar el sesgo.

## 3. Modelo estrella sugerido (para Analytics)

Facts (grano):

| Fact | Grain | Fuentes |
|---|---|---|
| fact_order | 1 orden | orders + tx agregada |
| fact_order_line | 1 línea | order-lines |
| fact_ticket | 1 ticket | tickets |
| fact_transaction | 1 intento pago | transactions |
| fact_tracking_event | 1 evento funnel | tracking_events |
| fact_session | 1 sesión | tracking_sessions |

Dims: date, user (anon), account, venue, venue_type, event, ticket_batch, promoter, utm_campaign, payment_method, order_status.

En Fase A aislada ya existen `fact_nightly_attendance` / `fact_sales_by_night` seed; en Fase B las vistas Discover deben alinearse a este grano.

## 4. Métricas v1

### YA desde Postgres (con salvedades DEV)

- Funnel PAGE_VIEW → EVENT_VIEW → CLICK_BUY → PURCHASE_COMPLETED (mejor dataset hoy).
- Sesiones / día; % sesiones con UTM (bajo).
- Catálogo: venues, events activos, capacidad, tipos, ciudades (normalizadas).
- Tickets emitidos / check-in (`redemption_date` o status inactive).
- Intentos de pago por status y método (PSE/CARD/FREE) desde `transactions`.
- GMV **aproximado** desde tx APPROVED (orphan-aware) o desde orders COMPLETED/APPROVED cuando existan.
- Ticket promedio, mix product_type (hoy solo `event`).
- Códigos promo: catálogo + usages (n=1, poco).

### Requieren fuente externa (Excel / Meta / IG)

- Proyecciones y % cumplimiento.
- Interacciones pauta / IG.
- Gastos, MCI, tareas.
- ROI ads de verdad (solo hay UTM parcial).

## 5. Queries ejemplo

Ver sección en respuesta del agente / correr en DEV read-only. Plantillas principales: ventas semanales desde transactions APPROVED; funnel; UTM; top eventos por tickets; nuevos vs recurrentes; sell-through por batch con COUNT tickets.

## 6. Riesgos

1. **Integridad referencial rota** en DEV (tx/tickets sin order).  
2. **Estados de orden ≠ estados de transacción** (APPROVED casi solo en tx).  
3. **Unix seconds vs timestamp** según tabla.  
4. **Tablas con guion** (`"order-lines"`, `"venue-types"`).  
5. **PII** en users/promoters — no replicar password; anonimizar email/phone/ID.  
6. **DEV ≠ prod** (Wompi sandbox, volumen bajo, datos de prueba “evento dashboard”).  
7. **sold_quantity** no mantenido.  
8. Confirmar siempre unidad COP vs centavos al cambiar de entorno.
