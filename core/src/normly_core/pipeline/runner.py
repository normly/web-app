# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresEmbeddingRepository,
    PostgresIdentityResolutionRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
)
from normly_core.pipeline import identity, references
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel


@dataclass
class RunSummary:
    records_processed: int = 0
    records_skipped: int = 0
    records_enqueued_for_review: int = 0
    documents_created: int = 0
    segments_created: int = 0
    embeddings_created: int = 0


def run_adapter(adapter: SourceAdapter, session: Session) -> RunSummary:
    delivery_repo = PostgresDeliveryRepository(session)
    document_repo = PostgresDocumentRepository(session)
    rights_repo = PostgresRightsRepository(session)
    edge_repo = PostgresEdgeRepository(session)
    segment_repo = PostgresSegmentRepository(session)
    embedding_repo = PostgresEmbeddingRepository(session)
    identity_repo = PostgresIdentityResolutionRepository(session)
    embedding_model: EmbeddingModel | None = None

    summary = RunSummary()

    for record in adapter.fetch():
        if delivery_repo.find_delivery(record.source_id, record.content_hash) is not None:
            summary.records_skipped += 1
            continue

        delivery = delivery_repo.record_delivery(
            source_id=record.source_id,
            content_hash=record.content_hash,
            ingested_at=datetime.now(timezone.utc),
        )
        summary.records_processed += 1

        result = identity.resolve(record, document_repo)
        if result.is_ambiguous:
            identity_repo.enqueue_case(
                delivery_id=delivery.id,
                raw_designation=record.raw_designation,
                raw_issuer=record.raw_issuer,
                reason=result.reason or "unknown",
            )
            summary.records_enqueued_for_review += 1
            continue

        if result.is_new:
            parsed = identity.parse_designation(record.raw_designation)
            document = document_repo.create_document(
                origin_issuer=record.raw_issuer or "unknown",
                origin_number=parsed.number,
                edition=parsed.edition or "",
                part=None,
                delivery_id=delivery.id,
            )
            summary.documents_created += 1
        else:
            document = document_repo.get_document_unchecked(result.document_id)

        if record.raw_issuer is not None:
            document_repo.add_designation(
                document_id=document.id,
                issuer=record.raw_issuer,
                designation=record.raw_designation,
                language="de",
                edition=None,
                is_primary=True,
                delivery_id=delivery.id,
            )
        if record.raw_title is not None:
            document_repo.add_title(
                document_id=document.id,
                language="de",
                title=record.raw_title,
                delivery_id=delivery.id,
            )

        rule = adapter.classify_rights(record)
        rights_repo.classify(
            document_id=document.id,
            jurisdiction=rule.jurisdiction,
            may_process=rule.may_process,
            may_index_fulltext=rule.may_index_fulltext,
            may_cite_passages=rule.may_cite_passages,
            may_export_free=rule.may_export_free,
            legal_basis_reference=rule.legal_basis_reference,
            classified_at=datetime.now(timezone.utc),
            classified_by="pipeline:automatic",
            delivery_id=delivery.id,
        )

        references.extract_references(
            record, document.id, delivery.id, document_repo, edge_repo, identity_repo
        )

        if record.full_text is not None and rule.may_index_fulltext:
            for section in adapter.extract_structure(record):
                segment = segment_repo.add_segment(
                    document_id=document.id,
                    delivery_id=delivery.id,
                    sequence_number=section.sequence_number,
                    heading=section.heading,
                    text=section.text,
                    language="de",
                )
                summary.segments_created += 1

                if embedding_model is None:
                    embedding_model = EmbeddingModel()
                vector = embedding_model.embed(segment.text)
                embedding_repo.add_embedding(
                    segment_id=segment.id,
                    delivery_id=delivery.id,
                    model_name=MODEL_NAME,
                    vector=vector,
                )
                summary.embeddings_created += 1

    return summary
