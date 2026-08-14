# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import EmbeddingORM, SegmentORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresIdentityResolutionRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:pipeline-revocation",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_revoking_a_delivery_removes_its_segments_and_embeddings(db_session):
    document, delivery = _setup(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    embedding_repo = PostgresEmbeddingRepository(db_session)

    segment = segment_repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    embedding_repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=[0.1] * 1024,
    )

    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_repo.revoke_delivery(delivery.id)

    remaining_segment = db_session.get(SegmentORM, segment.id)
    assert remaining_segment is None
    assert embedding_repo.get_embedding(segment.id, "model-a") is None


def test_revoking_a_delivery_rejects_its_pending_identity_case(db_session):
    document, delivery = _setup(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    case = identity_repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="???", raw_issuer=None,
        reason="unparseable_designation",
    )

    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_repo.revoke_delivery(delivery.id)

    assert case.id not in {c.id for c in identity_repo.list_pending_cases()}
