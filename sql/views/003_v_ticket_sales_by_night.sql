-- v1 ticket fact, aggregated: sold tickets and revenue by tenant/venue/night.
-- Preferred revenue source for Discover (tickets.price_paid_cop).
-- Grain: account_id + venue_id + night_date.
--
-- Required Discover columns:
--   tickets(id, venue_id, event_id, tier, price_paid_cop, purchased_at, status)
--   events(id, venue_id, price_cop)
--   ticket_tiers(id, price_cop)
--   venues(id, account_id)
--
-- Rules:
--   * COUNT(tickets) — never ticket_batches.sold_quantity / tier.sold_quantity.
--   * price_paid_cop is COP pesos; revenue_cents = pesos * 100.
--   * Fallback price: ticket → tier.price_cop → event.price_cop.
--   * purchased_at is timestamptz; night_date in America/Bogota.
--   * Canceled statuses excluded (EN/ES dirty enum).
--   * No PII columns.

CREATE OR REPLACE VIEW analytics.v_ticket_sales_by_night AS
SELECT
    v.account_id,
    COALESCE(t.venue_id, e.venue_id) AS venue_id,
    (t.purchased_at AT TIME ZONE 'America/Bogota')::date AS night_date,
    COUNT(t.id)::integer AS tickets_sold,
    (SUM(
        COALESCE(t.price_paid_cop, tt.price_cop, e.price_cop, 0)
    ) * 100)::bigint AS revenue_cents
FROM tickets t
LEFT JOIN ticket_tiers tt ON tt.id = t.tier
LEFT JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
WHERE v.account_id IS NOT NULL
  AND COALESCE(LOWER(t.status), 'active') NOT IN (
      'canceled', 'cancelled', 'cancelado'
  )
GROUP BY v.account_id, COALESCE(t.venue_id, e.venue_id), 3;
