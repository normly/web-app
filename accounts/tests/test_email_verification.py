# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re

from sqlalchemy import select

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.orm import AccountTokenORM
from normly_core.graph.postgres.repositories import PostgresAccountRepository


def _register(client, email, password):
    return client.post("/v1/accounts/register", json={"email": email, "password": password})


def _verification_token(db_session, email):
    account = PostgresAccountRepository(db_session).get_account_by_email(email)
    row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.EMAIL_VERIFICATION,
        )
    ).scalar_one()
    return row.token


def test_verify_email_marks_the_account_verified(client, db_session):
    _register(client, "verify@example.de", "correct horse battery staple")
    token = _verification_token(db_session, "verify@example.de")

    response = client.get("/v1/accounts/verify-email", params={"token": token})

    assert response.status_code == 200
    account = PostgresAccountRepository(db_session).get_account_by_email("verify@example.de")
    assert account.email_verified_at is not None


def test_verify_email_rejects_an_unknown_token(client):
    response = client.get(
        "/v1/accounts/verify-email", params={"token": "not-a-real-token"}
    )

    assert response.status_code == 400


def test_verify_email_rejects_a_reused_token(client, db_session):
    _register(client, "reuse-verify@example.de", "correct horse battery staple")
    token = _verification_token(db_session, "reuse-verify@example.de")

    first = client.get("/v1/accounts/verify-email", params={"token": token})
    second = client.get("/v1/accounts/verify-email", params={"token": token})

    assert first.status_code == 200
    assert second.status_code == 400


def test_resend_verification_email_sends_a_new_token_for_an_unverified_account(
    client, email_sender, db_session,
):
    _register(client, "resend@example.de", "correct horse battery staple")
    email_sender.sent.clear()

    response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "resend@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 1
    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    new_token = match.group(1)

    verify_response = client.get("/v1/accounts/verify-email", params={"token": new_token})
    assert verify_response.status_code == 200


def test_resend_verification_email_is_silent_for_an_already_verified_account(
    client, email_sender, db_session,
):
    _register(client, "already-verified@example.de", "correct horse battery staple")
    token = _verification_token(db_session, "already-verified@example.de")
    client.get("/v1/accounts/verify-email", params={"token": token})
    email_sender.sent.clear()

    response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "already-verified@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 0


def test_resend_verification_email_returns_the_same_response_for_an_unknown_address(client):
    known_response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "unknown@example.de"}
    )

    assert known_response.status_code == 200
    assert known_response.json() == {
        "status": "if_the_account_exists_and_is_unverified_an_email_was_sent"
    }
