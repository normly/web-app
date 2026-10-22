# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_token: str | None = None
    jurisdiction: str
    language: Literal["de", "en"]
    message: str


class CitationResponse(BaseModel):
    document_id: uuid.UUID
    segment_id: uuid.UUID | None
    designation: str
    section: str | None
    # None: the citation backs the whole answer rather than one paragraph.
    paragraph_index: int | None


class ChatResponse(BaseModel):
    session_id: uuid.UUID | None
    session_token: str | None
    # The paragraphs joined by a blank line; kept for clients that render
    # plain text.
    answer: str
    answer_type: Literal["structural", "synthesis", "fallback"]
    paragraphs: list[str]
    citations: list[CitationResponse]


class ChatSessionSummary(BaseModel):
    id: uuid.UUID
    session_token: str
    jurisdiction: str
    language: str
    title: str | None
    created_at: datetime


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    answer_type: Literal["structural", "synthesis", "fallback"] | None
    paragraphs: list[str]
    citations: list[CitationResponse]
    created_at: datetime


class ChatSessionMessagesResponse(BaseModel):
    session_id: uuid.UUID
    # The frontend sets its chat cookie from this, so that new questions
    # continue the reopened session.
    session_token: str
    title: str | None
    messages: list[ChatMessageResponse]


class ChatSessionTitleResponse(BaseModel):
    title: str


class DeletedSessionsResponse(BaseModel):
    deleted: int


class BudgetExhaustedDetail(BaseModel):
    reason: Literal["quota_exhausted", "pool_daily_exhausted", "pool_monthly_exhausted"]
    resets_at: datetime
    anonymous: bool


class BudgetExhaustedResponse(BaseModel):
    detail: BudgetExhaustedDetail


class ChatUsageResponse(BaseModel):
    used: int
    limit: int
    resets_at: datetime
    pool_exhausted: bool
    pool_resets_at: datetime | None


class ErrorResponse(BaseModel):
    detail: str
