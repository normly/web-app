# accounts/tests/test_email_change.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re

from normly_core.graph.postgres.repositories import PostgresAccountRepository


def _register_and_authorize(client, email="owner@example.de"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": "correct horse"}
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['session_token']}"}


def test_requesting_an_email_change_sends_a_confirmation_to_the_new_address(
    client, email_sender
):
    headers = _register_and_authorize(client)

    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "new-address@example.de"},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 2  # registration verification + this
    change_email = email_sender.sent[-1]
    assert change_email["to"] == "new-address@example.de"


def test_email_change_body_contains_an_absolute_confirm_link_with_encoded_email(
    client, email_sender
):
    headers = _register_and_authorize(client)

    client.post(
        "/v1/accounts/email/change", json={"new_email": "new+addr@example.de"},
        headers=headers,
    )

    body = email_sender.sent[-1]["body"]
    assert "http://localhost:3000/confirm-email-change?token=" in body
    token = re.search(r"token=([^&\s]+)", body).group(1)
    assert token
    # The '+' in the address must be percent-encoded in the link -- an
    # unencoded '+' would be read back as a literal space by a URL/form
    # decoder, corrupting the address (the same class of bug already fixed
    # once on the frontend side of this plan).
    assert "email=new%2Baddr%40example.de" in body


def test_email_is_not_changed_until_the_link_is_confirmed(client, email_sender):
    headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/email/change", json={"new_email": "pending@example.de"}, headers=headers,
    )

    session_response = client.get("/v1/accounts/session", headers=headers)

    assert session_response.json()["email"] == "owner@example.de"


def test_confirming_the_link_actually_changes_the_email(client, email_sender):
    headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/email/change", json={"new_email": "confirmed@example.de"}, headers=headers,
    )
    token = re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)

    confirm_response = client.get(
        f"/v1/accounts/email/confirm?token={token}&email=confirmed@example.de"
    )

    assert confirm_response.status_code == 200
    session_response = client.get("/v1/accounts/session", headers=headers)
    assert session_response.json()["email"] == "confirmed@example.de"


def test_requesting_a_change_to_an_already_registered_email_returns_409(client):
    client.post(
        "/v1/accounts/register", json={"email": "taken@example.de", "password": "x"}
    )
    headers = _register_and_authorize(client, email="requester@example.de")

    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "taken@example.de"}, headers=headers,
    )

    assert response.status_code == 409


def test_confirming_returns_409_when_the_address_is_claimed_after_the_pre_check(
    client, email_sender, monkeypatch, db_session
):
    # Mirrors the race the pre-check in confirm_email_change cannot close: by
    # the time update_email actually runs, someone else has taken the
    # address. Simulated here by stubbing out the pre-check (making it
    # report the address as free, as it would if the race window landed a
    # moment later) while the address has genuinely already been claimed.
    headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/email/change", json={"new_email": "racy@example.de"}, headers=headers,
    )
    token = re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)
    PostgresAccountRepository(db_session).create_account(
        email="racy@example.de", password_hash="hashed"
    )
    monkeypatch.setattr(
        PostgresAccountRepository, "get_account_by_email", lambda self, email: None
    )

    response = client.get(
        f"/v1/accounts/email/confirm?token={token}&email=racy@example.de"
    )

    assert response.status_code == 409


def test_confirming_an_invalid_token_returns_400(client):
    response = client.get(
        "/v1/accounts/email/confirm?token=does-not-exist&email=whatever@example.de"
    )
    assert response.status_code == 400


def test_email_change_requires_authorization(client):
    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "nope@example.de"},
    )
    assert response.status_code == 401


def test_email_change_mails_in_the_request_language(client, email_sender):
    headers = _register_and_authorize(client)

    client.post(
        "/v1/accounts/email/change",
        json={"new_email": "changed-en@example.de", "locale": "en"}, headers=headers,
    )

    mail = email_sender.sent[-1]
    assert mail["subject"] == "Confirm your new email address"
    assert "changed-en@example.de" in mail["body"]


# --- The pending address is bound to the token, never taken from the link ---

def _request_change(client, email_sender, headers, new_email):
    client.post("/v1/accounts/email/change", json={"new_email": new_email}, headers=headers)
    return re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)


def test_a_tampered_address_in_the_link_is_refused(client, email_sender):
    """
    The requester controls owned@example.de and receives its link; swapping
    the address in that link must not move the account to a mailbox nobody
    proved.
    """
    headers = _register_and_authorize(client)
    token = _request_change(client, email_sender, headers, "owned@example.de")

    response = client.get(f"/v1/accounts/email/confirm?token={token}&email=victim@example.de")

    assert (response.status_code, response.json()["detail"]) == (400, "invalid or expired token")
    assert client.get("/v1/accounts/session", headers=headers).json()["email"] == "owner@example.de"


def test_confirming_without_the_address_in_the_link_uses_the_tokens(client, email_sender):
    headers = _register_and_authorize(client)
    token = _request_change(client, email_sender, headers, "from-token@example.de")

    response = client.get(f"/v1/accounts/email/confirm?token={token}")

    assert response.status_code == 200
    assert client.get("/v1/accounts/session", headers=headers).json()["email"] == "from-token@example.de"


def test_a_token_without_a_stored_address_is_refused(client, db_session):
    """Tokens issued before the address was stored on them (pre-0042)."""
    from datetime import datetime, timedelta, timezone

    from normly_core.graph.domain import AccountTokenPurpose
    from normly_core.graph.postgres.orm import AccountTokenORM
    import uuid

    headers = _register_and_authorize(client)
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    now = datetime.now(timezone.utc)
    db_session.add(AccountTokenORM(
        id=uuid.uuid4(), account_id=uuid.UUID(account_id), email=None,
        purpose=AccountTokenPurpose.EMAIL_CHANGE, token="legacy-change-token",
        created_at=now, expires_at=now + timedelta(hours=1), used_at=None,
    ))
    db_session.flush()

    response = client.get(
        "/v1/accounts/email/confirm?token=legacy-change-token&email=legacy@example.de"
    )

    assert (response.status_code, response.json()["detail"]) == (400, "invalid or expired token")
    assert client.get("/v1/accounts/session", headers=headers).json()["email"] == "owner@example.de"
