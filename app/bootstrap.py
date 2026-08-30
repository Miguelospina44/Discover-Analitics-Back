import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_password
from app.infra.orm import AnalyticsUser

logger = logging.getLogger(__name__)


async def ensure_bootstrap_admin(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if settings.is_production:
        return
    if not settings.bootstrap_account_id:
        logger.warning("BOOTSTRAP_ACCOUNT_ID vacío: no se crea usuario inicial")
        return

    async with factory() as session:
        existing = await session.execute(
            select(AnalyticsUser).where(AnalyticsUser.email == settings.bootstrap_admin_email.lower())
        )
        if existing.scalar_one_or_none() is not None:
            return
        session.add(
            AnalyticsUser(
                id=uuid4(),
                email=settings.bootstrap_admin_email.lower(),
                password_hash=hash_password(settings.bootstrap_admin_password),
                role="admin",
                account_id=UUID(settings.bootstrap_account_id),
            )
        )
        await session.commit()
        logger.info("Usuario bootstrap creado (solo development)")
