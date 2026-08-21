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
        client.app, GoogleProfile(
            subject_id="google-sub-1", email="newgoogle@example.de", email_verified=True
        )
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
        client.app, GoogleProfile(
            subject_id="google-sub-2", email="linkme@example.de", email_verified=True
        )
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
    profile = GoogleProfile(
        subject_id="google-sub-3", email="returning@example.de", email_verified=True
    )
    _override_google_client(client.app, profile)

    first = client.get(
        "/v1/accounts/google/callback", params={"code": "code-1", "state": "state-1"}
    )
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "code-2", "state": "state-2"}
    )

    assert first.json()["account"]["id"] == second.json()["account"]["id"]


def test_google_callback_refuses_to_link_an_unverified_email_to_an_existing_account(client):
    """
    A Google identity may *assert* any email address; only `email_verified`
    means Google checked it. Linking on an unverified assertion would hand
    whoever controls that Google identity a full session on the victim's
    existing password account.
    """
    client.post(
        "/v1/accounts/register",
        json={"email": "victim@example.de", "password": "correct horse battery staple"},
    )
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="attacker-sub", email="victim@example.de", email_verified=False
        )
    )

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 400
    assert "not verified" in response.json()["detail"]


def test_google_callback_still_creates_an_account_for_an_unverified_unknown_email(client):
    """
    The risk is takeover of something that already exists. With no account on
    that address, an unverified email can only produce a new Google-only
    account reachable by this very Google subject -- no one else is harmed.
    """
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="unverified-sub", email="nobodyelse@example.de", email_verified=False
        )
    )

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "nobodyelse@example.de"


def test_google_callback_returns_400_when_the_user_cancels_consent(client):
    """
    Cancelling on Google's consent screen redirects back with `?error=...`
    and no `code`. That is an ordinary outcome, not a malformed request --
    it must be the spec's 400, not FastAPI's own 422.
    """
    response = client.get(
        "/v1/accounts/google/callback",
        params={"state": "fake-state", "error": "access_denied"},
    )

    assert response.status_code == 400
    # Google's raw error value is third-party input and is never echoed back.
    assert "access_denied" not in response.json()["detail"]


def test_google_callback_returns_400_when_the_token_exchange_fails(client):
    """
    An expired code or a wrong client secret makes Google answer non-2xx.
    That is the caller's problem, not a defect in this service, so it must
    not surface as a 500.
    """
    import httpx

    from normly_accounts.dependencies import get_google_oauth_client

    class _FailingGoogleOAuthClient:
        def build_authorization_url(self, redirect_uri: str, state: str) -> str:
            return "https://accounts.google.com/o/oauth2/v2/auth"

        def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile:
            raise httpx.HTTPStatusError(
                "400 Bad Request",
                request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
                response=httpx.Response(400),
            )

    client.app.dependency_overrides[get_google_oauth_client] = _FailingGoogleOAuthClient

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "expired", "state": "fake-state"}
    )

    assert response.status_code == 400


def test_google_callback_is_409_when_the_account_already_has_another_google_identity(
    client, db_session
):
    """
    An account carries at most one Google identity (account_id is the primary
    key of account_google_identity). A second subject resolving to the same
    address -- a deleted and recreated Google account, say -- used to raise an
    uncaught IntegrityError: a 500, and a session too poisoned to answer
    anything else.
    """
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="old-sub", email="relinked@example.de", email_verified=True
        )
    )
    first = client.get(
        "/v1/accounts/google/callback", params={"code": "c1", "state": "s1"}
    )
    assert first.status_code == 200

    _override_google_client(
        client.app, GoogleProfile(
            subject_id="new-sub", email="relinked@example.de", email_verified=True
        )
    )
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "c2", "state": "s2"}
    )

    assert second.status_code == 409

    # The session is still usable afterwards -- the savepoint rolled back the
    # failed insert, not the whole request.
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    assert PostgresAccountRepository(db_session).get_account_by_email(
        "relinked@example.de"
    ) is not None
