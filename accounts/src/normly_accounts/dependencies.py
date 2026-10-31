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
from normly_accounts.permissions import allows

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
    extended = session_repo.extend_session(
        account_session.id, datetime.now(timezone.utc) + _SESSION_LIFETIME
    )
    if not extended:
        # Deleted between lookup and update (block, invitation reset):
        # the UPDATE waited for that commit and then matched no row.
        raise HTTPException(status_code=401, detail="invalid or expired session")

    # Read the account before committing: until the commit, the extend holds
    # the session row, so a block or invitation accept that deletes it waits
    # and cannot change the role this request acts with (ADR-030).
    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    if account.blocked_at is not None:
        # Blocking deletes all sessions; this also covers a session created
        # in the moment between the block and that deletion.
        raise HTTPException(status_code=401, detail="invalid or expired session")
    session.commit()
    return account


def require_capability(key: str):
    """
    Dependency factory: the current account must hold `key` per
    permissions.CAPABILITIES. The role comes from the database on every
    request, so a downgrade or block takes effect on the next one.
    """
    def dependency(account: Account = Depends(get_current_account)) -> Account:
        if not allows(account.role, key):
            raise HTTPException(status_code=403, detail="forbidden")
        return account

    return dependency


def get_email_sender(request: Request):
    return request.app.state.email_sender


def get_google_oauth_client():
    return build_google_oauth_client_from_env()
