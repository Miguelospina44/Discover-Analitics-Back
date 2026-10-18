-- Setup de usuario de solo lectura para Analytics sobre Discover DB
-- Ejecutar como superusuario en la base de datos de Discover (pary_db / pary_db_test)

-- 1. Crear rol de solo lectura
CREATE ROLE analytics_readonly NOINHERIT LOGIN PASSWORD 'CHANGE-ME-RANDOM-SECRET';

-- 2. Permitir conexión
GRANT CONNECT ON DATABASE pary_db TO analytics_readonly;
-- Si es entorno de desarrollo:
-- GRANT CONNECT ON DATABASE pary_db_test TO analytics_readonly;

-- 3. Uso del schema analytics
GRANT USAGE ON SCHEMA analytics TO analytics_readonly;

-- 4. SELECT únicamente sobre vistas necesarias
GRANT SELECT ON analytics.v_nightly_attendance TO analytics_readonly;
GRANT SELECT ON analytics.v_sales_by_night TO analytics_readonly;
-- No GRANT sobre public.users ni otras tablas operativas.

-- 5. Verificar permisos
\c pary_db analytics_readonly
-- Debe funcionar:
SELECT COUNT(*) FROM analytics.v_nightly_attendance;

-- No debe funcionar (sin permisos):
-- SELECT * FROM public.users;
-- INSERT INTO analytics.v_nightly_attendance (...) VALUES (...);

-- 6. Revocar acceso (rotación de secretos)
-- \c pary_db postgres
-- REVOKE CONNECT ON DATABASE pary_db FROM analytics_readonly;
-- DROP ROLE analytics_readonly;

-- IMPORTANTE:
-- - NO otorgar permisos sobre tablas public.* (users, venues, tickets, orders)
-- - NO otorgar INSERT, UPDATE, DELETE, TRUNCATE
-- - Rotación de contraseña cada 90 días
-- - Usar TLS en producción (sslmode=require o verify-full)
-- - Verificar que vistas analytics.v_* existen antes de otorgar SELECT
