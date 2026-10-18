-- Cross-tenant market trend by ISO weekday (1=Monday … 7=Sunday, Bogotá).
-- Grain is the weekday, not a venue. Averages of per-venue-night points.
-- Fail-closed: ≥5 venues, ≥3 accounts, ≥20 tickets that weekday.

CREATE OR REPLACE VIEW analytics.v_market_by_weekday AS
WITH per_venue_day AS (
    SELECT
        EXTRACT(ISODOW FROM s.night_date)::integer AS iso_weekday,
        s.account_id,
        s.venue_id,
        SUM(s.tickets_sold)::integer AS tickets_sold,
        SUM(s.revenue_cents)::bigint AS revenue_cents,
        CASE
            WHEN SUM(s.tickets_sold) > 0
            THEN SUM(s.revenue_cents) / SUM(s.tickets_sold)
        END AS avg_ticket_cents
    FROM analytics.v_ticket_sales_by_night s
    GROUP BY 1, s.account_id, s.venue_id
)
SELECT
    iso_weekday,
    COUNT(DISTINCT venue_id)::integer AS venues_in_sample,
    COUNT(DISTINCT account_id)::integer AS accounts_in_sample,
    ROUND(AVG(tickets_sold)::numeric, 2) AS avg_tickets_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tickets_sold)
        AS median_tickets_per_venue,
    ROUND(AVG(revenue_cents)::numeric, 0) AS avg_revenue_cents_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_ticket_cents)
        AS median_avg_ticket_cents
FROM per_venue_day
GROUP BY iso_weekday
HAVING COUNT(DISTINCT venue_id) >= 5
   AND COUNT(DISTINCT account_id) >= 3
   AND SUM(tickets_sold) >= 20;
