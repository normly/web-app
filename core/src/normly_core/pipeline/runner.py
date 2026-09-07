# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.domain import Delivery
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresEmbeddingRepository,
    PostgresIdentityResolutionRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
)
from normly_core.pipeline import identity, references, work_assignment
from normly_core.pipeline.domain import RawRecord, SourceAdapter
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel


@dataclass
class RunSummary:
    records_processed: int = 0
    records_skipped: int = 0
    records_enqueued_for_review: int = 0
    records_failed: int = 0
    documents_created: int = 0
    segments_created: int = 0
    embeddings_created: int = 0


def _absorb(summary: RunSummary, delta: RunSummary) -> None:
    """Fold a finished record's counts into the run's."""
    summary.records_enqueued_for_review += delta.records_enqueued_for_review
    summary.documents_created += delta.documents_created
    summary.segments_created += delta.segments_created
    summary.embeddings_created += delta.embeddings_created


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

    def process(record: RawRecord, delivery: Delivery) -> RunSummary:
        """Process one record. Counts what it wrote; writes what it counts."""
        nonlocal embedding_model
        delta = RunSummary()

        # The rights gate comes first, before any artifact exists. An
        # unclassifiable record and one that must not be processed are treated
        # alike: nothing is written, the record goes to review.
        rule = adapter.classify_rights(record)
        if rule is None or not rule.may_process:
            identity_repo.enqueue_case(
                delivery_id=delivery.id,
                raw_designation=record.raw_designation,
                raw_issuer=record.raw_issuer,
                reason=(
                    "cannot_classify_rights" if rule is None else "processing_not_permitted"
                ),
            )
            delta.records_enqueued_for_review += 1
            return delta

        language = record.language or "de"

        result = identity.resolve(record, document_repo)
        if result.is_ambiguous:
            identity_repo.enqueue_case(
                delivery_id=delivery.id,
                raw_designation=record.raw_designation,
                raw_issuer=record.raw_issuer,
                reason=result.reason or "unknown",
            )
            delta.records_enqueued_for_review += 1
            return delta

        if result.is_new:
            parsed = identity.parse_designation(record.raw_designation)
            assignment = work_assignment.determine_work_assignment(record, document_repo)
            if assignment.is_ambiguous:
                identity_repo.enqueue_case(
                    delivery_id=delivery.id,
                    raw_designation=record.raw_designation,
                    raw_issuer=record.raw_issuer,
                    reason=assignment.reason,
                )
                delta.records_enqueued_for_review += 1
                return delta
            document = document_repo.create_document(
                origin_issuer=record.raw_issuer or "unknown",
                origin_number=parsed.number,
                edition=parsed.edition or "",
                part=None,
                delivery_id=delivery.id,
                work_id=assignment.work_id,
            )
            delta.documents_created += 1
        else:
            document = document_repo.get_document_unchecked(result.document_id)

        if record.raw_issuer is not None:
            document_repo.add_designation(
                document_id=document.id,
                issuer=record.raw_issuer,
                designation=record.raw_designation,
                language=language,
                edition=None,
                is_primary=True,
                delivery_id=delivery.id,
            )
        if record.raw_title is not None:
            document_repo.add_title(
                document_id=document.id,
                language=language,
                title=record.raw_title,
                delivery_id=delivery.id,
            )

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
            record, document.id, delivery.id, document_repo, edge_repo, identity_repo, rule
        )

        if record.full_text is not None and rule.may_index_fulltext:
            for section in adapter.extract_structure(record):
                segment, segment_created = segment_repo.add_segment(
                    document_id=document.id,
                    delivery_id=delivery.id,
                    sequence_number=section.sequence_number,
                    heading=section.heading,
                    text=section.text,
                    language=language,
                )
                if segment_created:
                    delta.segments_created += 1

                if embedding_model is None:
                    embedding_model = EmbeddingModel()
                vector = embedding_model.embed(segment.text)
                _, embedding_created = embedding_repo.add_embedding(
                    segment_id=segment.id,
                    delivery_id=delivery.id,
                    model_name=MODEL_NAME,
                    vector=vector,
                )
                if embedding_created:
                    delta.embeddings_created += 1

        return delta

    # Anything an adapter raises while producing the next record happens here,
    # in this loop's own `next()` call, not inside the guard below -- and a
    # generator that raised cannot be resumed, so this loop could not carry on
    # even if it caught it. Per-source isolation therefore belongs to the
    # adapters, which skip a file they cannot read and keep yielding (see
    # docling_extraction.report_skipped_source). What reaches this line is what
    # an adapter could not handle at all, and it ends the run -- notably a
    # PipelineInitializationError, which is a misconfigured deployment rather
    # than one bad file and would fail the same way for every remaining source.
    # It is deliberately left uncaught all the way out to the process: main()
    # never reaches its commit or its summary line, and the operator gets a
    # traceback naming the bad artifacts_path and a non-zero exit code instead
    # of a success line over zero records.
    for record in adapter.fetch():
        if delivery_repo.find_delivery(record.source_id, record.content_hash) is not None:
            summary.records_skipped += 1
            continue

        summary.records_processed += 1

        # One bad record must block only itself. The savepoint takes the
        # record's partial writes back without discarding the run, and the
        # delta is only absorbed once the record is through — so the summary
        # never counts artifacts that were rolled back. The delivery row
        # itself is recorded inside this same savepoint: if anything about
        # this record fails, the delivery must roll back with it, or
        # find_delivery() would find it on the next run and skip a record
        # that was never actually processed — permanently losing it.
        try:
            with session.begin_nested():
                delivery = delivery_repo.record_delivery(
                    source_id=record.source_id,
                    content_hash=record.content_hash,
                    ingested_at=datetime.now(timezone.utc),
                )
                delta = process(record, delivery)
        except Exception as error:  # noqa: BLE001 — isolation is the point
            print(
                f"record {record.raw_designation!r} failed: {error!r}",
                file=sys.stderr,
            )
            summary.records_failed += 1
            continue

        _absorb(summary, delta)

    return summary
