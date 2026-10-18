-- Venue dimension with normalized city (DEV inventory: Medellín/medellin/Medellin).
-- Tenant: account_id. Business venue attributes only — not buyer PII.

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
    END AS city_normalized
FROM venues v
WHERE v.account_id IS NOT NULL;
