-- Sell-through by ticket_tier (price stage), not ticket_batches.
-- Grain: account + event + tier.
-- COUNT(tickets) / ticket_tiers.capacity.
-- NEVER use sold_quantity (DEV inventory: always 0 / unmaintained).
-- No PII. Tenant via venues.account_id.

CREATE OR REPLACE VIEW analytics.v_sellthrough_by_tier AS
SELECT
    v.account_id,
    e.id AS event_id,
    e.venue_id,
    tt.id AS tier_id,
    tt.price_cop AS tier_price_cop,
    NULLIF(tt.capacity, 0) AS tier_capacity,
    COUNT(t.id)::integer AS tickets_sold,
    CASE
        WHEN NULLIF(tt.capacity, 0) IS NULL THEN NULL
        ELSE ROUND((COUNT(t.id)::numeric / tt.capacity) * 100, 2)
    END AS sellthrough_pct
FROM ticket_tiers tt
JOIN events e ON e.id = tt.event_id
JOIN venues v ON v.id = e.venue_id
LEFT JOIN tickets t
    ON t.tier = tt.id
    AND COALESCE(LOWER(t.status), 'active') NOT IN (
        'canceled', 'cancelled', 'cancelado'
    )
WHERE v.account_id IS NOT NULL
GROUP BY
    v.account_id,
    e.id,
    e.venue_id,
    tt.id,
    tt.price_cop,
    tt.capacity;
