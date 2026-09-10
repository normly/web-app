# accounts/src/normly_accounts/routers/google.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    GoogleIdentityAlreadyLinkedError,
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresOAuthStateRepository,
)

from normly_accounts.dependencies import get_google_oauth_client, get_session
from normly_accounts.google_oauth import GoogleOAuthClient
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import SessionResponse
from normly_accounts.security import generate_token

google_router = APIRouter(prefix="/v1/accounts/google", tags=["google"])

_STATE_TTL = timedelta(minutes=10)
_STATE_RETENTION = timedelta(hours=1)


def _redirect_uri() -> str:
    return os.environ.get(
        "NORMLY_GOOGLE_REDIRECT_URI", "http://localhost:8000/v1/accounts/google/callback"
    )


@google_router.get("/login")
def google_login(
    session: Session = Depends(get_session),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> RedirectResponse:
    state = generate_token()
    now = datetime.now(timezone.utc)
    state_repo = PostgresOAuthStateRepository(session)
    # Server-side, DB-backed state, not a cookie: Google redirects the
    # browser back through this frontend's own BFF callback route (per
    # NORMLY_GOOGLE_REDIRECT_URI's documented, mandatory convention -- see
    # frontend/README.md), and that route's server-side fetch to this
    # endpoint carries no browser cookies at all. Both endpoints instead
    # share this same database.
    state_repo.delete_states_before(now - _STATE_RETENTION)
    state_repo.create_state(state=state, created_at=now, expires_at=now + _STATE_TTL)
    session.commit()
    url = google_client.build_authorization_url(_redirect_uri(), state)
    return RedirectResponse(url, status_code=302)


@google_router.get("/callback", response_model=SessionResponse)
def google_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> SessionResponse:
    if PostgresOAuthStateRepository(session).consume_state(state) is None:
        raise HTTPException(status_code=400, detail="Google OAuth state mismatch")

    # Google redirects back here with EITHER `code` or `error` -- clicking
    # "Cancel" on the consent screen yields `?error=access_denied` and no
    # code. Declaring `code` as required would turn that ordinary outcome
    # into a 422 from FastAPI's own validation instead of the 400 the design
    # spec mandates. Google's raw `error` value is never echoed back: it is
    # third-party input and tells the caller nothing they can act on.
    if error is not None or code is None:
        raise HTTPException(status_code=400, detail="Google OAuth was cancelled or failed")

    try:
        profile = google_client.exchange_code(code, _redirect_uri())
    except httpx.HTTPError:
        # An expired/replayed code or a misconfigured client secret makes
        # Google answer non-2xx, which raise_for_status() turns into an
        # HTTPStatusError; transport failures raise other HTTPError
        # subclasses. Neither is a bug in this service, so neither is a 500.
        raise HTTPException(status_code=400, detail="Google OAuth token exchange failed")

    google_repo = PostgresAccountGoogleIdentityRepository(session)
    account_repo = PostgresAccountRepository(session)

    account = google_repo.get_account_by_google_subject(profile.subject_id)
    if account is None:
        # Not yet linked -- either a brand-new account, or an existing
        # email/password account with the same address to link to instead
        # of creating a duplicate.
        existing = account_repo.get_account_by_email(profile.email)
        if existing is not None:
            # Linking hands whoever completed this flow full control of an
            # account that already belongs to someone. A Google identity may
            # *assert* any address, so an unverified one is no evidence at
            # all -- refuse rather than take over the existing account.
            if not profile.email_verified:
                raise HTTPException(
                    status_code=400, detail="Google account email is not verified"
                )
            account = existing
        else:
            # No account to take over, so an unverified address is harmless
            # here: it can only create a new Google-only account reachable
            # by this very Google subject.
            account = account_repo.create_account(email=profile.email, password_hash=None)
        try:
            google_repo.link_google_identity(
                account_id=account.id, google_subject_id=profile.subject_id
            )
        except GoogleIdentityAlreadyLinkedError:
            # The account already carries a different Google identity -- e.g.
            # the user's original Google account was deleted and recreated,
            # giving them a new subject id for the same address. Resolving
            # that means unlinking the old identity, which needs a
            # deliberate, authenticated account-settings action rather than
            # a silent relink from an unauthenticated callback.
            raise HTTPException(
                status_code=409,
                detail="this account is already linked to a different Google identity",
            )

    return _create_session_response(account, session)
