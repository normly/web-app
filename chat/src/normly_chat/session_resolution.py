# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from normly_chat.security import generate_session_token


def resolve_session(
    session_token: str | None, account_token: str | None, jurisdiction: str, language: str,
    chat_repo, accounts_client,
):
    """
    Implements the three cases from the design spec's "Sitzungsidentität und
    Kontoverknüpfung" section: no/invalid account token is a no-op on the
    session; a valid token links an unlinked session, preserving history; a
    valid token for a DIFFERENT account than the one already linked starts a
    fresh session rather than appending someone else's messages to it.

    Returns (session, is_new_session) -- the router needs to know whether to
    return the client a NEW session_token or the one it already had.
    """
    session = None
    if session_token is not None:
        session = chat_repo.get_session_by_token(session_token)

    identity = None
    if account_token is not None:
        identity = accounts_client.validate_session(account_token)

    if session is not None and identity is not None and session.account_id not in (
        None, identity.account_id,
    ):
        session = None  # force creation of a fresh, correctly-owned session below

    is_new = session is None
    if is_new:
        session = chat_repo.create_session(
            session_token=generate_session_token(), jurisdiction=jurisdiction,
            language=language, created_at=datetime.now(timezone.utc),
            account_id=identity.account_id if identity is not None else None,
        )
    elif identity is not None and session.account_id is None:
        chat_repo.link_account(session.id, identity.account_id)
        session = chat_repo.get_session_by_token(session.session_token)

    return session, is_new
