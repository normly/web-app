# accounts/src/normly_accounts/routers/google.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
)

from normly_accounts.dependencies import get_google_oauth_client, get_session
from normly_accounts.google_oauth import GoogleOAuthClient
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import SessionResponse
from normly_accounts.security import generate_token

google_router = APIRouter(prefix="/v1/accounts/google", tags=["google"])


def _redirect_uri() -> str:
    return os.environ.get(
        "NORMLY_GOOGLE_REDIRECT_URI", "http://localhost:8000/v1/accounts/google/callback"
    )


@google_router.get("/login")
def google_login(
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> RedirectResponse:
    state = generate_token()
    url = google_client.build_authorization_url(_redirect_uri(), state)
    return RedirectResponse(url, status_code=302)


@google_router.get("/callback", response_model=SessionResponse)
def google_callback(
    code: str, state: str, session: Session = Depends(get_session),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> SessionResponse:
    profile = google_client.exchange_code(code, _redirect_uri())

    google_repo = PostgresAccountGoogleIdentityRepository(session)
    account_repo = PostgresAccountRepository(session)

    account = google_repo.get_account_by_google_subject(profile.subject_id)
    if account is None:
        # Not yet linked -- either a brand-new account, or an existing
        # email/password account with the same address to link to instead
        # of creating a duplicate.
        account = account_repo.get_account_by_email(profile.email)
        if account is None:
            account = account_repo.create_account(email=profile.email, password_hash=None)
        google_repo.link_google_identity(
            account_id=account.id, google_subject_id=profile.subject_id
        )

    return _create_session_response(account, session)
