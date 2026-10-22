# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The quota key of an anonymous caller. Same derivation as api/'s rate
limiter (api/src/normly_api/rate_limit.py), duplicated because chat/ does
not depend on api/: X-Normly-Anon-Id from the frontend BFF plus the
rightmost X-Forwarded-For entry, the one our own reverse proxy appended.
"""

from __future__ import annotations

from starlette.requests import Request


def _client_origin_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def anonymous_caller_key(request: Request) -> str:
    anon_id = request.headers.get("x-normly-anon-id")
    origin = _client_origin_address(request)
    return f"anon:{anon_id}:{origin}" if anon_id else f"anon:{origin}"
