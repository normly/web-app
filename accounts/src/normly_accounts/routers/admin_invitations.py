# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import EmailStr
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AccountInvitation, AdminAction
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)
from normly_core.notifications.email import EmailSender

from normly_accounts.admin_mail import INVITATION_LIFETIME_DAYS, send_invitation
from normly_accounts.admin_rules import publisher_or_400
from normly_accounts.admin_schemas import (
    CreateInvitationRequest, InvitationCheckResponse, InvitationResponse,
)
from normly_accounts.dependencies import get_email_sender, get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT
from normly_accounts.security import generate_token

admin_invitations_router = APIRouter(prefix="/v1/admin/invitations", tags=["admin"])

_LIFETIME = timedelta(days=INVITATION_LIFETIME_DAYS)


def _response(invitation: AccountInvitation, email_sent: bool) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id, email=invitation.email, role=invitation.role,
        publisher_id=invitation.publisher_id, expires_at=invitation.expires_at,
        email_sent=email_sent,
    )


def _refuse_blocked(session: Session, email: str) -> Account | None:
    account = PostgresAccountRepository(session).get_account_by_email(email)
    if account is not None and account.blocked_at is not None:
        raise HTTPException(status_code=409, detail="account_blocked")
    return account


@admin_invitations_router.get("/check", response_model=InvitationCheckResponse)
def check_invitation(
    email: EmailStr,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> InvitationCheckResponse:
    account = PostgresAccountRepository(session).get_account_by_email(email)
    invitation = PostgresInvitationRepository(session).get_invitation_by_email(email)
    return InvitationCheckResponse(
        existing_account=account is not None,
        blocked=account is not None and account.blocked_at is not None,
        open_invitation=invitation is not None
        and invitation.expires_at > datetime.now(timezone.utc),
    )


@admin_invitations_router.post("", response_model=InvitationResponse, status_code=201)
def create_invitation(
    payload: CreateInvitationRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> InvitationResponse:
    publisher = publisher_or_400(session, payload.publisher_id)
    account = _refuse_blocked(session, payload.email)
    now = datetime.now(timezone.utc)
    invitation = PostgresInvitationRepository(session).save_invitation(
        email=payload.email, role=payload.role, publisher_id=payload.publisher_id,
        locale=payload.locale, token=generate_token(), invited_by=admin.id,
        created_at=now, expires_at=now + _LIFETIME,
    )
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_CREATED, actor_account_id=admin.id, occurred_at=now,
        target_account_id=account.id if account else None,
        target_invitation_id=invitation.id, target_publisher_id=payload.publisher_id,
        details={
            "role": payload.role.value, "locale": payload.locale,
            "publisher_id": str(payload.publisher_id) if payload.publisher_id else None,
        },
    )
    # Durable before the mail goes out: a link must never point to a token
    # that a failed commit threw away. The message itself is never stored.
    session.commit()
    sent = send_invitation(
        email_sender, invitation, publisher_name=publisher.name if publisher else None,
        message=payload.message,
    )
    return _response(invitation, sent)


@admin_invitations_router.post("/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(
    invitation_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> InvitationResponse:
    repo = PostgresInvitationRepository(session)
    invitation = repo.get_invitation(invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="invitation not found")
    account = _refuse_blocked(session, invitation.email)
    now = datetime.now(timezone.utc)
    renewed = repo.renew_invitation(invitation_id, token=generate_token(), expires_at=now + _LIFETIME)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_RESENT, actor_account_id=admin.id, occurred_at=now,
        target_account_id=account.id if account else None, target_invitation_id=invitation_id,
    )
    session.commit()
    publisher = (
        PostgresPublisherRepository(session).get_publisher(renewed.publisher_id)
        if renewed.publisher_id else None
    )
    sent = send_invitation(
        email_sender, renewed, publisher_name=publisher.name if publisher else None, message=None,
    )
    return _response(renewed, sent)


@admin_invitations_router.delete("/{invitation_id}", status_code=204)
def withdraw_invitation(
    invitation_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    if not PostgresInvitationRepository(session).delete_invitation(invitation_id):
        raise HTTPException(status_code=404, detail="invitation not found")
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_WITHDRAWN, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_invitation_id=invitation_id,
    )
    session.commit()
    return Response(status_code=204)
