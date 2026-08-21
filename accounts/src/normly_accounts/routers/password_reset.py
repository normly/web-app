# accounts/src/normly_accounts/routers/password_reset.py
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
from normly_accounts.schemas import PasswordResetConfirmRequest, PasswordResetRequestRequest
from normly_accounts.security import generate_token, hash_password

logger = logging.getLogger(__name__)

password_reset_router = APIRouter(prefix="/v1/accounts/password-reset", tags=["password-reset"])

_RESET_TOKEN_LIFETIME = timedelta(hours=1)


@password_reset_router.post("/request")
def request_password_reset(
    payload: PasswordResetRequestRequest, session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account = PostgresAccountRepository(session).get_account_by_email(payload.email)
    if account is not None:
        now = datetime.now(timezone.utc)
        token = PostgresAccountTokenRepository(session).create_token(
            account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET,
            token=generate_token(), created_at=now, expires_at=now + _RESET_TOKEN_LIFETIME,
        )
        try:
            email_sender.send(
                to=account.email, subject="Passwort zurücksetzen",
                body=f"Zum Zurücksetzen deines Passworts: token={token.token}",
            )
        except Exception:
            # Per the design spec: the reset-request call itself must not
            # fail when SMTP is unreachable -- the token is already
            # persisted, delivery is decoupled (no retry mechanism yet,
            # tracked as an accepted open point). Failing loudly here would
            # also turn this into an account-enumeration side-channel: the
            # unknown-address branch below never calls send() at all, so a
            # raised exception here would make known vs. unknown addresses
            # distinguishable by status code during an SMTP outage. Never
            # log the token itself.
            logger.exception("password reset email delivery failed for %s", account.email)
    # Same response whether or not the account exists -- enumeration
    # protection, same principle as login's generic 401.
    return {"status": "if_the_account_exists_an_email_was_sent"}


@password_reset_router.post("/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirmRequest, session: Session = Depends(get_session),
) -> dict:
    token = PostgresAccountTokenRepository(session).consume_token(
        payload.token, AccountTokenPurpose.PASSWORD_RESET
    )
    if token is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    PostgresAccountRepository(session).set_password_hash(
        token.account_id, hash_password(payload.new_password)
    )
    return {"status": "password_changed"}
