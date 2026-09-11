from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.measures import GenderPoint, quality_for_gender


def _gender_sql(
    *,
    all_accounts: bool,
    venue_id: UUID | None,
    gender: str | None,
) -> text:
    where = ["night_date >= :period_start", "night_date <= :period_end"]
    if not all_accounts:
        where.append("account_id = :account_id")
    if venue_id is not None:
        where.append("venue_id = :venue_id")
    if gender is not None:
        where.append("gender = :gender")
    where_sql = " AND ".join(where)
    account_select = "NULL::uuid AS account_id" if all_accounts else "account_id"
    group = "gender" if all_accounts else "account_id, gender"
    return text(
        f"""
        SELECT {account_select}, gender, SUM(headcount)::int AS headcount
        FROM analytics.fact_attendance_detail
        WHERE {where_sql}
        GROUP BY {group}
        ORDER BY gender
        """
    )


@dataclass(frozen=True)
class GenderQueryResult:
    points: list[GenderPoint]
    quality: str


class GenderRepository:
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
    ) -> GenderQueryResult:
        params: dict = {"period_start": period_start, "period_end": period_end}
        if account_id is not None:
            params["account_id"] = account_id
        if venue_id is not None:
            params["venue_id"] = venue_id
        if gender is not None:
            params["gender"] = gender

        sql = _gender_sql(
            all_accounts=account_id is None,
            venue_id=venue_id,
            gender=gender,
        )
        result = await self._session.execute(sql, params)
        rows = result.mappings().all()
        total = sum(int(row["headcount"]) for row in rows) or 0
        points: list[GenderPoint] = []
        for row in rows:
            count = int(row["headcount"])
            g = str(row["gender"])
            if g not in ("woman", "man", "other", "undisclosed"):
                continue
            points.append(
                GenderPoint(
                    gender=g,  # type: ignore[arg-type]
                    headcount=count,
                    share=(count / total) if total else 0.0,
                    account_id=row["account_id"],
                )
            )
        return GenderQueryResult(points=points, quality=quality_for_gender(points))
