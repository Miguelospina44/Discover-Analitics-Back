# Checklist de Seguridad — Conexión a Discover DB

Completar antes de activar `DATA_SOURCE=discover` en producción.

## 1. Configuración de Base de Datos

- [ ] Usuario `analytics_readonly` creado con contraseña fuerte (≥32 caracteres random)
- [ ] `GRANT SELECT` únicamente sobre vistas `analytics.v_*` (ver `docs/discover-readonly-setup.sql`)
- [ ] **NO** hay permisos sobre `public.users`, `public.venues`, `public.tickets`, etc.
- [ ] **NO** hay permisos INSERT, UPDATE, DELETE, TRUNCATE
- [ ] Vistas `analytics.v_nightly_attendance` y `v_sales_by_night` existen y solo exponen agregados permitidos
- [ ] Vistas **no** exponen PII: sin `users.email`, `users.phone`, `users.password_hash`

## 2. Configuración de Aplicación

- [ ] Variable `DISCOVER_DATABASE_URL` configurada con `postgresql+asyncpg://`
- [ ] URL incluye `sslmode=require` o `sslmode=verify-full` en producción
- [ ] `DISCOVER_POOL_SIZE` ≤ 5 (recomendado 3)
- [ ] `DISCOVER_REQUIRE_SSL=true` en producción
- [ ] Archivo `.env` en `.gitignore` (no subir credenciales al repo)
- [ ] `.env.example` actualizado sin valores reales
- [ ] `APP_ENV=production` en producción
- [ ] `LOG_LEVEL=WARNING` o `ERROR` en producción (no INFO ni DEBUG)

## 3. Secretos y Credenciales

- [ ] `JWT_SECRET` rotado y diferente del desarrollo
- [ ] Contraseñas de BD nunca en código, solo en variables de entorno
- [ ] Contraseñas de BD nunca en logs, errores ni respuestas HTTP
- [ ] Plan de rotación de secretos documentado (recomendado: 90 días)
- [ ] Acceso a `.env` de producción restringido (ops/devops únicamente)

## 4. Validación y Testing

- [ ] Smoke test: autenticación → consulta de métricas → cierre de sesión
- [ ] Tests unitarios pasan: `pytest tests/test_discover_config.py`
- [ ] Validación al arranque: app no levanta si configuración inválida
- [ ] Verificar que errores SQL devuelven mensaje genérico (sin host, usuario, tabla)
- [ ] Verificar `data_source: discover` en respuesta de métricas
- [ ] Verificar multi-tenancy: usuarios solo ven datos de su `account_id`

## 5. Minimización de Datos

- [ ] Métricas exponen solo agregados (counts, sums, avgs)
- [ ] **NO** se expone: nombres completos, emails, teléfonos, direcciones IP
- [ ] **NO** se expone: hashes de contraseña, tokens, datos de pago
- [ ] Logs no contienen PII ni query parameters con IDs de usuario

## 6. Infraestructura

- [ ] TLS habilitado entre Analytics y Discover DB
- [ ] Certificados válidos y no auto-firmados en producción
- [ ] Red: solo Analytics puede conectarse a Discover DB (firewall/security groups)
- [ ] Monitoreo de pool de conexiones (utilización, timeouts, errores)
- [ ] Alertas configuradas: conexión caída, pool saturado, query timeout

## 7. Operación

- [ ] Documentación de rotación de secretos actualizada
- [ ] Runbook de incidentes: qué hacer si Discover DB cae
- [ ] Fallback: `DATA_SOURCE=seed` disponible para emergencias
- [ ] Proceso de rollback documentado
- [ ] Logs centralizados y monitoreados

## 8. Compliance

- [ ] Revisión de privacidad: solo datos necesarios
- [ ] GDPR/CCPA: minimización de datos, no almacenar PII innecesariamente
- [ ] Auditoría de acceso: quién tiene acceso a credenciales de producción
- [ ] Documentación de retención de datos

## 9. Post-Deployment

- [ ] Verificar métricas de producción con datos reales
- [ ] Monitorear performance: latencia de consultas, carga en Discover DB
- [ ] Validar que pool size es adecuado (no saturado, no infrautilizado)
- [ ] Programar primera rotación de `analytics_readonly` password (90 días)

## 10. Secret Scanning (Opcional pero Recomendado)

- [ ] Job `secrets` de CI corre Gitleaks (`.gitleaks.toml`)
- [ ] Pre-commit hook local opcional con la misma config
- [ ] Baseline: escaneo inicial del historial completo
- [ ] Proceso documentado: qué hacer si se detecta un secreto filtrado

---

**Aprobadores requeridos:**

- [ ] Tech Lead / Arquitecto
- [ ] DevOps / Ops
- [ ] Security / Compliance (si aplica)

**Fecha de revisión:** _________________

**Fecha de activación en producción:** _________________
