# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date
from pathlib import Path

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.runner import run_adapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def _make_source(db_session, *, jurisdiction: str):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction=jurisdiction,
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )


def test_eur_lex_and_dguv_runs_populate_a_queryable_graph_with_correct_rights_asymmetry(
    db_session,
):
    eur_lex_source = _make_source(db_session, jurisdiction="EU")
    dguv_source = _make_source(db_session, jurisdiction="DE")

    eur_lex_adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=eur_lex_source.id, legislation_reference="2006/42/EC",
    )
    dguv_adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=dguv_source.id)

    eur_lex_summary = run_adapter(eur_lex_adapter, db_session)
    dguv_summary = run_adapter(dguv_adapter, db_session)

    assert eur_lex_summary.documents_created == 8  # legal act + 7 referenced standards
    assert dguv_summary.documents_created == 1
    assert dguv_summary.segments_created == 3
    assert dguv_summary.embeddings_created == 3

    doc_repo = PostgresDocumentRepository(db_session)
    segment_repo = PostgresSegmentRepository(db_session)

    eur_lex_standard = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")
    assert eur_lex_standard is not None
    assert segment_repo.list_segments_for_jurisdiction(eur_lex_standard.id, "EU") == []

    rights_repo = PostgresRightsRepository(db_session)
    eur_lex_rights = rights_repo.get_classification(eur_lex_standard.id, "EU")
    assert eur_lex_rights is not None
    assert eur_lex_rights.may_index_fulltext is False
    assert eur_lex_rights.may_cite_passages is False

    dguv_document = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1")
    assert dguv_document is not None
    dguv_segments = segment_repo.list_segments_for_jurisdiction(dguv_document.id, "DE")
    assert len(dguv_segments) == 3
    assert [s.heading for s in dguv_segments] == [
        "§ 1 Geltungsbereich",
        "§ 2 Pflichten des Unternehmers",
        "§ 3 Pflichten der Versicherten",
    ]


def test_running_the_same_adapter_twice_skips_unchanged_records(db_session):
    dguv_source = _make_source(db_session, jurisdiction="DE")
    dguv_adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=dguv_source.id)

    first_summary = run_adapter(dguv_adapter, db_session)
    second_summary = run_adapter(dguv_adapter, db_session)

    assert first_summary.records_processed == 1
    assert second_summary.records_processed == 0
    assert second_summary.records_skipped == 1
    assert second_summary.documents_created == 0
    assert second_summary.segments_created == 0
    assert second_summary.embeddings_created == 0
