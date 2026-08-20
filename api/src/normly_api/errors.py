# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from normly_api.schemas import ErrorResponse

# The two handlers below are registered application-wide, so every route can
# answer with a 400 or a 503 regardless of what it declares itself. Passing this
# to include_router() is how that gets into the schema: FastAPI merges the
# router-level `responses` with whatever a single route declares on top of them,
# and the route wins on a shared status code -- which is what lets /v1/export
# refine the 400 description below without losing the 503.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "Malformed request -- an invalid or missing path or query parameter.",
    },
    503: {
        "model": ErrorResponse,
        "description": "The service cannot reach its database. Retrying may succeed.",
    },
}

NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": (
            "No such document, or the document is not rights-classified for the "
            "requested jurisdiction. The two are deliberately indistinguishable: "
            "telling them apart would disclose the existence of gated content."
        ),
    },
}


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

    # Only genuinely infrastructure-level failures become 503. A programming
    # error (a KeyError, a None dereference, a RuntimeError raised on an
    # inconsistent database state) must NOT be dressed up as "temporarily
    # unavailable": that invites a pointless retry and hides the defect from
    # anyone watching status codes. Everything not listed here propagates and
    # surfaces as an honest 500.
    #
    # ConnectionError is a subclass of OSError and so is covered by it.
    for infrastructure_error in (SQLAlchemyError, OSError):

        @app.exception_handler(infrastructure_error)
        async def _infrastructure_error_as_503(
            request: Request, exc: Exception
        ) -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={"detail": "service temporarily unavailable"},
            )
