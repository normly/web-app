# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _make_document(db_session, content_hash="sha256:segment-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_add_segment_and_read_back(db_session):
    document, delivery = _make_document(db_session)
    repo = PostgresSegmentRepository(db_session)

    segment = repo.add_segment(
        document_id=document.id,
        delivery_id=delivery.id,
        sequence_number=1,
        heading="§ 3 Grundpflichten",
        text="Der Unternehmer hat dafür zu sorgen, dass...",
        language="de",
    )

    assert segment.document_id == document.id
    assert segment.sequence_number == 1


def test_add_segment_is_idempotent_by_document_and_sequence(db_session):
    document, delivery = _make_document(db_session)
    repo = PostgresSegmentRepository(db_session)

    first = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    second = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )

    assert first.id == second.id


def test_a_second_delivery_gets_its_own_segment_row(db_session):
    """
    Idempotency is per delivery, not per document.

    An amended text re-ingested as a second delivery must store its own
    segments. Sharing the first delivery's row would hand back stale text under
    a new delivery's lineage — and revoking the first delivery would delete a
    segment the second one believes it owns.
    """
    document, first_delivery = _make_document(db_session, "sha256:segment-delivery-one")
    second_delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=PostgresSourceRepository(db_session)
        .find_by_publisher("DGUV")
        .id,
        content_hash="sha256:segment-delivery-two",
        ingested_at=datetime.now(timezone.utc),
    )
    repo = PostgresSegmentRepository(db_session)

    first = repo.add_segment(
        document_id=document.id, delivery_id=first_delivery.id, sequence_number=1,
        heading="§ 3", text="Fassung 2024", language="de",
    )
    second = repo.add_segment(
        document_id=document.id, delivery_id=second_delivery.id, sequence_number=1,
        heading="§ 3", text="Fassung 2026", language="de",
    )

    assert first.id != second.id
    assert first.text == "Fassung 2024"
    assert second.text == "Fassung 2026"
    assert second.delivery_id == second_delivery.id


def test_segments_are_gated_by_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    segment_repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )

    assert segment_repo.list_segments_for_jurisdiction(document.id, "DE") == []

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber", delivery_id=delivery.id,
    )

    segments = segment_repo.list_segments_for_jurisdiction(document.id, "DE")
    assert len(segments) == 1
    assert segments[0].text == "Text A"


def test_segments_stop_being_readable_when_fulltext_indexing_is_withdrawn(db_session):
    """
    The read gate asks the question the write gate asked.

    Segments are only ever written when `may_index_fulltext` is true. Because
    classification is updated in place, a later tightening has to take the
    already-written segments out of reach as well.
    """
    document, delivery = _make_document(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    segment_repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber", delivery_id=delivery.id,
    )
    assert len(segment_repo.list_segments_for_jurisdiction(document.id, "DE")) == 1

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=False,
        may_cite_passages=False, may_export_free=True, legal_basis_reference="Lizenz widerrufen",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber", delivery_id=delivery.id,
    )

    assert segment_repo.list_segments_for_jurisdiction(document.id, "DE") == []
