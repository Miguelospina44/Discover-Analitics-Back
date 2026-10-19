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


async def get_discover_db(request: Request) -> AsyncIterator[AsyncSession]:
    discover_factory = getattr(request.app.state, "discover_session_factory", None)
    if discover_factory is None:
        async for session in get_db(request):
            yield session
    else:
        async with discover_factory() as session:
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
        plan=settings.default_plan,
        tenant_kind=settings.default_tenant_kind,
    )


async def get_db_for_user(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    async for session in get_db(request):
        yield session


async def get_metrics_db(
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(settings_dep),
) -> AsyncIterator[AsyncSession]:
    if settings.uses_discover_source:
        async for session in get_discover_db(request):
            yield session
    else:
        async for session in get_db(request):
            yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthedDbSession = Annotated[AsyncSession, Depends(get_db_for_user)]
MetricsDbSession = Annotated[AsyncSession, Depends(get_metrics_db)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
CurrentSettings = Annotated[Settings, Depends(settings_dep)]
