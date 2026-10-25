# ADR 0008 — Respuestas de “Detalles Evento” desde Google Sheets

## Contexto

Los colectivos llenan el Google Form “Detalles Evento”. Las respuestas caen en una Google Sheet (pestaña `Respuestas de formulario 1`). Analytics debe listar y resumir esas filas **sin** exponer PII financiero ni de identidad, y **sin** que un local vea el formulario de un colectivo.

## Decisión

### Fuente

- Cliente de **solo lectura** (`spreadsheets.readonly`).
- Credenciales solo por entorno: `GOOGLE_SHEETS_CREDENTIALS_FILE`, `EVENT_FORM_SHEET_ID`.
- `EVENT_FORM_SOURCE=fixture` (default) sirve un JSON de ejemplo con `is_demo=true`. No llama a Google.
- `EVENT_FORM_SOURCE=sheets` exige archivo de cuenta de servicio + sheet id. Si faltan, **no arranca**.
- Caché en memoria de filas **ya sanitizadas**, TTL 5 min (`EVENT_FORM_CACHE_TTL_SECONDS`).

### Allowlist

El parser empareja columnas por encabezado (no por letra). Correo, cuenta bancaria, banco y cédula/NIT **nunca** se copian. Cualquier encabezado no reconocido se descarta (fail-closed).

### Alias de colectivo

`app/data/collective_aliases.json` (o `COLLECTIVE_ALIASES_FILE`): `alias → account_id` + nombre canónico. Discover lo mantiene. “Coffe” y “Coffee Club” son el mismo tenant. Filas sin mapa: `assignment_status=sin_asignar`, visibles **solo** a `super_admin`.

### Quién ve qué (regla de Miguel)

No se crea un rol nuevo.

| Actor | Resultado |
|---|---|
| `super_admin` (staff interno de Discover) | Todas las filas, incluidas `sin_asignar` |
| `tenant_kind=collective` u `organizer` | Solo filas mapeadas a **su** `account_id` |
| `venue` / `group` (cualquier rol de app: admin, consultant, viewer) | **403** |

`admin` de un local **no** es el admin de Discover. El admin interno ya existe: `super_admin` (ADR 0007).

### Comisiones y suciedad

No hay catálogo cerrado de comisión. `11.5%` se guarda como `11.5`. Fechas o preventas ilegibles no tumban la fila (`has_presale=null`, `event_at=null`, `event_at_raw` conservado).

## Consecuencias

- Miguel crea una cuenta de servicio, comparte la Sheet en modo **lector** con su email, y pone la ruta JSON + el id en `.env` local.
- Este repo no commitea el JSON de la cuenta ni se conecta a la Sheet real en tests.
