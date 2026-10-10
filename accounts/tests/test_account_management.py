# accounts/tests/test_account_management.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.domain import ChatMessageRole, NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository, PostgresChatRepository, PostgresNotificationRepository,
    PostgresWatchlistRepository, PostgresWorkRepository,
)


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


def test_deleting_an_account_commits_before_the_response_is_returned(real_client, migrated_engine):
    """
    Proves the deleted row is gone via a genuinely independent second
    connection (migrated_engine.connect(), not db_session) -- NOT that the
    commit happens before the response is sent. A TestClient call runs the
    whole request lifecycle, including get_session()'s own deferred commit,
    synchronously before this test function resumes -- there is no window
    for a second connection to race the response. What this DOES prove:
    the row is really durable in Postgres, not merely visible because the
    test and the app happened to share one uncommitted Session (the bug in
    the old version of this test).
    """
    headers = _register(real_client, email="commit-check-2@example.de", password="correct horse")
    account_id = real_client.get("/v1/accounts/session", headers=headers).json()["account_id"]

    response = real_client.request(
        "DELETE", "/v1/accounts/me", json={"password": "correct horse"}, headers=headers,
    )
    assert response.status_code == 200

    with migrated_engine.connect() as connection:
        account = PostgresAccountRepository(Session(bind=connection)).get_account_by_id(
            uuid.UUID(account_id)
        )
    assert account is None


def test_account_deletion_requires_authorization(client):
    response = client.request("DELETE", "/v1/accounts/me", json={"password": "x"})
    assert response.status_code == 401
