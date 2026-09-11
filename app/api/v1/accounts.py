from fastapi import APIRouter

from app.api.deps import AuthedDbSession, CurrentPrincipal
from app.api.v1.schemas import AccountOut
from app.data.account_repository import AccountRepository
from app.domain.errors import ForbiddenError

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> list[AccountOut]:
    if not principal.super_admin:
        raise ForbiddenError("Solo superadmin ve el listado de clientes")
    accounts = await AccountRepository(session).list_all()
    return [AccountOut.model_validate(a) for a in accounts]
