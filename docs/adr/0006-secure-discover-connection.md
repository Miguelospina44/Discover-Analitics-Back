# ADR 0006 — Conexión segura de solo lectura a Discover DB

## Contexto

Con DATA_SOURCE=discover, Analytics debe leer vistas `analytics.v_*` desde la Postgres de Discover para alimentar métricas. Esto introduce riesgos de seguridad y exposición de datos que requieren controles técnicos y organizacionales.

### Requisitos de seguridad

1. **Separación de conexiones:** lectura de Discover separada de escritura de Analytics
2. **Solo lectura:** permisos mínimos (SELECT únicamente sobre vistas necesarias)
3. **Multi-tenancy:** todas las consultas filtran por `account_id` del token
4. **Secretos:** credenciales solo en variables de entorno, nunca en código ni logs
5. **Fail-closed:** configuración inválida impide el arranque
6. **Minimización de datos:** solo agregados, sin PII ni hashes de contraseña
7. **TLS:** cifrado en tránsito en producción
8. **Manejo de errores:** sin filtración de detalles internos (DSN, hosts, SQL)

Este ADR **revisa** ADR 0001 (un solo `DATABASE_URL` el día 1) y **completa** ADR 0005: la base propia de Analytics permanece aislada; Discover se lee por un segundo DSN de solo lectura.

## Decisión

### 1. Configuración

Nuevas variables de entorno:

```bash
DISCOVER_DATABASE_URL=postgresql+asyncpg://analytics_readonly:SECRET@host:5432/pary_db?sslmode=require
DISCOVER_POOL_SIZE=3
DISCOVER_MAX_OVERFLOW=2
DISCOVER_POOL_TIMEOUT=10
DISCOVER_REQUIRE_SSL=true
```

- **DISCOVER_DATABASE_URL** requerido cuando `DATA_SOURCE=discover`
- Validación al inicio: falta driver asyncpg o sslmode → error fatal
- Pool pequeño (3+2) para limitar carga sobre Discover
- Timeout de 10s para evitar conexiones colgadas

### 2. Pool separado con READ ONLY

El factory de Discover (`create_discover_session_factory`) crea un engine distinto, con pool 3+2, `pool_pre_ping`, timeouts de pool/conexión/comando y:

- `default_transaction_read_only=on` (sesión Postgres)
- `statement_timeout` desde `QUERY_TIMEOUT_SECONDS`
- `ssl=True` cuando `DISCOVER_REQUIRE_SSL=true`
- `application_name=discover-analytics-readonly`

El factory cuelga en `app.state.discover_session_factory`. `MetricsDbSession` elige Discover o la base propia según `data_source`. No se abre conexión en el arranque; el pool se crea en memoria.

### 3. Multi-tenancy en consultas

Toda consulta sobre vistas Discover filtra por `account_id`:

```sql
SELECT ... FROM analytics.v_sales_by_night
WHERE account_id = :account_id
  AND night_date >= :period_start
  AND night_date <= :period_end
```

El `account_id` proviene del JWT (verificado por `get_principal`), nunca del input del usuario.

### 4. Permisos de base de datos

Esquema de permisos recomendado en Discover DB:

```sql
CREATE ROLE analytics_readonly NOINHERIT LOGIN PASSWORD 'random-secret';
GRANT CONNECT ON DATABASE pary_db TO analytics_readonly;
GRANT USAGE ON SCHEMA analytics TO analytics_readonly;
GRANT SELECT ON analytics.v_nightly_attendance TO analytics_readonly;
GRANT SELECT ON analytics.v_sales_by_night TO analytics_readonly;
-- GRANT SELECT solo a vistas agregadas existentes; no a public.*
```

**NO** otorgar:
- Permisos sobre tablas `public.*` (venues, users, tickets, orders)
- INSERT, UPDATE, DELETE, TRUNCATE
- Acceso a columnas PII: `users.password_hash`, `users.email`, `users.phone`

### 5. Vistas con minimización de datos

