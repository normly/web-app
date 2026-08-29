# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from normly_api.rate_limit import enforce_rate_limit
from normly_core.graph.postgres.orm import RateLimitBucketORM


@pytest.fixture()
def rate_limited_client(client):
    """
    The shared `client` fixture disables rate limiting for the rest of the
    suite (see conftest.py). These tests are the ones that must NOT be
    no-op'd, so they drop that override and run the real dependency --
    including its own session and its commit.
    """
    client.app.dependency_overrides.pop(enforce_rate_limit, None)
    return client


@pytest.fixture()
def anon_id() -> str:
    """
    A fresh identifier per test. The real dependency commits to the
    session-scoped container, so a literal key would collide with a
    neighbouring test, a re-run of the same test, or a second test session
    within the same minute.
    """
    return f"anon-{uuid.uuid4()}"


def _bucket_total(engine, key_suffix: str) -> int:
    with Session(engine) as session:
        rows = session.execute(
            select(RateLimitBucketORM).where(RateLimitBucketORM.key.like(f"{key_suffix}%"))
        ).scalars().all()
        return sum(row.request_count for row in rows)


def test_requests_within_the_limit_succeed(rate_limited_client, monkeypatch, anon_id):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        response = rate_limited_client.get(
            "/v1/documents/search",
            params={"jurisdiction": "DE"},
            headers={"X-Normly-Anon-Id": anon_id},
        )
        assert response.status_code == 200


def test_exceeding_the_limit_returns_429(rate_limited_client, monkeypatch, anon_id):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        rate_limited_client.get(
            "/v1/documents/search",
            params={"jurisdiction": "DE"},
            headers={"X-Normly-Anon-Id": anon_id},
        )

    response = rate_limited_client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": anon_id},
    )
    assert response.status_code == 429


def test_different_anon_ids_are_counted_separately(rate_limited_client, monkeypatch, anon_id):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 1)
    other_anon_id = f"anon-{uuid.uuid4()}"

    rate_limited_client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": anon_id},
    )
    response = rate_limited_client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": other_anon_id},
    )
    assert response.status_code == 200


def test_the_counter_is_committed_and_outlives_the_request(
    rate_limited_client, monkeypatch, anon_id, migrated_engine,
):
    """
    The regression guard for the bug this whole dependency had:
    record_and_check only flushes, and the request's own session is rolled
    back when it closes, so unless enforce_rate_limit commits on a session of
    its own, nothing is ever persisted and the limiter is inert in production.
    Asserting the 429 alone does not prove this -- inside one test the shared,
    still-open session would show a working counter either way. Reading the
    row back through a *separate* connection is what proves the commit.
    """
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 2)

    statuses = [
        rate_limited_client.get(
            "/v1/documents/search",
            params={"jurisdiction": "DE"},
            headers={"X-Normly-Anon-Id": anon_id},
        ).status_code
        for _ in range(4)
    ]

    assert statuses == [200, 200, 429, 429]
    assert _bucket_total(migrated_engine, anon_id) == 4


def test_a_spoofed_leftmost_forwarded_for_does_not_buy_a_fresh_bucket(
    rate_limited_client, monkeypatch, anon_id,
):
    """
    Proxies append to X-Forwarded-For, so the leftmost entry is whatever the
    caller sent. Keying on it would let anyone reset their own counter by
    varying that value; only the rightmost entry -- what our own trusted hop
    saw -- is trustworthy.
    """
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 1)

    first = rate_limited_client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": anon_id, "X-Forwarded-For": "203.0.113.9, 10.0.0.1"},
    )
    second = rate_limited_client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": anon_id, "X-Forwarded-For": "198.51.100.4, 10.0.0.1"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
