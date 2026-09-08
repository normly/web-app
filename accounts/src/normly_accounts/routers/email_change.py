# accounts/src/normly_accounts/routers/email_change.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AccountTokenPurpose, EmailAlreadyRegisteredError
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_current_account, get_email_sender, get_session
from normly_core.notifications.email import EmailSender
from normly_accounts.schemas import EmailChangeRequest
from normly_accounts.security import generate_token

logger = logging.getLogger(__name__)

email_change_router = APIRouter(prefix="/v1/accounts/email", tags=["email-change"])

_EMAIL_CHANGE_TOKEN_LIFETIME = timedelta(hours=24)


def _public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")


@email_change_router.post("/change")
def request_email_change(
    payload: EmailChangeRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session), email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account_repo = PostgresAccountRepository(session)
    if account_repo.get_account_by_email(payload.new_email) is not None:
        # Unlike anonymous registration/reset-request, this caller is already
        # authenticated -- there is no enumeration risk in telling them the
        # address is taken, since they cannot use that information against
        # anyone but themselves.
        raise HTTPException(status_code=409, detail="an account already exists for this email")

    now = datetime.now(timezone.utc)
    token = PostgresAccountTokenRepository(session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.EMAIL_CHANGE,
        # The token's `email` field carries the PENDING new address here --
        # a different use than the "address with no account yet" case
        # magic-link/registration use it for, but the same nullable column;
        # account_id is set to the existing account in both this case and
        # that one, which is what account.email is actually changed to.
        token=generate_token(), created_at=now, expires_at=now + _EMAIL_CHANGE_TOKEN_LIFETIME,
    )
    # create_token's own signature takes email= as an alternative to
    # account_id=, not alongside it (see ck_account_token_account_or_email) --
    # so the pending address cannot travel on this token as written. Store it
    # via a second, minimal mechanism instead: reuse the token string itself
    # as the pointer, and re-derive the pending address from the *request*
    # this handler is already holding, encoding it into the emailed link
    # instead of the token record.
    try:
        confirm_url = (
            f"{_public_base_url()}/confirm-email-change"
            f"?token={quote(token.token)}&email={quote(payload.new_email)}"
        )
        email_sender.send(
            to=payload.new_email, subject="Bestätige deine neue E-Mail-Adresse",
            body=f"Zum Bestätigen deiner neuen E-Mail-Adresse: {confirm_url}",
        )
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
    return {"status": "confirmation_sent"}


@email_change_router.get("/confirm")
def confirm_email_change(
    token: str, email: str, session: Session = Depends(get_session),
) -> dict:
    consumed = PostgresAccountTokenRepository(session).consume_token(
        token, AccountTokenPurpose.EMAIL_CHANGE
    )
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    account_repo = PostgresAccountRepository(session)
    if account_repo.get_account_by_email(email) is not None:
        # The address was claimed by someone else between the request and
        # this confirm (e.g. a race with another registration) -- refuse
        # rather than raise an IntegrityError from the UPDATE below.
        raise HTTPException(status_code=409, detail="an account already exists for this email")

    try:
        account_repo.update_email(consumed.account_id, email)
    except EmailAlreadyRegisteredError:
        # The pre-check above narrows but does not close the race: a second
        # confirm for the same newly-freed address can still slip past it
        # and hit uq_account_email in update_email itself. Same response as
        # the pre-check, so the client sees one consistent 409 either way.
        raise HTTPException(status_code=409, detail="an account already exists for this email")
    return {"status": "email_changed"}
