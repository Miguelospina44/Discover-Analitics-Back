import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.domain.errors import AppError

logger = logging.getLogger(__name__)

_GENERIC_DB = "Error al procesar la solicitud. Intenta de nuevo más tarde."
_GENERIC_INTERNAL = "Error interno del servidor"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Error de base de datos: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": _GENERIC_DB})

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no controlado: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": _GENERIC_INTERNAL})
