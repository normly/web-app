# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_as_400(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "invalid or missing query parameter"},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_as_503(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "service temporarily unavailable"},
        )
