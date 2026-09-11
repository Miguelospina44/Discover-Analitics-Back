"""fact tables, dim_venues, and isolated seed data

Revision ID: 0002_fact_tables_seed
Revises: 0001_analytics_core
Create Date: 2026-08-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_fact_tables_seed"
down_revision: Union[str, Sequence[str], None] = "0001_analytics_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed tenant / venue IDs for local seed (must match BOOTSTRAP_ACCOUNT_ID)
SEED_ACCOUNT = "a1111111-1111-4111-8111-111111111111"
SEED_VENUE_A = "b2222222-2222-4222-8222-222222222201"
SEED_VENUE_B = "b2222222-2222-4222-8222-222222222202"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE analytics.dim_venues (
            venue_id UUID PRIMARY KEY,
            account_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            city VARCHAR(120) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_analytics_dim_venues_account_id ON analytics.dim_venues (account_id)"
    )
    op.execute(
        """
        CREATE TABLE analytics.fact_nightly_attendance (
            account_id UUID NOT NULL,
            venue_id UUID NOT NULL REFERENCES analytics.dim_venues (venue_id),
            night_date DATE NOT NULL,
            redeemed_tickets INTEGER NOT NULL CHECK (redeemed_tickets >= 0),
            PRIMARY KEY (account_id, venue_id, night_date)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_nightly_attendance_account_night
        ON analytics.fact_nightly_attendance (account_id, night_date)
        """
    )
    op.execute(
        """
        CREATE TABLE analytics.fact_sales_by_night (
            account_id UUID NOT NULL,
            venue_id UUID NOT NULL REFERENCES analytics.dim_venues (venue_id),
            night_date DATE NOT NULL,
            order_count INTEGER NOT NULL CHECK (order_count >= 0),
            revenue_cents BIGINT NOT NULL CHECK (revenue_cents >= 0),
            PRIMARY KEY (account_id, venue_id, night_date)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_sales_by_night_account_night
        ON analytics.fact_sales_by_night (account_id, night_date)
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.dim_venues (venue_id, account_id, name, city) VALUES
        ('{SEED_VENUE_A}', '{SEED_ACCOUNT}', 'Bar Demo Laureles', 'Medellín'),
        ('{SEED_VENUE_B}', '{SEED_ACCOUNT}', 'Rooftop Demo Provenza', 'Medellín')
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.fact_nightly_attendance
            (account_id, venue_id, night_date, redeemed_tickets)
        SELECT
            '{SEED_ACCOUNT}'::uuid,
            v.venue_id,
            d.night_date,
            (20 + (EXTRACT(DOY FROM d.night_date)::int % 40) + v.offset_tickets)::int
        FROM (
            VALUES
                ('{SEED_VENUE_A}'::uuid, 0),
                ('{SEED_VENUE_B}'::uuid, 15)
        ) AS v(venue_id, offset_tickets)
        CROSS JOIN generate_series(
            DATE '2026-08-01',
            DATE '2026-08-14',
            INTERVAL '1 day'
        ) AS d(night_date)
        """
    )
    op.execute(
        f"""
        INSERT INTO analytics.fact_sales_by_night
            (account_id, venue_id, night_date, order_count, revenue_cents)
        SELECT
            '{SEED_ACCOUNT}'::uuid,
            v.venue_id,
            d.night_date,
            (8 + (EXTRACT(DOY FROM d.night_date)::int % 12) + v.offset_orders)::int,
            ((150000 + (EXTRACT(DOY FROM d.night_date)::int % 20) * 25000
              + v.offset_revenue)::bigint)
        FROM (
            VALUES
                ('{SEED_VENUE_A}'::uuid, 0, 0),
                ('{SEED_VENUE_B}'::uuid, 5, 80000)
        ) AS v(venue_id, offset_orders, offset_revenue)
        CROSS JOIN generate_series(
            DATE '2026-08-01',
            DATE '2026-08-14',
            INTERVAL '1 day'
        ) AS d(night_date)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analytics.fact_sales_by_night")
    op.execute("DROP TABLE IF EXISTS analytics.fact_nightly_attendance")
    op.execute("DROP TABLE IF EXISTS analytics.dim_venues")
