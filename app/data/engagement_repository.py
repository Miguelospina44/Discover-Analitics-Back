from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.orm import Engagement


class EngagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_account(self, account_id: UUID) -> list[Engagement]:
        result = await self._session.execute(
            select(Engagement)
            .where(Engagement.account_id == account_id)
            .order_by(Engagement.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_account(self, engagement_id: UUID, account_id: UUID) -> Engagement | None:
        result = await self._session.execute(
            select(Engagement).where(
                Engagement.id == engagement_id,
                Engagement.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, engagement: Engagement) -> Engagement:
        self._session.add(engagement)
        await self._session.commit()
        await self._session.refresh(engagement)
        return engagement
