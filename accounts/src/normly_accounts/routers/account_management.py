# accounts/src/normly_accounts/routers/account_management.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresChatRepository,
)

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import (
    DeleteAccountRequest, ExportAccountFields, ExportChatMessage, ExportChatSession,
    ExportResponse,
)
from normly_accounts.security import verify_password

account_management_router = APIRouter(prefix="/v1/accounts", tags=["account-management"])


@account_management_router.delete("/me")
def delete_account(
    payload: DeleteAccountRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    if account.password_hash is not None:
        if payload.password is None or not verify_password(
            payload.password, account.password_hash
        ):
            raise HTTPException(status_code=401, detail="password is incorrect")
    # else: passwordless account -- the frontend already required a typed
    # email-address confirmation before ever sending this request; the valid
    # session itself is the only server-side proof available.

    PostgresAccountRepository(session).delete_account(account.id)
    return {"status": "account_deleted"}


@account_management_router.get("/export", response_model=ExportResponse)
def export_account_data(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> ExportResponse:
    google_linked = PostgresAccountGoogleIdentityRepository(session).has_google_identity(
        account.id
    )

    chat_repo = PostgresChatRepository(session)
    chat_sessions = chat_repo.list_sessions_for_account(account.id)
    exported_sessions = []
    for chat_session in chat_sessions:
        messages = chat_repo.list_messages_for_session(chat_session.id)
        exported_sessions.append(
            ExportChatSession(
                session_token=chat_session.session_token, jurisdiction=chat_session.jurisdiction,
                language=chat_session.language, created_at=chat_session.created_at,
                messages=[
                    ExportChatMessage(role=m.role.value, content=m.content, created_at=m.created_at)
                    for m in messages
                ],
            )
        )

    return ExportResponse(
        account=ExportAccountFields(
            email=account.email, created_at=account.created_at,
            email_verified=account.email_verified_at is not None, google_linked=google_linked,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
        ),
        chat_sessions=exported_sessions,
    )
