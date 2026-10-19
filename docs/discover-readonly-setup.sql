-- Setup de usuario de solo lectura para Analytics sobre Discover DB
-- Ejecutar como superusuario en Discover (pary_db / pary_db_test).
-- Contraseña: ponerla en el entorno, nunca commitear un secreto real.
-- Vistas: las 16 de sql/views. SELECT solo sobre esas vistas.
-- v_market_by_* no tienen account_id: agregados anónimos entre clientes.

-- 1. Crear rol de solo lectura
CREATE ROLE analytics_readonly NOINHERIT LOGIN PASSWORD 'CHANGE-ME-RANDOM-SECRET';

-- 2. Permitir conexión
GRANT CONNECT ON DATABASE pary_db TO analytics_readonly;
-- GRANT CONNECT ON DATABASE pary_db_test TO analytics_readonly;

-- 3. Uso del schema analytics
GRANT USAGE ON SCHEMA analytics TO analytics_readonly;

-- 4. SELECT únicamente sobre vistas agregadas (mínimo privilegio)
GRANT SELECT ON analytics.v_nightly_attendance TO analytics_readonly;
GRANT SELECT ON analytics.v_sales_by_night TO analytics_readonly;
GRANT SELECT ON analytics.v_ticket_sales_by_night TO analytics_readonly;
GRANT SELECT ON analytics.v_event_metrics TO analytics_readonly;
GRANT SELECT ON analytics.v_sellthrough_by_tier TO analytics_readonly;
GRANT SELECT ON analytics.v_sales_velocity TO analytics_readonly;
GRANT SELECT ON analytics.v_purchase_hours TO analytics_readonly;
GRANT SELECT ON analytics.v_buyer_mix_by_event TO analytics_readonly;
GRANT SELECT ON analytics.v_buyer_mix_by_month TO analytics_readonly;
GRANT SELECT ON analytics.v_activity_by_weekday TO analytics_readonly;
GRANT SELECT ON analytics.v_venues_normalized TO analytics_readonly;
GRANT SELECT ON analytics.v_audience_by_gender_age TO analytics_readonly;
GRANT SELECT ON analytics.v_market_by_city TO analytics_readonly;
GRANT SELECT ON analytics.v_market_by_venue_type TO analytics_readonly;
GRANT SELECT ON analytics.v_market_by_weekday TO analytics_readonly;
GRANT SELECT ON analytics.v_market_by_price_band TO analytics_readonly;

-- 5. Verificar
-- \c pary_db analytics_readonly
-- SELECT COUNT(*) FROM analytics.v_nightly_attendance;
-- No debe funcionar:
-- SELECT * FROM public.users;
-- SELECT password_hash FROM public.users;
-- INSERT INTO analytics.v_nightly_attendance (...) VALUES (...);

-- 6. Rotación
-- REVOKE CONNECT ON DATABASE pary_db FROM analytics_readonly;
-- DROP ROLE analytics_readonly;

-- IMPORTANTE:
-- - NO GRANT sobre public.users, venues, tickets, orders, events, ticket_tiers
-- - NO INSERT/UPDATE/DELETE/TRUNCATE
-- - Las vistas v_buyer_mix_* usan user_id solo dentro del SQL; el SELECT de la vista no lo expone
-- - Columnas permitidas: app/domain/discover_views.py
-- - TLS en producción (sslmode=require o verify-full)
