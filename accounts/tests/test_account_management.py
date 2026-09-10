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


def test_export_includes_watchlist_entries(client, db_session):
    headers = _register(client, email="watchlistexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=uuid.UUID(account_id), work_id=work.id
    )
    db_session.commit()

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["watchlist"]) == 1
    assert body["watchlist"][0]["work_id"] == str(work.id)


def test_export_includes_notifications(client, db_session):
    headers = _register(client, email="notificationsexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresNotificationRepository(db_session).create(
        account_id=uuid.UUID(account_id), work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=None,
        trigger_document_id=None, trigger_jurisdiction=None, may_process=None,
        may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.commit()

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["work_id"] == str(work.id)
    assert body["notifications"][0]["trigger_type"] == "new_edition"
    assert body["notifications"][0]["emailed_at"] is None


def test_export_includes_notifications_even_for_email_preference_accounts(client, db_session):
    # notifications.py's list_notifications hides notifications in the in-app
    # feed once the account is EMAIL-only -- a display-only concern. The
    # export must NOT apply that filter: a full personal-data export shows
    # everything regardless of the account's current display preference.
    headers = _register(client, email="emailprefexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresNotificationRepository(db_session).create(
        account_id=uuid.UUID(account_id), work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=None,
        trigger_document_id=None, trigger_jurisdiction=None, may_process=None,
        may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.commit()

    # Sanity check: the in-app feed does hide it, as designed.
    assert client.get("/v1/accounts/notifications", headers=headers).json() == []

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["work_id"] == str(work.id)
