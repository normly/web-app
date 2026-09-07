# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import (
    EdgeType,
    IdentityResolutionCaseType,
    IdentityResolutionStatus,
    LegalBasisCategory,
)
from normly_core.graph.postgres.orm import DocumentDesignationORM, DocumentORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference, RightsRule
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records):
        self.source_id = source_id
        self._records = records

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return []

    def classify_rights(self, record):
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        )


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )


def test_a_national_adoption_signal_reuses_the_original_documents_work(db_session):
    source = _make_source(db_session)
    din_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-din", raw_designation="EN ISO 9001:2018",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    bs_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-bs", raw_designation="EN ISO 9001:2018",
        raw_issuer="BS", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2018", edge_type=EdgeType.ADOPTED_FROM)
        ],
    )
    adapter = _FakeAdapter(source.id, [din_record, bs_record])

    summary = run_adapter(adapter, db_session)

    assert summary.documents_created == 2
    din_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "DIN")
    ).scalar_one()
    bs_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "BS")
    ).scalar_one()
    assert din_document.work_id == bs_document.work_id


def test_an_unrelated_record_gets_its_own_work(db_session):
    source = _make_source(db_session)
    record_a = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-a", raw_designation="EN ISO 9001:2018",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    record_b = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-b", raw_designation="Vorschrift 1",
        raw_issuer="DGUV", raw_title=None, full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record_a, record_b])

    run_adapter(adapter, db_session)

    documents = db_session.execute(select(DocumentORM)).scalars().all()
    work_ids = {document.work_id for document in documents}
    assert len(work_ids) == 2


def test_conflicting_work_signals_get_their_own_work_and_a_merge_case(db_session):
    source = _make_source(db_session)
    din_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-din", raw_designation="EN ISO 9001:2015",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    iso_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-iso", raw_designation="9001:2015",
        raw_issuer="ISO", raw_title=None, full_text=None,
    )
    conflicted_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-bs", raw_designation="EN ISO 9001:2015",
        raw_issuer="BS", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2015", edge_type=EdgeType.ADOPTED_FROM),
            RawReference(target_issuer="ISO", target_designation="9001:2015", edge_type=EdgeType.REPLACES),
        ],
    )
    adapter = _FakeAdapter(source.id, [din_record, iso_record, conflicted_record])

    summary = run_adapter(adapter, db_session)

    # DIN, ISO, and the conflicted BS document all get created -- the
    # conflicting signal no longer drops the document, it gets its own fresh
    # Work plus a work_merge case for a curator to resolve.
    assert summary.documents_created == 3
    assert summary.records_enqueued_for_review == 0

    din_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "DIN")
    ).scalar_one()
    iso_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "ISO")
    ).scalar_one()
    bs_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "BS")
    ).scalar_one()

    delivery = PostgresDeliveryRepository(db_session).find_delivery(source.id, "sha256:runner-conflict-bs")
    cases = PostgresIdentityResolutionRepository(db_session).list_pending_cases()
    conflict_case = next(case for case in cases if case.delivery_id == delivery.id)
    assert conflict_case.status == IdentityResolutionStatus.PENDING
    assert conflict_case.reason == "conflicting_work_signal"
    assert conflict_case.case_type == IdentityResolutionCaseType.WORK_MERGE
    assert conflict_case.source_work_id == bs_document.work_id
    assert conflict_case.target_work_id in {din_document.work_id, iso_document.work_id}
