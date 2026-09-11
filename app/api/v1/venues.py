from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import AuthedDbSession, CurrentPrincipal
from app.api.v1.schemas import VenueOut
from app.data.venue_repository import VenueRepository

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueOut])
async def list_venues(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
    account_id: UUID | None = Query(None),
) -> list[VenueOut]:
    scope = principal.resolve_account_scope(account_id)
    venues = await VenueRepository(session).list_for_scope(scope)
    return [
        VenueOut(
            venue_id=v.venue_id,
            account_id=v.account_id,
            name=v.name,
            city=v.city,
        )
        for v in venues
    ]
