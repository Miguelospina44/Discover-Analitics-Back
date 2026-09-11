from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.exc import ProgrammingError

from app.api.deps import AuthedDbSession, CurrentPrincipal, CurrentSettings
from app.api.v1.schemas import (
    AttendancePointOut,
    GenderMeasureResponse,
    GenderPointOut,
    GremialBenchmarksResponse,
    MeasureResponse,
    SalesMeasureResponse,
    SalesPointOut,
)
from app.data.attendance_repository import AttendanceRepository
from app.data.benchmark_repository import BenchmarkRepository
from app.data.gender_repository import GenderRepository
from app.data.sales_repository import SalesRepository, quality_for_sales
from app.domain.measures import (
    ATTENDANCE_BY_GENDER,
    NIGHTLY_ATTENDANCE,
    SALES_BY_NIGHT,
    quality_for_points,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])

_GENDERS = frozenset({"woman", "man", "other", "undisclosed"})


def _gender_param(gender: str | None) -> str | None:
    if gender is None:
        return None
    if gender not in _GENDERS:
        return None
    return gender


@router.get("/nightly-attendance", response_model=MeasureResponse)
async def nightly_attendance(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    gender: str | None = Query(None),
) -> MeasureResponse:
    scope_id = principal.resolve_account_scope(account_id)
    try:
        points = await AttendanceRepository(session, settings).list_for_scope(
            scope_id,
            period_start,
            period_end,
            venue_id=venue_id,
            gender=_gender_param(gender),
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
        data_source=settings.data_source,
        scope="global" if scope_id is None else "account",
        points=[
            AttendancePointOut(
                venue_id=point.venue_id,
                night_date=point.night_date,
                redeemed_tickets=point.redeemed_tickets,
                account_id=point.account_id,
            )
            for point in points
        ],
    )


@router.get("/sales-by-night", response_model=SalesMeasureResponse)
async def sales_by_night(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
) -> SalesMeasureResponse:
    scope_id = principal.resolve_account_scope(account_id)
    try:
        points = await SalesRepository(session, settings).list_for_scope(
            scope_id,
            period_start,
            period_end,
            venue_id=venue_id,
        )
        quality = quality_for_sales(points)
    except ProgrammingError:
        await session.rollback()
        points = []
        quality = "missing"

    return SalesMeasureResponse(
        name=SALES_BY_NIGHT.name,
        title=SALES_BY_NIGHT.title,
        unit=SALES_BY_NIGHT.unit,
        definition=SALES_BY_NIGHT.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=quality,
        data_source=settings.data_source,
        scope="global" if scope_id is None else "account",
        points=[
            SalesPointOut(
                venue_id=point.venue_id,
                night_date=point.night_date,
                order_count=point.order_count,
                revenue_cents=point.revenue_cents,
                account_id=point.account_id,
            )
            for point in points
        ],
    )


@router.get("/attendance-by-gender", response_model=GenderMeasureResponse)
async def attendance_by_gender(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    gender: str | None = Query(None),
) -> GenderMeasureResponse:
    scope_id = principal.resolve_account_scope(account_id)
    try:
        result = await GenderRepository(session, settings).list_for_scope(
            scope_id,
            period_start,
            period_end,
            venue_id=venue_id,
            gender=_gender_param(gender),
        )
        points = result.points
        quality = result.quality
    except ProgrammingError:
        await session.rollback()
        points = []
        quality = "missing"

    return GenderMeasureResponse(
        name=ATTENDANCE_BY_GENDER.name,
        title=ATTENDANCE_BY_GENDER.title,
        unit=ATTENDANCE_BY_GENDER.unit,
        definition=ATTENDANCE_BY_GENDER.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=quality,
        data_source=settings.data_source,
        scope="global" if scope_id is None else "account",
        points=[
            GenderPointOut(
                gender=point.gender,
                headcount=point.headcount,
                share=point.share,
                account_id=point.account_id,
            )
            for point in points
        ],
    )


@router.get("/gremial-benchmarks", response_model=GremialBenchmarksResponse)
async def gremial_benchmarks(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
) -> GremialBenchmarksResponse:
    _ = principal
    try:
        bench = await BenchmarkRepository(session, settings).gremial(period_start, period_end)
    except ProgrammingError:
        await session.rollback()
        return GremialBenchmarksResponse(
            period_start=period_start,
            period_end=period_end,
            avg_tickets_per_venue_night=None,
            median_tickets_per_venue_night=None,
            avg_orders_per_venue_night=None,
            median_orders_per_venue_night=None,
            accounts_in_sample=0,
            nights_in_sample=0,
        )

    return GremialBenchmarksResponse(
        period_start=period_start,
        period_end=period_end,
        avg_tickets_per_venue_night=bench.avg_tickets_per_venue_night,
        median_tickets_per_venue_night=bench.median_tickets_per_venue_night,
        avg_orders_per_venue_night=bench.avg_orders_per_venue_night,
        median_orders_per_venue_night=bench.median_orders_per_venue_night,
        accounts_in_sample=bench.accounts_in_sample,
        nights_in_sample=bench.nights_in_sample,
        share_woman=bench.share_woman,
        share_man=bench.share_man,
        share_other=bench.share_other,
        share_undisclosed=bench.share_undisclosed,
    )
