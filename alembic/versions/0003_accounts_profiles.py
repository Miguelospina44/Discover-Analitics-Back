"""accounts table, Miguel's Club tenant, superadmin + client users

Revision ID: 0003_accounts_profiles
Revises: 0002_fact_tables_seed
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_accounts_profiles"
down_revision: Union[str, Sequence[str], None] = "0002_fact_tables_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
SEED_ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"
SEED_VENUE_MIGUEL = "b2222222-2222-4222-8222-222222222203"
USER_SUPERADMIN = "c3333333-3333-4333-8333-333333333301"
USER_MIGUEL = "c3333333-3333-4333-8333-333333333302"
# bcrypt of change-me-now
PW_HASH = "$2b$12$MqXv9Cis1cgGYVDW.nMDBuVgOjLVOv1TCzZBkE0A0/IHwHxnRJJ4W"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE analytics.accounts (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(80) NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.accounts (id, name, slug) VALUES
        ('{SEED_ACCOUNT_DEMO}', 'Demo Discover', 'demo-discover'),
        ('{SEED_ACCOUNT_MIGUEL}', 'Miguel''s Club', 'miguels-club')
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.dim_venues (venue_id, account_id, name, city) VALUES
        ('{SEED_VENUE_MIGUEL}', '{SEED_ACCOUNT_MIGUEL}', 'Miguel''s Club', 'Medellín')
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.fact_nightly_attendance
            (account_id, venue_id, night_date, redeemed_tickets)
        SELECT
            '{SEED_ACCOUNT_MIGUEL}'::uuid,
            '{SEED_VENUE_MIGUEL}'::uuid,
            d.night_date,
            (45 + (EXTRACT(DOY FROM d.night_date)::int % 35))::int
        FROM generate_series(
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
            '{SEED_ACCOUNT_MIGUEL}'::uuid,
            '{SEED_VENUE_MIGUEL}'::uuid,
            d.night_date,
            (18 + (EXTRACT(DOY FROM d.night_date)::int % 15))::int,
            ((220000 + (EXTRACT(DOY FROM d.night_date)::int % 18) * 30000)::bigint)
        FROM generate_series(
            DATE '2026-08-01',
            DATE '2026-08-14',
            INTERVAL '1 day'
        ) AS d(night_date)
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.users (id, email, password_hash, role, account_id)
        VALUES
        (
          '{USER_SUPERADMIN}',
          'superadmin@discover.example.com',
          '{PW_HASH}',
          'super_admin',
          '{SEED_ACCOUNT_DEMO}'
        ),
        (
          '{USER_MIGUEL}',
          'miguel@miguelsclub.example.com',
          '{PW_HASH}',
          'admin',
          '{SEED_ACCOUNT_MIGUEL}'
        )
        ON CONFLICT (email) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM analytics.users
        WHERE id IN ('{USER_SUPERADMIN}', '{USER_MIGUEL}')
        """
    )
    op.execute(
        f"""
        DELETE FROM analytics.fact_sales_by_night
        WHERE account_id = '{SEED_ACCOUNT_MIGUEL}'
        """
    )
    op.execute(
        f"""
        DELETE FROM analytics.fact_nightly_attendance
        WHERE account_id = '{SEED_ACCOUNT_MIGUEL}'
        """
    )
    op.execute(
        f"DELETE FROM analytics.dim_venues WHERE venue_id = '{SEED_VENUE_MIGUEL}'"
    )
    op.execute("DROP TABLE IF EXISTS analytics.accounts")
