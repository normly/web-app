# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from normly_chat.security import generate_session_token


def resolve_session(
    session_token: str | None, identity, jurisdiction: str, language: str, chat_repo,
):
    """
    Resolves the chat session for a request. Anonymous chats are not stored
    (the router never calls this without a valid account), so a session is
    only reused when it belongs to the requesting identity; anything else,
    including a session of another account or a legacy unlinked row, yields a
    fresh session. Nothing is ever linked to an account after the fact.

    Returns (session, is_new_session) -- the router needs to know whether to
    return the client a NEW session_token or the one it already had.
    """
    session = None
    if session_token is not None:
        session = chat_repo.get_session_by_token(session_token)

    owner_id = identity.account_id if identity is not None else None
    if session is not None and session.account_id != owner_id:
        session = None  # force creation of a fresh, correctly-owned session below

    is_new = session is None
    if is_new:
        session = chat_repo.create_session(
            session_token=generate_session_token(), jurisdiction=jurisdiction,
            language=language, created_at=datetime.now(timezone.utc),
            account_id=identity.account_id if identity is not None else None,
        )

    return session, is_new
