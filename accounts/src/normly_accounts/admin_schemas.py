# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from normly_core.graph.domain import BlockReason, Role

from normly_accounts.schemas import Locale

PublisherName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreatePublisherRequest(BaseModel):
    name: PublisherName


class PublisherResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class InvitationCheckResponse(BaseModel):
    existing_account: bool
    blocked: bool
    open_invitation: bool


def _binding_is_consistent(role: Role, publisher_id: uuid.UUID | None) -> None:
    if (role is Role.PUBLISHER) != (publisher_id is not None):
        raise ValueError("a publisher_id is required for the publisher role and only for it")


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: Role
    publisher_id: uuid.UUID | None = None
    locale: Locale = "de"
    message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_binding(self) -> "CreateInvitationRequest":
        _binding_is_consistent(self.role, self.publisher_id)
        return self


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    publisher_id: uuid.UUID | None
    expires_at: datetime
    email_sent: bool


class EmailSentResponse(BaseModel):
    email_sent: bool


class UpdateAccountRequest(BaseModel):
    role: Role | None = None
    publisher_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "UpdateAccountRequest":
        if (self.role is None) == (self.publisher_id is None):
            raise ValueError("send either role or publisher_id")
        return self


class BlockAccountRequest(BaseModel):
    reason: BlockReason


class RemoveAccountRequest(BaseModel):
    confirm_email: str


class AdminUserResponse(BaseModel):
    kind: Literal["account", "invitation"]
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    sign_in_methods: list[str]
    role: Role
    publisher_id: uuid.UUID | None
    publisher_name: str | None
    last_login_at: datetime | None
    created_at: datetime | None
    status: Literal["active", "blocked", "invited", "expired"]
    block_reason: BlockReason | None
    expires_at: datetime | None


class AdminUserPageResponse(BaseModel):
    rows: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminSummaryResponse(BaseModel):
    accounts_total: int
    accounts_active_30_days: int
    accounts_by_role: dict[str, int]
    publishers_with_accounts: int
    open_invitations: int
    blocked: int
    most_frequent_block_reason: BlockReason | None


class RoleMatrixRow(BaseModel):
    capability: str
    planned: bool
    values: dict[str, str]


class RoleMatrixResponse(BaseModel):
    roles: list[str]
    rows: list[RoleMatrixRow]
