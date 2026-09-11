"""fact_attendance_detail for cross-filter venue x gender

Revision ID: 0005_attendance_detail
Revises: 0004_attendance_by_gender
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005_attendance_detail"
down_revision: Union[str, Sequence[str], None] = "0004_attendance_by_gender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
SEED_ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"
SEED_VENUE_A = "b2222222-2222-4222-8222-222222222201"
SEED_VENUE_B = "b2222222-2222-4222-8222-222222222202"
SEED_VENUE_MIGUEL = "b2222222-2222-4222-8222-222222222203"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE analytics.fact_attendance_detail (
            account_id UUID NOT NULL,
            venue_id UUID NOT NULL REFERENCES analytics.dim_venues (venue_id),
            night_date DATE NOT NULL,
            gender VARCHAR(32) NOT NULL
              CHECK (gender IN ('woman', 'man', 'other', 'undisclosed')),
            headcount INTEGER NOT NULL CHECK (headcount >= 0),
            PRIMARY KEY (account_id, venue_id, night_date, gender)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_attendance_detail_account_night
        ON analytics.fact_attendance_detail (account_id, night_date)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_attendance_detail_venue
        ON analytics.fact_attendance_detail (venue_id)
        """
    )

    # Demo venues + Miguel venue with gender mix per night
    op.execute(
        f"""
        INSERT INTO analytics.fact_attendance_detail
            (account_id, venue_id, night_date, gender, headcount)
        SELECT
            v.account_id,
            v.venue_id,
            d.night_date,
            g.gender,
            GREATEST(
              1,
              (
                CASE g.gender
                  WHEN 'woman' THEN v.base_w
                  WHEN 'man' THEN v.base_m
                  WHEN 'other' THEN v.base_o
                  ELSE v.base_u
                END
                + (EXTRACT(DOY FROM d.night_date)::int % g.mod)
              )::int
            )
        FROM (
            VALUES
                ('{SEED_ACCOUNT_DEMO}'::uuid, '{SEED_VENUE_A}'::uuid, 28, 22, 2, 3),
                ('{SEED_ACCOUNT_DEMO}'::uuid, '{SEED_VENUE_B}'::uuid, 22, 18, 2, 3),
                ('{SEED_ACCOUNT_MIGUEL}'::uuid, '{SEED_VENUE_MIGUEL}'::uuid, 36, 52, 3, 5)
        ) AS v(account_id, venue_id, base_w, base_m, base_o, base_u)
        CROSS JOIN generate_series(
            DATE '2026-08-01',
            DATE '2026-08-14',
            INTERVAL '1 day'
        ) AS d(night_date)
        CROSS JOIN (
            VALUES
                ('woman', 7),
                ('man', 5),
                ('other', 2),
                ('undisclosed', 3)
        ) AS g(gender, mod)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analytics.fact_attendance_detail")
