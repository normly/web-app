# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import AccountTokenPurpose, Role
from normly_core.graph.postgres.repositories import PostgresAccountTokenRepository

from tests.admin_support import auth_headers, make_account, make_publisher


def test_session_reports_role_and_publisher(client, db_session):
    publisher = make_publisher(db_session)
    account = make_account(db_session, "p@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id)
    body = client.get("/v1/accounts/session", headers=auth_headers(db_session, account)).json()
    assert body["role"] == "publisher"
    assert body["publisher_id"] == str(publisher.id)


def test_a_blocked_account_has_no_valid_session(client, db_session):
    account = make_account(db_session, "blocked@example.de", blocked=True)
    headers = auth_headers(db_session, account)
    assert client.get("/v1/accounts/session", headers=headers).status_code == 401
    assert client.get("/v1/accounts/export", headers=headers).status_code == 401


def test_password_login_of_a_blocked_account_is_refused(client, db_session):
    make_account(db_session, "blocked-pw@example.de", password="correct horse", blocked=True)
    response = client.post(
        "/v1/accounts/login", json={"email": "blocked-pw@example.de", "password": "correct horse"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "account_blocked"


def test_a_wrong_password_still_answers_401_for_a_blocked_account(client, db_session):
    make_account(db_session, "blocked-pw2@example.de", password="correct horse", blocked=True)
    response = client.post(
        "/v1/accounts/login", json={"email": "blocked-pw2@example.de", "password": "wrong"}
    )
    assert response.status_code == 401


def test_magic_link_and_reset_requests_send_nothing_for_a_blocked_account(
    client, db_session, email_sender
):
    make_account(db_session, "blocked-ml@example.de", blocked=True)
    for path in ("/v1/accounts/magic-link/request", "/v1/accounts/password-reset/request"):
        response = client.post(path, json={"email": "blocked-ml@example.de"})
        assert response.status_code == 200
    assert email_sender.sent == []


def test_magic_link_confirm_of_a_blocked_account_is_refused(client, db_session):
    from datetime import datetime, timedelta, timezone

    account = make_account(db_session, "blocked-ml2@example.de", blocked=True)
    now = datetime.now(timezone.utc)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK, token="ml-blocked",
        created_at=now, expires_at=now + timedelta(minutes=15),
    )
    response = client.post("/v1/accounts/magic-link/confirm", json={"token": "ml-blocked"})
    assert response.status_code == 403
    assert response.json()["detail"] == "account_blocked"
