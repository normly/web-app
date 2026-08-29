# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_requests_within_the_limit_succeed(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})
        assert response.status_code == 200


def test_exceeding_the_limit_returns_429(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        client.get("/v1/documents/search", params={"jurisdiction": "DE"})

    response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})
    assert response.status_code == 429


def test_different_anon_ids_are_counted_separately(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 1)

    client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": "anon-a"},
    )
    response = client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": "anon-b"},
    )
    assert response.status_code == 200
