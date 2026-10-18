-- New vs returning buyers per calendar month (America/Bogota).
-- PRIVACY: fail-closed. Omit the row unless DISTINCT buyers >= 10.
-- Never select user_id or any PII. Guests (user_id NULL) excluded.

CREATE OR REPLACE VIEW analytics.v_buyer_mix_by_month AS
WITH first_month AS (
    SELECT
        v.account_id,
        t.user_id,
        MIN(
            DATE_TRUNC(
                'month',
                t.purchased_at AT TIME ZONE 'America/Bogota'
            )::date
        ) AS first_order_month
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
month_buyers AS (
    SELECT DISTINCT
        v.account_id,
        DATE_TRUNC(
            'month',
            t.purchased_at AT TIME ZONE 'America/Bogota'
        )::date AS order_month,
        t.user_id
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
)
SELECT
    mb.account_id,
    mb.order_month,
    COUNT(DISTINCT mb.user_id)::integer AS buyer_count,
    COUNT(DISTINCT mb.user_id) FILTER (
        WHERE fm.first_order_month = mb.order_month
    )::integer AS new_buyers,
    COUNT(DISTINCT mb.user_id) FILTER (
        WHERE fm.first_order_month < mb.order_month
    )::integer AS returning_buyers
FROM month_buyers mb
JOIN first_month fm
    ON fm.account_id = mb.account_id
   AND fm.user_id = mb.user_id
GROUP BY mb.account_id, mb.order_month
HAVING COUNT(DISTINCT mb.user_id) >= 10;
