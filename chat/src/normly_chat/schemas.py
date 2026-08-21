# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
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


class ChatResponse(BaseModel):
    session_token: str
    answer: str
    answer_type: Literal["structural", "synthesis", "fallback"]
    citations: list[CitationResponse]


class ErrorResponse(BaseModel):
    detail: str
