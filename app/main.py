import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.v1 import (
    accounts,
    auth,
    consulting,
    engagements,
    events,
    health,
    metrics,
    venues,
)
from app.bootstrap import ensure_bootstrap_admin
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infra.db import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    factory = create_session_factory(settings)
    app.state.session_factory = factory
    try:
        await ensure_bootstrap_admin(factory, settings)
    except OSError:
        logging.getLogger(__name__).warning("Bootstrap omitido: base no disponible")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(accounts.router, prefix=settings.api_prefix)
    app.include_router(venues.router, prefix=settings.api_prefix)
    app.include_router(engagements.router, prefix=settings.api_prefix)
    app.include_router(metrics.router, prefix=settings.api_prefix)
    app.include_router(events.router, prefix=settings.api_prefix)
    app.include_router(consulting.router, prefix=settings.api_prefix)
    return app


app = create_app()
