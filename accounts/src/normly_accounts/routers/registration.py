# accounts/src/normly_accounts/routers/registration.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    EmailAlreadyRegisteredError,
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_email_sender, get_session
from normly_accounts.email import EmailSender
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import RegisterRequest, SessionResponse
from normly_accounts.security import generate_token, hash_password

logger = logging.getLogger(__name__)

registration_router = APIRouter(prefix="/v1/accounts", tags=["registration"])

_VERIFICATION_TOKEN_LIFETIME = timedelta(hours=48)


@registration_router.post("/register", response_model=SessionResponse)
def register(
    payload: RegisterRequest, session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> SessionResponse:
    account_repo = PostgresAccountRepository(session)
    try:
        account = account_repo.create_account(
            email=payload.email, password_hash=hash_password(payload.password)
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="an account already exists for this email")

    now = datetime.now(timezone.utc)
    token = PostgresAccountTokenRepository(session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token=generate_token(), created_at=now, expires_at=now + _VERIFICATION_TOKEN_LIFETIME,
    )
    try:
        email_sender.send(
            to=account.email, subject="Bestätige deine E-Mail-Adresse",
            body=f"Bitte bestätige deine E-Mail-Adresse: token={token.token}",
        )
    except Exception:
        # Per the design spec: registration itself must not fail when SMTP
        # is unreachable -- the account and verification token are already
        # persisted, delivery is decoupled (no retry mechanism yet, tracked
        # as an accepted open point). Never log the token itself.
        logger.exception("registration verification email delivery failed for %s", account.email)

    return _create_session_response(account, session)
