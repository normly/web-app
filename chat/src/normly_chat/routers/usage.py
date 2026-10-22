# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from normly_chat.accounts_client import AccountsClient
from normly_chat.budget_guard import POOL_REGISTERED, BudgetGuard
from normly_chat.dependencies import get_accounts_client, get_budget_guard
from normly_chat.schemas import ChatUsageResponse

usage_router = APIRouter(prefix="/v1/chat", tags=["chat"])

_BEARER_PREFIX = "Bearer "


@usage_router.get("/usage", response_model=ChatUsageResponse)
def get_usage(
    authorization: str | None = Header(default=None),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    guard: BudgetGuard = Depends(get_budget_guard),
) -> ChatUsageResponse:
    """The signed-in user's AI answers today, for the profile's usage section."""
    identity = None
    if authorization is not None and (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        identity = accounts_client.validate_session(authorization[len(_BEARER_PREFIX):])
    if identity is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    status = guard.status(pool=POOL_REGISTERED, user_key=f"account:{identity.account_id}")
    return ChatUsageResponse(
        used=status.used, limit=status.limit, resets_at=status.resets_at,
        pool_exhausted=status.pool_exhausted, pool_resets_at=status.pool_resets_at,
    )
