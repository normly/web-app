# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.postgres.repositories import PostgresAccountRepository


def test_setting_a_password_for_a_passwordless_account_needs_no_current_password(
    client, db_session
):
    account = PostgresAccountRepository(db_session).create_account(
        email="passwordless@example.de", password_hash=None
    )
    # Simulate an authenticated session the way a Google/magic-link login
    # would establish one, without going through that whole flow.
    login_response = client.post(
        "/v1/accounts/magic-link/request", json={"email": "passwordless@example.de"}
    )
    assert login_response.status_code == 200

    # No session exists yet for this pre-seeded account without going through
    # a real login flow -- register a password directly via the repository's
    # own session-issuing path instead, matching how login.py builds one.
    from datetime import datetime, timedelta, timezone
    from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="passwordless-session", created_at=now,
        expires_at=now + timedelta(days=30),
    )
    headers = {"Authorization": f"Bearer {session.session_token}"}

    response = client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 200
    login_check = client.post(
        "/v1/accounts/login", json={"email": "passwordless@example.de", "password": "new secret"}
    )
    assert login_check.status_code == 200


def test_changing_an_existing_password_requires_the_current_one(client):
    register = client.post(
        "/v1/accounts/register", json={"email": "haspassword@example.de", "password": "old secret"}
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = client.post(
        "/v1/accounts/password",
        json={"current_password": "wrong secret", "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 401


def test_changing_an_existing_password_with_the_correct_current_one_succeeds(client):
    register = client.post(
        "/v1/accounts/register", json={"email": "correct@example.de", "password": "old secret"}
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = client.post(
        "/v1/accounts/password",
        json={"current_password": "old secret", "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 200
    login_check = client.post(
        "/v1/accounts/login", json={"email": "correct@example.de", "password": "new secret"}
    )
    assert login_check.status_code == 200


def test_set_password_requires_authorization(client):
    response = client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "x"},
    )
    assert response.status_code == 401


def test_changing_a_password_via_real_client_is_durable_across_independent_requests(real_client):
    """
    Uses `real_client` (not `client`) so get_session()'s own commit-at-
    teardown genuinely runs against the real engine, and proves the change
    is durable by logging in again in a SEPARATE request -- each request
    through real_client gets its own freshly-constructed Session, not the
    one shared db_session the default `client` fixture reuses. This does
    NOT reproduce the original before-response-sent timing race (a
    TestClient call runs the whole request lifecycle, including the
    deferred commit, synchronously before this test function resumes) --
    it proves the new password hash is really durable and independently
    re-queryable, not merely visible within one shared, possibly-
    uncommitted session (the bug the old delete-account test had).
    """
    register = real_client.post(
        "/v1/accounts/register",
        json={"email": "real-client-password@example.de", "password": "old secret"},
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = real_client.post(
        "/v1/accounts/password",
        json={"current_password": "old secret", "new_password": "new secret"},
        headers=headers,
    )
    assert response.status_code == 200

    login_check = real_client.post(
        "/v1/accounts/login",
        json={"email": "real-client-password@example.de", "password": "new secret"},
    )
    assert login_check.status_code == 200
