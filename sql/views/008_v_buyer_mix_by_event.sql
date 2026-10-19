-- New vs returning buyers per event. Aggregates only.
-- PRIVACY: fail-closed. Omit the row unless DISTINCT buyers >= 10.
-- Never select user_id, email, phone, name, or any PII.
-- New = first paid ticket in the tenant is this event.
-- Guest tickets (user_id NULL) are excluded from the mix.

CREATE OR REPLACE VIEW analytics.v_buyer_mix_by_event AS
WITH first_event AS (
    SELECT
        v.account_id,
        t.user_id,
        (
            ARRAY_AGG(
                COALESCE(t.event_id, tt.event_id)
                ORDER BY t.purchased_at ASC
            ) FILTER (
                WHERE COALESCE(t.event_id, tt.event_id) IS NOT NULL
            )
        )[1] AS first_event_id
    FROM tickets t
    LEFT JOIN ticket_tiers tt ON tt.id = t.tier
    LEFT JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
    JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
    WHERE v.account_id IS NOT NULL
      AND t.user_id IS NOT NULL
      AND t.purchased_at IS NOT NULL
      AND COALESCE(LOWER(t.status), 'active') NOT IN (
          'canceled', 'cancelled', 'cancelado'
      )
    GROUP BY v.account_id, t.user_id
),
event_buyers AS (
    SELECT DISTINCT
        v.account_id,
        COALESCE(t.event_id, tt.event_id) AS event_id,
        COALESCE(t.venue_id, e.venue_id) AS venue_id,
        t.user_id
    FROM tickets t
    LEFT JOIN ticket_tiers tt ON tt.id = t.tier
    LEFT JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
    JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
    WHERE v.account_id IS NOT NULL
      AND t.user_id IS NOT NULL
      AND COALESCE(t.event_id, tt.event_id) IS NOT NULL
      AND COALESCE(LOWER(t.status), 'active') NOT IN (
          'canceled', 'cancelled', 'cancelado'
      )
)
SELECT
    eb.account_id,
    eb.event_id,
    eb.venue_id,
    COUNT(DISTINCT eb.user_id)::integer AS buyer_count,
    COUNT(DISTINCT eb.user_id) FILTER (
        WHERE fe.first_event_id = eb.event_id
    )::integer AS new_buyers,
    COUNT(DISTINCT eb.user_id) FILTER (
        WHERE fe.first_event_id IS DISTINCT FROM eb.event_id
    )::integer AS returning_buyers
FROM event_buyers eb
JOIN first_event fe
    ON fe.account_id = eb.account_id
   AND fe.user_id = eb.user_id
GROUP BY eb.account_id, eb.event_id, eb.venue_id
HAVING COUNT(DISTINCT eb.user_id) >= 10;
