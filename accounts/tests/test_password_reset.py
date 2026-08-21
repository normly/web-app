# accounts/tests/test_password_reset.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from fastapi.testclient import TestClient


def _register(client, email, password):
    return client.post("/v1/accounts/register", json={"email": email, "password": password})


class _RaisingEmailSender:
    """Test double: simulates an unreachable SMTP relay."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        raise OSError("simulated SMTP outage")


def test_password_reset_request_sends_an_email_for_a_known_address(client, email_sender):
    _register(client, "reset@example.de", "correct horse battery staple")
    email_sender.sent.clear()

    response = client.post(
        "/v1/accounts/password-reset/request", json={"email": "reset@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "reset@example.de"


def test_password_reset_request_returns_the_same_response_for_an_unknown_address(
    client, email_sender
):
    _register(client, "reset@example.de", "correct horse battery staple")
    email_sender.sent.clear()

    known = client.post(
        "/v1/accounts/password-reset/request", json={"email": "reset@example.de"}
    )
    unknown = client.post(
        "/v1/accounts/password-reset/request", json={"email": "nobody@example.de"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    # No email actually sent for the unknown address -- but the response
    # gives no signal of that difference.
    assert len(email_sender.sent) == 1


def test_password_reset_confirm_changes_the_password(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountTokenRepository

    _register(client, "confirm@example.de", "old password here")
    client.post("/v1/accounts/password-reset/request", json={"email": "confirm@example.de"})
    token_repo = PostgresAccountTokenRepository(db_session)
    # Read the token back the same way the email body would have contained
    # it -- the test's own request created exactly one pending token for
    # this account, look it up via the repository rather than parsing an
    # email body neither the test nor the production code renders yet.
    from normly_core.graph.domain import AccountTokenPurpose
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    account = PostgresAccountRepository(db_session).get_account_by_email("confirm@example.de")
    from sqlalchemy import select
    from normly_core.graph.postgres.orm import AccountTokenORM

    token_row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.PASSWORD_RESET,
        )
    ).scalar_one()

    response = client.post(
        "/v1/accounts/password-reset/confirm",
        json={"token": token_row.token, "new_password": "a brand new password"},
    )
    assert response.status_code == 200

    login = client.post(
        "/v1/accounts/login",
        json={"email": "confirm@example.de", "password": "a brand new password"},
    )
    assert login.status_code == 200

    old_login = client.post(
        "/v1/accounts/login",
        json={"email": "confirm@example.de", "password": "old password here"},
    )
    assert old_login.status_code == 401


def test_password_reset_confirm_rejects_an_already_used_token(client, db_session):
    from sqlalchemy import select
    from normly_core.graph.domain import AccountTokenPurpose
    from normly_core.graph.postgres.orm import AccountTokenORM
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    _register(client, "reuse@example.de", "correct horse battery staple")
    client.post("/v1/accounts/password-reset/request", json={"email": "reuse@example.de"})
    account = PostgresAccountRepository(db_session).get_account_by_email("reuse@example.de")
    token_row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.PASSWORD_RESET,
        )
    ).scalar_one()

    first = client.post(
        "/v1/accounts/password-reset/confirm",
        json={"token": token_row.token, "new_password": "first new password"},
    )
    second = client.post(
        "/v1/accounts/password-reset/confirm",
        json={"token": token_row.token, "new_password": "second new password"},
    )

    assert first.status_code == 200
    assert second.status_code == 400


def test_password_reset_confirm_rejects_an_unknown_token(client):
    response = client.post(
        "/v1/accounts/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "irrelevant"},
    )

    assert response.status_code == 400


def test_password_reset_request_still_succeeds_when_email_delivery_fails(client, db_session):
    # The account must already exist so the request hits the send() call at
    # all -- register it through the normal client first.
    _register(client, "outage@example.de", "correct horse battery staple")

    from normly_accounts.dependencies import get_email_sender, get_session
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: _RaisingEmailSender()

    with TestClient(app) as raising_client:
        response = raising_client.post(
            "/v1/accounts/password-reset/request", json={"email": "outage@example.de"}
        )

    # A failed send must not fail the request -- the spec is explicit that
    # registration/reset requests "schlagen NICHT fehl" when SMTP is down;
    # the token is already persisted, delivery is a separate concern.
    assert response.status_code == 200
    assert response.json() == {"status": "if_the_account_exists_an_email_was_sent"}


def test_password_reset_request_is_indistinguishable_for_known_vs_unknown_address_during_outage(
    client, db_session
):
    # This is the actual enumeration-protection property: under an SMTP
    # outage, a known address whose send() raises must produce the exact
    # same response as an unknown address (which never calls send() at
    # all) -- otherwise the status code alone reveals which emails are
    # registered.
    _register(client, "outage2@example.de", "correct horse battery staple")

    from normly_accounts.dependencies import get_email_sender, get_session
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: _RaisingEmailSender()

    with TestClient(app) as raising_client:
        known = raising_client.post(
            "/v1/accounts/password-reset/request", json={"email": "outage2@example.de"}
        )
        unknown = raising_client.post(
            "/v1/accounts/password-reset/request", json={"email": "nobody2@example.de"}
        )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
