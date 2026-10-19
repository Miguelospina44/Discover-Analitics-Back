-- Cross-tenant market trend by cover/ticket price band (COP pesos, not cents).
-- Bands: free=0; entry≤40000; standard≤80000; high≤150000; premium_cover>150000.
-- OUTPUT: no tenant/venue IDs. Fail-closed: ≥5 venues, ≥3 accounts, ≥20 tickets.

CREATE OR REPLACE VIEW analytics.v_market_by_price_band AS
WITH priced AS (
    SELECT
        s.account_id,
        s.venue_id,
        s.tickets_sold,
        s.revenue_cents,
        CASE
            WHEN s.tickets_sold <= 0 THEN 'free'
            WHEN (s.revenue_cents / s.tickets_sold) / 100.0 <= 0 THEN 'free'
            WHEN (s.revenue_cents / s.tickets_sold) / 100.0 <= 40000 THEN 'entry'
            WHEN (s.revenue_cents / s.tickets_sold) / 100.0 <= 80000 THEN 'standard'
            WHEN (s.revenue_cents / s.tickets_sold) / 100.0 <= 150000 THEN 'high'
            ELSE 'premium_cover'
        END AS price_band
    FROM analytics.v_ticket_sales_by_night s
),
per_venue AS (
    SELECT
        price_band,
        account_id,
        venue_id,
        SUM(tickets_sold)::integer AS tickets_sold,
        SUM(revenue_cents)::bigint AS revenue_cents,
        CASE
            WHEN SUM(tickets_sold) > 0
            THEN SUM(revenue_cents) / SUM(tickets_sold)
        END AS avg_ticket_cents
    FROM priced
    GROUP BY price_band, account_id, venue_id
)
SELECT
    price_band,
    COUNT(DISTINCT venue_id)::integer AS venues_in_sample,
    COUNT(DISTINCT account_id)::integer AS accounts_in_sample,
    ROUND(AVG(tickets_sold)::numeric, 2) AS avg_tickets_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tickets_sold)
        AS median_tickets_per_venue,
    ROUND(AVG(revenue_cents)::numeric, 0) AS avg_revenue_cents_per_venue,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_ticket_cents)
        AS median_avg_ticket_cents
FROM per_venue
GROUP BY price_band
HAVING COUNT(DISTINCT venue_id) >= 5
   AND COUNT(DISTINCT account_id) >= 3
   AND SUM(tickets_sold) >= 20;
