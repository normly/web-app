# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import auth_headers, make_account, make_admin, make_publisher

ADMIN_ENDPOINTS = [
    ("GET", "/v1/admin/publishers", None),
    ("POST", "/v1/admin/publishers", {"name": "X"}),
    ("GET", "/v1/admin/invitations/check?email=a@b.example", None),
    ("POST", "/v1/admin/invitations", {"email": "a@b.example", "role": "user"}),
]


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ENDPOINTS)
def test_admin_endpoints_need_an_administrator(client, db_session, method, path, body):
    assert client.request(method, path, json=body).status_code == 401
    for role in (Role.USER, Role.PUBLISHER):
        publisher_id = make_publisher(db_session, f"P-{role.value}").id if role is Role.PUBLISHER else None
        account = make_account(db_session, f"{role.value}@example.de", role=role, publisher_id=publisher_id)
        response = client.request(method, path, json=body, headers=auth_headers(db_session, account))
        assert response.status_code == 403


def test_create_and_list_publishers(client, db_session):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/publishers", json={"name": "  DIN Media  "}, headers=headers)
    assert created.status_code == 201
    assert created.json()["name"] == "DIN Media"
    duplicate = client.post("/v1/admin/publishers", json={"name": "din media"}, headers=headers)
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "publisher_name_taken")
    assert [p["name"] for p in client.get("/v1/admin/publishers", headers=headers).json()] == ["DIN Media"]


def test_invite_a_publisher_sends_the_mail_with_the_personal_message(client, db_session, email_sender):
    admin, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    response = client.post("/v1/admin/invitations", headers=headers, json={
        "email": "partner@vde.example", "role": "publisher", "publisher_id": str(publisher.id),
        "locale": "de", "message": "Wie besprochen.",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["email_sent"] is True and body["role"] == "publisher"
    invitation = PostgresInvitationRepository(db_session).get_invitation_by_email("partner@vde.example")
    [mail] = email_sender.sent
    assert mail["to"] == "partner@vde.example"
    assert f"/invitation?token={invitation.token}" in mail["body"]
    assert "Wie besprochen." in mail["body"] and "VDE Verlag" in mail["body"]
    assert PostgresAdminAuditRepository(db_session).list_for_target_account(admin.id) == []


@pytest.mark.parametrize("payload", [
    {"email": "x@example.de", "role": "publisher"},  # missing publisher
    {"email": "x@example.de", "role": "user", "publisher_id": "00000000-0000-0000-0000-000000000001"},
    {"email": "x@example.de", "role": "user", "message": "x" * 501},
    {"email": "x@example.de", "role": "publisher", "publisher_id": "00000000-0000-0000-0000-000000000001"},
])
def test_invalid_invitations_are_rejected_with_400(client, db_session, payload):
    _, headers = make_admin(db_session)
    assert client.post("/v1/admin/invitations", json=payload, headers=headers).status_code == 400


def test_an_unknown_publisher_is_named_by_a_fixed_code(client, db_session):
    _, headers = make_admin(db_session)
    response = client.post("/v1/admin/invitations", headers=headers, json={
        "email": "x@example.de", "role": "publisher",
        "publisher_id": "00000000-0000-0000-0000-000000000001",
    })
    assert (response.status_code, response.json()["detail"]) == (400, "unknown_publisher")


def test_a_blocked_account_cannot_be_invited(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "blocked@example.de", blocked=True)
    response = client.post("/v1/admin/invitations", headers=headers,
                           json={"email": "blocked@example.de", "role": "user"})
    assert (response.status_code, response.json()["detail"]) == (409, "account_blocked")


def test_check_reports_existing_account_and_open_invitation(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "known@example.de")
    client.post("/v1/admin/invitations", headers=headers, json={"email": "known@example.de", "role": "user"})
    body = client.get("/v1/admin/invitations/check?email=known@example.de", headers=headers).json()
    assert body == {"existing_account": True, "blocked": False, "open_invitation": True,
                    "verified": False}


def test_check_reports_whether_the_account_is_verified(client, db_session):
    """The dialog warns that accepting resets an unverified account (ADR-030)."""
    _, headers = make_admin(db_session)
    account = make_account(db_session, "verified-check@example.de")
    PostgresAccountRepository(db_session).mark_email_verified(account.id, datetime.now(timezone.utc))
    db_session.flush()

    def check(email):
        return client.get(f"/v1/admin/invitations/check?email={email}", headers=headers).json()

    assert check("verified-check@example.de")["verified"] is True
    assert check("nobody@example.de") == {"existing_account": False, "blocked": False,
                                          "open_invitation": False, "verified": False}


def test_resend_replaces_the_token_and_sends_no_personal_message(client, db_session, email_sender):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/invitations", headers=headers, json={
        "email": "again@example.de", "role": "user", "message": "Erste Nachricht",
    }).json()
    repo = PostgresInvitationRepository(db_session)
    old_token = repo.get_invitation(created["id"]).token

    response = client.post(f"/v1/admin/invitations/{created['id']}/resend", headers=headers)

    assert response.status_code == 200
    assert repo.get_invitation_by_token(old_token) is None
    assert "Erste Nachricht" not in email_sender.sent[-1]["body"]


def test_withdraw_deletes_the_invitation_and_is_audited(client, db_session):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/invitations", headers=headers,
                          json={"email": "gone@example.de", "role": "user"}).json()
    assert client.delete(f"/v1/admin/invitations/{created['id']}", headers=headers).status_code == 204
    assert client.delete(f"/v1/admin/invitations/{created['id']}", headers=headers).status_code == 404
    actions = [
        row[0] for row in db_session.execute(
            sa.text(
                "SELECT action FROM admin_audit_log WHERE target_invitation_id = :i "
                "ORDER BY occurred_at"
            ), {"i": created["id"]},
        )
    ]
    assert actions == [AdminAction.INVITATION_CREATED.value, AdminAction.INVITATION_WITHDRAWN.value]


def test_a_failing_mail_relay_keeps_the_invitation(client, db_session):
    from normly_accounts.dependencies import get_email_sender

    class Raising:
        def send(self, **kwargs):
            raise OSError("simulated SMTP outage")

    client.app.dependency_overrides[get_email_sender] = lambda: Raising()
    _, headers = make_admin(db_session)
    response = client.post("/v1/admin/invitations", headers=headers,
                           json={"email": "nomail@example.de", "role": "user"})
    assert response.status_code == 201
    assert response.json()["email_sent"] is False
