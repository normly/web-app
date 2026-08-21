# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

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
