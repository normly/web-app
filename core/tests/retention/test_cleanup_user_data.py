# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from normly_core import retention
from normly_core.graph.domain import (
    AccountTokenPurpose,
    ChatMessageRole,
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import (
    AccountGoogleIdentityORM,
    AccountORM,
    AccountSessionORM,
    AccountTokenORM,
    ChatMessageCitationORM,
    ChatMessageORM,
    ChatSessionORM,
    NotificationORM,
    NotifiedEdgeORM,
    NotifiedRetirementORM,
    RightsNotificationBaselineORM,
    WatchlistORM,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
    PostgresChatRepository,
    PostgresDeletionLogRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresNotifiedRetirementRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)
from normly_core.pipeline.cli import main

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
EPS = timedelta(seconds=1)


def _count(session, orm) -> int:
    return session.execute(sa.select(sa.func.count()).select_from(orm)).scalar_one()


def _log(session):
    return {
        (kind, entity)
        for kind, entity, _ in PostgresDeletionLogRepository(session).entries_since(
            NOW - timedelta(days=1)
        )
    }


def _account(session, email, *, created_at=None, verified=False):
    account = PostgresAccountRepository(session).create_account(email=email, password_hash=None)
    values = {}
    if created_at is not None:
        values["created_at"] = created_at
    if verified:
        values["email_verified_at"] = NOW
    if values:
        session.execute(
            sa.update(AccountORM).where(AccountORM.id == account.id).values(**values)
        )
    return account


# --- sessions ---------------------------------------------------------------

def test_delete_sessions_expired_before_only_removes_old_ones(db_session):
    account = _account(db_session, "s@example.de")
    repo = PostgresAccountSessionRepository(db_session)
    cutoff = NOW - retention.ACCOUNT_SESSION_GRACE
    for name, expires in (("old", cutoff - EPS), ("edge", cutoff), ("new", cutoff + EPS)):
        repo.create_session(
            account_id=account.id, session_token=name, created_at=cutoff - timedelta(days=30),
            expires_at=expires,
        )

    assert repo.delete_sessions_expired_before(cutoff) == 1
    assert repo.delete_sessions_expired_before(cutoff) == 0
    assert {s.session_token for s in repo.list_sessions_for_account(account.id)} == {
        "edge", "new",
    }


# --- tokens -----------------------------------------------------------------

def test_delete_tokens_done_before_uses_expiry_or_use(db_session):
    account = _account(db_session, "t@example.de")
    repo = PostgresAccountTokenRepository(db_session)
    cutoff = NOW - retention.ACCOUNT_TOKEN_GRACE
    created = cutoff - timedelta(days=5)
    future = NOW + timedelta(days=1)

    def make(name, expires_at, used_at=None):
        repo.create_token(
            account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET, token=name,
            created_at=created, expires_at=expires_at,
        )
        if used_at is not None:
            db_session.execute(
                sa.update(AccountTokenORM)
                .where(AccountTokenORM.token == name).values(used_at=used_at)
            )

    make("expired-old", cutoff - EPS)
    make("expired-new", cutoff + EPS)
    make("expired-edge", cutoff)
    make("used-old", future, used_at=cutoff - EPS)
    make("used-new", future, used_at=cutoff + EPS)
    make("unused-valid", future)

    assert repo.delete_tokens_done_before(cutoff) == 2
    assert repo.delete_tokens_done_before(cutoff) == 0
    left = set(db_session.execute(sa.select(AccountTokenORM.token)).scalars())
    assert left == {"expired-new", "expired-edge", "used-new", "unused-valid"}


# --- notifications ----------------------------------------------------------

def _notification(session, account, work, created_at, *, read):
    repo = PostgresNotificationRepository(session)
    row = repo.create(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None,
        may_export_free=None, emailed_at=None,
    )
    session.execute(
        sa.update(NotificationORM).where(NotificationORM.id == row.id).values(
            created_at=created_at, read_at=NOW if read else None,
        )
    )
    return row.id


def test_delete_unread_before_only_touches_old_unread(db_session):
    account = _account(db_session, "n@example.de")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    cutoff = NOW - retention.UNREAD_NOTIFICATION_MAX_AGE
    old_unread = _notification(db_session, account, work, cutoff - EPS, read=False)
    edge_unread = _notification(db_session, account, work, cutoff, read=False)
    new_unread = _notification(db_session, account, work, cutoff + EPS, read=False)
    old_read = _notification(db_session, account, work, cutoff - EPS, read=True)
    repo = PostgresNotificationRepository(db_session)

    assert repo.delete_unread_before(cutoff) == 1
    assert repo.delete_unread_before(cutoff) == 0
    left = set(db_session.execute(sa.select(NotificationORM.id)).scalars())
    assert left == {edge_unread, new_unread, old_read}
    assert old_unread not in left


# --- abandoned registrations ------------------------------------------------

def test_delete_unverified_accounts_boundaries_and_log(db_session):
    cutoff = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE
    old = _account(db_session, "old@example.de", created_at=cutoff - EPS)
    edge = _account(db_session, "edge@example.de", created_at=cutoff)
    new = _account(db_session, "new@example.de", created_at=cutoff + EPS)
    verified = _account(
        db_session, "verified@example.de", created_at=cutoff - timedelta(days=100),
        verified=True,
    )
    repo = PostgresAccountRepository(db_session)

    assert repo.delete_unverified_accounts_created_before(cutoff) == 1
    assert repo.delete_unverified_accounts_created_before(cutoff) == 0
    left = set(db_session.execute(sa.select(AccountORM.id)).scalars())
    assert left == {edge.id, new.id, verified.id}
    assert _log(db_session) == {("account", old.id)}


def test_accounts_in_use_are_not_abandoned(db_session):
    cutoff = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE
    long_ago = cutoff - timedelta(days=100)
    google = _account(db_session, "google@example.de", created_at=long_ago)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=google.id, google_subject_id="subject-1",
    )
    # An expired session row still marks the account as recently used: sessions
    # are removed 7 days after expiry, so a surviving row means recent use.
    session_account = _account(db_session, "sess@example.de", created_at=long_ago)
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=session_account.id, session_token="in-use", created_at=long_ago,
        expires_at=cutoff - timedelta(days=1),
    )
    abandoned = _account(db_session, "abandoned@example.de", created_at=long_ago)

    assert PostgresAccountRepository(
        db_session
    ).delete_unverified_accounts_created_before(cutoff) == 1

    left = set(db_session.execute(sa.select(AccountORM.id)).scalars())
    assert left == {google.id, session_account.id}
    assert _log(db_session) == {("account", abandoned.id)}


