# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

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
    PostgresNotifiedEdgeRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def _make_delivery(db_session, content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_document(db_session, delivery_id, origin_number):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number=origin_number, edition="2026", part=None,
        delivery_id=delivery_id,
    )


def _make_edge(db_session, content_hash_suffix):
    delivery = _make_delivery(db_session, content_hash=f"sha256:notified-edge-{content_hash_suffix}")
    from_doc = _make_document(db_session, delivery.id, f"TST-NE-FROM-{content_hash_suffix}")
    to_doc = _make_document(db_session, delivery.id, f"TST-NE-TO-{content_hash_suffix}")
    return PostgresEdgeRepository(db_session).create_edge(
        from_document_id=from_doc.id, to_document_id=to_doc.id,
        edge_type=EdgeType.REFERENCES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )


def test_has_been_notified_is_false_before_mark_notified_and_true_after(db_session):
    account = _make_account(db_session, "notified-edge@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    edge_id = _make_edge(db_session, "before-after").id

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is False

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is True


def test_mark_notified_is_idempotent(db_session):
    account = _make_account(db_session, "notified-edge-idempotent@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    edge_id = _make_edge(db_session, "idempotent").id

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )
    # Calling it again for the same key must not raise (e.g. a duplicate-key
    # error) -- notify-watchers always checks has_been_notified first, but
    # the method itself should be safe to call twice.
    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is True


def test_has_been_notified_is_scoped_to_the_exact_key(db_session):
    account = _make_account(db_session, "notified-edge-scoped@example.de")
    other_account = _make_account(db_session, "notified-edge-other@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    edge_id = _make_edge(db_session, "scoped").id

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    # Different account, same edge/work/trigger_type -- not notified.
    assert repo.has_been_notified(
        account_id=other_account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is False
    # Same account/work/edge, different trigger_type -- not notified.
    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION, trigger_edge_id=edge_id,
    ) is False
