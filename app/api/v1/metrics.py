from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.exc import ProgrammingError

from app.api.deps import CurrentPrincipal, CurrentSettings, MetricsDbSession
from app.api.v1.schemas import (
    AttendancePointOut,
    AudienceGenderAgePointOut,
    AudienceGenderAgeResponse,
    GenderMeasureResponse,
    GenderPointOut,
    GremialBenchmarksResponse,
    MeasureResponse,
    SalesMeasureResponse,
    SalesPointOut,
)
from app.data.attendance_repository import AttendanceRepository
from app.data.audience_repository import AudienceRepository
from app.data.benchmark_repository import BenchmarkRepository
from app.data.gender_repository import GenderRepository
from app.data.sales_repository import SalesRepository, quality_for_sales
from app.domain.analytics_scope import organizer_scope, venue_scope
from app.domain.audience import DEMO_LABEL
from app.domain.measures import (
    ATTENDANCE_BY_GENDER,
    AUDIENCE_BY_GENDER_AGE,
    NIGHTLY_ATTENDANCE,
    SALES_BY_NIGHT,
    quality_for_points,
)
from app.domain.metric_definitions import MIN_COHORT_SIZE

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
    session: MetricsDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    gender: str | None = Query(None),
) -> MeasureResponse:
    scope = principal.resolve_access_scope(
        requested_account=account_id,
        requested_venue=venue_id,
        measure=NIGHTLY_ATTENDANCE.name,
    )
    scope_id = scope.account_id
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
    session: MetricsDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
) -> SalesMeasureResponse:
    scope = principal.resolve_access_scope(
        requested_account=account_id,
        requested_venue=venue_id,
        measure=SALES_BY_NIGHT.name,
    )
    scope_id = scope.account_id
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
    session: MetricsDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    gender: str | None = Query(None),
) -> GenderMeasureResponse:
    scope = principal.resolve_access_scope(
        requested_account=account_id,
        requested_venue=venue_id,
        measure=ATTENDANCE_BY_GENDER.name,
    )
    scope_id = scope.account_id
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


@router.get("/audience-by-gender-age", response_model=AudienceGenderAgeResponse)
async def audience_by_gender_age(
    session: MetricsDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    event_id: UUID | None = Query(None),
) -> AudienceGenderAgeResponse:
    access = principal.resolve_access_scope(
        requested_account=account_id,
        requested_venue=venue_id,
        requested_event=event_id,
        measure=AUDIENCE_BY_GENDER_AGE.name,
    )
    scope_account = access.account_id or principal.account_id
    if access.event_scoped:
        data_scope = organizer_scope(scope_account, access.event_ids)
    else:
        data_scope = venue_scope(scope_account)

    try:
        result = await AudienceRepository(session, settings).list_gender_age(
            scope_account,
            period_start,
            period_end,
            venue_id=None if access.event_scoped else venue_id,
            scope=data_scope,
        )
    except ProgrammingError:
        await session.rollback()
        result = None

    if result is None:
        return AudienceGenderAgeResponse(
            name=AUDIENCE_BY_GENDER_AGE.name,
            title=AUDIENCE_BY_GENDER_AGE.title,
            unit=AUDIENCE_BY_GENDER_AGE.unit,
            definition=AUDIENCE_BY_GENDER_AGE.definition,
            as_of=datetime.now(UTC).date(),
            data_quality="missing",
            data_source=settings.data_source,
            is_demo=settings.uses_seed_facts,
            demo_label=DEMO_LABEL if settings.uses_seed_facts else None,
            scope="event" if access.event_scoped else "account",
            k_anonymity=MIN_COHORT_SIZE,
            suppressed=False,
            points=[],
        )

    return AudienceGenderAgeResponse(
        name=AUDIENCE_BY_GENDER_AGE.name,
        title=AUDIENCE_BY_GENDER_AGE.title,
        unit=AUDIENCE_BY_GENDER_AGE.unit,
        definition=AUDIENCE_BY_GENDER_AGE.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=result.quality,
        data_source=settings.data_source,
        is_demo=result.is_demo,
        demo_label=result.demo_label,
        scope="event" if access.event_scoped else "account",
        k_anonymity=MIN_COHORT_SIZE,
        suppressed=result.suppressed,
        points=[
            AudienceGenderAgePointOut(
                gender=point.gender,
                age_band=point.age_band,
                headcount=point.headcount,
                share=point.share,
            )
            for point in result.points
        ],
    )


@router.get("/gremial-benchmarks", response_model=GremialBenchmarksResponse)
async def gremial_benchmarks(
    session: MetricsDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
) -> GremialBenchmarksResponse:
    principal.require_entitlement("gremial_benchmarks")
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
