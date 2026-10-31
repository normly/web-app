# accounts/tests/test_google_login.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_accounts.google_oauth import GoogleProfile
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresOAuthStateRepository,
)


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


def _seed_state(db_session, state: str = "fake-state") -> None:
    now = datetime.now(timezone.utc)
    PostgresOAuthStateRepository(db_session).create_state(
        state=state, created_at=now, expires_at=now + timedelta(minutes=10)
    )
    db_session.commit()


def test_google_login_redirects_to_googles_consent_screen(client, db_session):
    response = client.get("/v1/accounts/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "accounts.google.com" in location
    from urllib.parse import parse_qs, urlparse

    query_state = parse_qs(urlparse(location).query)["state"][0]
    # Query it back the same way /callback will -- consume_state marks it
    # used, proving both that the row exists and that /callback's own check
    # would accept it.
    consumed = PostgresOAuthStateRepository(db_session).consume_state(query_state)
    assert consumed is not None


def test_google_callback_creates_a_new_account_for_an_unseen_subject(client, db_session):
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-1", email="newgoogle@example.de", email_verified=True
        )
    )
    _seed_state(db_session, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "newgoogle@example.de"


def test_google_callback_links_to_an_existing_email_password_account(client, db_session):
    client.post(
        "/v1/accounts/register",
        json={"email": "linkme@example.de", "password": "correct horse battery staple"},
    )
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-2", email="linkme@example.de", email_verified=True
        )
    )

    _seed_state(db_session, "fake-state")
    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "linkme@example.de"

    # A second callback with the same Google subject resolves to the SAME
    # account rather than raising a duplicate-email error -- proves the
    # link, not just a coincidental match.
    _seed_state(db_session, "fake-state-2")
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code-2", "state": "fake-state-2"}
    )
    assert second.json()["account"]["id"] == response.json()["account"]["id"]


def test_google_callback_reuses_the_account_for_a_returning_google_subject(client, db_session):
    profile = GoogleProfile(
        subject_id="google-sub-3", email="returning@example.de", email_verified=True
    )
    _override_google_client(client.app, profile)

    _seed_state(db_session, "state-1")
    first = client.get(
        "/v1/accounts/google/callback", params={"code": "code-1", "state": "state-1"}
    )
    _seed_state(db_session, "state-2")
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "code-2", "state": "state-2"}
    )

    assert first.json()["account"]["id"] == second.json()["account"]["id"]


def test_google_callback_refuses_to_link_an_unverified_email_to_an_existing_account(
    client, db_session
):
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
    _seed_state(db_session, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 400
    assert "not verified" in response.json()["detail"]


def test_google_callback_still_creates_an_account_for_an_unverified_unknown_email(
    client, db_session
):
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
    _seed_state(db_session, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "nobodyelse@example.de"


def test_google_callback_returns_400_when_the_user_cancels_consent(client, db_session):
    """
    Cancelling on Google's consent screen redirects back with `?error=...`
    and no `code`. That is an ordinary outcome, not a malformed request --
    it must be the spec's 400, not FastAPI's own 422. A valid state row is
    seeded here too, so this test still genuinely exercises the
    cancellation path rather than failing earlier on the state check.
    """
    _seed_state(db_session, "fake-state")
    response = client.get(
        "/v1/accounts/google/callback",
        params={"state": "fake-state", "error": "access_denied"},
    )

    assert response.status_code == 400
    # Google's raw error value is third-party input and is never echoed back.
    assert "access_denied" not in response.json()["detail"]


def test_google_callback_returns_400_when_the_token_exchange_fails(client, db_session):
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
    _seed_state(db_session, "fake-state")

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
    _seed_state(db_session, "s1")
    first = client.get(
        "/v1/accounts/google/callback", params={"code": "c1", "state": "s1"}
    )
    assert first.status_code == 200

    _override_google_client(
        client.app, GoogleProfile(
            subject_id="new-sub", email="relinked@example.de", email_verified=True
        )
    )
    _seed_state(db_session, "s2")
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


def test_google_callback_returns_400_when_state_was_never_issued(client):
    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "never-issued"}
    )

    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_google_callback_returns_400_when_state_is_reused(client, db_session):
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="replay-sub", email="replay@example.de", email_verified=True
        )
    )
    _seed_state(db_session, "one-time-state")

    first = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "one-time-state"}
    )
    assert first.status_code == 200

    second = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code-2", "state": "one-time-state"}
    )
    assert second.status_code == 400


