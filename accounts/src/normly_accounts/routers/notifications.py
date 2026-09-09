# accounts/src/normly_accounts/routers/notifications.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, NotificationPreference
from normly_core.graph.postgres.repositories import PostgresNotificationRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import NotificationResponse

notifications_router = APIRouter(prefix="/v1/accounts", tags=["notifications"])


def _notification_response(notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id, work_id=notification.work_id,
        trigger_type=notification.trigger_type.value,
        trigger_document_id=notification.trigger_document_id,
        trigger_jurisdiction=notification.trigger_jurisdiction,
        created_at=notification.created_at, read_at=notification.read_at,
    )


@notifications_router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[NotificationResponse]:
    # "Nur per E-Mail" means exactly that: the rows are still created (the
    # notification table is what makes notify-watchers' dedup and the mail
    # itself work), but the in-app feed hides them -- otherwise EMAIL and
    # BOTH would be indistinguishable in the UI. The account's CURRENT
    # preference governs the CURRENT display, so switching away from EMAIL
    # makes earlier notifications visible again; no preference-at-creation
    # is tracked per row. mark_read needs no counterpart check: a client
    # cannot discover a hidden notification's id to mark it read.
    if account.notification_preference == NotificationPreference.EMAIL:
        return []
    notifications = PostgresNotificationRepository(session).list_for_account(account.id)
    return [_notification_response(n) for n in notifications]


@notifications_router.patch("/notifications/{notification_id}", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> NotificationResponse:
    repo = PostgresNotificationRepository(session)
    updated = repo.mark_read(
        notification_id, account_id=account.id, read_at=datetime.now(timezone.utc)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="notification not found")
    notifications = repo.list_for_account(account.id)
    return _notification_response(next(n for n in notifications if n.id == notification_id))
