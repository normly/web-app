# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import make_account, make_admin, make_publisher


def _invite(client, headers, db_session, email, **extra):
    client.post("/v1/admin/invitations", headers=headers, json={"email": email, **extra})
    return PostgresInvitationRepository(db_session).get_invitation_by_email(email).token


def test_accepting_creates_a_verified_signed_in_publisher(client, db_session):
    _, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    token = _invite(client, headers, db_session, "partner@vde.example",
                    role="publisher", publisher_id=str(publisher.id), locale="en")

    response = client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert response.status_code == 200
    session_token = response.json()["session_token"]
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {session_token}"}).json()
    assert (session["role"], session["publisher_id"]) == ("publisher", str(publisher.id))
    account = PostgresAccountRepository(db_session).get_account_by_email("partner@vde.example")
    assert account.email_verified_at is not None and account.locale == "en"
    assert PostgresInvitationRepository(db_session).get_invitation_by_token(token) is None
    again = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (again.status_code, again.json()["detail"]) == (410, "invitation_invalid")


def test_an_existing_account_gets_the_role_only_on_accept(client, db_session):
    _, headers = make_admin(db_session)
    existing = make_account(db_session, "colleague@example.de", password="correct horse")
    token = _invite(client, headers, db_session, "colleague@example.de", role="administrator")
    accounts = PostgresAccountRepository(db_session)
    assert accounts.get_account_by_id(existing.id).role is Role.USER

    client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert accounts.get_account_by_id(existing.id).role is Role.ADMINISTRATOR


def test_a_matching_address_alone_never_grants_the_role(client, db_session):
    """Someone registers the invited address first; without the link nothing changes."""
    _, headers = make_admin(db_session)
    _invite(client, headers, db_session, "target@vde.example", role="administrator")
    client.post("/v1/accounts/register", json={"email": "target@vde.example", "password": "correct horse"})
    login = client.post("/v1/accounts/login", json={"email": "target@vde.example", "password": "correct horse"})
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {login.json()['session_token']}"}).json()
    assert session["role"] == "user"


def test_expired_and_blocked(client, db_session):
    _, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, "late@example.de", role="user")
    db_session.execute(sa.text("UPDATE account_invitation SET expires_at = :t WHERE token = :k"),
                       {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "k": token})
    assert client.post("/v1/accounts/invitations/accept", json={"token": token}).status_code == 410

    make_account(db_session, "soon-blocked@example.de")
    token = _invite(client, headers, db_session, "soon-blocked@example.de", role="user")
    account = PostgresAccountRepository(db_session).get_account_by_email("soon-blocked@example.de")
    client.post(f"/v1/admin/accounts/{account.id}/block", json={"reason": "abuse"}, headers=headers)
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (403, "account_blocked")


def test_accepting_a_user_invitation_cannot_remove_the_last_administrator(client, db_session):
    admin, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, admin.email, role="user")
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (409, "last_administrator")
    assert PostgresAccountRepository(db_session).get_account_by_id(admin.id).role is Role.ADMINISTRATOR
