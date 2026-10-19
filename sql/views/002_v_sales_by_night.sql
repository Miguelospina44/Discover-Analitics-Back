-- Fase B compatibility view: paid orders per venue-night.
-- Does not copy rows. Requires schema analytics.
-- Tenant: venues.account_id. Repositories MUST also filter account_id.
--
-- Money: Discover stores order totals in COP pesos (not cents).
-- revenue_cents = pesos * 100 to match analytics.fact_sales_by_night.
--
-- Paid statuses only. Do NOT mix transactions.status = 'APPROVED'
-- (DEV inventory: many approved txs are orphans vs current orders).
-- Do NOT treat INITIAL_TRANSACTION as a sale (open carts).

CREATE OR REPLACE VIEW analytics.v_sales_by_night AS
SELECT
    v.account_id,
    o.venue_id,
    (to_timestamp(o.order_date) AT TIME ZONE 'America/Bogota')::date AS night_date,
    COUNT(*)::integer AS order_count,
    (SUM(COALESCE(o.total_amount, 0)) * 100)::bigint AS revenue_cents
FROM orders o
JOIN venues v ON v.id = o.venue_id
WHERE v.account_id IS NOT NULL
  AND o.order_status IN ('COMPLETED', 'CONFIRMED_FREE', 'APPROVED')
GROUP BY v.account_id, o.venue_id, 3;
