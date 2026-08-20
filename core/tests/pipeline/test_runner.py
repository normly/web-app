# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import PostgresSourceRepository
from normly_core.pipeline.domain import RawRecord, RawReference, RawSection, RightsRule
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records, sections_by_designation=None):
        self.source_id = source_id
        self._records = records
        self._sections = sections_by_designation or {}

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return self._sections.get(record.raw_designation, [])

    def classify_rights(self, record):
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=record.full_text is not None,
            may_cite_passages=record.full_text is not None, may_export_free=True,
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
