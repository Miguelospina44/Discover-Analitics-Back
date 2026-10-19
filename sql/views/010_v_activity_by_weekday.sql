-- Ticket sales by ISO weekday (1=Monday … 7=Sunday), America/Bogota.
-- Grain: account_id + iso_weekday. Aggregated only. No PII.
-- Source: tickets.purchased_at. COUNT(tickets), never sold_quantity.

CREATE OR REPLACE VIEW analytics.v_activity_by_weekday AS
SELECT
    v.account_id,
    EXTRACT(
        ISODOW FROM (t.purchased_at AT TIME ZONE 'America/Bogota')
    )::integer AS iso_weekday,
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
