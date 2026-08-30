# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import SetPasswordRequest
from normly_accounts.security import hash_password, verify_password

password_router = APIRouter(prefix="/v1/accounts", tags=["password"])


@password_router.post("/password")
def set_password(
    payload: SetPasswordRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    if account.password_hash is not None:
        if payload.current_password is None or not verify_password(
            payload.current_password, account.password_hash
        ):
            raise HTTPException(status_code=401, detail="current password is incorrect")
    # else: passwordless account (Google/magic-link) -- the valid session
    # itself already proved identity, nothing to compare the new password
    # against.

    PostgresAccountRepository(session).set_password_hash(
        account.id, hash_password(payload.new_password)
    )
    return {"status": "password_set"}
