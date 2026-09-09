# accounts/src/normly_accounts/routers/watchlist.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
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
    # add_watch's own IntegrityError handler only resolves the "already
    # watching this pair" race, which it answers by returning the existing
    # row. A work_id that references no Work has no such row to find, so it
    # re-raises -- and the application-wide infrastructure handler would
    # dress that up as a 503, telling the caller the service is down when
    # they simply sent an id that does not exist.
    try:
        watch = PostgresWatchlistRepository(session).add_watch(
            account_id=account.id, work_id=payload.work_id
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="work not found")
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
