# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import NotificationORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def _make_delivery(db_session, content_hash="sha256:notification-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_document(db_session, delivery_id):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number="TST-001", edition="2026", part=None,
        delivery_id=delivery_id,
    )


def _make_edge(db_session, from_document_id, to_document_id, delivery_id):
    return PostgresEdgeRepository(db_session).create_edge(
        from_document_id=from_document_id, to_document_id=to_document_id,
        edge_type=EdgeType.REFERENCES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery_id,
    )


def test_list_for_account_orders_newest_first(db_session):
    account = _make_account(db_session, "notif-list@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:notif-list-fixture")
    repo = PostgresNotificationRepository(db_session)

    # Create edges for both notifications
    from_doc1 = _make_document(db_session, delivery.id)
    to_doc1 = _make_document(db_session, delivery.id)
    edge1 = _make_edge(db_session, from_doc1.id, to_doc1.id, delivery.id)

    from_doc2 = _make_document(db_session, delivery.id)
    to_doc2 = _make_document(db_session, delivery.id)
    edge2 = _make_edge(db_session, from_doc2.id, to_doc2.id, delivery.id)

    first = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge1.id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    # NotificationORM.created_at is server_default=sa.func.now(), and
    # Postgres's now() is transaction-scoped -- it returns the SAME value
    # for every statement inside one transaction, so a time.sleep() here
    # would not actually separate created_at values. Force `first`
    # explicitly older instead.
    db_session.execute(
        sa.update(NotificationORM)
        .where(NotificationORM.id == first.id)
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()
    second = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge2.id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    listed = repo.list_for_account(account.id)
    assert [n.id for n in listed] == [second.id, first.id]


def test_mark_read_only_succeeds_for_the_owning_account(db_session):
    owner = _make_account(db_session, "notif-owner@example.de")
    other = _make_account(db_session, "notif-other@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:notif-owner-fixture")
    from_doc = _make_document(db_session, delivery.id)
    to_doc = _make_document(db_session, delivery.id)
    edge = _make_edge(db_session, from_doc.id, to_doc.id, delivery.id)
    repo = PostgresNotificationRepository(db_session)

    notification = repo.create(
        account_id=owner.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge.id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    now = datetime.now(timezone.utc)

    assert repo.mark_read(notification.id, account_id=other.id, read_at=now) is False
    assert repo.mark_read(notification.id, account_id=owner.id, read_at=now) is True
    assert repo.list_for_account(owner.id)[0].read_at is not None


def test_delete_read_before_only_removes_read_notifications_older_than_cutoff(db_session):
    account = _make_account(db_session, "notif-cleanup@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    old_read = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    new_read = repo.create(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    old_unread = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )

    # created_at is server_default=func.now(), frozen for the whole
    # transaction -- backdate explicitly, same technique as
    # test_list_for_account_orders_newest_first above.
    db_session.execute(
        sa.update(NotificationORM)
        .where(NotificationORM.id.in_([old_read.id, old_unread.id]))
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()

    now = datetime.now(timezone.utc)
    repo.mark_read(old_read.id, account_id=account.id, read_at=now)
    repo.mark_read(new_read.id, account_id=account.id, read_at=now)
    # old_unread stays unread.

    deleted_count = repo.delete_read_before(datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert deleted_count == 1
    remaining_ids = {n.id for n in repo.list_for_account(account.id)}
    assert remaining_ids == {new_read.id, old_unread.id}


def test_delete_read_before_returns_the_number_of_rows_deleted(db_session):
    account = _make_account(db_session, "notif-cleanup-count@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    first = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    second = repo.create(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.execute(
        sa.update(NotificationORM)
        .where(NotificationORM.id.in_([first.id, second.id]))
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()
    now = datetime.now(timezone.utc)
    repo.mark_read(first.id, account_id=account.id, read_at=now)
    repo.mark_read(second.id, account_id=account.id, read_at=now)

    deleted_count = repo.delete_read_before(datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert deleted_count == 2
    assert repo.list_for_account(account.id) == []
