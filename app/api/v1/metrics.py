from datetime import UTC, date, datetime

from fastapi import APIRouter, Query
from sqlalchemy.exc import ProgrammingError

from app.api.deps import AuthedDbSession, CurrentPrincipal
from app.api.v1.schemas import AttendancePointOut, MeasureResponse
from app.data.attendance_repository import AttendanceRepository
from app.domain.measures import NIGHTLY_ATTENDANCE, quality_for_points

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/nightly-attendance", response_model=MeasureResponse)
async def nightly_attendance(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    period_start: date = Query(...),
    period_end: date = Query(...),
) -> MeasureResponse:
    try:
        points = await AttendanceRepository(session).list_for_account(
            principal.account_id, period_start, period_end
        )
        quality = quality_for_points(points)
    except ProgrammingError:
        await session.rollback()
        points = []
        quality = "missing"

    return MeasureResponse(
        name=NIGHTLY_ATTENDANCE.name,
        title=NIGHTLY_ATTENDANCE.title,
        unit=NIGHTLY_ATTENDANCE.unit,
        definition=NIGHTLY_ATTENDANCE.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=quality,
        points=[
            AttendancePointOut(
                venue_id=point.venue_id,
                night_date=point.night_date,
                redeemed_tickets=point.redeemed_tickets,
            )
            for point in points
        ],
    )