Las vistas `analytics.v_*` deben:
- Filtrar por `account_id` (permitir que Analytics aplique WHERE)
- Exponer solo agregados o IDs, sin datos personales
- Ejemplo: sí `venue_id`, `night_date`, `order_count`; no `user.email`, `user.phone`

### 6. Manejo de errores sin filtración

```python
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request, exc):
    logger.error(f"Error de base de datos: {type(exc).__name__}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error al procesar la solicitud. Intenta de nuevo más tarde."}
    )
```

- Errores SQL loguean solo el tipo de excepción, no el mensaje completo
- No se devuelven al cliente: host, puerto, usuario, tabla, columna
- ProgrammingError → "missing" data_quality, sin exponer SQL

### 7. Logging seguro

- `sqlalchemy.engine` en nivel WARNING (no INFO ni DEBUG en producción)
- Nunca loguear: `DISCOVER_DATABASE_URL`, `JWT_SECRET`, credenciales
- Logs estructurados sin interpolar variables de entorno

### 8. Validación al arranque

`Settings.validate_startup()` corre en el lifespan. Mensajes de error **no** incluyen DSN, host ni password. Fallos:

- `DATA_SOURCE=discover` sin `DISCOVER_DATABASE_URL`
- driver distinto de asyncpg
- DSN igual a `DATABASE_URL`
- `sslmode` ausente si `DISCOVER_REQUIRE_SSL=true`
- `JWT_SECRET` de desarrollo cuando `APP_ENV=production`

Fail-closed: configuración incorrecta impide que la app levante.

CI escanea secretos con Gitleaks (`.gitleaks.toml` + job `secrets` en `.github/workflows/ci.yml`).

### 9. Rotación de secretos

1. Crear nuevo usuario `analytics_readonly_v2` con mismo GRANT
2. Actualizar `DISCOVER_DATABASE_URL` en entorno (sin downtime si usa reload)
3. Verificar métricas
4. Revocar permisos del usuario anterior: `REVOKE CONNECT ON DATABASE ... FROM analytics_readonly`
5. `DROP ROLE analytics_readonly`

Rotación recomendada: cada 90 días, tras cambio de personal con acceso, o ante incidente.

### 10. Checklist de seguridad

Antes de activar DATA_SOURCE=discover en producción:

- [ ] Usuario `analytics_readonly` creado con SELECT únicamente sobre vistas `analytics.v_*`
- [ ] Vistas `analytics.v_*` aplicadas y probadas en Discover DB
- [ ] `DISCOVER_DATABASE_URL` con `sslmode=require` o `sslmode=verify-full`
- [ ] Pool size ≤ 5 para no saturar Discover
- [ ] `.env` en `.gitignore` (no subir credenciales)
- [ ] `APP_ENV=production` → logging en WARNING, no INFO
- [ ] Smoke test de autenticación → métricas → cierre de sesión
- [ ] Verificar que errores SQL devuelven mensaje genérico al cliente
- [ ] Rotación de `JWT_SECRET` independiente de Discover
- [ ] Monitoreo: pool usage, query timeout, conexiones colgadas

## Consecuencias

### Positivas

- Separación clara: Analytics no puede escribir en Discover
- Multi-tenancy forzado a nivel de SQL (WHERE account_id)
- Fail-closed: configuración incorrecta → app no levanta
- Minimización: solo datos agregados, sin PII
- Rotación de secretos sin cambio de código

### Negativas

- Complejidad: dos pools de conexiones
- Dependencia: si Discover DB cae, métricas fallan (pero consultoría sigue)
- Latencia: consultas a Discover pueden ser lentas si tablas crecen

### Mitigación

- Pool pequeño + timeout → protege Discover
- `data_source=seed` como fallback de desarrollo
- Cache (TTL 60s) reduce carga sobre vistas
- Monitoreo independiente de disponibilidad Discover vs Analytics

## Alternativas descartadas

1. **Una sola conexión:** expone Discover a escrituras accidentales
2. **Copiar datos a Analytics:** desnormalización, lag, GDPR
3. **API Gateway entre Analytics y Discover:** overhead, latencia
4. **Credenciales en código:** violación de buenas prácticas
