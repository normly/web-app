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
        responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def _make_source(db_session, *, jurisdiction="DE"):
    return PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction=jurisdiction,
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )


def test_add_segment_and_read_back(db_session):
    document, delivery = _make_document(db_session)
    repo = PostgresSegmentRepository(db_session)

    segment, _ = repo.add_segment(
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

    first, first_created = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    second, second_created = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )

    assert first.id == second.id
    # The second call created nothing, and says so.
    assert first_created is True
    assert second_created is False


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

    first, first_created = repo.add_segment(
        document_id=document.id, delivery_id=first_delivery.id, sequence_number=1,
        heading="§ 3", text="Fassung 2024", language="de",
    )
    second, second_created = repo.add_segment(
        document_id=document.id, delivery_id=second_delivery.id, sequence_number=1,
        heading="§ 3", text="Fassung 2026", language="de",
    )

    assert first.id != second.id
    assert first_created is True
    assert second_created is True
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
        classified_by="Test Reviewer", delivery_id=delivery.id,
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
        classified_by="Test Reviewer", delivery_id=delivery.id,
    )
    assert len(segment_repo.list_segments_for_jurisdiction(document.id, "DE")) == 1

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=False,
        may_cite_passages=False, may_export_free=True, legal_basis_reference="Lizenz widerrufen",
        classified_at=datetime.now(timezone.utc),
        classified_by="Test Reviewer", delivery_id=delivery.id,
    )

    assert segment_repo.list_segments_for_jurisdiction(document.id, "DE") == []


def _seeded_document(db_session, *, content_hash, may_cite_passages, may_index_fulltext=True):
    source = _make_source(db_session, jurisdiction="DE")
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=content_hash, edition="2020", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction="DE", may_process=True,
        may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
        may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="test",
        delivery_id=delivery.id,
    )
    repo = PostgresSegmentRepository(db_session)
    second, _ = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=2,
        heading="§ 2 Pflichten", text="Zweiter Text", language="de",
    )
    first, _ = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 1 Geltungsbereich", text="Erster Text", language="de",
    )
    return document, delivery, first, second


def test_citable_segments_are_listed_in_sequence_order(db_session):
    document, _, first, second = _seeded_document(
        db_session, content_hash="sha256:citable-1", may_cite_passages=True,
    )

    segments = PostgresSegmentRepository(db_session).list_citable_segments_for_jurisdiction(
        document.id, "DE",
    )

    assert [s.id for s in segments] == [first.id, second.id]


def test_indexable_but_not_citable_segments_are_not_listed(db_session):
    document, _, _, _ = _seeded_document(
        db_session, content_hash="sha256:citable-2", may_cite_passages=False,
    )

    repo = PostgresSegmentRepository(db_session)
    assert repo.list_citable_segments_for_jurisdiction(document.id, "DE") == []
    assert len(repo.list_segments_for_jurisdiction(document.id, "DE")) == 2


def test_citable_segments_respect_jurisdiction_and_revocation(db_session):
    document, delivery, _, _ = _seeded_document(
        db_session, content_hash="sha256:citable-3", may_cite_passages=True,
    )
    repo = PostgresSegmentRepository(db_session)
    assert repo.list_citable_segments_for_jurisdiction(document.id, "AT") == []

    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    assert repo.list_citable_segments_for_jurisdiction(document.id, "DE") == []


def test_segment_headings_are_returned_for_visible_segments_only(db_session):
    visible_doc, _, first, second = _seeded_document(
        db_session, content_hash="sha256:headings-1", may_cite_passages=False,
    )
    hidden_doc, _, hidden, _ = _seeded_document(
        db_session, content_hash="sha256:headings-2", may_cite_passages=True,
        may_index_fulltext=False,
    )

    headings = PostgresSegmentRepository(db_session).list_segment_headings_for_jurisdiction(
        [first.id, second.id, hidden.id], "DE",
    )

    assert headings == {first.id: "§ 1 Geltungsbereich", second.id: "§ 2 Pflichten"}
    assert PostgresSegmentRepository(db_session).list_segment_headings_for_jurisdiction(
        [], "DE",
    ) == {}
