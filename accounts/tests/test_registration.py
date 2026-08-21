# accounts/tests/test_registration.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


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
