# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from normly_core.graph.domain import (
    ChatAnswerType, ChatMessage, ChatMessageCitation, ChatMessageRole,
)
from normly_core.graph.postgres.repositories import (
    PostgresChatRepository,
    PostgresSegmentRepository,
)

from normly_chat.accounts_client import AccountsClient
from normly_chat.api_client import ApiClient
from normly_chat.budget_guard import POOL_REGISTERED, BudgetGuard
from normly_chat.citation_labels import CitationResolver
from normly_chat.dependencies import (
    get_accounts_client, get_api_client, get_budget_guard, get_llm_client, get_session,
)
from normly_chat.llm_client import LlmClient
from normly_chat.markers import split_paragraphs
from normly_chat.metered_llm_client import MeteredLlmClient
from normly_chat.schemas import (
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionSummary,
    ChatSessionTitleResponse,
    CitationResponse,
    DeletedSessionsResponse,
)
from normly_chat.titles import fallback_title, generate_title

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


def _display_title(stored: str | None, first_question: str | None) -> str | None:
    if stored:
        return stored
    return fallback_title(first_question) if first_question else None


def _owned_session_or_404(chat_repo, session_id: uuid.UUID, account_id: uuid.UUID):
    chat_session = chat_repo.get_session_for_account(session_id, account_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    return chat_session


def _message_response(
    message: ChatMessage, citations: list[ChatMessageCitation], labels: CitationResolver,
) -> ChatMessageResponse:
    if message.role == ChatMessageRole.USER:
        return ChatMessageResponse(
            role="user", content=message.content, answer_type=None,
            paragraphs=[message.content], citations=[], created_at=message.created_at,
        )
    paragraphs = split_paragraphs(message.content)
    raw = [
        {
            "document_id": c.document_id, "segment_id": c.segment_id,
            # An index without a matching paragraph backs the whole answer.
            "paragraph_index": (
                c.paragraph_index
                if c.paragraph_index is not None and c.paragraph_index < len(paragraphs)
                else None
            ),
        }
        for c in citations
    ]
    return ChatMessageResponse(
        role="assistant", content=message.content,
        answer_type=message.answer_type.value if message.answer_type else None,
        paragraphs=paragraphs,
        citations=[CitationResponse(**c) for c in labels.resolve(raw)],
        created_at=message.created_at,
    )


@sessions_router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> list[ChatSessionSummary]:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    sessions = chat_repo.list_sessions_for_account(account_id)
    first_questions = chat_repo.first_user_messages_for_sessions([s.id for s in sessions])
    return [
        ChatSessionSummary(
            id=s.id, session_token=s.session_token, jurisdiction=s.jurisdiction,
            language=s.language, title=_display_title(s.title, first_questions.get(s.id)),
            created_at=s.created_at,
        )
        for s in sessions
    ]


@sessions_router.get(
    "/sessions/{session_id}/messages", response_model=ChatSessionMessagesResponse,
)
def get_session_messages(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    api_client: ApiClient = Depends(get_api_client),
) -> ChatSessionMessagesResponse:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    chat_session = _owned_session_or_404(chat_repo, session_id, account_id)

    messages = chat_repo.list_messages_for_session(chat_session.id)
    citations_by_message = chat_repo.citations_for_messages([m.id for m in messages])
    # Labels are resolved against the session's own jurisdiction, so a chat
    # reads the same whatever jurisdiction the UI shows right now.
    labels = CitationResolver(
        api_client, PostgresSegmentRepository(session), chat_session.jurisdiction,
    )
    first_question = next(
        (m.content for m in messages if m.role == ChatMessageRole.USER), None,
    )
    return ChatSessionMessagesResponse(
        session_id=chat_session.id, session_token=chat_session.session_token,
        title=_display_title(chat_session.title, first_question),
        messages=[
            _message_response(m, citations_by_message.get(m.id, []), labels) for m in messages
        ],
    )


@sessions_router.post(
    "/sessions/{session_id}/title", response_model=ChatSessionTitleResponse,
)
def create_session_title(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    llm_client: LlmClient = Depends(get_llm_client),
    guard: BudgetGuard = Depends(get_budget_guard),
) -> ChatSessionTitleResponse:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    chat_session = _owned_session_or_404(chat_repo, session_id, account_id)
    if chat_session.title:
        return ChatSessionTitleResponse(title=chat_session.title)

    first_question = chat_repo.first_user_messages_for_sessions([chat_session.id]).get(
        chat_session.id
    )
    if first_question is None:
        raise HTTPException(status_code=404, detail="chat session has no question yet")

    # Titles cost tokens of the registered pool but no quota, so only a chat
    # with an AI answer -- already limited by the quota -- gets a model title.
    # Otherwise, and when the pool is spent, the fallback title is returned
    # without a model call and without storing it, like any title failure.
    has_ai_answer = any(
        message.answer_type == ChatAnswerType.SYNTHESIS
        for message in chat_repo.list_messages_for_session(chat_session.id)
    )
    if not has_ai_answer or not guard.pool_available(POOL_REGISTERED):
        return ChatSessionTitleResponse(title=fallback_title(first_question))
    title = generate_title(
        MeteredLlmClient(llm_client, guard, POOL_REGISTERED), first_question, chat_session.language,
    )
    if title is None:
        # Nothing stored: a later call may still get a model title.
        return ChatSessionTitleResponse(title=fallback_title(first_question))
    chat_repo.set_session_title(chat_session.id, title)
    session.commit()
    return ChatSessionTitleResponse(title=title)


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
