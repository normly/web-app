# accounts/tests/test_notifications.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresNotificationRepository,
    PostgresWorkRepository,
)


def _register_and_authorize(client, email="notifications@example.de"):
    response = client.post("/v1/accounts/register", json={"email": email, "password": "correct horse"})
    body = response.json()
    return body["account"]["id"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_notification(db_session, account_id):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    # trigger_edge_id has an FK to the edge table -- a fabricated UUID here
    # would violate that constraint, and these tests don't exercise edge
    # linkage, so use the nullable None the schema already allows.
    notification = PostgresNotificationRepository(db_session).create(
        account_id=account_id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.commit()
    return notification


def test_list_notifications(client, db_session):
    account_id, headers = _register_and_authorize(client)
    _make_notification(db_session, account_id)

    response = client.get("/v1/accounts/notifications", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["read_at"] is None


def test_mark_notification_read(client, db_session):
    account_id, headers = _register_and_authorize(client)
    notification = _make_notification(db_session, account_id)

    response = client.patch(f"/v1/accounts/notifications/{notification.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_mark_notification_read_for_a_missing_id_returns_404(client):
    _, headers = _register_and_authorize(client)
    response = client.patch(f"/v1/accounts/notifications/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_mark_notification_read_for_another_accounts_notification_returns_404(client, db_session):
    account_id_1, headers_1 = _register_and_authorize(client, email="account1@example.de")
    _, headers_2 = _register_and_authorize(client, email="account2@example.de")
    notification = _make_notification(db_session, account_id_1)

    response = client.patch(f"/v1/accounts/notifications/{notification.id}", headers=headers_2)
    assert response.status_code == 404


def test_notification_endpoints_require_authentication(client):
    response = client.get("/v1/accounts/notifications")
    assert response.status_code == 401


def test_email_only_preference_hides_notifications_from_the_in_app_feed(client, db_session):
    """
    "Nur per E-Mail" has to be distinguishable from "beides": the rows are
    still created (for dedup and for the mail itself), but the bell feed
    hides them. The account's CURRENT preference governs the CURRENT display
    -- no preference-at-creation-time is tracked per row.
    """
    account_id, headers = _register_and_authorize(client, email="email-only@example.de")
    _make_notification(db_session, account_id)
    assert len(client.get("/v1/accounts/notifications", headers=headers).json()) == 1

    client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )

    response = client.get("/v1/accounts/notifications", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_switching_away_from_email_only_makes_notifications_visible_again(client, db_session):
    account_id, headers = _register_and_authorize(client, email="email-then-both@example.de")
    _make_notification(db_session, account_id)
    client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )
    assert client.get("/v1/accounts/notifications", headers=headers).json() == []

    client.patch(
        "/v1/accounts/profile", json={"notification_preference": "both"}, headers=headers
    )

    assert len(client.get("/v1/accounts/notifications", headers=headers).json()) == 1
