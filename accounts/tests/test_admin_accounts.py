# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import sqlalchemy as sa

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from tests.admin_support import auth_headers, make_account, make_admin, make_publisher


def _actions(db_session, account_id):
    return [r[0] for r in db_session.execute(sa.text(
        "SELECT action FROM admin_audit_log WHERE target_account_id = :a ORDER BY occurred_at"
    ), {"a": account_id})]


def test_downgrade_to_user_takes_effect_on_the_next_request(client, db_session):
    _, headers = make_admin(db_session)
    other, other_headers = make_admin(db_session, "second@normly.example")
    assert client.get("/v1/admin/publishers", headers=other_headers).status_code == 200

    response = client.patch(f"/v1/admin/accounts/{other.id}", json={"role": "user"}, headers=headers)

    assert response.status_code == 204
    assert client.get("/v1/admin/publishers", headers=other_headers).status_code == 403
    assert _actions(db_session, other.id) == ["role_changed"]


def test_upgrades_need_an_invitation(client, db_session):
    _, headers = make_admin(db_session)
    user = make_account(db_session, "plain@example.de")
    response = client.patch(f"/v1/admin/accounts/{user.id}", json={"role": "administrator"}, headers=headers)
    assert (response.status_code, response.json()["detail"]) == (409, "upgrade_requires_invitation")


def test_change_publisher(client, db_session):
    _, headers = make_admin(db_session)
    din, vde = make_publisher(db_session, "DIN Media"), make_publisher(db_session, "VDE Verlag")
    partner = make_account(db_session, "p@example.de", role=Role.PUBLISHER, publisher_id=din.id)

    response = client.patch(f"/v1/admin/accounts/{partner.id}",
                            json={"publisher_id": str(vde.id)}, headers=headers)

    assert response.status_code == 204
    assert PostgresAccountRepository(db_session).get_account_by_id(partner.id).publisher_id == vde.id
    user = make_account(db_session, "u@example.de")
    not_publisher = client.patch(f"/v1/admin/accounts/{user.id}",
                                 json={"publisher_id": str(vde.id)}, headers=headers)
    assert (not_publisher.status_code, not_publisher.json()["detail"]) == (409, "not_a_publisher")


def test_the_own_account_is_protected(client, db_session):
    admin, headers = make_admin(db_session)
    for method, path, body in (
        ("PATCH", f"/v1/admin/accounts/{admin.id}", {"role": "user"}),
        ("POST", f"/v1/admin/accounts/{admin.id}/block", {"reason": "other"}),
        ("DELETE", f"/v1/admin/accounts/{admin.id}", {"confirm_email": admin.email}),
    ):
        response = client.request(method, path, json=body, headers=headers)
        assert (response.status_code, response.json()["detail"]) == (409, "self_action")


def test_ensure_administrator_remains(db_session):
    """
    Through the panel the acting administrator is itself active, so the rule
    only bites when two administrators act at the same time (the row lock in
    lock_active_administrator_ids serializes them) and when an invitation is
    accepted (test_invitation_accept.py). Hence tested directly here.
    """
    import pytest
    from fastapi import HTTPException

    from normly_accounts.admin_rules import ensure_administrator_remains

    only = make_account(db_session, "only-admin@normly.example", role=Role.ADMINISTRATOR)
    with pytest.raises(HTTPException) as caught:
        ensure_administrator_remains(db_session, only)
    assert (caught.value.status_code, caught.value.detail) == (409, "last_administrator")

    blocked_admin = make_account(db_session, "blocked-admin@normly.example",
                                 role=Role.ADMINISTRATOR, blocked=True)
    with pytest.raises(HTTPException):
        ensure_administrator_remains(db_session, only)  # a blocked admin does not count
    ensure_administrator_remains(db_session, blocked_admin)  # not active: nothing to protect

    make_account(db_session, "second-admin@normly.example", role=Role.ADMINISTRATOR)
    ensure_administrator_remains(db_session, only)  # another active admin exists
    ensure_administrator_remains(db_session, make_account(db_session, "u@normly.example"))


def test_block_ends_sessions_mails_neutrally_and_unblock_restores(client, db_session, email_sender, monkeypatch):
    monkeypatch.setenv("NORMLY_CONTACT_EMAIL", "kontakt@normly.example")
    _, headers = make_admin(db_session)
    user = make_account(db_session, "crawler@example.de", locale="en")
    user_headers = auth_headers(db_session, user)

    response = client.post(f"/v1/admin/accounts/{user.id}/block",
                           json={"reason": "bulk_retrieval"}, headers=headers)

    assert response.json() == {"email_sent": True}
    assert client.get("/v1/accounts/session", headers=user_headers).status_code == 401
    [mail] = email_sender.sent
    assert mail["subject"] == "Your normly account has been blocked"
    assert "kontakt@normly.example" in mail["body"] and "bulk" not in mail["body"]
    again = client.post(f"/v1/admin/accounts/{user.id}/block", json={"reason": "abuse"}, headers=headers)
    assert (again.status_code, again.json()["detail"]) == (409, "already_blocked")

    assert client.post(f"/v1/admin/accounts/{user.id}/unblock", headers=headers).status_code == 204
    assert PostgresAccountRepository(db_session).get_account_by_id(user.id).blocked_at is None
    assert _actions(db_session, user.id) == ["account_blocked", "account_unblocked"]


def test_remove_needs_the_confirmation_address_and_keeps_the_audit(client, db_session, email_sender):
    _, headers = make_admin(db_session)
    user = make_account(db_session, "leaving@example.de")

    wrong = client.request("DELETE", f"/v1/admin/accounts/{user.id}",
                           json={"confirm_email": "other@example.de"}, headers=headers)
    assert wrong.status_code == 400

    response = client.request("DELETE", f"/v1/admin/accounts/{user.id}",
                              json={"confirm_email": " Leaving@example.de "}, headers=headers)

    assert response.json() == {"email_sent": True}
    assert PostgresAccountRepository(db_session).get_account_by_id(user.id) is None
    assert _actions(db_session, user.id) == ["account_removed"]
    assert email_sender.sent[-1]["to"] == "leaving@example.de"
    stored = db_session.execute(sa.text("SELECT details::text FROM admin_audit_log")).scalars().all()
    assert not any("leaving@example.de" in d for d in stored)
