# accounts/tests/test_registration.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re

from fastapi.testclient import TestClient

from normly_core.graph.postgres.repositories import PostgresAccountRepository


class _RaisingEmailSender:
    """Test double: simulates an unreachable SMTP relay."""

    def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        raise OSError("simulated SMTP outage")


def test_register_creates_an_account_and_returns_a_session(client, email_sender):
    response = client.post(
        "/v1/accounts/register",
        json={"email": "new@example.de", "password": "correct horse battery staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "new@example.de"
    assert body["account"]["email_verified"] is False
    assert "session_token" in body


def test_register_sends_a_verification_email(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "verifyme@example.de", "password": "correct horse battery staple"},
    )

    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "verifyme@example.de"


def test_register_verification_email_contains_an_absolute_link(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "verifylink@example.de", "password": "correct horse battery staple"},
    )

    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    assert "http://localhost:3000/verify-email?token=" in body
    assert match.group(1)


def test_register_rejects_a_duplicate_email(client):
    client.post(
        "/v1/accounts/register",
        json={"email": "dup@example.de", "password": "correct horse battery staple"},
    )

    response = client.post(
        "/v1/accounts/register",
        json={"email": "dup@example.de", "password": "a different password"},
    )

    assert response.status_code == 409


def test_register_still_returns_a_session_when_email_delivery_fails(
    db_url, monkeypatch, db_session
):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_accounts.dependencies import get_email_sender, get_session
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: _RaisingEmailSender()

    with TestClient(app) as raising_client:
        response = raising_client.post(
            "/v1/accounts/register",
            json={"email": "outage@example.de", "password": "correct horse battery staple"},
        )

    # A failed send must not fail registration -- the account is already
    # persisted by the time send() is called, and the spec is explicit that
    # the request itself "does NOT fail" when SMTP is down.
    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "outage@example.de"
    assert "session_token" in body


def test_register_mails_in_german_by_default_with_html(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "de-default@example.de", "password": "correct horse battery staple"},
    )
    mail = email_sender.sent[0]
    assert mail["subject"] == "Bestätige deine E-Mail-Adresse"
    assert "48 Stunden" in mail["body"]
    assert mail["html"] is not None and 'lang="de"' in mail["html"]


def test_register_stores_the_locale_and_mails_in_it(client, email_sender, db_session):
    response = client.post(
        "/v1/accounts/register",
        json={"email": "en-user@example.de", "password": "correct horse battery staple",
              "locale": "en"},
    )
    assert response.json()["account"]["locale"] == "en"
    assert email_sender.sent[0]["subject"] == "Confirm your email address"
    account = PostgresAccountRepository(db_session).get_account_by_email("en-user@example.de")
    assert account.locale == "en"


def test_register_rejects_an_unsupported_locale(client):
    response = client.post(
        "/v1/accounts/register",
        json={"email": "fr@example.de", "password": "correct horse battery staple",
              "locale": "fr"},
    )
    assert response.status_code == 400
