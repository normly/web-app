# accounts/tests/test_magic_link.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.orm import AccountTokenORM
from normly_core.graph.postgres.repositories import PostgresAccountRepository


class _RaisingEmailSender:
    """Test double: simulates an unreachable SMTP relay."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        raise OSError("simulated SMTP outage")


def _magic_link_token(db_session, email):
    # A token for a known address is bound to the account; one for an address
    # that has no account yet names the address itself.
    account = PostgresAccountRepository(db_session).get_account_by_email(email)
    binding = (
        AccountTokenORM.account_id == account.id
        if account is not None
        else AccountTokenORM.email == email
    )
    row = db_session.execute(
        select(AccountTokenORM).where(
            binding, AccountTokenORM.purpose == AccountTokenPurpose.MAGIC_LINK
        )
    ).scalar_one()
    return row.token


def test_magic_link_request_creates_no_account_for_an_unknown_email(
    client, db_session, email_sender
):
    """
    Creating the account here would let anyone conjure a permanent account for
    any address they can type, unauthenticated. The token names the address
    instead, and confirm turns it into an account.
    """
    response = client.post(
        "/v1/accounts/magic-link/request", json={"email": "brandnew@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 1
    assert PostgresAccountRepository(db_session).get_account_by_email(
        "brandnew@example.de"
    ) is None

    row = db_session.execute(
        select(AccountTokenORM).where(AccountTokenORM.email == "brandnew@example.de")
    ).scalar_one()
    assert row.account_id is None


def test_magic_link_confirm_creates_the_account_for_an_unknown_email(client, db_session):
    client.post(
        "/v1/accounts/magic-link/request", json={"email": "confirmed-new@example.de"}
    )
    token = _magic_link_token(db_session, "confirmed-new@example.de")

    response = client.post("/v1/accounts/magic-link/confirm", json={"token": token})

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "confirmed-new@example.de"
    account = PostgresAccountRepository(db_session).get_account_by_email(
        "confirmed-new@example.de"
    )
    assert account is not None
    assert account.password_hash is None
    assert account.email_verified_at is not None


def test_magic_link_request_reuses_an_existing_account(client, db_session, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "existing@example.de", "password": "correct horse battery staple"},
    )
    account_before = PostgresAccountRepository(db_session).get_account_by_email(
        "existing@example.de"
    )

    client.post("/v1/accounts/magic-link/request", json={"email": "existing@example.de"})

    account_after = PostgresAccountRepository(db_session).get_account_by_email(
        "existing@example.de"
    )
    assert account_after.id == account_before.id


def test_magic_link_confirm_logs_in_and_marks_the_account_verified(client, db_session):
    client.post("/v1/accounts/magic-link/request", json={"email": "magic@example.de"})
    token = _magic_link_token(db_session, "magic@example.de")

    response = client.post("/v1/accounts/magic-link/confirm", json={"token": token})

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "magic@example.de"
    assert response.json()["account"]["email_verified"] is True


def test_magic_link_confirm_rejects_an_unknown_token(client):
    response = client.post(
        "/v1/accounts/magic-link/confirm", json={"token": "not-a-real-token"}
    )

    assert response.status_code == 400


def test_magic_link_confirm_is_single_use(client, db_session):
    client.post("/v1/accounts/magic-link/request", json={"email": "singleuse@example.de"})
    token = _magic_link_token(db_session, "singleuse@example.de")

    first = client.post("/v1/accounts/magic-link/confirm", json={"token": token})
    second = client.post("/v1/accounts/magic-link/confirm", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 400


def test_magic_link_email_body_contains_an_absolute_link(client, email_sender):
    client.post("/v1/accounts/magic-link/request", json={"email": "linktest@example.de"})

    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    assert body.startswith(
        "Zum Anmelden: http://localhost:3000/magic-link?token="
    )
    assert match.group(1)


def test_magic_link_request_still_succeeds_when_email_delivery_fails(client, db_session):
    from normly_accounts.dependencies import get_email_sender, get_session
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: _RaisingEmailSender()

    with TestClient(app) as raising_client:
        response = raising_client.post(
            "/v1/accounts/magic-link/request", json={"email": "outage@example.de"}
        )

    # A failed send must not fail the request -- the token is already
    # persisted by the time send() is called, and the spec is explicit that
    # these email-triggering requests must not fail when SMTP is unreachable.
    assert response.status_code == 200
    assert response.json() == {"status": "if_the_request_is_valid_an_email_was_sent"}

    row = db_session.execute(
        select(AccountTokenORM).where(AccountTokenORM.email == "outage@example.de")
    ).scalar_one()
    assert row.account_id is None
    # The account still waits for a confirm that the undelivered link cannot
    # produce; the user simply requests a new link.
    assert PostgresAccountRepository(db_session).get_account_by_email(
        "outage@example.de"
    ) is None
