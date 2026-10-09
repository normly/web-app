# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import (
    EdgeType,
    LegalBasisCategory,
    Layer,
    WithdrawnDeliveryError,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _setup(db_session, content_hash="sha256:guard-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash=content_hash,
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return delivery, first, second


def _write_calls(db_session, first, second):
    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    return {
        "create_document": lambda delivery_id: doc_repo.create_document(
            origin_issuer="DGUV", origin_number="3", edition="2026", part=None,
            delivery_id=delivery_id,
        ),
        "add_designation": lambda delivery_id: doc_repo.add_designation(
            document_id=first.id, issuer="DGUV", designation="DGUV Regel 1",
            language="de", edition=None, is_primary=True, delivery_id=delivery_id,
        ),
        "add_title": lambda delivery_id: doc_repo.add_title(
            document_id=first.id, language="de", title="DGUV Regel 1",
            delivery_id=delivery_id,
        ),
        "create_edge": lambda delivery_id: edge_repo.create_edge(
            from_document_id=first.id, to_document_id=second.id,
            edge_type=EdgeType.REFERENCES, jurisdiction=None, layer=Layer.FREE,
            delivery_id=delivery_id,
        ),
        "classify": lambda delivery_id: rights_repo.classify(
            document_id=first.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="Test Reviewer", delivery_id=delivery_id,
        ),
    }


WRITE_METHODS = (
    "create_document",
    "add_designation",
    "add_title",
    "create_edge",
    "classify",
)


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_on_a_withdrawn_delivery_is_refused(db_session, method):
    delivery, first, second = _setup(db_session, f"sha256:guard-withdrawn-{method}")
    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    with pytest.raises(WithdrawnDeliveryError) as raised:
        _write_calls(db_session, first, second)[method](delivery.id)

    assert raised.value.delivery_id == delivery.id


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_on_an_unknown_delivery_is_refused(db_session, method):
    _delivery, first, second = _setup(db_session, f"sha256:guard-unknown-{method}")
    unknown = uuid.uuid4()

    with pytest.raises(WithdrawnDeliveryError):
        _write_calls(db_session, first, second)[method](unknown)


def test_reingesting_a_withdrawn_delivery_cannot_resurrect_a_revoked_classification(
    db_session,
):
    """
    The exploit this guard exists for:

    1. delivery A classifies the document as readable in DE
    2. the publisher withdraws A — the classification is revoked, the document
       becomes unreadable
    3. the pipeline re-runs for A, as the idempotency rule allows
    4. classify() merges revoked_at=None over the revoked row
    5. the document is readable again, silently

    Step 3 must fail instead.
    """
    delivery, document, _second = _setup(db_session, "sha256:guard-resurrection")
    doc_repo = PostgresDocumentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)

    def classify():
        rights_repo.classify(
            document_id=document.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="Test Reviewer", delivery_id=delivery.id,
        )

    classify()
    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is not None

    delivery_repo.revoke_delivery(delivery.id)
    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None

    with pytest.raises(WithdrawnDeliveryError):
        classify()

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    assert rights_repo.get_classification(document.id, "DE").revoked_at is not None


def test_revoke_delivery_stays_callable_on_a_withdrawn_delivery(db_session):
    """The guard must not be on the revoker itself — revocation is idempotent."""
    delivery, _first, _second = _setup(db_session, "sha256:guard-revoke-twice")
    delivery_repo = PostgresDeliveryRepository(db_session)

    delivery_repo.revoke_delivery(delivery.id)
    delivery_repo.revoke_delivery(delivery.id)

    assert delivery_repo.get_delivery(delivery.id).withdrawn_at is not None


def test_record_delivery_stays_callable_for_a_withdrawn_delivery(db_session):
    """record_delivery creates deliveries; it cannot require an active one."""
    delivery, _first, _second = _setup(db_session, "sha256:guard-record-again")
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_repo.revoke_delivery(delivery.id)

    again = delivery_repo.record_delivery(
        source_id=delivery.source_id,
        content_hash=delivery.content_hash,
        ingested_at=datetime.now(timezone.utc),
    )

    assert again.id == delivery.id
    assert again.withdrawn_at is not None
