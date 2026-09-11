"""Re-apply seed facts if needed (idempotent for dim + facts wipe/reload).

Usage (from repo root, venv active):
  python -m scripts.seed_dev
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.infra.db import create_session_factory

SEED_ACCOUNT = UUID("a1111111-1111-4111-8111-111111111111")
SEED_ACCOUNT_MIGUEL = UUID("a1111111-1111-4111-8111-111111111112")
SEED_VENUE_A = UUID("b2222222-2222-4222-8222-222222222201")
SEED_VENUE_B = UUID("b2222222-2222-4222-8222-222222222202")
SEED_VENUE_MIGUEL = UUID("b2222222-2222-4222-8222-222222222203")
USER_SUPERADMIN = UUID("c3333333-3333-4333-8333-333333333301")
USER_MIGUEL = UUID("c3333333-3333-4333-8333-333333333302")


async def seed(session: AsyncSession) -> None:
    settings = get_settings()

    await session.execute(
        text(
            """
            INSERT INTO analytics.accounts (id, name, slug)
            VALUES
              (:demo, 'Demo Discover', 'demo-discover'),
              (:miguel, 'Miguel''s Club', 'miguels-club')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"demo": SEED_ACCOUNT, "miguel": SEED_ACCOUNT_MIGUEL},
    )

    await session.execute(
        text(
            """
            INSERT INTO analytics.dim_venues (venue_id, account_id, name, city)
            VALUES
              (:va, :acc, 'Bar Demo Laureles', 'Medellín'),
              (:vb, :acc, 'Rooftop Demo Provenza', 'Medellín'),
              (:vm, :acc_m, 'Miguel''s Club', 'Medellín')
            ON CONFLICT (venue_id) DO NOTHING
            """
        ),
        {
            "va": SEED_VENUE_A,
            "vb": SEED_VENUE_B,
            "vm": SEED_VENUE_MIGUEL,
            "acc": SEED_ACCOUNT,
            "acc_m": SEED_ACCOUNT_MIGUEL,
        },
    )

    start = date(2026, 8, 1)
    for offset in range(14):
        night = start + timedelta(days=offset)
        for venue_id, account_id, ticket_boost, order_boost, revenue_boost in (
            (SEED_VENUE_A, SEED_ACCOUNT, 0, 0, 0),
            (SEED_VENUE_B, SEED_ACCOUNT, 15, 5, 80_000),
            (SEED_VENUE_MIGUEL, SEED_ACCOUNT_MIGUEL, 25, 10, 70_000),
        ):
            tickets = 20 + (night.toordinal() % 40) + ticket_boost
            orders = 8 + (night.toordinal() % 12) + order_boost
            revenue = 150_000 + (night.toordinal() % 20) * 25_000 + revenue_boost
            await session.execute(
                text(
                    """
                    INSERT INTO analytics.fact_nightly_attendance
                      (account_id, venue_id, night_date, redeemed_tickets)
                    VALUES (:acc, :vid, :nd, :tickets)
                    ON CONFLICT (account_id, venue_id, night_date)
                    DO UPDATE SET redeemed_tickets = EXCLUDED.redeemed_tickets
                    """
                ),
                {
                    "acc": account_id,
                    "vid": venue_id,
                    "nd": night,
                    "tickets": tickets,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO analytics.fact_sales_by_night
                      (account_id, venue_id, night_date, order_count, revenue_cents)
                    VALUES (:acc, :vid, :nd, :orders, :revenue)
                    ON CONFLICT (account_id, venue_id, night_date)
                    DO UPDATE SET
                      order_count = EXCLUDED.order_count,
                      revenue_cents = EXCLUDED.revenue_cents
                    """
                ),
                {
                    "acc": account_id,
                    "vid": venue_id,
                    "nd": night,
                    "orders": orders,
                    "revenue": revenue,
                },
            )

    ph = hash_password(settings.bootstrap_admin_password)
    for user_id, email, role, acc in (
        (
            USER_SUPERADMIN,
            "superadmin@discover.example.com",
            "super_admin",
            SEED_ACCOUNT,
        ),
        (
            USER_MIGUEL,
            "miguel@miguelsclub.example.com",
            "admin",
            SEED_ACCOUNT_MIGUEL,
        ),
    ):
        await session.execute(
            text(
                """
                INSERT INTO analytics.users (id, email, password_hash, role, account_id)
                VALUES (:id, :email, :ph, :role, :acc)
                ON CONFLICT (email) DO UPDATE SET
                  password_hash = EXCLUDED.password_hash,
                  role = EXCLUDED.role,
                  account_id = EXCLUDED.account_id
                """
            ),
            {"id": user_id, "email": email, "ph": ph, "role": role, "acc": acc},
        )

    email = settings.bootstrap_admin_email.lower()
    existing = await session.execute(
        text("SELECT id FROM analytics.users WHERE email = :email"),
        {"email": email},
    )
    if existing.first() is None and settings.bootstrap_account_id:
        await session.execute(
            text(
                """
                INSERT INTO analytics.users (id, email, password_hash, role, account_id)
                VALUES (gen_random_uuid(), :email, :ph, 'admin', :acc)
                """
            ),
            {
                "email": email,
                "ph": ph,
                "acc": UUID(settings.bootstrap_account_id),
            },
        )
    await session.commit()
    print(
        f"Seed OK demo={SEED_ACCOUNT} miguel={SEED_ACCOUNT_MIGUEL} "
        f"users=superadmin+miguel (+bootstrap {email})"
    )


async def main() -> None:
    factory = create_session_factory(get_settings())
    async with factory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
