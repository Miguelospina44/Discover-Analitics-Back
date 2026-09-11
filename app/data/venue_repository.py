from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.orm import DimVenue


class VenueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scope(self, account_id: UUID | None) -> list[DimVenue]:
        q = select(DimVenue).order_by(DimVenue.name.asc())
        if account_id is not None:
            q = q.where(DimVenue.account_id == account_id)
        result = await self._session.execute(q)
        return list(result.scalars().all())
