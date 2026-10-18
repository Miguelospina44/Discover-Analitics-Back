-- v1 event grain: revenue, tickets sold, occupancy, sell-through.
-- Tenant: venues.account_id. Aggregates only — no ticket/user rows.
--
-- Capacity: events.capacity, else venues.aforo.
-- Sold tickets: COUNT(tickets), never sold_quantity.
-- Occupancy: redeemed / aforo (physical door).
-- Sell-through: sold / event capacity (inventory).
-- Money: price_paid_cop (COP pesos) * 100 → revenue_cents.
-- Tickets are matched once: event_id or tier belonging to the event.

CREATE OR REPLACE VIEW analytics.v_event_metrics AS
SELECT
    v.account_id,
    e.id AS event_id,
    e.venue_id,
    e.date::date AS event_date,
    NULLIF(e.capacity, 0) AS event_capacity,
    NULLIF(v.aforo, 0) AS venue_aforo,
    COUNT(t.id)::integer AS tickets_sold,
    COUNT(t.id) FILTER (
        WHERE t.redemption_date IS NOT NULL
    )::integer AS tickets_redeemed,
    (SUM(
        COALESCE(
            t.price_paid_cop,
            (
                SELECT tt.price_cop
                FROM ticket_tiers tt
                WHERE tt.id = t.tier
            ),
            e.price_cop,
            0
        )
    ) * 100)::bigint AS revenue_cents,
    CASE
        WHEN NULLIF(e.capacity, 0) IS NULL THEN NULL
        ELSE ROUND((COUNT(t.id)::numeric / e.capacity) * 100, 2)
    END AS sellthrough_pct,
    CASE
        WHEN NULLIF(v.aforo, 0) IS NULL THEN NULL
        ELSE ROUND(
            (
                COUNT(t.id) FILTER (WHERE t.redemption_date IS NOT NULL)
            )::numeric / v.aforo * 100,
            2
        )
    END AS occupancy_pct
FROM events e
JOIN venues v ON v.id = e.venue_id
LEFT JOIN tickets t
    ON COALESCE(LOWER(t.status), 'active') NOT IN (
        'canceled', 'cancelled', 'cancelado'
    )
    AND (
        t.event_id = e.id
        OR t.tier IN (
            SELECT tt.id FROM ticket_tiers tt WHERE tt.event_id = e.id
        )
    )
WHERE v.account_id IS NOT NULL
GROUP BY
    v.account_id,
    e.id,
    e.venue_id,
    e.date,
    e.capacity,
    e.price_cop,
    v.aforo;
