# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LogoutRequest(BaseModel):
    session_token: str


class UpdateProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None


class SessionResponse(BaseModel):
    session_token: str
    account: AccountResponse


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class EmailChangeRequest(BaseModel):
    new_email: EmailStr


class MagicLinkRequestRequest(BaseModel):
    email: EmailStr


class MagicLinkConfirmRequest(BaseModel):
    token: str


class SessionValidationResponse(BaseModel):
    account_id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None


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
