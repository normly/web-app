# chat/src/normly_chat/errors.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from normly_chat.schemas import ErrorResponse

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "Malformed request -- an invalid or missing field.",
    },
    503: {
        "model": ErrorResponse,
        "description": "The service cannot reach the database, api/, accounts/, or Ollama.",
    },
}


def _describe_location(error: dict) -> str:
    location = error.get("loc") or ()
    return ".".join(str(part) for part in location) or "request"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_as_400(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        locations = sorted({_describe_location(error) for error in exc.errors()})
        detail = "invalid or missing parameter: " + ", ".join(locations)
        return JSONResponse(status_code=400, content={"detail": detail})

    import httpx

    for infrastructure_error in (SQLAlchemyError, OSError, httpx.HTTPError):

        @app.exception_handler(infrastructure_error)
        async def _infrastructure_error_as_503(
            request: Request, exc: Exception
        ) -> JSONResponse:
            return JSONResponse(
                status_code=503, content={"detail": "service temporarily unavailable"},
            )
