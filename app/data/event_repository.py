from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.measures import EventPerformance
from app.infra.orm import DimEvent

_PERFORMANCE_COLUMNS = """
    event_id, account_id, venue_id, name, event_type, event_date,
    redeemed_tickets, order_count, revenue_cents,
    headcount_woman, headcount_man, headcount_other,
    headcount_undisclosed, headcount_total
"""


def _row_to_performance(row) -> EventPerformance:
    return EventPerformance(
        event_id=row["event_id"],
        account_id=row["account_id"],
        venue_id=row["venue_id"],
        name=row["name"],
        event_type=row["event_type"],
        event_date=row["event_date"],
        redeemed_tickets=(
            int(row["redeemed_tickets"]) if row["redeemed_tickets"] is not None else None
        ),
        order_count=int(row["order_count"]) if row["order_count"] is not None else None,
        revenue_cents=int(row["revenue_cents"]) if row["revenue_cents"] is not None else None,
        headcount_woman=(
            int(row["headcount_woman"]) if row["headcount_woman"] is not None else None
        ),
        headcount_man=int(row["headcount_man"]) if row["headcount_man"] is not None else None,
        headcount_other=(
            int(row["headcount_other"]) if row["headcount_other"] is not None else None
        ),
        headcount_undisclosed=(
            int(row["headcount_undisclosed"])
            if row["headcount_undisclosed"] is not None
            else None
        ),
        headcount_total=(
            int(row["headcount_total"]) if row["headcount_total"] is not None else None
        ),
    )


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scope(
        self,
        account_id: UUID | None,
        venue_id: UUID | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> list[DimEvent]:
        q = select(DimEvent).order_by(DimEvent.event_date.desc(), DimEvent.name.asc())
        if account_id is not None:
            q = q.where(DimEvent.account_id == account_id)
        if venue_id is not None:
            q = q.where(DimEvent.venue_id == venue_id)
        if period_start is not None:
            q = q.where(DimEvent.event_date >= period_start)
        if period_end is not None:
            q = q.where(DimEvent.event_date <= period_end)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_by_id(self, event_id: UUID, account_id: UUID | None) -> DimEvent | None:
        q = select(DimEvent).where(DimEvent.event_id == event_id)
        if account_id is not None:
            q = q.where(DimEvent.account_id == account_id)
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

    async def performance_for_event(
        self, event_id: UUID, account_id: UUID | None
    ) -> EventPerformance | None:
        where = ["event_id = :event_id"]
        params: dict = {"event_id": event_id}
        if account_id is not None:
            where.append("account_id = :account_id")
            params["account_id"] = account_id
        sql = text(
            f"""
            SELECT {_PERFORMANCE_COLUMNS}
            FROM analytics.v_event_performance
            WHERE {" AND ".join(where)}
            """
        )
        result = await self._session.execute(sql, params)
        row = result.mappings().one_or_none()
        return _row_to_performance(row) if row is not None else None
