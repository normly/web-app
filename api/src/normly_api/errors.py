# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _describe_location(error: dict) -> str:
    """
    Name WHERE a validation error occurred, using only the location path
    pydantic reports ("query", "jurisdiction") -> "query.jurisdiction".

    The submitted value is deliberately never echoed back: reflecting caller
    input into a response body is an avoidable detail-leak, and the location
    alone is what the caller needs in order to fix the request.
    """
    location = error.get("loc") or ()
    return ".".join(str(part) for part in location) or "request"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_as_400(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # A malformed path segment (/v1/documents/not-a-uuid) and a missing
        # query parameter both land here, so the message is built from the
        # reported locations rather than assuming "query parameter".
        locations = sorted({_describe_location(error) for error in exc.errors()})
        detail = "invalid or missing parameter: " + ", ".join(locations)
        return JSONResponse(status_code=400, content={"detail": detail})

    @app.exception_handler(Exception)
    async def _unhandled_exception_as_503(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "service temporarily unavailable"},
        )
