-- Venue dimension with normalized city and venue type.
-- Tenant: account_id. Business venue attributes only — not buyer PII.
-- City (DEV): Medellín / medellin / Medellin.
-- Type: venues.venue_type text (bar, discotk, discoteca, club, rooftop).
-- If Discover only has venue_type_id, project the catalog name into venue_type
-- before applying this view.

CREATE OR REPLACE VIEW analytics.v_venues_normalized AS
SELECT
    v.account_id,
    v.id AS venue_id,
    NULLIF(v.aforo, 0) AS aforo,
    v.city AS city_raw,
    CASE TRANSLATE(LOWER(TRIM(v.city)), 'áéíóúüñ', 'aeiouun')
        WHEN 'medellin' THEN 'Medellín'
        WHEN 'bogota' THEN 'Bogotá'
        WHEN 'cali' THEN 'Cali'
        WHEN 'barranquilla' THEN 'Barranquilla'
        WHEN 'cartagena' THEN 'Cartagena'
        ELSE NULLIF(TRIM(v.city), '')
    END AS city_normalized,
    CASE TRANSLATE(LOWER(TRIM(COALESCE(v.venue_type, ''))), 'áéíóúüñ', 'aeiouun')
        WHEN 'bar' THEN 'bar'
        WHEN 'discotk' THEN 'discoteca'
        WHEN 'discoteca' THEN 'discoteca'
        WHEN 'disco' THEN 'discoteca'
        WHEN 'club' THEN 'club'
        WHEN 'rooftop' THEN 'rooftop'
        WHEN '' THEN 'unknown'
        ELSE COALESCE(NULLIF(LOWER(TRIM(v.venue_type)), ''), 'unknown')
    END AS venue_type_normalized
FROM venues v
WHERE v.account_id IS NOT NULL;
