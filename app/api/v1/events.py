from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import AuthedDbSession, CurrentPrincipal, CurrentSettings
from app.api.v1.schemas import EventOut, EventPerformanceOut, EventPerformanceResponse
from app.data.event_repository import EventRepository
from app.domain.errors import NotFoundError
from app.domain.measures import EVENT_PERFORMANCE, quality_for_event_performance

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    account_id: UUID | None = Query(None),
    venue_id: UUID | None = Query(None),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
) -> list[EventOut]:
    scope = principal.resolve_account_scope(account_id)
    events = await EventRepository(session).list_for_scope(
        scope,
        venue_id=venue_id,
        period_start=period_start,
        period_end=period_end,
    )
    return [EventOut.model_validate(event) for event in events]


@router.get("/{event_id}", response_model=EventPerformanceResponse)
async def get_event(
    event_id: UUID,
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    account_id: UUID | None = Query(None),
) -> EventPerformanceResponse:
    scope = principal.resolve_account_scope(account_id)
    repo = EventRepository(session)
    event = await repo.get_by_id(event_id, scope)
    if event is None:
        raise NotFoundError("Evento no encontrado")

    perf = await repo.performance_for_event(event_id, scope)
    quality = quality_for_event_performance(perf)

    return EventPerformanceResponse(
        name=EVENT_PERFORMANCE.name,
        title=EVENT_PERFORMANCE.title,
        unit=EVENT_PERFORMANCE.unit,
        definition=EVENT_PERFORMANCE.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=quality,
        data_source=settings.data_source,
        scope="global" if scope is None else "account",
        event=EventOut.model_validate(event),
        performance=EventPerformanceOut(
            redeemed_tickets=perf.redeemed_tickets if perf else None,
            order_count=perf.order_count if perf else None,
            revenue_cents=perf.revenue_cents if perf else None,
            headcount_woman=perf.headcount_woman if perf else None,
            headcount_man=perf.headcount_man if perf else None,
            headcount_other=perf.headcount_other if perf else None,
            headcount_undisclosed=perf.headcount_undisclosed if perf else None,
            headcount_total=perf.headcount_total if perf else None,
        ),
    )
