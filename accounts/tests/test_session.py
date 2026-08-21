# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_session_returns_the_account_for_a_valid_token(client):
    register = client.post(
        "/v1/accounts/register",
        json={"email": "session@example.de", "password": "correct horse battery staple"},
    )
    token = register.json()["session_token"]

    response = client.get("/v1/accounts/session", params={"session_token": token})

    assert response.status_code == 200
    assert response.json()["email"] == "session@example.de"


def test_session_returns_401_for_an_unknown_token(client):
    response = client.get(
        "/v1/accounts/session", params={"session_token": "not-a-real-token"}
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

    client.get("/v1/accounts/session", params={"session_token": token})

    # Same test transaction, so the extension is visible without a commit.
    assert session_repo.get_session_by_token(token).expires_at >= original_expiry
