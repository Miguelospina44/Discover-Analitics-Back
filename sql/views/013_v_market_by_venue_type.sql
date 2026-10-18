-- Cross-tenant market trend by normalized venue type (bar / discoteca / …).
-- OUTPUT has no tenant or venue identifiers. Averages and medians only.
-- Fail-closed: ≥5 venues, ≥3 accounts, ≥20 tickets in the type.

CREATE OR REPLACE VIEW analytics.v_market_by_venue_type AS
WITH per_venue AS (
    SELECT
        vn.venue_type_normalized,
        vn.account_id,
        vn.venue_id,
        SUM(s.tickets_sold)::integer AS tickets_sold,
        SUM(s.revenue_cents)::bigint AS revenue_cents,
        CASE
            WHEN SUM(s.tickets_sold) > 0
            THEN SUM(s.revenue_cents) / SUM(s.tickets_sold)
        END AS avg_ticket_cents
    FROM analytics.v_ticket_sales_by_night s
    JOIN analytics.v_venues_normalized vn ON vn.venue_id = s.venue_id
    WHERE vn.venue_type_normalized IS NOT NULL
      AND vn.venue_type_normalized <> 'unknown'
    GROUP BY vn.venue_type_normalized, vn.account_id, vn.venue_id
)
SELECT
    venue_type_normalized,
    COUNT(DISTINCT venue_id)::integer AS venues_in_sample,
    COUNT(DISTINCT account_id)::integer AS accounts_in_sample,
    ROUND(AVG(tickets_sold)::numeric, 2) AS avg_tickets_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tickets_sold)
        AS median_tickets_per_venue,
    ROUND(AVG(revenue_cents)::numeric, 0) AS avg_revenue_cents_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_ticket_cents)
        AS median_avg_ticket_cents
FROM per_venue
GROUP BY venue_type_normalized
HAVING COUNT(DISTINCT venue_id) >= 5
   AND COUNT(DISTINCT account_id) >= 3
   AND SUM(tickets_sold) >= 20;
