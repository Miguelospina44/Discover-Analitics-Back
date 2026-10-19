-- Tickets sold in windows before the event night (sales velocity).
-- Grain: account + event + window_key.
-- Windows: early_bird (>7d), week_before (3-7d), last_days (1-2d), same_day (0d).
-- Source: tickets.purchased_at vs events.date. COUNT(tickets) only.
-- Tenant via venues.account_id. No PII.

CREATE OR REPLACE VIEW analytics.v_sales_velocity AS
SELECT
    v.account_id,
    e.id AS event_id,
    e.venue_id,
    e.date::date AS event_date,
    CASE
        WHEN (e.date::date - (t.purchased_at AT TIME ZONE 'America/Bogota')::date) > 7
            THEN 'early_bird'
        WHEN (e.date::date - (t.purchased_at AT TIME ZONE 'America/Bogota')::date) >= 3
            THEN 'week_before'
        WHEN (e.date::date - (t.purchased_at AT TIME ZONE 'America/Bogota')::date) >= 1
            THEN 'last_days'
        ELSE 'same_day'
    END AS window_key,
    COUNT(t.id)::integer AS tickets_sold,
    (SUM(
        COALESCE(t.price_paid_cop, tt.price_cop, e.price_cop, 0)
    ) * 100)::bigint AS revenue_cents
FROM tickets t
LEFT JOIN ticket_tiers tt ON tt.id = t.tier
JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
WHERE v.account_id IS NOT NULL
  AND t.purchased_at IS NOT NULL
  AND e.date IS NOT NULL
  AND COALESCE(LOWER(t.status), 'active') NOT IN (
      'canceled', 'cancelled', 'cancelado'
  )
GROUP BY
    v.account_id,
    e.id,
    e.venue_id,
    e.date,
    5;
