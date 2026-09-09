# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.dependencies import get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import SessionValidationResponse

session_router = APIRouter(prefix="/v1/accounts", tags=["session"])

_SESSION_LIFETIME = timedelta(days=30)


_BEARER_PREFIX = "Bearer "


@session_router.get("/session", response_model=SessionValidationResponse)
def validate_session(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> SessionValidationResponse:
    # The session token is a 30-day credential, so it travels in a header
    # rather than the query string: reverse proxies, access logs and browser
    # history routinely capture URLs. This matches how logout takes the same
    # credential in a POST body, and the care the design spec takes to keep
    # the magic-link token out of a GET query string.
    #
    # A missing or malformed header is answered with the same 401 as a token
    # that simply is not valid -- from the caller's side both mean "this
    # request carries no usable session", and a 400 would only distinguish
    # them for no one's benefit.
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="invalid or expired session")
    session_token = authorization[len(_BEARER_PREFIX):]

    session_repo = PostgresAccountSessionRepository(session)
    account_session = session_repo.get_session_by_token(session_token)
    if account_session is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    session_repo.extend_session(
        account_session.id, datetime.now(timezone.utc) + _SESSION_LIFETIME
    )

    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    return SessionValidationResponse(
        account_id=account.id, email=account.email,
        first_name=account.first_name, last_name=account.last_name,
        avatar_data_url=avatar_data_url(account),
        has_password=account.password_hash is not None,
        notification_preference=account.notification_preference.value,
    )
