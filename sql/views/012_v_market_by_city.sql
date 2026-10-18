-- Cross-tenant market trend by normalized city.
-- OUTPUT has no account_id, venue_id, event_id, or PII — averages/medians only.
-- Fail-closed: omit the city unless
--   DISTINCT venues >= 5 AND DISTINCT accounts >= 3 AND tickets >= 20.
-- Totals are not published (a neighbor must not subtract to recover one venue).

CREATE OR REPLACE VIEW analytics.v_market_by_city AS
WITH per_venue AS (
    SELECT
        vn.city_normalized,
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
    WHERE vn.city_normalized IS NOT NULL
    GROUP BY vn.city_normalized, vn.account_id, vn.venue_id
)
SELECT
    city_normalized,
    COUNT(DISTINCT venue_id)::integer AS venues_in_sample,
    COUNT(DISTINCT account_id)::integer AS accounts_in_sample,
    ROUND(AVG(tickets_sold)::numeric, 2) AS avg_tickets_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tickets_sold)
        AS median_tickets_per_venue,
    ROUND(AVG(revenue_cents)::numeric, 0) AS avg_revenue_cents_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_ticket_cents)
        AS median_avg_ticket_cents
FROM per_venue
GROUP BY city_normalized
HAVING COUNT(DISTINCT venue_id) >= 5
   AND COUNT(DISTINCT account_id) >= 3
   AND SUM(tickets_sold) >= 20;
