-- Fase B: aggregation over Discover operational tables (apply on Discover Postgres).
-- Does not copy rows. Requires schema analytics to exist.
-- Assumption: venues.account_id is tenant; orders.order_date is unix seconds.

CREATE OR REPLACE VIEW analytics.v_sales_by_night AS
SELECT
    v.account_id,
    o.venue_id,
    (to_timestamp(o.order_date) AT TIME ZONE 'America/Bogota')::date AS night_date,
    COUNT(*)::integer AS order_count,
    (SUM(o.total_amount) * 100)::bigint AS revenue_cents
FROM orders o
JOIN venues v ON v.id = o.venue_id
WHERE v.account_id IS NOT NULL
  AND o.order_status IS DISTINCT FROM 'canceled'
GROUP BY v.account_id, o.venue_id, 3;
