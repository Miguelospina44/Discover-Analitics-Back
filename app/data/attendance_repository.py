from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.measures import AttendancePoint


def _attendance_sql(
    *,
    all_accounts: bool,
    venue_id: UUID | None,
    gender: str | None,
) -> text:
    """Build SUM from fact_attendance_detail with optional filters."""
    where = ["night_date >= :period_start", "night_date <= :period_end"]
    if not all_accounts:
        where.append("account_id = :account_id")
    if venue_id is not None:
        where.append("venue_id = :venue_id")
    if gender is not None:
        where.append("gender = :gender")
    where_sql = " AND ".join(where)
    return text(
        f"""
        SELECT account_id, venue_id, night_date, SUM(headcount)::int AS redeemed_tickets
        FROM analytics.fact_attendance_detail
        WHERE {where_sql}
        GROUP BY account_id, venue_id, night_date
        ORDER BY night_date ASC
        """
    )


# Discover fallback without gender/venue filters on detail
DISCOVER_SQL = text(
    """
    SELECT account_id, venue_id, night_date, redeemed_tickets
    FROM analytics.v_nightly_attendance
    WHERE account_id = :account_id
      AND night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)

DISCOVER_SQL_ALL = text(
    """
    SELECT account_id, venue_id, night_date, redeemed_tickets
    FROM analytics.v_nightly_attendance
    WHERE night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)


class AttendanceRepository:
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
        gender: str | None = None,
    ) -> list[AttendancePoint]:
        seed = self._settings.uses_seed_facts
        params: dict = {"period_start": period_start, "period_end": period_end}
        if account_id is not None:
            params["account_id"] = account_id
        if venue_id is not None:
            params["venue_id"] = venue_id
        if gender is not None:
            params["gender"] = gender

        if seed:
            sql = _attendance_sql(
                all_accounts=account_id is None,
                venue_id=venue_id,
                gender=gender,
            )
        else:
            # Discover path: ignore gender until view supports it
            sql = DISCOVER_SQL_ALL if account_id is None else DISCOVER_SQL
            if venue_id is not None:
                # best-effort client filter after fetch if view has no venue param
                pass

        result = await self._session.execute(sql, params)
        rows = result.mappings().all()
        points = [
            AttendancePoint(
                venue_id=row["venue_id"],
                night_date=row["night_date"],
                redeemed_tickets=int(row["redeemed_tickets"]),
                account_id=row["account_id"],
            )
            for row in rows
        ]
        if not seed and venue_id is not None:
            points = [p for p in points if p.venue_id == venue_id]
        return points

    async def list_for_account(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
    ) -> list[AttendancePoint]:
        return await self.list_for_scope(account_id, period_start, period_end)