def test_recheck_skips_an_account_verified_after_selection(db_session):
    cutoff = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE
    account = _account(db_session, "race@example.de", created_at=cutoff - timedelta(days=1))
    repo = PostgresAccountRepository(db_session)

    selected = repo._abandoned_registration_ids(cutoff, lock=True)
    assert selected == [account.id]
    repo.mark_email_verified(account.id, NOW)

    assert repo._abandoned_registration_ids(cutoff, only=selected) == []


def test_delete_unverified_accounts_cascades(db_session):
    cutoff = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE
    account = _account(db_session, "cascade@example.de", created_at=cutoff - EPS)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    _notification(db_session, account, work, NOW, read=False)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token="ct", created_at=NOW, expires_at=NOW + timedelta(days=1),
    )
    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:unverified-cascade", ingested_at=NOW,
    )
    documents = PostgresDocumentRepository(db_session)
    document = documents.create_document(
        origin_issuer="Test", origin_number="TST-1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    other = documents.create_document(
        origin_issuer="Test", origin_number="TST-2", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=other.id, to_document_id=document.id,
        edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )
    PostgresRightsNotificationBaselineRepository(db_session).upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )
    PostgresNotifiedEdgeRepository(db_session).mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge.id,
    )
    PostgresNotifiedRetirementRepository(db_session).mark_notified(
        account_id=account.id, work_id=work.id, document_id=document.id, retired_at=NOW,
    )
    chat = PostgresChatRepository(db_session)
    session = chat.create_session(
        session_token="cc", jurisdiction="DE", language="de", created_at=NOW,
        account_id=account.id,
    )
    message = chat.create_message(
        session_id=session.id, role=ChatMessageRole.USER, content="Hi", answer_type=None,
        created_at=NOW,
    )
    _cite(db_session, message.id)
    db_session.flush()

    assert PostgresAccountRepository(db_session).delete_unverified_accounts_created_before(
        cutoff
    ) == 1

    for orm in (
        AccountORM, AccountTokenORM, NotificationORM, WatchlistORM,
        RightsNotificationBaselineORM, NotifiedEdgeORM, NotifiedRetirementORM, ChatSessionORM,
        ChatMessageORM, ChatMessageCitationORM,
    ):
        assert _count(db_session, orm) == 0, orm.__name__
    assert _log(db_session) == {("account", account.id)}


