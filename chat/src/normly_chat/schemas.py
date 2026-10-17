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
    created_at: datetime


class DeletedSessionsResponse(BaseModel):
    deleted: int


class ErrorResponse(BaseModel):
    detail: str
