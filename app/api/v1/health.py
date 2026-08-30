from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import CurrentSettings, DbSession
from app.api.v1.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: CurrentSettings) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/ready", response_model=ReadyResponse)
async def ready(session: DbSession) -> ReadyResponse:
    await session.execute(text("SELECT 1"))
    return ReadyResponse(status="ok", database="up")
