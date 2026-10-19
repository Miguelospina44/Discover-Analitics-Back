-- Aggregated buyers by declared gender × age band.
-- OUTPUT has no user_id and no profile fields. COUNT(DISTINCT user_id) only.
--
-- ASSUMED Discover columns (Miguel must verify on the real DB):
--   public.users.id
--   public.users.gender          text, nullable
--   public.users.birth_date      date, nullable
--   public.tickets.user_id
--   public.tickets.event_id / tickets.tier → ticket_tiers.event_id
--   public.tickets.venue_id
--   public.tickets.status
--   public.events.id, events.date, events.venue_id
--   public.venues.id, venues.account_id
--
-- If the real names differ, adjust this view before applying it.
-- Documented alternatives (NOT in this SQL): users.birthdate, users.date_of_birth,
-- users.age, users.sexo. Do not invent values when the column is null.
--
-- Age is years at events.date (America/Bogota calendar date). Under 18 or
-- missing birth_date → age_band sin_dato. Null/blank/unknown gender → sin_dato.
-- Guest tickets (user_id IS NULL) are excluded (no profile to aggregate).
-- k-anonymity (< 10) is applied in the API after period + scope rollup,
-- so two small events can still form a publishable cell.

CREATE OR REPLACE VIEW analytics.v_audience_by_gender_age AS
SELECT
    v.account_id,
    COALESCE(t.event_id, tt.event_id) AS event_id,
    COALESCE(t.venue_id, e.venue_id) AS venue_id,
    e.date::date AS event_date,
    CASE LOWER(TRIM(COALESCE(u.gender, '')))
        WHEN 'woman' THEN 'woman'
        WHEN 'female' THEN 'woman'
        WHEN 'mujer' THEN 'woman'
        WHEN 'f' THEN 'woman'
        WHEN 'femenino' THEN 'woman'
        WHEN 'man' THEN 'man'
        WHEN 'male' THEN 'man'
        WHEN 'hombre' THEN 'man'
        WHEN 'm' THEN 'man'
        WHEN 'masculino' THEN 'man'
        WHEN 'other' THEN 'other'
        WHEN 'otro' THEN 'other'
        WHEN 'non_binary' THEN 'other'
        WHEN 'non-binary' THEN 'other'
        WHEN 'nb' THEN 'other'
        WHEN 'no_binario' THEN 'other'
        ELSE 'sin_dato'
    END AS gender,
    CASE
        WHEN u.birth_date IS NULL THEN 'sin_dato'
        WHEN EXTRACT(
            YEAR FROM age(e.date::timestamp, u.birth_date::timestamp)
        ) < 18 THEN 'sin_dato'
        WHEN EXTRACT(
            YEAR FROM age(e.date::timestamp, u.birth_date::timestamp)
        ) <= 24 THEN '18-24'
        WHEN EXTRACT(
            YEAR FROM age(e.date::timestamp, u.birth_date::timestamp)
        ) <= 34 THEN '25-34'
        WHEN EXTRACT(
            YEAR FROM age(e.date::timestamp, u.birth_date::timestamp)
        ) <= 44 THEN '35-44'
        WHEN EXTRACT(
            YEAR FROM age(e.date::timestamp, u.birth_date::timestamp)
        ) <= 54 THEN '45-54'
        ELSE '55+'
    END AS age_band,
    COUNT(DISTINCT t.user_id)::integer AS headcount
FROM tickets t
LEFT JOIN ticket_tiers tt ON tt.id = t.tier
LEFT JOIN events e ON e.id = COALESCE(t.event_id, tt.event_id)
JOIN venues v ON v.id = COALESCE(t.venue_id, e.venue_id)
JOIN users u ON u.id = t.user_id
WHERE v.account_id IS NOT NULL
  AND t.user_id IS NOT NULL
  AND COALESCE(t.event_id, tt.event_id) IS NOT NULL
  AND e.date IS NOT NULL
  AND COALESCE(LOWER(t.status), 'active') NOT IN (
      'canceled', 'cancelled', 'cancelado'
  )
GROUP BY
    v.account_id,
    COALESCE(t.event_id, tt.event_id),
    COALESCE(t.venue_id, e.venue_id),
    e.date::date,
    5,
    6;
