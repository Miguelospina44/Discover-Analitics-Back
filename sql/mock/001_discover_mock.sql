-- Fase B — MOCK de la Postgres operativa de Discover (solo pruebas locales).
-- NO ejecutar contra la Postgres real de Discover: aquí sí creamos tablas en
-- `public` para simular `venues`, `tickets` y `orders`. En Discover real estas
-- tablas ya existen y este repo NUNCA les aplica DDL (solo CREATE VIEW en analytics).
--
-- Uso (contra una base de prueba aislada):
--   psql "$DB" -f sql/mock/001_discover_mock.sql
--   psql "$DB" -f sql/views/001_v_nightly_attendance.sql
--   psql "$DB" -f sql/views/002_v_sales_by_night.sql
--
-- Fechas en septiembre 2026 y venue_ids propios para distinguir claramente los
-- datos derivados de las vistas de los facts seed (agosto) de la Fase A.

BEGIN;

DROP TABLE IF EXISTS public.tickets CASCADE;
DROP TABLE IF EXISTS public.orders CASCADE;
DROP TABLE IF EXISTS public.venues CASCADE;

CREATE TABLE public.venues (
    id         uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    name       text NOT NULL,
    city       text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.tickets (
    id              bigserial PRIMARY KEY,
    venue_id        uuid NOT NULL REFERENCES public.venues(id),
    redemption_date bigint,               -- unix seconds (nullable = sin redimir)
    price_cents     integer NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.orders (
    id           bigserial PRIMARY KEY,
    venue_id     uuid NOT NULL REFERENCES public.venues(id),
    order_date   bigint NOT NULL,         -- unix seconds
    total_amount numeric(12,2) NOT NULL DEFAULT 0,
    order_status text NOT NULL DEFAULT 'paid',
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Dos venues del account Demo + un venue del account "Miguel's Club".
INSERT INTO public.venues (id, account_id, name, city) VALUES
  ('d4444444-4444-4444-8444-444444444401', 'a1111111-1111-4111-8111-111111111111', 'Discover Bar Centro',   'Medellín'),
  ('d4444444-4444-4444-8444-444444444402', 'a1111111-1111-4111-8111-111111111111', 'Discover Rooftop Norte', 'Medellín'),
  ('d4444444-4444-4444-8444-444444444403', 'a1111111-1111-4111-8111-111111111112', 'Discover Club Miguel',   'Medellín');

-- Helper: unix seconds para las 22:00 hora Bogotá de una fecha local.
-- (redondea de vuelta a la misma night_date en la vista).
-- tickets: filas individuales (la vista hace COUNT(*)).
INSERT INTO public.tickets (venue_id, redemption_date, price_cents)
SELECT
    v.id,
    EXTRACT(EPOCH FROM ((d + TIME '22:00') AT TIME ZONE 'America/Bogota'))::bigint,
    2500
FROM public.venues v
CROSS JOIN generate_series(DATE '2026-09-01', DATE '2026-09-10', INTERVAL '1 day') AS g(d)
CROSS JOIN generate_series(
    1,
    -- conteo determinista por venue/noche (10..40 tickets)
    10 + (EXTRACT(DAY FROM g.d)::int * (CASE v.id
        WHEN 'd4444444-4444-4444-8444-444444444401' THEN 1
        WHEN 'd4444444-4444-4444-8444-444444444402' THEN 2
        ELSE 3 END))
) AS n(i);

-- Algunos tickets sin redimir (redemption_date NULL) — la vista los excluye.
INSERT INTO public.tickets (venue_id, redemption_date, price_cents)
SELECT v.id, NULL, 2500
FROM public.venues v, generate_series(1, 5) s;

-- orders: incluye canceladas (la vista las excluye).
INSERT INTO public.orders (venue_id, order_date, total_amount, order_status)
SELECT
    v.id,
    EXTRACT(EPOCH FROM ((d + TIME '22:30') AT TIME ZONE 'America/Bogota'))::bigint,
    (150 + (EXTRACT(DAY FROM g.d)::int * 7))::numeric,
    'paid'
FROM public.venues v
CROSS JOIN generate_series(DATE '2026-09-01', DATE '2026-09-10', INTERVAL '1 day') AS g(d)
CROSS JOIN generate_series(
    1,
    5 + (EXTRACT(DAY FROM g.d)::int % 6)
) AS n(i);

INSERT INTO public.orders (venue_id, order_date, total_amount, order_status)
SELECT
    v.id,
    EXTRACT(EPOCH FROM ((DATE '2026-09-05' + TIME '23:00') AT TIME ZONE 'America/Bogota'))::bigint,
    999::numeric,
    'canceled'
FROM public.venues v, generate_series(1, 4) s;

COMMIT;
