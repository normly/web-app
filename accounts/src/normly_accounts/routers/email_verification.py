# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
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
from normly_accounts.schemas import VerifyEmailResendRequest
from normly_accounts.security import generate_token

email_verification_router = APIRouter(prefix="/v1/accounts", tags=["email-verification"])

_VERIFICATION_TOKEN_LIFETIME = timedelta(hours=48)


def _public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")


@email_verification_router.get("/verify-email")
def verify_email(token: str, session: Session = Depends(get_session)) -> dict:
    consumed = PostgresAccountTokenRepository(session).consume_token(
        token, AccountTokenPurpose.EMAIL_VERIFICATION
    )
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    PostgresAccountRepository(session).mark_email_verified(
        consumed.account_id, datetime.now(timezone.utc)
    )
    return {"status": "email_verified"}


@email_verification_router.post("/verify-email/resend")
def resend_verification_email(
    payload: VerifyEmailResendRequest, session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account = PostgresAccountRepository(session).get_account_by_email(payload.email)
    if account is not None and account.email_verified_at is None:
        now = datetime.now(timezone.utc)
        token = PostgresAccountTokenRepository(session).create_token(
            account_id=account.id, purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
            token=generate_token(), created_at=now, expires_at=now + _VERIFICATION_TOKEN_LIFETIME,
        )
        try:
            email_sender.send(
                to=account.email, subject="Bestätige deine E-Mail-Adresse",
                body=(
                    f"Bitte bestätige deine E-Mail-Adresse: "
                    f"{_public_base_url()}/verify-email?token={token.token}"
                ),
            )
        except Exception:
            # Same rationale as every other best-effort send in this
            # codebase (password_reset.py, registration.py): the request
            # itself must not fail when SMTP is unreachable, and staying
            # silent here (rather than raising) avoids turning a delivery
            # outage into an account-enumeration side-channel between a
            # known-unverified address and an unknown one. Never log the
            # token itself.
            pass
    # Same response regardless of whether the account exists or is
    # already verified -- enumeration protection, same principle as
    # password-reset's own request endpoint.
    return {"status": "if_the_account_exists_and_is_unverified_an_email_was_sent"}
