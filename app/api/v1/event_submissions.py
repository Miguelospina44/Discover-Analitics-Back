from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentPrincipal, CurrentSettings
from app.api.v1.schemas import (
    EventSubmissionBucketOut,
    EventSubmissionKpisOut,
    EventSubmissionListResponse,
    EventSubmissionOut,
    EventSubmissionSummaryResponse,
)
from app.data.event_submission_repository import EventSubmissionRepository
from app.domain.event_submissions import (
    DEMO_LABEL,
    as_of_date,
    resolve_event_form_access,
)

router = APIRouter(prefix="/event-submissions", tags=["event-submissions"])


def _item(row) -> EventSubmissionOut:
    return EventSubmissionOut(**row.as_public_dict())


@router.get("", response_model=EventSubmissionListResponse)
async def list_event_submissions(
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    collective: str | None = Query(None),
    presale: bool | None = Query(None),
    commission: str | None = Query(None),
) -> EventSubmissionListResponse:
    access = resolve_event_form_access(principal)
    repo = EventSubmissionRepository(settings)
    rows = repo.list_visible(
        access,
        period_start=period_start,
        period_end=period_end,
        collective=collective,
        presale=presale,
        commission=commission,
    )
    return EventSubmissionListResponse(
        name="event_submissions",
        title="Respuestas de detalles de evento",
        data_source=settings.event_form_source,
        is_demo=repo.is_demo,
        demo_label=DEMO_LABEL if repo.is_demo else None,
        as_of=as_of_date(),
        scope="admin" if access.kind == "all" else "collective",
        unmapped_visible=access.kind == "all",
        count=len(rows),
        items=[_item(row) for row in rows],
    )


@router.get("/summary", response_model=EventSubmissionSummaryResponse)
async def event_submissions_summary(
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    collective: str | None = Query(None),
    presale: bool | None = Query(None),
    commission: str | None = Query(None),
) -> EventSubmissionSummaryResponse:
    access = resolve_event_form_access(principal)
    repo = EventSubmissionRepository(settings)
    summary = repo.summarize(
        access,
        period_start=period_start,
        period_end=period_end,
        collective=collective,
        presale=presale,
        commission=commission,
    )
    return EventSubmissionSummaryResponse(
        name="event_submissions_summary",
        title="Resumen de respuestas de detalles de evento",
        data_source=settings.event_form_source,
        is_demo=repo.is_demo,
        demo_label=DEMO_LABEL if repo.is_demo else None,
        as_of=as_of_date(),
        scope="admin" if access.kind == "all" else "collective",
        kpis=EventSubmissionKpisOut(
            event_count=summary.event_count,
            collective_count=summary.collective_count,
            presale_pct=summary.presale_pct,
            events_this_month=summary.events_this_month,
            top_collective=summary.top_collective,
        ),
        unmapped_count=summary.unmapped_count,
        distributions={
            "by_month": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_month
            ],
            "by_commission": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_commission
            ],
            "by_presale": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_presale
            ],
            "by_commitment": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_commitment
            ],
            "by_benefit": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_benefit
            ],
            "by_payment_method": [
                EventSubmissionBucketOut(key=item.key, count=item.count)
                for item in summary.by_payment_method
            ],
        },
    )
