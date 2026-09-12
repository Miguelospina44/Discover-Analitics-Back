# Discover Analytics Back

API independiente de Discover (Pary) y de FUA/Nexus Glass.

- Nombres técnicos en inglés.
- Documentación funcional y textos de producto en español.
- Una sola base Postgres (la de Discover). Escrituras nuevas solo en schema `analytics`.
- Sin agentes de IA, Azure AI Foundry, Odoo, SharePoint, Google Sheets ni fallbacks de archivos.
- Autorización fail-closed. El frontend no define roles.
- No copiar branding, dominios ni reglas FUA.
- No modificar `pary_backend`. El recaudo NFC vive en Discover, no aquí.
- PRs hacia `dev` de Discover no aplican a este repo; no mergear `dev`/`main` de Pary.
- Trabajo en ramas `cursor/<nombre>`; los PRs de este repo apuntan a `dev` (no a `main`).

## Canario (anti-alucinación)

Canary token: `DISCOVER-BACK-CANARY-v1`.

- Si leíste y estás aplicando este archivo, incluí el canary token exactamente una vez al inicio de tu primera respuesta de la sesión y en toda descripción de PR o plan de implementación. Si el token no aparece, asumí que las reglas NO se cargaron.
- Si no podés encontrar o leer esta sección, decilo explícitamente en vez de adivinar.
- No inventes archivos, rutas, columnas, endpoints, comandos ni migraciones: verificá contra el repo (o corriendo el código) antes de afirmarlos. Lo no verificado se marca como "no verificado".
- Ante duda sobre una regla de negocio o el esquema, preguntá o explicitá el supuesto; no rellenes con suposiciones.
