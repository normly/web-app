# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The quota keys of an anonymous caller. Same derivation as api/'s rate
limiter (api/src/normly_api/rate_limit.py), duplicated because chat/ does
not depend on api/: X-Normly-Anon-Id from the frontend BFF plus the
rightmost X-Forwarded-For entry, the one our own reverse proxy appended.

The anon id is a client cookie, so a second key per address alone bounds
what rotating it can gain (ADR-029).
"""

from __future__ import annotations

import uuid

from starlette.requests import Request


def _client_origin_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _valid_anon_id(value: str | None) -> str | None:
    # The BFF issues UUIDs; anything else is dropped, which also bounds the
    # key length.
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def anonymous_caller_keys(request: Request) -> tuple[str, str]:
    """(caller key, address key) of an anonymous caller."""
    anon_id = _valid_anon_id(request.headers.get("x-normly-anon-id"))
    origin = _client_origin_address(request)
    caller_key = f"anon:{anon_id}:{origin}" if anon_id else f"anon:{origin}"
    return caller_key, f"anon-address:{origin}"
