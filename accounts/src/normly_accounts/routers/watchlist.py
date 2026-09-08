# accounts/src/normly_accounts/routers/watchlist.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresWatchlistRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import AddWatchlistEntryRequest, WatchlistEntryResponse

watchlist_router = APIRouter(prefix="/v1/accounts", tags=["watchlist"])


@watchlist_router.post("/watchlist", response_model=WatchlistEntryResponse)
def add_watch(
    payload: AddWatchlistEntryRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> WatchlistEntryResponse:
    watch = PostgresWatchlistRepository(session).add_watch(
        account_id=account.id, work_id=payload.work_id
    )
    return WatchlistEntryResponse(work_id=watch.work_id, created_at=watch.created_at)


@watchlist_router.delete("/watchlist/{work_id}")
def remove_watch(
    work_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    PostgresWatchlistRepository(session).remove_watch(account_id=account.id, work_id=work_id)
    return {"status": "removed"}


@watchlist_router.get("/watchlist", response_model=list[WatchlistEntryResponse])
def list_watches(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[WatchlistEntryResponse]:
    watches = PostgresWatchlistRepository(session).list_watches_for_account(account.id)
    return [WatchlistEntryResponse(work_id=w.work_id, created_at=w.created_at) for w in watches]
