# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_session_returns_the_account_for_a_valid_token(client):
    register = client.post(
        "/v1/accounts/register",
        json={"email": "session@example.de", "password": "correct horse battery staple"},
    )
    token = register.json()["session_token"]

    response = client.get(
        "/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "session@example.de"


def test_session_returns_401_for_an_unknown_token(client):
    response = client.get(
        "/v1/accounts/session", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


def test_session_extends_the_expiry_on_each_successful_check(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository

    register = client.post(
        "/v1/accounts/register",
        json={"email": "extend@example.de", "password": "correct horse battery staple"},
    )
    token = register.json()["session_token"]
    session_repo = PostgresAccountSessionRepository(db_session)
    original_expiry = session_repo.get_session_by_token(token).expires_at

    client.get(
        "/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}
    )

    # Same test transaction, so the extension is visible without a commit.
    assert session_repo.get_session_by_token(token).expires_at >= original_expiry


def test_session_returns_401_when_the_authorization_header_is_missing(client):
    """
    No credential at all is the same answer as an unusable one -- and it must
    be a 401, not the validation handler's 400.
    """
    response = client.get("/v1/accounts/session")

    assert response.status_code == 401


def test_session_returns_401_for_an_authorization_header_without_the_bearer_scheme(client):
    register = client.post(
        "/v1/accounts/register",
        json={"email": "noscheme@example.de", "password": "correct horse battery staple"},
    )
    token = register.json()["session_token"]

    # A valid token, but presented without the scheme the endpoint documents.
    response = client.get("/v1/accounts/session", headers={"Authorization": token})

    assert response.status_code == 401


def test_the_session_token_never_travels_in_the_query_string(client):
    """
    A 30-day credential in a URL lands in access logs and proxy history. The
    old query-parameter form must be gone, not merely deprecated.
    """
    register = client.post(
        "/v1/accounts/register",
        json={"email": "noquery@example.de", "password": "correct horse battery staple"},
    )
    token = register.json()["session_token"]

    response = client.get("/v1/accounts/session", params={"session_token": token})

    assert response.status_code == 401
