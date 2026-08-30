from uuid import UUID

from fastapi import APIRouter

from app.api.deps import AuthedDbSession, CurrentPrincipal
from app.api.v1.schemas import EngagementCreate, EngagementOut
from app.data.engagement_repository import EngagementRepository
from app.domain.errors import AppError, NotFoundError
from app.infra.orm import Engagement

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.get("", response_model=list[EngagementOut])
async def list_engagements(session: AuthedDbSession, principal: CurrentPrincipal) -> list[Engagement]:
    return await EngagementRepository(session).list_for_account(principal.account_id)


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_engagement(
    engagement_id: UUID,
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> Engagement:
    engagement = await EngagementRepository(session).get_for_account(
        engagement_id, principal.account_id
    )
    if engagement is None:
        raise NotFoundError("Estudio no encontrado")
    return engagement


@router.post("", response_model=EngagementOut, status_code=201)
async def create_engagement(
    body: EngagementCreate,
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> Engagement:
    principal.require_write()
    if body.period_end < body.period_start:
        raise AppError("El fin del periodo no puede ser anterior al inicio")
    engagement = Engagement(
        account_id=principal.account_id,
        title=body.title,
        client_name=body.client_name,
        period_start=body.period_start,
        period_end=body.period_end,
        scope=body.scope,
        objectives=body.objectives,
        status="active",
    )
    return await EngagementRepository(session).add(engagement)
