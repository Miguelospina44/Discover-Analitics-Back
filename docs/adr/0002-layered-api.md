# ADR 0002 — Capas estrictas

## Contexto

Hay que tratar datos de boletas y de consultoría sin mezclar SQL en routers.

## Decisión

Routers solo orquestan. Repos no conocen HTTP. Medidas no conocen FastAPI. Modelos ORM ≠ schemas de API.

## Consecuencias

Más archivos al inicio; el vertical slice (asistencia nocturna + engagement) valida el recorrido antes de más módulos.
