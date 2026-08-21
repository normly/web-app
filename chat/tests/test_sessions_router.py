# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_chat.accounts_client import ChatAccountIdentity


class _FakeAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, token):
        return self._identity


def test_missing_authorization_header_returns_401(client):
    response = client.get("/v1/chat/sessions")
    assert response.status_code == 401


def test_invalid_account_token_returns_401(client):
    from normly_chat.dependencies import get_accounts_client
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(None)
    from normly_chat.dependencies import get_session
    # Reuse the same db_session override the `client` fixture already set up.
    app.dependency_overrides[get_session] = client.app.dependency_overrides[get_session]

    from fastapi.testclient import TestClient
    with TestClient(app) as raising_client:
        response = raising_client.get(
            "/v1/chat/sessions", headers={"Authorization": "Bearer not-a-real-token"},
        )
    assert response.status_code == 401


def test_returns_only_the_authenticated_accounts_sessions(client, db_session):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )
    from datetime import datetime, timezone

    account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router@example.de", password_hash=None,
    )
    other_account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router-other@example.de", password_hash=None,
    )
    chat_repo = PostgresChatRepository(db_session)
    mine = chat_repo.create_session(
        session_token="mine-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    chat_repo.create_session(
        session_token="theirs-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=other_account.id,
    )

    from normly_chat.dependencies import get_accounts_client
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)

    response = client.get(
        "/v1/chat/sessions", headers={"Authorization": "Bearer whatever-the-fake-accepts"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_token"] == mine.session_token
