# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import SessionSummaryResponse

sessions_router = APIRouter(prefix="/v1/accounts", tags=["sessions"])

_BEARER_PREFIX = "Bearer "


@sessions_router.get("/sessions", response_model=list[SessionSummaryResponse])
def list_sessions(
    authorization: str | None = Header(default=None),
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[SessionSummaryResponse]:
    # get_current_account has already validated this header -- re-reading it
    # here only identifies WHICH of the account's sessions is the one making
    # this very request, for the is_current flag below.
    current_token = authorization[len(_BEARER_PREFIX):] if authorization else None

    session_repo = PostgresAccountSessionRepository(session)
    sessions = session_repo.list_sessions_for_account(account.id)
    return [
        SessionSummaryResponse(
            id=s.id, created_at=s.created_at, expires_at=s.expires_at,
            is_current=(s.session_token == current_token),
        )
        for s in sessions
    ]


@sessions_router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    revoked = PostgresAccountSessionRepository(session).revoke_session_by_id(
        session_id, account.id
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "session_revoked"}
