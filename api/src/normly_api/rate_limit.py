# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresRateLimitRepository

# 60 anonymous requests/minute per key, applied to every api/ endpoint (not
# just search) -- see docs/superpowers/specs/2026-08-29-reference-graph-
# search-and-browse-design.md. Module-level so tests can monkeypatch it down
# to a small number instead of making 60 real requests. A fixed one-minute
# bucket (floored to the minute), not a sliding window: simple, and precise
# enough for the abuse pattern this guards against (systematic scraping),
# not split-second fairness.
_REQUESTS_PER_WINDOW = 60


def _client_origin_address(request: Request) -> str:
    # Trusts X-Forwarded-For from the immediate reverse proxy, per CLAUDE.md's
    # "hinter beliebigem Reverse Proxy" deployment assumption -- this is only
    # safe because the proxy is the sole path to this service; a caller
    # reaching api/ directly could otherwise spoof this header. Falls back to
    # the direct connection address when absent (e.g. local/test requests).
    #
    # Rightmost entry, not leftmost: proxies APPEND (nginx's
    # $proxy_add_x_forwarded_for), so the last entry is what our own trusted
    # hop observed, while everything left of it is caller-supplied and freely
    # forgeable. Exactly one hop is trusted, matching the deployment model.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    # X-Normly-Anon-Id is set by the frontend BFF's middleware and forwarded
    # on every proxied api/ call -- see frontend/src/middleware.ts. Its
    # absence (a hypothetical direct caller bypassing the frontend) degrades
    # to origin-address-only limiting rather than rejecting the request.
    anon_id = request.headers.get("x-normly-anon-id")
    origin = _client_origin_address(request)
    key = f"{anon_id}:{origin}" if anon_id else origin

    window_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    # Deliberately NOT the request's own session (get_session): that session is
    # closed -- and therefore rolled back -- at the end of the request, and
    # repository methods in this codebase flush but never commit. Counting a
    # request must survive the request, including when the handler afterwards
    # raises: a 404 from a scanned document ID has to count against the caller's
    # quota, because ID scanning is exactly the abuse this guards against.
    engine = request.app.state.engine
    with Session(engine) as session:
        allowed = PostgresRateLimitRepository(session).record_and_check(
            key=key, window_start=window_start, limit=_REQUESTS_PER_WINDOW,
        )
        session.commit()

    if not allowed:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
