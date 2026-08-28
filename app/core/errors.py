from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        fields = sorted(
            {
                str(error["loc"][-1])
                for error in exc.errors()
                if error.get("loc")
            }
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "La solicitud no cumple el contrato esperado.",
                "invalid_fields": fields,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Error no controlado | method=%s | path=%s | type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error interno controlado."},
            headers={"Cache-Control": "no-store"},
        )
