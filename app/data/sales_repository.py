from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.measures import Quality

SEED_SQL = text(
    """
    SELECT account_id, venue_id, night_date, order_count, revenue_cents
    FROM analytics.fact_sales_by_night
    WHERE account_id = :account_id
      AND night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)

SEED_SQL_ALL = text(
    """
    SELECT account_id, venue_id, night_date, order_count, revenue_cents
    FROM analytics.fact_sales_by_night
    WHERE night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)

DISCOVER_SQL = text(
    """
    SELECT account_id, venue_id, night_date, order_count, revenue_cents
    FROM analytics.v_sales_by_night
    WHERE account_id = :account_id
      AND night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)

DISCOVER_SQL_ALL = text(
    """
    SELECT account_id, venue_id, night_date, order_count, revenue_cents
    FROM analytics.v_sales_by_night
    WHERE night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)


@dataclass(frozen=True)
class SalesPoint:
    venue_id: UUID
    night_date: date
    order_count: int
    revenue_cents: int
    account_id: UUID | None = None


def quality_for_sales(points: list[SalesPoint]) -> Quality:
    if not points:
        return "missing"
    if any(point.order_count == 0 or point.revenue_cents == 0 for point in points):
        return "partial"
    return "ok"


class SalesRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def list_for_scope(
        self,
        account_id: UUID | None,
        period_start: date,
        period_end: date,
        venue_id: UUID | None = None,
    ) -> list[SalesPoint]:
        seed = self._settings.uses_seed_facts
        params: dict = {"period_start": period_start, "period_end": period_end}
        if account_id is not None:
            params["account_id"] = account_id

        if account_id is None:
            sql = SEED_SQL_ALL if seed else DISCOVER_SQL_ALL
        else:
            sql = SEED_SQL if seed else DISCOVER_SQL

        if venue_id is not None:
            # inject venue filter into SQL via rewritten query
            table = (
                "analytics.fact_sales_by_night"
                if seed
                else "analytics.v_sales_by_night"
            )
            where = [
                "night_date >= :period_start",
                "night_date <= :period_end",
                "venue_id = :venue_id",
            ]
            if account_id is not None:
                where.insert(0, "account_id = :account_id")
            sql = text(
                f"""
                SELECT account_id, venue_id, night_date, order_count, revenue_cents
                FROM {table}
                WHERE {" AND ".join(where)}
                ORDER BY night_date ASC
                """
            )
            params["venue_id"] = venue_id

        result = await self._session.execute(sql, params)
        rows = result.mappings().all()
        return [
            SalesPoint(
                venue_id=row["venue_id"],
                night_date=row["night_date"],
                order_count=int(row["order_count"]),
                revenue_cents=int(row["revenue_cents"]),
                account_id=row["account_id"],
            )
            for row in rows
        ]

    async def list_for_account(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
    ) -> list[SalesPoint]:
        return await self.list_for_scope(account_id, period_start, period_end)
