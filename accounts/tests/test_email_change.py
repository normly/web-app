# accounts/tests/test_email_change.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re


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
