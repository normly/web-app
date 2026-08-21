# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import ChatAnswerType, ChatMessageRole
from normly_core.graph.postgres.repositories import (
    PostgresChatRepository,
    PostgresSegmentRepository,
)

from normly_chat.accounts_client import AccountsClient
from normly_chat.api_client import ApiClient
from normly_chat.classify import QuestionType, classify
from normly_chat.dependencies import (
    get_accounts_client, get_api_client, get_embedding_model, get_ollama_client, get_session,
)
from normly_chat.ollama_client import OllamaClient
from normly_chat.schemas import ChatRequest, ChatResponse, CitationResponse
from normly_chat.session_resolution import resolve_session
from normly_chat.structural import build_structural_answer
from normly_chat.synthesis import build_synthesis_answer

chat_router = APIRouter(prefix="/v1/chat", tags=["chat"])

_BEARER_PREFIX = "Bearer "


@chat_router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest, authorization: str | None = Header(default=None),
    session: Session = Depends(get_session), api_client: ApiClient = Depends(get_api_client),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    embedding_model=Depends(get_embedding_model),
) -> ChatResponse:
    if not payload.message or not payload.jurisdiction:
        raise HTTPException(status_code=400, detail="message and jurisdiction are required")

    # RFC 7235 makes the auth scheme case-insensitive, so a client sending
    # "bearer <token>" must not silently degrade to an anonymous session.
    account_token = None
    if authorization is not None and (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        account_token = authorization[len(_BEARER_PREFIX):]

    chat_repo = PostgresChatRepository(session)
    chat_session, _ = resolve_session(
        payload.session_token, account_token, payload.jurisdiction, payload.language,
        chat_repo, accounts_client,
    )

    question_type = classify(payload.message)
    if question_type == QuestionType.SYNTHESIS:
        result = build_synthesis_answer(
            payload.message, payload.jurisdiction, payload.language, embedding_model,
            PostgresSegmentRepository(session), ollama_client,
        )
    else:
        result = build_structural_answer(
            question_type, payload.message, payload.jurisdiction, payload.language, api_client,
        )

    answer_type = (
        ChatAnswerType.FALLBACK if result.is_fallback
        else ChatAnswerType.SYNTHESIS if question_type == QuestionType.SYNTHESIS
        else ChatAnswerType.STRUCTURAL
    )

    now = datetime.now(timezone.utc)
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content=payload.message,
        answer_type=None, created_at=now,
    )
    answer_message = chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content=result.text,
        answer_type=answer_type, created_at=now,
    )
    for citation in result.citations:
        chat_repo.add_citation(
            message_id=answer_message.id, document_id=citation["document_id"],
            segment_id=citation.get("segment_id"),
        )

    return ChatResponse(
        session_token=chat_session.session_token, answer=result.text,
        answer_type=answer_type.value,
        citations=[
            CitationResponse(document_id=c["document_id"], segment_id=c.get("segment_id"))
            for c in result.citations
        ],
    )
