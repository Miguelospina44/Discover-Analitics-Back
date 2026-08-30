from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.orm import Finding, Recommendation


class ConsultingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_findings(self, account_id: UUID, engagement_id: UUID) -> list[Finding]:
        result = await self._session.execute(
            select(Finding)
            .where(Finding.account_id == account_id, Finding.engagement_id == engagement_id)
            .order_by(Finding.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_finding(self, finding: Finding) -> Finding:
        self._session.add(finding)
        await self._session.commit()
        await self._session.refresh(finding)
        return finding

    async def add_recommendation(self, recommendation: Recommendation) -> Recommendation:
        self._session.add(recommendation)
        await self._session.commit()
        await self._session.refresh(recommendation)
        return recommendation
