# ADR 0005 — DB aislada primero, Discover después

## Contexto

ADR 0001 asumía una sola Postgres Discover desde el día 1. Eso acoplaba el diseño del schema de consultoría a tablas operativas (`tickets`, `venues`) y bloqueaba pruebas locales sin datos de Pary.

## Decisión

1. **Fase A:** base `discover_analytics` vacía + schema `analytics` (auth, consultoría, facts seed). `DATA_SOURCE=seed`.
2. **Fase B:** misma app; `DATA_SOURCE=discover`; métricas leen vistas `analytics.v_*` sobre Discover; la escritura de consultoría sigue en schema `analytics`.

## Consecuencias

- Smoke E2E no depende de redenciones reales.
- El cable del repositorio es un switch por env (`seed` | `discover`).
- Cuando se conecte Discover, no hay que rediseñar engagements/findings.
