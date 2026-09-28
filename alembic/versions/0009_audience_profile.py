"""fact_audience_profile: segmentación ANÓNIMA de audiencia (¿quién es mi público?)

Fase D: la audiencia se modela como AGREGADOS ANÓNIMOS por segmento. Cada fila es
un conteo (headcount) de personas para una combinación de buckets
(gender, age_band, zone, recurrence) en una noche y cuenta. NO hay datos
personales: ni nombres, ni correos, ni teléfonos, ni filas por individuo. Solo
totales por segmento, de los que el producto deriva shares. Esta invariante de
privacidad es intencional y debe conservarse (ver también app/infra/orm.py y
app/data/audience_repository.py).

El account_id es FK real -> analytics.accounts (ON DELETE RESTRICT), igual que
migración 0006, para que la integridad de tenant sea invariante de base.

Revision ID: 0009_audience_profile
Revises: 0008_leads
Create Date: 2026-09-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009_audience_profile"
down_revision: Union[str, Sequence[str], None] = "0008_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vocabularios controlados (deben coincidir con los CHECK del ORM).
GENDERS: tuple[str, ...] = ("woman", "man", "other", "undisclosed")
AGE_BANDS: tuple[str, ...] = ("18-24", "25-34", "35-44", "45+", "undisclosed")
RECURRENCES: tuple[str, ...] = ("nuevo", "recurrente", "undisclosed")

# IDs fijos del seed (deben coincidir con migraciones 0002/0003).
SEED_ACCOUNT_DEMO = "a1111111-1111-4111-8111-111111111111"
SEED_ACCOUNT_MIGUEL = "a1111111-1111-4111-8111-111111111112"


def upgrade() -> None:
    genders_csv = ", ".join(f"'{g}'" for g in GENDERS)
    age_bands_csv = ", ".join(f"'{a}'" for a in AGE_BANDS)
    recurrences_csv = ", ".join(f"'{r}'" for r in RECURRENCES)
    op.execute(
        f"""
        CREATE TABLE analytics.fact_audience_profile (
            account_id UUID NOT NULL,
            night_date DATE NOT NULL,
            gender VARCHAR(32) NOT NULL
              CHECK (gender IN ({genders_csv})),
            age_band VARCHAR(32) NOT NULL
              CHECK (age_band IN ({age_bands_csv})),
            zone VARCHAR(120) NOT NULL,
            recurrence VARCHAR(32) NOT NULL
              CHECK (recurrence IN ({recurrences_csv})),
            headcount INTEGER NOT NULL CHECK (headcount >= 0),
            PRIMARY KEY (account_id, night_date, gender, age_band, zone, recurrence)
        )
        """
    )
    # account_id como FK real -> accounts (ON DELETE RESTRICT), igual que 0006/0007.
    op.create_foreign_key(
        "fk_fact_audience_profile_account",
        source_table="fact_audience_profile",
        referent_table="accounts",
        local_cols=["account_id"],
        remote_cols=["id"],
        source_schema="analytics",
        referent_schema="analytics",
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE INDEX ix_fact_audience_profile_account_night
        ON analytics.fact_audience_profile (account_id, night_date)
        """
    )

    # Seed ANÓNIMO: por cada cuenta, zona y noche sembrada (2026-08-01..14) se
    # reparte un total de zona entre los buckets usando pesos fraccionarios que
    # suman ~1 por dimensión, de modo que las distribuciones son plausibles.
    # headcount = round(zone_base * peso_gender * peso_age * peso_recurrence).
    # Se descartan los buckets que redondean a 0 para no meter ruido. Todo son
    # conteos agregados: NO se guarda ninguna persona ni dato personal.
    op.execute(
        f"""
        INSERT INTO analytics.fact_audience_profile
            (account_id, night_date, gender, age_band, zone, recurrence, headcount)
        SELECT account_id, night_date, gender, age_band, zone, recurrence, headcount
        FROM (
            SELECT
                z.account_id,
                d.night_date,
                g.gender,
                a.age_band,
                z.zone,
                r.recurrence,
                ROUND(
                    (z.zone_base + (EXTRACT(DOY FROM d.night_date)::int % 40))
                    * g.w * a.w * r.w
                )::int AS headcount
            FROM (
                VALUES
                    ('{SEED_ACCOUNT_DEMO}'::uuid, 'Laureles', 320),
                    ('{SEED_ACCOUNT_DEMO}'::uuid, 'Provenza', 300),
                    ('{SEED_ACCOUNT_DEMO}'::uuid, 'El Poblado', 360),
                    ('{SEED_ACCOUNT_DEMO}'::uuid, 'Envigado', 240),
                    ('{SEED_ACCOUNT_MIGUEL}'::uuid, 'Laureles', 220),
                    ('{SEED_ACCOUNT_MIGUEL}'::uuid, 'Envigado', 200)
            ) AS z(account_id, zone, zone_base)
            CROSS JOIN generate_series(
                DATE '2026-08-01',
                DATE '2026-08-14',
                INTERVAL '1 day'
            ) AS d(night_date)
            CROSS JOIN (
                VALUES
                    ('woman', 0.42),
                    ('man', 0.46),
                    ('other', 0.05),
                    ('undisclosed', 0.07)
            ) AS g(gender, w)
            CROSS JOIN (
                VALUES
                    ('18-24', 0.30),
                    ('25-34', 0.38),
                    ('35-44', 0.18),
                    ('45+', 0.09),
                    ('undisclosed', 0.05)
            ) AS a(age_band, w)
            CROSS JOIN (
                VALUES
                    ('nuevo', 0.45),
                    ('recurrente', 0.50),
                    ('undisclosed', 0.05)
            ) AS r(recurrence, w)
        ) s
        WHERE headcount >= 1
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analytics.fact_audience_profile")
