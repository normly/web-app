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
    return SessionResponse(
        session_token=created.session_token,
        account=AccountResponse(
            id=account.id, email=account.email,
            email_verified=account.email_verified_at is not None,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
            has_password=account.password_hash is not None,
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
