# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.orm import (
    DocumentDesignationORM,
    DocumentTitleORM,
    EdgeORM,
    EmbeddingORM,
    RightsClassificationORM,
    SegmentORM,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference, RawSection, RightsRule
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records, sections_by_designation=None, may_index_fulltext: bool = True):
        self.source_id = source_id
        self._records = records
        self._sections = sections_by_designation or {}
        self._may_index_fulltext = may_index_fulltext

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return self._sections.get(record.raw_designation, [])

    def classify_rights(self, record):
        may_index_fulltext = record.full_text is not None and self._may_index_fulltext
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=may_index_fulltext,
            may_cite_passages=may_index_fulltext, may_export_free=True,
            legal_basis_reference="§ 5 UrhG",
        )


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )


def test_run_adapter_creates_a_document_for_a_new_record(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-new-doc", raw_designation="DGUV Vorschrift 1",
        raw_issuer="DGUV", raw_title="Grundsätze der Prävention", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    summary = run_adapter(adapter, db_session)

    assert summary.documents_created == 1
    assert summary.records_processed == 1
    assert summary.records_skipped == 0


def test_run_adapter_skips_unchanged_delivery_on_second_run(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-skip", raw_designation="DGUV Vorschrift 2",
        raw_issuer="DGUV", raw_title="Titel", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)
    second_summary = run_adapter(adapter, db_session)

    assert second_summary.records_skipped == 1
    assert second_summary.documents_created == 0


def test_run_adapter_segments_and_embeds_full_text_records(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-fulltext", raw_designation="DGUV Vorschrift 3",
        raw_issuer="DGUV", raw_title="Titel", full_text="§ 1 Text. § 2 Mehr Text.",
    )
    sections = {
        "DGUV Vorschrift 3": [
            RawSection(sequence_number=1, heading="§ 1", text="Text."),
            RawSection(sequence_number=2, heading="§ 2", text="Mehr Text."),
        ]
    }
    adapter = _FakeAdapter(source.id, [record], sections)

    summary = run_adapter(adapter, db_session)

    assert summary.segments_created == 2
    assert summary.embeddings_created == 2


def test_run_adapter_enqueues_unparseable_designations(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-ambiguous", raw_designation="   ",
        raw_issuer="DGUV", raw_title=None, full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    summary = run_adapter(adapter, db_session)

    assert summary.records_enqueued_for_review == 1
    assert summary.documents_created == 0


def test_run_adapter_does_not_segment_when_rights_forbid_fulltext_indexing(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-rights-gate", raw_designation="DGUV Vorschrift 4",
        raw_issuer="DGUV", raw_title="Titel", full_text="§ 1 Text. § 2 Mehr Text.",
    )
    sections = {
        "DGUV Vorschrift 4": [
            RawSection(sequence_number=1, heading="§ 1", text="Text."),
            RawSection(sequence_number=2, heading="§ 2", text="Mehr Text."),
        ]
    }
    adapter = _FakeAdapter(source.id, [record], sections, may_index_fulltext=False)

    summary = run_adapter(adapter, db_session)

    assert summary.segments_created == 0
    assert summary.embeddings_created == 0


def test_run_adapter_writes_consistent_delivery_id_lineage_across_all_artifacts(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-lineage", raw_designation="DGUV Vorschrift 5",
        raw_issuer="DGUV", raw_title="Titel", full_text="§ 1 Text.",
    )
    sections = {
        "DGUV Vorschrift 5": [RawSection(sequence_number=1, heading="§ 1", text="Text.")]
    }
    adapter = _FakeAdapter(source.id, [record], sections)

    run_adapter(adapter, db_session)

    delivery = PostgresDeliveryRepository(db_session).find_delivery(record.source_id, record.content_hash)
    assert delivery is not None

    designation = db_session.execute(
        select(DocumentDesignationORM).where(DocumentDesignationORM.designation == "DGUV Vorschrift 5")
    ).scalar_one()
    title = db_session.execute(
        select(DocumentTitleORM).where(DocumentTitleORM.title == "Titel")
    ).scalar_one()
    rights = db_session.execute(
        select(RightsClassificationORM).where(RightsClassificationORM.document_id == designation.document_id)
    ).scalar_one()
    segment = db_session.execute(
        select(SegmentORM).where(SegmentORM.document_id == designation.document_id)
    ).scalar_one()
    embedding = db_session.execute(
        select(EmbeddingORM).where(EmbeddingORM.segment_id == segment.id)
    ).scalar_one()

    assert designation.delivery_id == delivery.id
    assert title.delivery_id == delivery.id
    assert rights.delivery_id == delivery.id
    assert segment.delivery_id == delivery.id
    assert embedding.delivery_id == delivery.id


def test_run_adapter_wires_reference_extraction_and_creates_edge(db_session):
    source = _make_source(db_session)

    setup_delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:runner-ref-target-setup",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    target_document = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=setup_delivery.id,
    )
    doc_repo.add_designation(
        document_id=target_document.id, issuer="EU", designation="2006/42/EC", language="de",
        edition=None, is_primary=True, delivery_id=setup_delivery.id,
    )

    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-ref-source", raw_designation="DGUV Vorschrift 6",
        raw_issuer="DGUV", raw_title="Titel", full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)

    source_designation = db_session.execute(
        select(DocumentDesignationORM).where(DocumentDesignationORM.designation == "DGUV Vorschrift 6")
    ).scalar_one()

    created = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == source_designation.document_id,
            EdgeORM.to_document_id == target_document.id,
        )
    ).scalar_one_or_none()
    assert created is not None
    assert created.edge_type == EdgeType.BASED_ON_LAW
