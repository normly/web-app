# accounts/src/normly_accounts/routers/magic_link.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_email_sender, get_session
from normly_accounts.email import EmailSender
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import MagicLinkConfirmRequest, MagicLinkRequestRequest, \
    SessionResponse
from normly_accounts.security import generate_token

logger = logging.getLogger(__name__)

magic_link_router = APIRouter(prefix="/v1/accounts/magic-link", tags=["magic-link"])

_MAGIC_LINK_TOKEN_LIFETIME = timedelta(minutes=15)


@magic_link_router.post("/request")
def request_magic_link(
    payload: MagicLinkRequestRequest, session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account = PostgresAccountRepository(session).get_account_by_email(payload.email)

    token_repo = PostgresAccountTokenRepository(session)
    now = datetime.now(timezone.utc)
    expires_at = now + _MAGIC_LINK_TOKEN_LIFETIME
    if account is not None:
        token = token_repo.create_token(
            account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK,
            token=generate_token(), created_at=now, expires_at=expires_at,
        )
    else:
        # Magic-link is a login AND a registration path, but for an address we
        # have never seen the token names the address rather than an account:
        # the account is created at `confirm`, once the link has been followed
        # and the mailbox is thereby proven readable. Creating it here would
        # let anyone conjure a permanent account for any address they can
        # type, unauthenticated.
        token = token_repo.create_token(
            email=payload.email, purpose=AccountTokenPurpose.MAGIC_LINK,
            token=generate_token(), created_at=now, expires_at=expires_at,
        )
    try:
        email_sender.send(
            to=payload.email, subject="Dein Login-Link",
            body=f"Zum Anmelden: token={token.token}",
        )
    except Exception:
        # Per the design spec: the magic-link request itself must not fail
        # when SMTP is unreachable -- the token is already persisted, delivery
        # is decoupled (no retry mechanism yet, tracked as an accepted open
        # point). Never log the token itself.
        logger.exception("magic link email delivery failed for %s", payload.email)
    return {"status": "if_the_request_is_valid_an_email_was_sent"}


@magic_link_router.post("/confirm", response_model=SessionResponse)
def confirm_magic_link(
    payload: MagicLinkConfirmRequest, session: Session = Depends(get_session),
) -> SessionResponse:
    consumed = PostgresAccountTokenRepository(session).consume_token(
        payload.token, AccountTokenPurpose.MAGIC_LINK
    )
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    account_repo = PostgresAccountRepository(session)
    if consumed.account_id is not None:
        account = account_repo.get_account_by_id(consumed.account_id)
    else:
        # The token named a bare address, and following the link has just
        # proven the mailbox readable -- so this, not the request, is where
        # the account comes into being. It may nevertheless exist by now: a
        # registration or a Google login could have claimed the address
        # between the request and this confirm.
        assert consumed.email is not None  # ck_account_token_account_or_email
        account = account_repo.get_account_by_email(consumed.email)
        if account is None:
            account = account_repo.create_account(
                email=consumed.email, password_hash=None
            )

    if account.email_verified_at is None:
        # Completing a magic-link login proves control of the mailbox --
        # the same proof email verification exists to establish. No
        # separate verification step needed for a magic-link-created or
        # magic-link-confirmed account.
        account_repo.mark_email_verified(account.id, datetime.now(timezone.utc))
        account = account_repo.get_account_by_id(account.id)

    return _create_session_response(account, session)