# --- delete_account -------------------------------------------------------

def test_delete_account_writes_one_account_entry_and_no_chat_entries(db_session):
    account = _account(db_session, "del@example.de")
    chat = PostgresChatRepository(db_session)
    chat.create_session(
        session_token="da", jurisdiction="DE", language="de", created_at=NOW,
        account_id=account.id,
    )

    PostgresAccountRepository(db_session).delete_account(account.id)

    assert _log(db_session) == {("account", account.id)}


# --- chats ------------------------------------------------------------------

def _chat_with_content(chat, token, account_id):
    session = chat.create_session(
        session_token=token, jurisdiction="DE", language="de", created_at=NOW,
        account_id=account_id,
    )
    message = chat.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="A",
        answer_type=None, created_at=NOW,
    )
    return session, message


def _cite(session, message_id):
    source = PostgresSourceRepository(session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/x",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(session).record_delivery(
        source_id=source.id, content_hash=f"sha256:{uuid.uuid4()}", ingested_at=NOW,
    )
    document = PostgresDocumentRepository(session).create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    PostgresChatRepository(session).add_citation(
        message_id=message_id, document_id=document.id, segment_id=None,
    )


def test_delete_anonymous_chat_sessions_removes_only_anonymous(db_session):
    account = _account(db_session, "chatowner@example.de")
    chat = PostgresChatRepository(db_session)
    anon_a, anon_message = _chat_with_content(chat, "anon-a", None)
    _cite(db_session, anon_message.id)
    anon_b, _ = _chat_with_content(chat, "anon-b", None)
    owned, _ = _chat_with_content(chat, "owned", account.id)

    assert chat.delete_anonymous_chat_sessions() == 2
    assert chat.delete_anonymous_chat_sessions() == 0

    assert set(db_session.execute(sa.select(ChatSessionORM.id)).scalars()) == {owned.id}
    assert _count(db_session, ChatMessageORM) == 1
    assert _count(db_session, ChatMessageCitationORM) == 0
    assert _log(db_session) == {("chat_session", anon_a.id), ("chat_session", anon_b.id)}


def test_delete_chat_session_only_own(db_session):
    mine = _account(db_session, "mine@example.de")
    theirs = _account(db_session, "theirs@example.de")
    chat = PostgresChatRepository(db_session)
    my_session, my_message = _chat_with_content(chat, "m", mine.id)
    _cite(db_session, my_message.id)
    their_session, _ = _chat_with_content(chat, "t", theirs.id)

    assert chat.delete_chat_session(their_session.id, mine.id) is False
    assert chat.delete_chat_session(uuid.uuid4(), mine.id) is False
    assert _count(db_session, ChatSessionORM) == 2
    assert _log(db_session) == set()

    assert chat.delete_chat_session(my_session.id, mine.id) is True
    assert set(db_session.execute(sa.select(ChatSessionORM.id)).scalars()) == {their_session.id}
    assert _count(db_session, ChatMessageORM) == 1
    assert _count(db_session, ChatMessageCitationORM) == 0
    assert _log(db_session) == {("chat_session", my_session.id)}


