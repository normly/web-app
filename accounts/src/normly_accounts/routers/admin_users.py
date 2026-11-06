# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, Role
from normly_core.graph.postgres.repositories import PostgresAdminDirectoryRepository

from normly_accounts.admin_schemas import (
    AdminSummaryResponse, AdminUserPageResponse, AdminUserResponse, RoleMatrixResponse,
    RoleMatrixRow,
)
from normly_accounts.dependencies import get_session, require_capability
from normly_accounts.permissions import CAPABILITIES, MATRIX_ROLES, USER_MANAGEMENT

admin_users_router = APIRouter(prefix="/v1/admin", tags=["admin"])

ACTIVE_WINDOW = timedelta(days=30)
PAGE_SIZES = (10, 20, 50)
SortKey = Literal[
    "email", "first_name", "last_name", "sign_in", "role", "publisher", "last_login_at",
    "created_at", "status",
]


@admin_users_router.get("/users", response_model=AdminUserPageResponse)
def list_users(
    q: str | None = Query(default=None, max_length=200),
    role: Role | None = None,
    status: Literal["active", "blocked", "invited", "expired"] | None = None,
    sort: SortKey = "email",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = 10,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> AdminUserPageResponse:
    if page_size not in PAGE_SIZES:
        raise HTTPException(status_code=400, detail="page_size must be 10, 20 or 50")
    result = PostgresAdminDirectoryRepository(session).list_users(
        query=q, role=role, status=status, sort=sort, descending=order == "desc",
        page=page, page_size=page_size, now=datetime.now(timezone.utc),
    )
    return AdminUserPageResponse(
        rows=[
            AdminUserResponse(**{**row.__dict__, "sign_in_methods": list(row.sign_in_methods)})
            for row in result.rows
        ],
        total=result.total, page=page, page_size=page_size,
    )


@admin_users_router.get("/users/summary", response_model=AdminSummaryResponse)
def summarize_users(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> AdminSummaryResponse:
    now = datetime.now(timezone.utc)
    summary = PostgresAdminDirectoryRepository(session).summarize(
        now=now, active_since=now - ACTIVE_WINDOW
    )
    return AdminSummaryResponse(
        accounts_total=summary.accounts_total,
        accounts_active_30_days=summary.accounts_active,
        accounts_by_role={role.value: n for role, n in summary.accounts_by_role.items()},
        publishers_with_accounts=summary.publishers_with_accounts,
        open_invitations=summary.open_invitations, blocked=summary.blocked,
        most_frequent_block_reason=summary.most_frequent_block_reason,
    )


@admin_users_router.get("/role-matrix", response_model=RoleMatrixResponse)
def role_matrix(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
) -> RoleMatrixResponse:
    return RoleMatrixResponse(
        roles=list(MATRIX_ROLES),
        rows=[
            RoleMatrixRow(capability=c.key, planned=c.planned, values=c.values)
            for c in CAPABILITIES
        ],
    )
