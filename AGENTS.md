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
