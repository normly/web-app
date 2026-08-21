# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)

_MODEL = "intfloat/multilingual-e5-large"


def _make_classified_document(db_session, *, jurisdiction, may_process, may_index_fulltext):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/similarity",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=f"sha256:similarity-{jurisdiction}-{may_process}",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=may_process,
        may_index_fulltext=may_index_fulltext, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="Test", delivery_id=delivery.id,
    )
    return document, delivery


def _add_segment_with_embedding(db_session, document, delivery, *, text, vector):
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading=None, text=text, language="de",
    )
    PostgresEmbeddingRepository(db_session).add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name=_MODEL, vector=vector,
    )
    return segment


def test_finds_the_closest_segment_first(db_session):
    document, delivery = _make_classified_document(
        db_session, jurisdiction="DE", may_process=True, may_index_fulltext=True,
    )
    close = _add_segment_with_embedding(
        db_session, document, delivery, text="nah", vector=[1.0] + [0.0] * 1023,
    )
    _add_segment_with_embedding(
        db_session, document, delivery, text="fern", vector=[0.0, 1.0] + [0.0] * 1022,
    )

    repo = PostgresSegmentRepository(db_session)
    results = repo.find_similar_segments_for_jurisdiction(
        [1.0] + [0.0] * 1023, "DE", _MODEL, limit=1,
    )
    assert [s.id for s in results] == [close.id]


def test_respects_the_rights_gate(db_session):
    document, delivery = _make_classified_document(
        db_session, jurisdiction="DE", may_process=True, may_index_fulltext=False,
    )
    _add_segment_with_embedding(
        db_session, document, delivery, text="nicht indexiert", vector=[1.0] + [0.0] * 1023,
    )

    repo = PostgresSegmentRepository(db_session)
    results = repo.find_similar_segments_for_jurisdiction([1.0] + [0.0] * 1023, "DE", _MODEL)
    assert results == []


def test_filters_by_model_name(db_session):
    document, delivery = _make_classified_document(
        db_session, jurisdiction="DE", may_process=True, may_index_fulltext=True,
    )
    _add_segment_with_embedding(
        db_session, document, delivery, text="anderes modell", vector=[1.0] + [0.0] * 1023,
    )

    repo = PostgresSegmentRepository(db_session)
    results = repo.find_similar_segments_for_jurisdiction(
        [1.0] + [0.0] * 1023, "DE", "a-different-model",
    )
    assert results == []
