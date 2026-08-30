from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.measures import AttendancePoint

ATTENDANCE_SQL = text(
    """
    SELECT venue_id, night_date, redeemed_tickets
    FROM analytics.v_nightly_attendance
    WHERE account_id = :account_id
      AND night_date >= :period_start
      AND night_date <= :period_end
    ORDER BY night_date ASC
    """
)


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_account(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
    ) -> list[AttendancePoint]:
        result = await self._session.execute(
            ATTENDANCE_SQL,
            {
                "account_id": account_id,
                "period_start": period_start,
                "period_end": period_end,
            },
        )
        rows = result.mappings().all()
        return [
            AttendancePoint(
                venue_id=row["venue_id"],
                night_date=row["night_date"],
                redeemed_tickets=int(row["redeemed_tickets"]),
            )
            for row in rows
        ]
