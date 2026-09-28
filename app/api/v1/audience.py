"""Fase D: segmentación ANÓNIMA de audiencia (¿quién es mi público?).

INVARIANTE DE PRIVACIDAD: este endpoint SOLO devuelve agregados anónimos
(conteos y shares por bucket). Nunca expone datos personales; la respuesta no
incluye nombres, correos, teléfonos ni filas por individuo.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.exc import ProgrammingError

from app.api.deps import AuthedDbSession, CurrentPrincipal, CurrentSettings
from app.api.v1.schemas import AudienceProfileResponse, AudienceSegmentOut
from app.data.audience_repository import AudienceRepository
from app.domain.measures import AUDIENCE_PROFILE, quality_for_audience

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/audience", response_model=AudienceProfileResponse)
async def audience_profile(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    settings: CurrentSettings,
    period_start: date = Query(...),
    period_end: date = Query(...),
    account_id: UUID | None = Query(None),
) -> AudienceProfileResponse:
    scope_id = principal.resolve_account_scope(account_id)
    try:
        profile = await AudienceRepository(session, settings).profile_for_scope(
            scope_id,
            period_start,
            period_end,
        )
        segments = profile.segments
        quality = quality_for_audience(segments)
    except ProgrammingError:
        await session.rollback()
        segments = []
        quality = "missing"

    return AudienceProfileResponse(
        name=AUDIENCE_PROFILE.name,
        title=AUDIENCE_PROFILE.title,
        unit=AUDIENCE_PROFILE.unit,
        definition=AUDIENCE_PROFILE.definition,
        as_of=datetime.now(UTC).date(),
        data_quality=quality,
        data_source=settings.data_source,
        scope="global" if scope_id is None else "account",
        period_start=period_start,
        period_end=period_end,
        segments=[
            AudienceSegmentOut(
                dimension=segment.dimension,
                key=segment.key,
                headcount=segment.headcount,
                share=segment.share,
            )
            for segment in segments
        ],
    )
