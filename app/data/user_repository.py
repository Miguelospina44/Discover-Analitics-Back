from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.orm import AnalyticsUser


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> AnalyticsUser | None:
        result = await self._session.execute(
            select(AnalyticsUser).where(AnalyticsUser.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> AnalyticsUser | None:
        result = await self._session.execute(
            select(AnalyticsUser).where(AnalyticsUser.id == user_id)
        )
        return result.scalar_one_or_none()
