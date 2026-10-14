# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresChatRepository

from normly_chat.accounts_client import AccountsClient
from normly_chat.dependencies import get_accounts_client, get_session
from normly_chat.schemas import ChatSessionSummary, DeletedSessionsResponse

sessions_router = APIRouter(prefix="/v1/chat", tags=["sessions"])

_BEARER_PREFIX = "Bearer "


def _require_account(authorization: str | None, accounts_client: AccountsClient) -> uuid.UUID:
    # An account token is REQUIRED on these endpoints, not optional -- listing
    # and deleting chat history are account-only operations (REQ-ACC-004).
    if authorization is None or not (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        raise HTTPException(status_code=401, detail="account session required")
    identity = accounts_client.validate_session(authorization[len(_BEARER_PREFIX):])
    if identity is None:
        raise HTTPException(status_code=401, detail="account session required")
    return identity.account_id


@sessions_router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> list[ChatSessionSummary]:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    sessions = chat_repo.list_sessions_for_account(account_id)
    return [
        ChatSessionSummary(
            id=s.id, session_token=s.session_token, jurisdiction=s.jurisdiction,
            language=s.language, created_at=s.created_at,
        )
        for s in sessions
    ]


@sessions_router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> Response:
    account_id = _require_account(authorization, accounts_client)
    # Unknown and foreign ids answer identically, so ids cannot be probed.
    if not PostgresChatRepository(session).delete_chat_session(session_id, account_id):
        raise HTTPException(status_code=404, detail="chat session not found")
    return Response(status_code=204)


@sessions_router.delete("/sessions", response_model=DeletedSessionsResponse)
def delete_all_sessions(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> DeletedSessionsResponse:
    account_id = _require_account(authorization, accounts_client)
    deleted = PostgresChatRepository(session).delete_chat_sessions_for_account(account_id)
    return DeletedSessionsResponse(deleted=deleted)
