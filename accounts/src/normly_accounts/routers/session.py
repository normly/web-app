# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.dependencies import get_session
from normly_accounts.schemas import SessionValidationResponse

session_router = APIRouter(prefix="/v1/accounts", tags=["session"])

_SESSION_LIFETIME = timedelta(days=30)


@session_router.get("/session", response_model=SessionValidationResponse)
def validate_session(
    session_token: str, session: Session = Depends(get_session),
) -> SessionValidationResponse:
    session_repo = PostgresAccountSessionRepository(session)
    account_session = session_repo.get_session_by_token(session_token)
    if account_session is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    session_repo.extend_session(
        account_session.id, datetime.now(timezone.utc) + _SESSION_LIFETIME
    )

    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    return SessionValidationResponse(account_id=account.id, email=account.email)
