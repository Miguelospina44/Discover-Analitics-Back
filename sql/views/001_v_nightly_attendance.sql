-- Read-only aggregation over Discover operational tables.
-- Apply on the same Postgres. Does not copy rows.
-- Assumption: venues.account_id is the tenant. tickets.redemption_date is unix seconds.

CREATE OR REPLACE VIEW analytics.v_nightly_attendance AS
SELECT
    v.account_id,
    t.venue_id,
    (to_timestamp(t.redemption_date) AT TIME ZONE 'America/Bogota')::date AS night_date,
    COUNT(*)::integer AS redeemed_tickets
FROM tickets t
JOIN venues v ON v.id = t.venue_id
WHERE t.redemption_date IS NOT NULL
  AND v.account_id IS NOT NULL
GROUP BY v.account_id, t.venue_id, 3;
