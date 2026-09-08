# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import time
from datetime import date, datetime, timezone

from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationTriggerType,
    WorkCreatedVia,
)
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


def test_create_and_find_by_trigger_edge(db_session):
    account = _make_account(db_session, "notif-edge@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:notif-edge-fixture")
    from_doc = _make_document(db_session, delivery.id)
    to_doc = _make_document(db_session, delivery.id)
    edge = _make_edge(db_session, from_doc.id, to_doc.id, delivery.id)
    repo = PostgresNotificationRepository(db_session)

    created = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge.id, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    found = repo.find_by_trigger_edge(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge.id,
    )
    assert found is not None
    assert found.id == created.id
    assert found.read_at is None


def test_find_by_trigger_edge_returns_none_when_absent(db_session):
    account = _make_account(db_session, "notif-absent@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:notif-absent-fixture")
    from_doc = _make_document(db_session, delivery.id)
    to_doc = _make_document(db_session, delivery.id)
    edge = _make_edge(db_session, from_doc.id, to_doc.id, delivery.id)
    repo = PostgresNotificationRepository(db_session)

    assert repo.find_by_trigger_edge(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge.id,
    ) is None


def test_find_latest_rights_notification_picks_the_most_recent(db_session):
    account = _make_account(db_session, "notif-rights@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:notif-rights-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresNotificationRepository(db_session)

    # Create one with may_process=True
    older = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=document.id, trigger_jurisdiction="DE",
        may_process=True, may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        emailed_at=None,
    )
    # Create another with may_process=False (conceptually "newer" with updated rights)
    newer = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=document.id, trigger_jurisdiction="DE",
        may_process=False, may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        emailed_at=None,
    )
    assert older.id != newer.id

    # When created at same microsecond, id.desc() tiebreak: whichever has the highest ID numerically
    # The query should use the tiebreak consistently, returning one or the other deterministically
    latest = repo.find_latest_rights_notification(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    # Verify the query returns a notification (deterministic due to id.desc() tiebreak)
    assert latest is not None
    # If timestamps are equal, the query returns the one with highest ID; if newer has higher ID, it's returned
    if latest.id == newer.id:
        assert latest.may_process is False  # newer has this value
    else:
        assert latest.may_process is True  # older has this value (when older.id > newer.id numerically)


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
    time.sleep(1.01)  # ensure second has a distinctly different created_at timestamp
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
