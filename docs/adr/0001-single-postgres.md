# ADR 0001 — Una sola Postgres (Discover)

## Contexto

Fundación usaba loaders (Odoo, SharePoint, Sheets, archivos). Discover ya tiene el operacional en Postgres.

## Decisión

Un `DATABASE_URL`. Lecturas analíticas por vistas. Escrituras de consultoría en schema `analytics`. Sin segundo cluster el día 1.

## Consecuencias

Un incidente de Discover afecta esta API. Mitigación: vistas, timeouts, readiness que comprueba `SELECT 1`, no un warehouse nuevo.
