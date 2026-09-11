from fastapi import APIRouter

from app.api.deps import AuthedDbSession, CurrentPrincipal, CurrentSettings, DbSession
from app.api.v1.schemas import LoginRequest, MeResponse, TokenResponse
from app.core.security import create_access_token, verify_password
from app.data.account_repository import AccountRepository
from app.data.user_repository import UserRepository
from app.domain.errors import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: DbSession,
    settings: CurrentSettings,
) -> TokenResponse:
    user = await UserRepository(session).get_by_email(body.email.lower())
    if user is None or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Credenciales inválidas")
    token = create_access_token(
        settings=settings,
        user_id=user.id,
        account_id=user.account_id,
        role=user.role,
        email=user.email,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(
    session: AuthedDbSession,
    principal: CurrentPrincipal,
) -> MeResponse:
    account = await AccountRepository(session).get_by_id(principal.account_id)
    return MeResponse(
        email=principal.email,
        role=principal.role,
        account_id=principal.account_id,
        account_name=account.name if account else None,
    )
