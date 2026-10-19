from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def _statement_timeout_ms(settings: Settings) -> str:
    return str(max(settings.query_timeout_seconds, 1) * 1000)


def app_connect_args(settings: Settings) -> dict:
    return {
        "timeout": 10,
        "command_timeout": settings.query_timeout_seconds,
        "server_settings": {
            "application_name": "discover-analytics-app",
            "statement_timeout": _statement_timeout_ms(settings),
        },
    }


def discover_connect_args(settings: Settings) -> dict:
    args: dict = {
        "timeout": settings.discover_pool_timeout,
        "command_timeout": settings.query_timeout_seconds,
        "server_settings": {
            "application_name": "discover-analytics-readonly",
            "default_transaction_read_only": "on",
            "statement_timeout": _statement_timeout_ms(settings),
        },
    }
    if settings.discover_require_ssl:
        args["ssl"] = True
    return args


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        connect_args=app_connect_args(settings),
    )
    return async_sessionmaker(engine, expire_on_commit=False)


def create_discover_session_factory(
    settings: Settings,
) -> async_sessionmaker[AsyncSession] | None:
    dsn = settings.discover_dsn
    if not settings.uses_discover_source or not dsn:
        return None

    engine = create_async_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=settings.discover_pool_size,
        max_overflow=settings.discover_max_overflow,
        pool_timeout=settings.discover_pool_timeout,
        connect_args=discover_connect_args(settings),
    )
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
