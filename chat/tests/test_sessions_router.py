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


def _seed(db_session, email, tokens):
    from datetime import datetime, timezone
    from normly_core.graph.domain import ChatMessageRole
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository, PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(
        email=email, password_hash=None,
    )
    repo = PostgresChatRepository(db_session)
    sessions = []
    for token in tokens:
        chat_session = repo.create_session(
            session_token=token, jurisdiction="DE", language="de",
            created_at=datetime.now(timezone.utc), account_id=account.id,
        )
        repo.create_message(
            session_id=chat_session.id, role=ChatMessageRole.USER, content="Frage",
            answer_type=None, created_at=datetime.now(timezone.utc),
        )
        sessions.append(chat_session)
    return account, sessions


def _act_as(client, account):
    from normly_chat.dependencies import get_accounts_client
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)


_AUTH = {"Authorization": "Bearer whatever-the-fake-accepts"}


def test_delete_own_session_returns_204_and_removes_it_with_a_log_entry(client, db_session):
    from sqlalchemy import text
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    account, (mine,) = _seed(db_session, "del-own@example.de", ["del-own-tok"])
    _act_as(client, account)

    response = client.delete(f"/v1/chat/sessions/{mine.id}", headers=_AUTH)

    assert response.status_code == 204
    repo = PostgresChatRepository(db_session)
    assert repo.get_session_by_token("del-own-tok") is None
    assert repo.list_messages_for_session(mine.id) == []
    logged = db_session.execute(
        text("select count(*) from deletion_log where kind = 'chat_session' and entity_id = :i"),
        {"i": mine.id},
    ).scalar_one()
    assert logged == 1


def test_delete_foreign_or_unknown_session_is_404_and_changes_nothing(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    me, _ = _seed(db_session, "del-me@example.de", ["del-me-tok"])
    _, (theirs,) = _seed(db_session, "del-them@example.de", ["del-them-tok"])
    _act_as(client, me)

    foreign = client.delete(f"/v1/chat/sessions/{theirs.id}", headers=_AUTH)
    unknown = client.delete(f"/v1/chat/sessions/{uuid.uuid4()}", headers=_AUTH)

    assert foreign.status_code == 404
    assert unknown.status_code == 404
    assert foreign.json() == unknown.json()
    assert PostgresChatRepository(db_session).get_session_by_token("del-them-tok") is not None


def test_delete_without_valid_account_is_401(client, db_session):
    from normly_chat.dependencies import get_accounts_client

    _, (target,) = _seed(db_session, "del-401@example.de", ["del-401-tok"])
    assert client.delete(f"/v1/chat/sessions/{target.id}").status_code == 401
    assert client.delete("/v1/chat/sessions").status_code == 401
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(None)
    assert client.delete(f"/v1/chat/sessions/{target.id}", headers=_AUTH).status_code == 401
    assert client.delete("/v1/chat/sessions", headers=_AUTH).status_code == 401


def test_delete_all_removes_only_own_sessions(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    me, _ = _seed(db_session, "delall-me@example.de", ["delall-a", "delall-b"])
    _seed(db_session, "delall-them@example.de", ["delall-c"])
    _act_as(client, me)

    response = client.delete("/v1/chat/sessions", headers=_AUTH)

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    repo = PostgresChatRepository(db_session)
    assert repo.get_session_by_token("delall-a") is None
    assert repo.get_session_by_token("delall-c") is not None
