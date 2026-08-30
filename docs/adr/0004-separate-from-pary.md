# ADR 0004 — API propia, no pary_backend

## Contexto

Discover ya tiene un backend Node/Sequelize para covers.

## Decisión

Analítica es un servicio FastAPI separado. Comparte Postgres, no comparte proceso, JWT ni deploys de Pary.

## Consecuencias

Hay que crear un rol de lectura y el schema `analytics` en el mismo cluster. No se llama a las rutas de `pary_backend` para KPIs.