def test_google_callback_stores_the_locale_on_a_new_account(client, db_session):
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-locale", email="google-en@example.de", email_verified=True
        )
    )
    _seed_state(db_session, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback",
        params={"code": "fake-code", "state": "fake-state", "locale": "en"},
    )

    assert response.status_code == 200
    account = PostgresAccountRepository(db_session).get_account_by_email("google-en@example.de")
    assert account.locale == "en"


def test_google_callback_refuses_a_blocked_account_without_linking_it(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountGoogleIdentityRepository
    from tests.admin_support import make_account

    account = make_account(db_session, "blocked-google@example.de", blocked=True)
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-blocked", email="blocked-google@example.de",
            email_verified=True,
        )
    )
    _seed_state(db_session, "blocked-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "blocked-state"}
    )

    assert (response.status_code, response.json()["detail"]) == (403, "account_blocked")
    assert not PostgresAccountGoogleIdentityRepository(db_session).has_google_identity(account.id)


# --- A Google-verified address marks the account verified (ADR-027, ADR-030) ---

def _callback(client, db_session, profile: GoogleProfile, state: str):
    _override_google_client(client.app, profile)
    _seed_state(db_session, state)
    return client.get(
        "/v1/accounts/google/callback", params={"code": f"code-{state}", "state": state}
    )


def _verified(db_session, email: str) -> bool:
    db_session.expire_all()
    account = PostgresAccountRepository(db_session).get_account_by_email(email)
    return account.email_verified_at is not None


def test_a_verified_google_address_verifies_a_new_account(client, db_session):
    response = _callback(client, db_session, GoogleProfile(
        subject_id="verify-new", email="verify-new@example.de", email_verified=True,
    ), "verify-new")

    assert response.json()["account"]["email_verified"] is True
    assert _verified(db_session, "verify-new@example.de")


def test_a_verified_google_address_verifies_an_account_it_links(client, db_session):
    client.post("/v1/accounts/register",
                json={"email": "verify-link@example.de", "password": "correct horse"})
    assert not _verified(db_session, "verify-link@example.de")

    response = _callback(client, db_session, GoogleProfile(
        subject_id="verify-link", email="verify-link@example.de", email_verified=True,
    ), "verify-link")

    assert response.json()["account"]["email_verified"] is True
    assert _verified(db_session, "verify-link@example.de")


def test_a_verified_google_address_verifies_an_already_linked_account(client, db_session):
    """Google-only accounts from before this rule were linked but never verified."""
    accounts = PostgresAccountRepository(db_session)
    legacy = accounts.create_account(email="verify-old@example.de", password_hash=None)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=legacy.id, google_subject_id="verify-old",
    )
    db_session.flush()

    response = _callback(client, db_session, GoogleProfile(
        subject_id="verify-old", email="verify-old@example.de", email_verified=True,
    ), "verify-old")

    assert response.json()["account"]["id"] == str(legacy.id)
    assert response.json()["account"]["email_verified"] is True
    assert _verified(db_session, "verify-old@example.de")


def test_an_unverified_google_assertion_verifies_nothing(client, db_session):
    _callback(client, db_session, GoogleProfile(
        subject_id="no-verify", email="no-verify@example.de", email_verified=False,
    ), "no-verify-1")
    assert not _verified(db_session, "no-verify@example.de")

    # Returning with the same unverified assertion changes nothing either.
    response = _callback(client, db_session, GoogleProfile(
        subject_id="no-verify", email="no-verify@example.de", email_verified=False,
    ), "no-verify-2")
    assert response.json()["account"]["email_verified"] is False
    assert not _verified(db_session, "no-verify@example.de")


def test_a_google_address_other_than_the_accounts_verifies_nothing(client, db_session):
    """
    The account's address may have changed since linking (e-mail change);
    Google then vouches for a different mailbox, not this account's.
    """
    accounts = PostgresAccountRepository(db_session)
    account = accounts.create_account(email="changed@example.de", password_hash=None)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=account.id, google_subject_id="changed-sub",
    )
    db_session.flush()

    _callback(client, db_session, GoogleProfile(
        subject_id="changed-sub", email="original@gmail.example", email_verified=True,
    ), "changed")

    assert not _verified(db_session, "changed@example.de")