def test_delete_chat_sessions_for_account(db_session):
    mine = _account(db_session, "mine2@example.de")
    theirs = _account(db_session, "theirs2@example.de")
    chat = PostgresChatRepository(db_session)
    a, _ = _chat_with_content(chat, "a", mine.id)
    b, _ = _chat_with_content(chat, "b", mine.id)
    other, _ = _chat_with_content(chat, "o", theirs.id)

    assert chat.delete_chat_sessions_for_account(mine.id) == 2
    assert chat.delete_chat_sessions_for_account(mine.id) == 0

    assert set(db_session.execute(sa.select(ChatSessionORM.id)).scalars()) == {other.id}
    assert _log(db_session) == {("chat_session", a.id), ("chat_session", b.id)}


# --- CLI --------------------------------------------------------------------

@pytest.fixture()
def committed_db(migrated_engine, db_url, monkeypatch):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    try:
        yield migrated_engine
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(sa.text(
                "TRUNCATE deletion_log, chat_message_citation, chat_message, chat_session, "
                "notification, account_token, account_session, account, work CASCADE"
            ))


def test_cleanup_user_data_command_runs_all_periods_and_commits(committed_db, capsys):
    now = datetime.now(timezone.utc)
    with Session(committed_db) as session:
        account = _account(
            session, "cli-keep@example.de", created_at=now, verified=True,
        )
        _account(
            session, "cli-unverified@example.de",
            created_at=now - retention.UNVERIFIED_ACCOUNT_MAX_AGE - timedelta(days=1),
        )
        PostgresAccountSessionRepository(session).create_session(
            account_id=account.id, session_token="cli-s",
            created_at=now - timedelta(days=60),
            expires_at=now - retention.ACCOUNT_SESSION_GRACE - timedelta(days=1),
        )
        PostgresAccountTokenRepository(session).create_token(
            account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET, token="cli-t",
            created_at=now - timedelta(days=3),
            expires_at=now - retention.ACCOUNT_TOKEN_GRACE - timedelta(hours=1),
        )
        work = PostgresWorkRepository(session).create_work(created_via=WorkCreatedVia.MANUAL)
        _notification(
            session, account, work,
            now - retention.READ_NOTIFICATION_MAX_AGE - timedelta(days=1), read=True,
        )
        _notification(
            session, account, work,
            now - retention.UNREAD_NOTIFICATION_MAX_AGE - timedelta(days=1), read=False,
        )
        chat = PostgresChatRepository(session)
        chat.create_session(
            session_token="cli-anon", jurisdiction="DE", language="de", created_at=now,
        )
        chat.create_session(
            session_token="cli-own", jurisdiction="DE", language="de", created_at=now,
            account_id=account.id,
        )
        PostgresDeletionLogRepository(session).record(
            kind="account", entity_id=uuid.uuid4(),
            deleted_at=now - retention.DELETION_LOG_MAX_AGE - timedelta(days=1),
        )
        session.commit()

    assert main(["cleanup-user-data"]) == 0

    out = capsys.readouterr().out
    assert (
        "sessions=1 tokens=1 unverified_accounts=1 notifications_read=1 "
        "notifications_unread=1 anonymous_chats=1 deletion_log=1"
    ) in out
    with Session(committed_db) as session:
        assert _count(session, AccountORM) == 1
        assert _count(session, ChatSessionORM) == 1
        assert _count(session, NotificationORM) == 0
        kinds = [k for k, _, _ in PostgresDeletionLogRepository(session).entries_since(
            now - timedelta(days=1)
        )]
        assert sorted(kinds) == ["account", "chat_session"]

    assert main(["cleanup-user-data"]) == 0
    assert (
        "sessions=0 tokens=0 unverified_accounts=0 notifications_read=0 "
        "notifications_unread=0 anonymous_chats=0 deletion_log=0"
    ) in capsys.readouterr().out
