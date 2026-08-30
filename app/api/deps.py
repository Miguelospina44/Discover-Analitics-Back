from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.domain.errors import UnauthorizedError
from app.domain.principal import Principal
from app.infra.db import create_session_factory

bearer = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        factory = create_session_factory(get_settings())
        request.app.state.session_factory = factory
    async with factory() as session:
        yield session


def settings_dep() -> Settings:
    return get_settings()


async def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> Principal:
    if creds is None or not creds.credentials:
        raise UnauthorizedError()
    payload = decode_access_token(creds.credentials, settings)
    return Principal(
        user_id=UUID(payload["sub"]),
        account_id=UUID(payload["account_id"]),
        role=str(payload["role"]),
        email=str(payload.get("email", "")),
    )


async def get_db_for_user(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    async for session in get_db(request):
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthedDbSession = Annotated[AsyncSession, Depends(get_db_for_user)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
CurrentSettings = Annotated[Settings, Depends(settings_dep)]
