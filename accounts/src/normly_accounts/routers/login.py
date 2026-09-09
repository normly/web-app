# accounts/src/normly_accounts/routers/login.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.dependencies import get_session
from normly_accounts.schemas import AccountResponse, LoginRequest, LogoutRequest, \
    SessionResponse
from normly_accounts.security import generate_token, verify_password

login_router = APIRouter(prefix="/v1/accounts", tags=["login"])

_SESSION_LIFETIME = timedelta(days=30)


def avatar_data_url(account: Account) -> str | None:
    if account.avatar_image is None or account.avatar_content_type is None:
        return None
    encoded = base64.b64encode(account.avatar_image).decode("ascii")
    return f"data:{account.avatar_content_type};base64,{encoded}"


def _create_session_response(account: Account, session: Session) -> SessionResponse:
    now = datetime.now(timezone.utc)
    session_repo = PostgresAccountSessionRepository(session)
    created = session_repo.create_session(
        account_id=account.id, session_token=generate_token(), created_at=now,
        expires_at=now + _SESSION_LIFETIME,
    )
    # Commit here, not just at the end of get_session()'s request scope.
    # FastAPI (routing.py's request_response wrapper) sends the HTTP
    # response and only THEN closes the yield-dependency's AsyncExitStack --
    # get_session()'s own `session.commit()` runs AFTER the client has
    # already received this response. A client that immediately calls
    # /v1/accounts/session with the token from this response races that
    # deferred commit: under READ COMMITTED, a second request's
    # get_session_by_token() can run (on its own connection) before this
    # session row is durable, and legitimately finds nothing -- a false 401
    # that looks like "logged out right after signing in". Confirmed by
    # direct measurement: a bare, non-concurrent, backend-only loop of
    # POST /v1/accounts/register immediately followed by GET
    # /v1/accounts/session (no browser, no proxy, no Next.js involved)
    # reproduced this in over half of 60 runs before this fix. Committing
    # explicitly here, before the response is even constructed, guarantees
    # the row is visible to any request that reacts to this response --
    # the later commit in get_session() becomes a harmless no-op.
    session.commit()
    return SessionResponse(
        session_token=created.session_token,
        account=AccountResponse(
            id=account.id, email=account.email,
            email_verified=account.email_verified_at is not None,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
            has_password=account.password_hash is not None,
            notification_preference=account.notification_preference.value,
        ),
    )


@login_router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> SessionResponse:
    account_repo = PostgresAccountRepository(session)
    account = account_repo.get_account_by_email(payload.email)

    # Same 401 whether the email is unknown or the password is wrong --
    # enumeration protection. A Google-only account (password_hash is None)
    # also falls through to this branch: verify_password is never called
    # against a None hash.
    if account is None or account.password_hash is None or not verify_password(
        payload.password, account.password_hash
    ):
        raise HTTPException(status_code=401, detail="invalid email or password")

    return _create_session_response(account, session)


@login_router.post("/logout")
def logout(payload: LogoutRequest, session: Session = Depends(get_session)) -> dict:
    PostgresAccountSessionRepository(session).revoke_session(payload.session_token)
    return {"status": "logged_out"}
