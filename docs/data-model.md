# Modelo de datos inicial

## Operativo (solo lectura, `public`)

| Tabla | Uso analítico |
|---|---|
| accounts | Tenant comercial |
| venues | Local; `account_id` |
| events | Contexto de noche |
| orders | Ventas / monto |
| tickets | Asistencia proxy: `redemption_date` |
| users | Perfil si hay consentimiento; no loguear PII |
| tracking_* | Embudo; fase posterior |

## Analítico derivado (vistas)

- `analytics.v_nightly_attendance` — tickets redimidos por `account_id`, `venue_id`, fecha.

No son tablas físicas. Se refrescan al consultar (vista simple). Si el volumen crece: vista materializada + job.

## Metadatos de consultoría (tablas `analytics`)

| Tabla | Qué |
|---|---|
| users | Login de esta app; `account_id` |
| engagements | Estudio: cliente, periodo, alcance, objetivos |
| findings | Hallazgo + evidencia + impacto + confianza |
| recommendations | Acción, prioridad, owner, fecha |

Hipótesis, escenarios, plan de acción y entregables: fase 4, mismas reglas de tenant.

## Calidad

Cada medida expone `as_of`, `unit`, `definition`, `data_quality` (`ok` \| `partial` \| `missing`).
