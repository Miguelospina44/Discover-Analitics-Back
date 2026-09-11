from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.orm import Account


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: UUID) -> Account | None:
        result = await self._session.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Account]:
        result = await self._session.execute(select(Account).order_by(Account.name.asc()))
        return list(result.scalars().all())
