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


def test_notification_endpoints_require_authentication(client):
    response = client.get("/v1/accounts/notifications")
    assert response.status_code == 401
