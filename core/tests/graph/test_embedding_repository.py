# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _make_segment(db_session, content_hash="sha256:embedding-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    return segment, delivery


def test_add_embedding_and_read_back(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    vector = [0.1] * 1024

    embedding, _ = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id,
        model_name="intfloat/multilingual-e5-large", vector=vector,
    )

    fetched = repo.get_embedding_unchecked(segment.id, "intfloat/multilingual-e5-large")
    assert fetched is not None
    assert fetched.id == embedding.id
    assert len(fetched.vector) == 1024


def test_add_embedding_is_idempotent_by_segment_and_model(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    vector = [0.2] * 1024

    first, first_created = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=vector,
    )
    second, second_created = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=vector,
    )

    assert first.id == second.id
    # The second call created nothing, and says so.
    assert first_created is True
    assert second_created is False


def test_embedding_is_removed_when_its_segment_is_deleted(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=[0.3] * 1024,
    )

    from normly_core.graph.postgres.orm import SegmentORM
    db_session.execute(
        sa.delete(SegmentORM).where(SegmentORM.id == segment.id)
    )
    db_session.flush()

    assert repo.get_embedding_unchecked(segment.id, "model-a") is None
