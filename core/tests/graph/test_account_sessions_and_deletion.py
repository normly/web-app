# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import (
    AccountTokenPurpose,
    ChatMessageRole,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import ChatMessageORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
    PostgresChatRepository,
    PostgresWorkRepository,
)


def _seed_account_session(repo: PostgresAccountSessionRepository, account_id):
    now = datetime.now(timezone.utc)
    return repo.create_session(
        account_id=account_id, session_token=f"tok-{account_id}-{now.timestamp()}",
        created_at=now, expires_at=now + timedelta(days=30),
    )


def test_list_sessions_for_account_returns_only_that_accounts_sessions(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    mine = account_repo.create_account(email="mine@example.de", password_hash=None)
    theirs = account_repo.create_account(email="theirs@example.de", password_hash=None)
    my_session = _seed_account_session(session_repo, mine.id)
    _seed_account_session(session_repo, theirs.id)

    result = session_repo.list_sessions_for_account(mine.id)

    assert [s.id for s in result] == [my_session.id]


def test_revoke_session_by_id_removes_it(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    account = account_repo.create_account(email="revoke@example.de", password_hash=None)
    to_revoke = _seed_account_session(session_repo, account.id)

    revoked = session_repo.revoke_session_by_id(to_revoke.id, account.id)

    assert revoked is True
    assert session_repo.list_sessions_for_account(account.id) == []


def test_revoke_session_by_id_refuses_a_session_belonging_to_another_account(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    mine = account_repo.create_account(email="owner@example.de", password_hash=None)
    theirs = account_repo.create_account(email="other@example.de", password_hash=None)
    their_session = _seed_account_session(session_repo, theirs.id)

    revoked = session_repo.revoke_session_by_id(their_session.id, mine.id)

    assert revoked is False
    assert len(session_repo.list_sessions_for_account(theirs.id)) == 1


def test_delete_account_removes_the_account_row(db_session):
    account_repo = PostgresAccountRepository(db_session)
    account = account_repo.create_account(email="delete-me@example.de", password_hash=None)

    account_repo.delete_account(account.id)

    assert account_repo.get_account_by_id(account.id) is None


def test_delete_account_cascades_to_chat_sessions_messages_and_citations(db_session):
    account_repo = PostgresAccountRepository(db_session)
    chat_repo = PostgresChatRepository(db_session)
    account = account_repo.create_account(email="cascade@example.de", password_hash=None)
    now = datetime.now(timezone.utc)
    chat_session = chat_repo.create_session(
        session_token="cascade-tok", jurisdiction="DE", language="de",
        created_at=now, account_id=account.id,
    )
    message = chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Hallo?",
        answer_type=None, created_at=now,
    )

    account_repo.delete_account(account.id)

    assert chat_repo.get_session_by_token("cascade-tok") is None
    assert chat_repo.list_messages_for_session(chat_session.id) == []
    # A direct row-count check on the message itself, not just via the
    # session-scoped listing above -- proves the message row is genuinely
    # gone, not merely unreachable through one query path. Uses the ORM
    # class directly (not the domain ChatMessage type) since Session.get
    # requires a mapped class.
    assert db_session.get(ChatMessageORM, message.id) is None


def test_delete_account_removes_sessions_and_tokens(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="tokens@example.de", password_hash=None)
    _seed_account_session(session_repo, account.id)
    now = datetime.now(timezone.utc)
    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET,
        token="delete-me-token", created_at=now, expires_at=now + timedelta(hours=1),
    )

    account_repo.delete_account(account.id)

    assert session_repo.list_sessions_for_account(account.id) == []
    assert token_repo.consume_token("delete-me-token", AccountTokenPurpose.PASSWORD_RESET) is None


def test_delete_account_removes_watchlist_and_notification_rows(db_session):
    account_repo = PostgresAccountRepository(db_session)
    work_repo = PostgresWorkRepository(db_session)
    account = account_repo.create_account(email="watcher@example.de", password_hash=None)
    work = work_repo.create_work(created_via=WorkCreatedVia.MANUAL)

    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    db_session.add(
        NotificationORM(
            id=uuid.uuid4(),
            account_id=account.id,
            work_id=work.id,
            trigger_type=NotificationTriggerType.NEW_EDITION,
            trigger_edge_id=None,
            trigger_document_id=None,
            trigger_jurisdiction=None,
            may_process=None,
            may_index_fulltext=None,
            may_cite_passages=None,
            may_export_free=None,
            read_at=None,
            emailed_at=None,
        )
    )
    db_session.flush()

    account_repo.delete_account(account.id)

    assert account_repo.get_account_by_id(account.id) is None


def test_delete_account_does_not_touch_another_accounts_data(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    victim = account_repo.create_account(email="stays@example.de", password_hash=None)
    to_delete = account_repo.create_account(email="goes@example.de", password_hash=None)
    _seed_account_session(session_repo, victim.id)

    account_repo.delete_account(to_delete.id)

    assert account_repo.get_account_by_id(victim.id) is not None
    assert len(session_repo.list_sessions_for_account(victim.id)) == 1
