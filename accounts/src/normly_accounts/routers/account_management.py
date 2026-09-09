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
    PostgresNotificationRepository,
    PostgresWatchlistRepository,
)

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import (
    DeleteAccountRequest, ExportAccountFields, ExportChatMessage, ExportChatSession,
    ExportNotification, ExportResponse, ExportWatchlistEntry,
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
    # Commit here, not just at the end of get_session()'s request scope --
    # same hazard and fix as _create_session_response in login.py: FastAPI
    # sends this response and only then closes the yield-dependency's
    # AsyncExitStack, so get_session()'s own commit runs AFTER the client
    # already sees "account_deleted". A commit failure between those two
    # points would tell the client (and the frontend, which then clears the
    # session cookie) that the account is gone when it might not be.
    # Committing explicitly here makes the deletion durable before the
    # response is even constructed.
    session.commit()
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

    watches = PostgresWatchlistRepository(session).list_watches_for_account(account.id)
    # Every notification is included regardless of the account's current
    # display preference -- EMAIL-preference accounts still see their in-app
    # feed hidden (notifications.py's own concern), but a full personal-data
    # export is not a display and must not apply that filter.
    notifications = PostgresNotificationRepository(session).list_for_account(account.id)

    return ExportResponse(
        account=ExportAccountFields(
            email=account.email, created_at=account.created_at,
            email_verified=account.email_verified_at is not None, google_linked=google_linked,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
            notification_preference=account.notification_preference.value,
        ),
        chat_sessions=exported_sessions,
        watchlist=[
            ExportWatchlistEntry(work_id=w.work_id, created_at=w.created_at) for w in watches
        ],
        notifications=[
            ExportNotification(
                id=n.id, work_id=n.work_id, trigger_type=n.trigger_type.value,
                trigger_document_id=n.trigger_document_id,
                trigger_jurisdiction=n.trigger_jurisdiction, created_at=n.created_at,
                read_at=n.read_at, emailed_at=n.emailed_at,
            )
            for n in notifications
        ],
    )
