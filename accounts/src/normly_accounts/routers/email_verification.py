# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_session

email_verification_router = APIRouter(prefix="/v1/accounts", tags=["email-verification"])


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
