# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.domain import (
    AccountTokenPurpose,
    ChatMessageRole,
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import ChatMessageORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
    PostgresChatRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotifiedEdgeRepository,
    PostgresNotifiedRetirementRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresSourceRepository,
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

    # rights_notification_baseline is the third account-referencing table
    # notify-watchers writes into, and it is created on the very first
    # observation of any watched Work -- so an account that ever watched
    # something will have one. Its FK to account declares no ON DELETE, so a
    # delete_account that forgets it fails with an IntegrityError.
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
        responsible_person="Test User",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:delete-account-baseline",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number="TST-DEL", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    other_document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number="TST-DEL-2", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=other_document.id, to_document_id=document.id,
        edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )
    PostgresRightsNotificationBaselineRepository(db_session).upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )

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

    # notified_edge is the fourth account-referencing bookkeeping table, and
    # the same class of bug applies: its FK to account also declares no ON
    # DELETE, so a delete_account that forgets it fails with an
    # IntegrityError too.
    PostgresNotifiedEdgeRepository(db_session).mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge.id,
    )
    db_session.flush()

    # notified_retirement is the fifth such table, with the same FK to account.
    PostgresNotifiedRetirementRepository(db_session).mark_notified(
        account_id=account.id, work_id=work.id, document_id=document.id,
        retired_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db_session.flush()

    account_repo.delete_account(account.id)

    assert account_repo.get_account_by_id(account.id) is None
    remaining = db_session.execute(
        sa.text("SELECT count(*) FROM notified_retirement WHERE account_id = :a"),
        {"a": account.id},
    ).scalar_one()
    assert remaining == 0


def test_delete_account_does_not_touch_another_accounts_data(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    victim = account_repo.create_account(email="stays@example.de", password_hash=None)
    to_delete = account_repo.create_account(email="goes@example.de", password_hash=None)
    _seed_account_session(session_repo, victim.id)

    account_repo.delete_account(to_delete.id)

    assert account_repo.get_account_by_id(victim.id) is not None
    assert len(session_repo.list_sessions_for_account(victim.id)) == 1
