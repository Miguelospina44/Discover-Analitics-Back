"""fact_attendance_by_gender + seed for demo and Miguel's Club

Revision ID: 0004_attendance_by_gender
Revises: 0003_accounts_profiles
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_attendance_by_gender"
down_revision: Union[str, Sequence[str], None] = "0003_accounts_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
SEED_ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE analytics.fact_attendance_by_gender (
            account_id UUID NOT NULL,
            night_date DATE NOT NULL,
            gender VARCHAR(32) NOT NULL
              CHECK (gender IN ('woman', 'man', 'other', 'undisclosed')),
            headcount INTEGER NOT NULL CHECK (headcount >= 0),
            PRIMARY KEY (account_id, night_date, gender)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_attendance_by_gender_account_night
        ON analytics.fact_attendance_by_gender (account_id, night_date)
        """
    )

    op.execute(
        f"""
        INSERT INTO analytics.fact_attendance_by_gender
            (account_id, night_date, gender, headcount)
        SELECT
            a.account_id,
            d.night_date,
            g.gender,
            GREATEST(
              1,
              (
                CASE g.gender
                  WHEN 'woman' THEN a.base_w
                  WHEN 'man' THEN a.base_m
                  WHEN 'other' THEN a.base_o
                  ELSE a.base_u
                END
                + (EXTRACT(DOY FROM d.night_date)::int % g.mod)
              )::int
            )
        FROM (
            VALUES
                ('{SEED_ACCOUNT_DEMO}'::uuid, 48, 38, 4, 6),
                ('{SEED_ACCOUNT_MIGUEL}'::uuid, 36, 52, 3, 5)
        ) AS a(account_id, base_w, base_m, base_o, base_u)
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
    op.execute("DROP TABLE IF EXISTS analytics.fact_attendance_by_gender")
