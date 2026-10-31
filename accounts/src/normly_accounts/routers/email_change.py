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
from normly_core.notifications.mail import format_duration, render_email
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
        # The pending address is bound to the token server-side: confirm takes
        # it from here, never from the link, so the link cannot redirect the
        # change to a mailbox nobody proved.
        account_id=account.id, email=payload.new_email,
        purpose=AccountTokenPurpose.EMAIL_CHANGE,
        token=generate_token(), created_at=now, expires_at=now + _EMAIL_CHANGE_TOKEN_LIFETIME,
    )
    # `email=` in the link only lets the confirm page show the address; the
    # confirm endpoint refuses a link whose address differs from the token's.
    confirm_url = (
        f"{_public_base_url()}/confirm-email-change"
        f"?token={quote(token.token)}&email={quote(payload.new_email)}"
    )
    mail = render_email(
        "email_change", payload.locale, base_url=_public_base_url(), action_url=confirm_url,
        new_email=payload.new_email,
        validity=format_duration(_EMAIL_CHANGE_TOKEN_LIFETIME, payload.locale),
    )
    try:
        email_sender.send(
            to=payload.new_email, subject=mail.subject, body=mail.text, html=mail.html,
        )
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
    session.commit()
    return {"status": "confirmation_sent"}


@email_change_router.get("/confirm")
def confirm_email_change(
    token: str, email: str | None = None, session: Session = Depends(get_session),
) -> dict:
    tokens = PostgresAccountTokenRepository(session)
    pending = tokens.find_unconsumed_token(token, AccountTokenPurpose.EMAIL_CHANGE)
    if pending is None or pending.account_id is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    # Lock order (ADR-030): account row before token rows, like invitation accept.
    PostgresAccountRepository(session).lock_account(pending.account_id)
    consumed = tokens.consume_token(token, AccountTokenPurpose.EMAIL_CHANGE)
    # A token without a stored address predates migration 0042; one whose
    # link carries a different address was tampered with. Neither proves the
    # mailbox the account would move to.
    if consumed is None or consumed.email is None or (
        email is not None and email != consumed.email
    ):
        raise HTTPException(status_code=400, detail="invalid or expired token")
    email = consumed.email

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
    session.commit()
    return {"status": "email_changed"}
