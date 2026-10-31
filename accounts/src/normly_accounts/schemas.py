# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

Locale = Literal["de", "en"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    locale: Locale = "de"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LogoutRequest(BaseModel):
    session_token: str


class UpdateProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    notification_preference: str | None = None
    locale: Locale | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    first_name: str | None
    last_name: str | None
    has_avatar: bool
    has_password: bool
    notification_preference: str
    locale: str


class SessionResponse(BaseModel):
    session_token: str
    account: AccountResponse


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr
    locale: Locale = "de"


class VerifyEmailResendRequest(BaseModel):
    email: EmailStr
    locale: Locale = "de"


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    locale: Locale = "de"


class MagicLinkRequestRequest(BaseModel):
    email: EmailStr
    locale: Locale = "de"


class MagicLinkConfirmRequest(BaseModel):
    token: str
    locale: Locale = "de"


class SessionValidationResponse(BaseModel):
    account_id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    has_avatar: bool
    has_password: bool
    # This endpoint is the frontend's only source of account state on initial
    # page load -- login returns no account data -- so every field the
    # profile overlay renders has to be here, not only on AccountResponse.
    notification_preference: str
    # Read by the frontend to show the administrator menu; the server checks
    # the role again on every admin request.
    role: str
    publisher_id: uuid.UUID | None


class SetPasswordRequest(BaseModel):
    current_password: str | None
    new_password: str


class SessionSummaryResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    is_current: bool


class ErrorResponse(BaseModel):
    detail: str


class DeleteAccountRequest(BaseModel):
    password: str | None


class ExportAccountFields(BaseModel):
    email: str
    created_at: datetime
    email_verified: bool
    google_linked: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None
    notification_preference: str


class ExportDocumentRef(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None


class ExportCitation(BaseModel):
    document: ExportDocumentRef
    # None once the cited segment is gone (takedown); the document reference
    # stays readable because the tombstone keeps its identifiers.
    segment_id: uuid.UUID | None
    paragraph_index: int | None


class ExportChatMessage(BaseModel):
    role: str
    content: str
    answer_type: str | None
    created_at: datetime
    citations: list[ExportCitation]


class ExportChatSession(BaseModel):
    id: uuid.UUID
    jurisdiction: str
    language: str
    title: str | None
    created_at: datetime
    messages: list[ExportChatMessage]


class ExportWatchlistEntry(BaseModel):
    work_id: uuid.UUID
    created_at: datetime
    documents: list[ExportDocumentRef]


class ExportNotification(BaseModel):
    id: uuid.UUID
    work_id: uuid.UUID
    trigger_type: str
    trigger_document_id: uuid.UUID | None
    trigger_jurisdiction: str | None
    created_at: datetime
    read_at: datetime | None
    emailed_at: datetime | None


class ExportResponse(BaseModel):
    account: ExportAccountFields
    chat_sessions: list[ExportChatSession]
    watchlist: list[ExportWatchlistEntry]
    notifications: list[ExportNotification]


class AddWatchlistEntryRequest(BaseModel):
    work_id: uuid.UUID


class WatchlistEntryResponse(BaseModel):
    work_id: uuid.UUID
    created_at: datetime


class NotificationResponse(BaseModel):
    id: uuid.UUID
    work_id: uuid.UUID
    trigger_type: str
    trigger_document_id: uuid.UUID | None
    trigger_jurisdiction: str | None
    created_at: datetime
    read_at: datetime | None


class AcceptInvitationRequest(BaseModel):
    token: str
