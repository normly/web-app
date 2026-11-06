# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
)

from normly_accounts.admin_rules import ensure_administrator_remains, snapshot
from normly_accounts.credentials import reset_credentials
from normly_accounts.dependencies import get_session
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import AcceptInvitationRequest, SessionResponse

invitation_router = APIRouter(prefix="/v1/accounts/invitations", tags=["invitations"])


@invitation_router.post("/accept", response_model=SessionResponse)
def accept_invitation(
    payload: AcceptInvitationRequest, session: Session = Depends(get_session),
) -> SessionResponse:
    """
    The click on the invitation link: proves the mailbox, binds role and
    publisher and signs the person in. A role is never granted because an
    address merely matches (ADR-030).
    """
    now = datetime.now(timezone.utc)
    invitations = PostgresInvitationRepository(session)
    invitation = invitations.get_invitation_by_token(payload.token, lock=True)
    if invitation is None or invitation.expires_at <= now:
        raise HTTPException(status_code=410, detail="invitation_invalid")

    accounts = PostgresAccountRepository(session)
    account = accounts.get_account_by_email(invitation.email)
    pre_registered = account is not None
    if pre_registered and account.email_verified_at is None:
        # Row lock before the reset: a password login re-reads the account
        # under the same lock (login.py), so it either commits its session
        # before the reset deletes it or sees the cleared password.
        if account.role is Role.ADMINISTRATOR:
            # Lock order (ADR-030): administrator rows first, like the admin
            # panel, then the account row, then its tokens.
            accounts.lock_active_administrator_ids()
        account = accounts.lock_account(account.id)
    if account is None:
        account = accounts.create_account(
            email=invitation.email, password_hash=None, locale=invitation.locale,
        )
    if account.blocked_at is not None:
        raise HTTPException(status_code=403, detail="account_blocked")
    if invitation.role is not Role.ADMINISTRATOR:
        ensure_administrator_remains(session, account)

    credentials_reset = pre_registered and account.email_verified_at is None
    google_linked = False
    if credentials_reset:
        # Nobody had proved this mailbox before the link was clicked: whoever
        # registered the address may not be its owner. Every credential they
        # could hold goes, so the role reaches only the session created below.
        # A Google link on an unverified account almost always means a real
        # owner who signed in with Google before such sign-ins marked the
        # address verified: keep their content, reset only the way in. Read
        # before reset_credentials, which unlinks Google.
        google_linked = PostgresAccountGoogleIdentityRepository(session).has_google_identity(
            account.id
        )
        reset_credentials(session, account.id)
        if not google_linked:
            # Nor does anything the registrant left behind belong to the owner.
            accounts.reset_unverified_account_content(account.id, locale=invitation.locale)
    if account.email_verified_at is None:
        accounts.mark_email_verified(account.id, now)
    accounts.set_role(account.id, role=invitation.role, publisher_id=invitation.publisher_id)
    invitations.delete_invitation(invitation.id)
    after = accounts.get_account_by_id(account.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_ACCEPTED, actor_account_id=account.id, occurred_at=now,
        target_account_id=account.id, target_invitation_id=invitation.id,
        target_publisher_id=invitation.publisher_id,
        details={
            "before": snapshot(account), "after": snapshot(after),
            "credentials_reset": credentials_reset,
            "content_reset": credentials_reset and not google_linked,
        },
    )
    # Commits before the response, like every sign-in path.
    return _create_session_response(after, session)
