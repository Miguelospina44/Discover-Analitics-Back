-- Peak purchase hours (0-23) in America/Bogota.
-- Grain: account_id + hour_of_day. Aggregated tickets only. No PII.
-- Source: tickets.purchased_at. COUNT(tickets), never sold_quantity.

CREATE OR REPLACE VIEW analytics.v_purchase_hours AS
SELECT
    v.account_id,
    EXTRACT(
        HOUR FROM (t.purchased_at AT TIME ZONE 'America/Bogota')
    )::integer AS hour_of_day,
    COUNT(t.id)::integer AS tickets_sold,
    (SUM(
        COALESCE(t.price_paid_cop, tt.price_cop, e.price_cop, 0)
    ) * 100)::bigint AS revenue_cents
FROM tickets t
LEFT JOIN ticket_tiers tt ON tt.id = t.tier
LEFT JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
WHERE v.account_id IS NOT NULL
  AND t.purchased_at IS NOT NULL
  AND COALESCE(LOWER(t.status), 'active') NOT IN (
      'canceled', 'cancelled', 'cancelado'
  )
GROUP BY v.account_id, 2;
