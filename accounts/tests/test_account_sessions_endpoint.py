# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository


def _register(client, email="sessions@example.de"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": "correct horse"}
    )
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def test_list_sessions_includes_the_current_one_marked_as_such(client):
    token, headers = _register(client)

    response = client.get("/v1/accounts/sessions", headers=headers)

    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True


def test_list_sessions_includes_other_sessions_not_marked_current(client, db_session):
    token, headers = _register(client)
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    now = datetime.now(timezone.utc)
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=account_id, session_token="other-device-token", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = client.get("/v1/accounts/sessions", headers=headers)

    sessions = response.json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["is_current"]]
    other = [s for s in sessions if not s["is_current"]]
    assert len(current) == 1
    assert len(other) == 1


def test_revoking_another_session_removes_it_from_the_list(client, db_session):
    token, headers = _register(client)
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    now = datetime.now(timezone.utc)
    other = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account_id, session_token="revoke-target", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = client.delete(f"/v1/accounts/sessions/{other.id}", headers=headers)

    assert response.status_code == 200
    remaining = client.get("/v1/accounts/sessions", headers=headers).json()
    assert len(remaining) == 1


def test_revoking_a_session_that_does_not_belong_to_you_returns_404(client):
    _, headers_a = _register(client, email="a@example.de")
    token_b, headers_b = _register(client, email="b@example.de")
    sessions_b = client.get("/v1/accounts/sessions", headers=headers_b).json()
    b_session_id = sessions_b[0]["id"]

    response = client.delete(f"/v1/accounts/sessions/{b_session_id}", headers=headers_a)

    assert response.status_code == 404
    # b's session is untouched.
    still_there = client.get("/v1/accounts/sessions", headers=headers_b)
    assert still_there.status_code == 200


def test_sessions_endpoints_require_authorization(client):
    assert client.get("/v1/accounts/sessions").status_code == 401
    import uuid
    assert client.delete(f"/v1/accounts/sessions/{uuid.uuid4()}").status_code == 401
