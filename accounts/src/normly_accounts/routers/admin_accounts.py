# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAdminAuditRepository,
)
from normly_core.notifications.email import EmailSender

from normly_accounts.admin_mail import send_account_notice
from normly_accounts.admin_rules import (
    ensure_administrator_remains, ensure_not_self, publisher_or_400, snapshot,
    target_account_or_404,
)
from normly_accounts.admin_schemas import (
    BlockAccountRequest, EmailSentResponse, RemoveAccountRequest, UpdateAccountRequest,
)
from normly_accounts.dependencies import get_email_sender, get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT

admin_accounts_router = APIRouter(prefix="/v1/admin/accounts", tags=["admin"])


@admin_accounts_router.patch("/{account_id}", status_code=204)
def update_account(
    account_id: uuid.UUID, payload: UpdateAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    """Downgrade to user or change a publisher's binding; upgrades go through an invitation."""
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    accounts = PostgresAccountRepository(session)
    if payload.role is not None:
        if payload.role is not Role.USER:
            raise HTTPException(status_code=409, detail="upgrade_requires_invitation")
        if target.role is Role.USER:
            return Response(status_code=204)
        ensure_administrator_remains(session, target)
        accounts.set_role(target.id, role=Role.USER, publisher_id=None)
        action = AdminAction.ROLE_CHANGED
    else:
        if target.role is not Role.PUBLISHER:
            raise HTTPException(status_code=409, detail="not_a_publisher")
        publisher_or_400(session, payload.publisher_id)
        if target.publisher_id == payload.publisher_id:
            return Response(status_code=204)
        accounts.set_role(target.id, role=Role.PUBLISHER, publisher_id=payload.publisher_id)
        action = AdminAction.PUBLISHER_CHANGED
    after = accounts.get_account_by_id(target.id)
    PostgresAdminAuditRepository(session).record(
        action=action, actor_account_id=admin.id, occurred_at=datetime.now(timezone.utc),
        target_account_id=target.id, target_publisher_id=after.publisher_id or target.publisher_id,
        details={"before": snapshot(target), "after": snapshot(after)},
    )
    session.commit()
    return Response(status_code=204)


@admin_accounts_router.post("/{account_id}/block", response_model=EmailSentResponse)
def block_account(
    account_id: uuid.UUID, payload: BlockAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EmailSentResponse:
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    if target.blocked_at is not None:
        raise HTTPException(status_code=409, detail="already_blocked")
    ensure_administrator_remains(session, target)
    now = datetime.now(timezone.utc)
    PostgresAccountRepository(session).block_account(target.id, reason=payload.reason, blocked_at=now)
    PostgresAccountSessionRepository(session).delete_sessions_for_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_BLOCKED, actor_account_id=admin.id, occurred_at=now,
        target_account_id=target.id, details={"reason": payload.reason.value},
    )
    session.commit()
    sent = send_account_notice(email_sender, "account_blocked", email=target.email, locale=target.locale)
    return EmailSentResponse(email_sent=sent)


@admin_accounts_router.post("/{account_id}/unblock", status_code=204)
def unblock_account(
    account_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    target = target_account_or_404(session, account_id)
    if target.blocked_at is None:
        raise HTTPException(status_code=409, detail="not_blocked")
    PostgresAccountRepository(session).unblock_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_UNBLOCKED, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_account_id=target.id,
        details={"reason": target.block_reason.value},
    )
    session.commit()
    return Response(status_code=204)


@admin_accounts_router.delete("/{account_id}", response_model=EmailSentResponse)
def remove_account(
    account_id: uuid.UUID, payload: RemoveAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EmailSentResponse:
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    if payload.confirm_email.strip().lower() != target.email.lower():
        raise HTTPException(status_code=400, detail="confirmation does not match")
    ensure_administrator_remains(session, target)
    # Same path as self-deletion (ADR-027): cascade plus deletion_log entry.
    PostgresAccountRepository(session).delete_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_REMOVED, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_account_id=target.id,
        details={"before": snapshot(target)},
    )
    session.commit()
    # After the commit: no mail announces a deletion that did not happen.
    sent = send_account_notice(email_sender, "account_removed", email=target.email, locale=target.locale)
    return EmailSentResponse(email_sent=sent)
