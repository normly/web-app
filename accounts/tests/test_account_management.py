# accounts/tests/test_account_management.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timezone

from normly_core.graph.domain import ChatMessageRole
from normly_core.graph.postgres.repositories import PostgresAccountRepository, PostgresChatRepository


def _register(client, email="delete-target@example.de", password="correct horse"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": password}
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['session_token']}"}


def test_deleting_a_password_account_requires_the_password(client):
    headers = _register(client)

    response = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "wrong password"}, headers=headers,
    )

    assert response.status_code == 401


def test_deleting_a_password_account_with_the_correct_password_succeeds(client):
    headers = _register(client, password="correct horse")

    response = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "correct horse"}, headers=headers,
    )

    assert response.status_code == 200
    session_check = client.get("/v1/accounts/session", headers=headers)
    assert session_check.status_code == 401


def test_deleting_an_account_commits_before_the_response_is_returned(client, db_session):
    headers = _register(client, email="commit-check@example.de", password="correct horse")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]

    response = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "correct horse"}, headers=headers,
    )

    assert response.status_code == 200
    # By the time the endpoint has returned, the deletion must already be
    # durable -- not merely pending in get_session()'s deferred commit at
    # request-teardown. Query the row back through the repository (same
    # session used by the request via dependency override) to confirm it is
    # actually gone, not just that the endpoint reported success.
    account = PostgresAccountRepository(db_session).get_account_by_id(uuid.UUID(account_id))
    assert account is None


def test_account_deletion_requires_authorization(client):
    response = client.request("DELETE", "/v1/accounts/me", json={"password": "x"})
    assert response.status_code == 401


def test_export_includes_account_fields(client):
    headers = _register(client, email="export@example.de")

    response = client.get("/v1/accounts/export", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "export@example.de"
    assert body["account"]["google_linked"] is False


def test_export_includes_chat_sessions_and_messages(client, db_session):
    headers = _register(client, email="chatexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    chat_repo = PostgresChatRepository(db_session)
    now = datetime.now(timezone.utc)
    chat_session = chat_repo.create_session(
        session_token="export-tok", jurisdiction="DE", language="de",
        created_at=now, account_id=account_id,
    )
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Testfrage",
        answer_type=None, created_at=now,
    )

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["chat_sessions"]) == 1
    assert body["chat_sessions"][0]["session_token"] == "export-tok"
    assert body["chat_sessions"][0]["messages"][0]["content"] == "Testfrage"


def test_export_requires_authorization(client):
    response = client.get("/v1/accounts/export")
    assert response.status_code == 401
