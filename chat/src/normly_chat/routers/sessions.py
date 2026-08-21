# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresChatRepository

from normly_chat.accounts_client import AccountsClient
from normly_chat.dependencies import get_accounts_client, get_session
from normly_chat.schemas import ChatSessionSummary

sessions_router = APIRouter(prefix="/v1/chat", tags=["sessions"])

_BEARER_PREFIX = "Bearer "


@sessions_router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> list[ChatSessionSummary]:
    # Unlike the main /v1/chat endpoint, an account token is REQUIRED here,
    # not optional -- listing sessions is inherently an account-only
    # operation (REQ-ACC-004 lists "gespeicherte Verläufe" as account-gated).
    if authorization is None or not (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        raise HTTPException(status_code=401, detail="account session required")
    account_token = authorization[len(_BEARER_PREFIX):]

    identity = accounts_client.validate_session(account_token)
    if identity is None:
        raise HTTPException(status_code=401, detail="account session required")

    chat_repo = PostgresChatRepository(session)
    sessions = chat_repo.list_sessions_for_account(identity.account_id)
    return [
        ChatSessionSummary(
            id=s.id, session_token=s.session_token, jurisdiction=s.jurisdiction,
            language=s.language, created_at=s.created_at,
        )
        for s in sessions
    ]
