# accounts/tests/test_error_handling.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from fastapi.testclient import TestClient

from normly_accounts.dependencies import get_session
from normly_accounts.main import create_app


def test_a_malformed_request_body_is_400_not_422(client):
    response = client.post("/v1/accounts/register", json={"email": "not-an-email"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "body" in detail
    # The submitted value is never reflected back -- this body carries
    # passwords and tokens.
    assert "not-an-email" not in detail


def test_a_broken_database_dependency_is_503(monkeypatch, db_url):
    """
    A database outage is retryable and must say so. Without app-wide handlers
    this surfaced as a 500, which tells a caller nothing and invites no retry.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    app = create_app()

    def _broken_session():
        raise ConnectionError("simulated database outage")
        yield  # pragma: no cover -- unreachable, keeps this a generator

    app.dependency_overrides[get_session] = _broken_session

    with TestClient(app, raise_server_exceptions=False) as broken_client:
        response = broken_client.post(
            "/v1/accounts/login",
            json={"email": "someone@example.de", "password": "correct horse battery staple"},
        )

    assert response.status_code == 503
    body = response.json()
    # ErrorResponse-shaped: a single `detail` string, and nothing about the
    # underlying failure leaked into it.
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str)
    assert "outage" not in body["detail"]


def test_a_programming_error_is_not_disguised_as_a_503(monkeypatch, db_url):
    """
    Only infrastructure failures may claim "temporarily unavailable". A plain
    bug must surface as a 500 -- retrying it will not help, and a 503 would
    hide the defect from anyone watching status codes.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    app = create_app()

    def _buggy_session():
        raise ValueError("a genuine programming error, not an outage")
        yield  # pragma: no cover -- unreachable, keeps this a generator

    app.dependency_overrides[get_session] = _buggy_session

    with TestClient(app, raise_server_exceptions=False) as buggy_client:
        response = buggy_client.post(
            "/v1/accounts/login",
            json={"email": "someone@example.de", "password": "correct horse battery staple"},
        )

    assert response.status_code == 500
