from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthedDbSession, CurrentPrincipal
from app.api.v1.schemas import (
    FindingCreate,
    FindingOut,
    RecommendationCreate,
    RecommendationOut,
)
from app.data.consulting_repository import ConsultingRepository
from app.data.engagement_repository import EngagementRepository
from app.domain.errors import NotFoundError
from app.infra.orm import Finding, Recommendation

router = APIRouter(tags=["consulting"])


async def _require_engagement(session: AsyncSession, account_id: UUID, engagement_id: UUID) -> None:
    found = await EngagementRepository(session).get_for_account(engagement_id, account_id)
    if found is None:
        raise NotFoundError("Estudio no encontrado")


@router.get("/findings", response_model=list[FindingOut])
async def list_findings(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    engagement_id: UUID = Query(...),
) -> list[Finding]:
    await _require_engagement(session, principal.account_id, engagement_id)
    return await ConsultingRepository(session).list_findings(principal.account_id, engagement_id)


@router.post("/findings", response_model=FindingOut, status_code=201)
async def create_finding(
    body: FindingCreate,
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> Finding:
    principal.require_write()
    await _require_engagement(session, principal.account_id, body.engagement_id)
    finding = Finding(
        account_id=principal.account_id,
        engagement_id=body.engagement_id,
        title=body.title,
        evidence=body.evidence,
        visual_id=body.visual_id,
        impact=body.impact,
        confidence=body.confidence,
        review_status="draft",
    )
    return await ConsultingRepository(session).add_finding(finding)


@router.post("/recommendations", response_model=RecommendationOut, status_code=201)
async def create_recommendation(
    body: RecommendationCreate,
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> Recommendation:
    principal.require_write()
    await _require_engagement(session, principal.account_id, body.engagement_id)
    recommendation = Recommendation(
        account_id=principal.account_id,
        engagement_id=body.engagement_id,
        finding_id=body.finding_id,
        action=body.action,
        expected_impact=body.expected_impact,
        effort=body.effort,
        priority=body.priority,
        owner=body.owner,
        due_date=body.due_date,
        status="pending_decision",
    )
    return await ConsultingRepository(session).add_recommendation(recommendation)
