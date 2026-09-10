# accounts/src/normly_accounts/dependencies.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.google_oauth import build_google_oauth_client_from_env

_BEARER_PREFIX = "Bearer "
_SESSION_LIFETIME = timedelta(days=30)


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()


def get_current_account(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Account:
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="invalid or expired session")
    session_token = authorization[len(_BEARER_PREFIX):]

    session_repo = PostgresAccountSessionRepository(session)
    account_session = session_repo.get_session_by_token(session_token)
    if account_session is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    # Sliding expiry on every authenticated call, not just the explicit
    # session-check endpoint -- any proof of activity is a reasonable signal
    # to extend a session, matching the same sliding-window philosophy
    # session.py's own validate_session already applies.
    session_repo.extend_session(
        account_session.id, datetime.now(timezone.utc) + _SESSION_LIFETIME
    )
    session.commit()

    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    return account


def get_email_sender(request: Request):
    return request.app.state.email_sender


def get_google_oauth_client():
    return build_google_oauth_client_from_env()
