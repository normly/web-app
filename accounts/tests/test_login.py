# accounts/tests/test_login.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def _register(client, email, password):
    return client.post("/v1/accounts/register", json={"email": email, "password": password})


def test_login_with_correct_credentials_returns_a_session(client):
    _register(client, "login@example.de", "correct horse battery staple")

    response = client.post(
        "/v1/accounts/login",
        json={"email": "login@example.de", "password": "correct horse battery staple"},
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "login@example.de"


def test_login_with_wrong_password_returns_401(client):
    _register(client, "wrongpw@example.de", "correct horse battery staple")

    response = client.post(
        "/v1/accounts/login",
        json={"email": "wrongpw@example.de", "password": "totally wrong"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_returns_the_same_401_as_wrong_password(client):
    known_wrong = client.post(
        "/v1/accounts/login",
        json={"email": "doesnotexist@example.de", "password": "irrelevant"},
    )

    assert known_wrong.status_code == 401
    assert known_wrong.json() == {"detail": "invalid email or password"}


def test_logout_revokes_the_session(client):
    register = _register(client, "logout@example.de", "correct horse battery staple")
    token = register.json()["session_token"]

    logout = client.post("/v1/accounts/logout", json={"session_token": token})
    assert logout.status_code == 200

    session_check = client.get(
        "/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert session_check.status_code == 401
