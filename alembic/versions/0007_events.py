"""dim_event (events as first-class entity) + derived v_event_performance view

Fase C1: los eventos pasan a ser una entidad de primer nivel. Se crea SOLO la
dimensión `dim_event`; el desempeño de cada evento se DERIVA uniendo el evento a
los hechos por-noche existentes sobre (account_id, venue_id, event_date =
night_date). No se crea una tabla física fact_event_performance para evitar
duplicación/divergencia: la derivación vive en la vista de solo lectura
analytics.v_event_performance.

Un evento = una noche en un venue (event_date -> night_date, un solo venue).

Revision ID: 0007_events
Revises: 0006_account_fks_role_check
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007_events"
down_revision: Union[str, Sequence[str], None] = "0006_account_fks_role_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vocabulario controlado de tipos de evento (debe coincidir con el CHECK del ORM).
EVENT_TYPES: tuple[str, ...] = ("regular", "especial", "privado", "festival", "otro")

# IDs fijos del seed (deben coincidir con migraciones 0002/0003).
SEED_ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
SEED_ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"
SEED_VENUE_A = "b2222222-2222-4222-8222-222222222201"
SEED_VENUE_B = "b2222222-2222-4222-8222-222222222202"
SEED_VENUE_MIGUEL = "b2222222-2222-4222-8222-222222222203"


def upgrade() -> None:
    types_csv = ", ".join(f"'{t}'" for t in EVENT_TYPES)
    op.execute(
        f"""
        CREATE TABLE analytics.dim_event (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id UUID NOT NULL,
            venue_id UUID NOT NULL REFERENCES analytics.dim_venues (venue_id),
            name VARCHAR(200) NOT NULL,
            event_type VARCHAR(32) NOT NULL DEFAULT 'regular'
              CHECK (event_type IN ({types_csv})),
            event_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_dim_event_venue_date_name UNIQUE (venue_id, event_date, name)
        )
        """
    )
    # account_id como FK real -> accounts (ON DELETE RESTRICT), igual que 0006.
    op.create_foreign_key(
        "fk_dim_event_account",
        source_table="dim_event",
        referent_table="accounts",
        local_cols=["account_id"],
        remote_cols=["id"],
        source_schema="analytics",
        referent_schema="analytics",
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE INDEX ix_dim_event_account_date
        ON analytics.dim_event (account_id, event_date)
        """
    )
    op.execute("CREATE INDEX ix_dim_event_venue ON analytics.dim_event (venue_id)")

    # Vista de solo lectura: desempeño derivado por evento uniendo dim_event a los
    # hechos por-noche sobre (account_id, venue_id, event_date = night_date).
    # LEFT JOIN para que un evento sin hechos siga apareciendo (con NULLs).
    op.execute(
        """
        CREATE VIEW analytics.v_event_performance AS
        SELECT
            e.event_id,
            e.account_id,
            e.venue_id,
            e.name,
            e.event_type,
            e.event_date,
            a.redeemed_tickets,
            s.order_count,
            s.revenue_cents,
            g.headcount_woman,
            g.headcount_man,
            g.headcount_other,
            g.headcount_undisclosed,
            g.headcount_total
        FROM analytics.dim_event e
        LEFT JOIN analytics.fact_nightly_attendance a
            ON a.account_id = e.account_id
           AND a.venue_id = e.venue_id
           AND a.night_date = e.event_date
        LEFT JOIN analytics.fact_sales_by_night s
            ON s.account_id = e.account_id
           AND s.venue_id = e.venue_id
           AND s.night_date = e.event_date
        LEFT JOIN (
            SELECT
                account_id,
                venue_id,
                night_date,
                SUM(headcount) FILTER (WHERE gender = 'woman')::int AS headcount_woman,
                SUM(headcount) FILTER (WHERE gender = 'man')::int AS headcount_man,
                SUM(headcount) FILTER (WHERE gender = 'other')::int AS headcount_other,
                SUM(headcount) FILTER (WHERE gender = 'undisclosed')::int
                    AS headcount_undisclosed,
                SUM(headcount)::int AS headcount_total
            FROM analytics.fact_attendance_detail
            GROUP BY account_id, venue_id, night_date
        ) g
            ON g.account_id = e.account_id
           AND g.venue_id = e.venue_id
           AND g.night_date = e.event_date
        """
    )

    # Seed demo: un evento por venue por cada noche sembrada (2026-08-01..14), con
    # tipo variado y determinista, para que el frontend tenga historia real.
    op.execute(
        f"""
        INSERT INTO analytics.dim_event
            (account_id, venue_id, name, event_type, event_date)
        SELECT
            v.account_id,
            v.venue_id,
            v.label || ' · ' || to_char(d.night_date, 'DD/MM'),
            CASE
                WHEN EXTRACT(DAY FROM d.night_date)::int % 7 = 0 THEN 'festival'
                WHEN EXTRACT(DAY FROM d.night_date)::int % 5 = 0 THEN 'especial'
                WHEN EXTRACT(DAY FROM d.night_date)::int % 3 = 0 THEN 'privado'
                WHEN EXTRACT(DAY FROM d.night_date)::int % 2 = 0 THEN 'otro'
                ELSE 'regular'
            END,
            d.night_date
        FROM (
            VALUES
                ('{SEED_ACCOUNT_DEMO}'::uuid, '{SEED_VENUE_A}'::uuid, 'Noche Laureles'),
                ('{SEED_ACCOUNT_DEMO}'::uuid, '{SEED_VENUE_B}'::uuid, 'Noche Provenza'),
                ('{SEED_ACCOUNT_MIGUEL}'::uuid, '{SEED_VENUE_MIGUEL}'::uuid, 'Noche Miguel''s')
        ) AS v(account_id, venue_id, label)
        CROSS JOIN generate_series(
            DATE '2026-08-01',
            DATE '2026-08-14',
            INTERVAL '1 day'
        ) AS d(night_date)
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS analytics.v_event_performance")
    op.execute("DROP TABLE IF EXISTS analytics.dim_event")
