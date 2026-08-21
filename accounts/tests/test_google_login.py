# accounts/tests/test_google_login.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_accounts.google_oauth import GoogleProfile


class _FakeGoogleOAuthClient:
    def __init__(self, profile: GoogleProfile):
        self._profile = profile

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile:
        return self._profile


def _override_google_client(app, profile: GoogleProfile) -> None:
    from normly_accounts.dependencies import get_google_oauth_client

    app.dependency_overrides[get_google_oauth_client] = lambda: _FakeGoogleOAuthClient(profile)


def test_google_login_redirects_to_googles_consent_screen(client):
    response = client.get("/v1/accounts/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


def test_google_callback_creates_a_new_account_for_an_unseen_subject(client):
    _override_google_client(
        client.app, GoogleProfile(subject_id="google-sub-1", email="newgoogle@example.de")
    )

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "newgoogle@example.de"


def test_google_callback_links_to_an_existing_email_password_account(client):
    client.post(
        "/v1/accounts/register",
        json={"email": "linkme@example.de", "password": "correct horse battery staple"},
    )
    _override_google_client(
        client.app, GoogleProfile(subject_id="google-sub-2", email="linkme@example.de")
    )

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "linkme@example.de"

    # A second callback with the same Google subject resolves to the SAME
    # account rather than raising a duplicate-email error -- proves the
    # link, not just a coincidental match.
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code-2", "state": "fake-state"}
    )
    assert second.json()["account"]["id"] == response.json()["account"]["id"]


def test_google_callback_reuses_the_account_for_a_returning_google_subject(client):
    profile = GoogleProfile(subject_id="google-sub-3", email="returning@example.de")
    _override_google_client(client.app, profile)

    first = client.get(
        "/v1/accounts/google/callback", params={"code": "code-1", "state": "state-1"}
    )
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "code-2", "state": "state-2"}
    )

    assert first.json()["account"]["id"] == second.json()["account"]["id"]
