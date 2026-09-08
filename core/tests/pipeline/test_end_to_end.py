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


def test_eur_lex_replaces_edges_are_created_for_a_consolidating_successor(db_session):
    """Real fixture data: EN ISO 12100:2010 consolidates three separately
    ingested predecessors. Every REPLACES edge must be created regardless of
    the Work-merge outcome -- create_edge() has no Work awareness. The
    Work-assignment side is deliberately NOT asserted as a clean three-way
    merge here: resolving three DIFFERENT pre-existing Works is the
    documented, pre-existing "conflicting_work_signal" path (see this plan's
    Global Constraints) -- asserted directly below instead."""
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import (
        PostgresEdgeRepository,
        PostgresIdentityResolutionRepository,
    )

    eur_lex_source = _make_source(db_session, jurisdiction="EU")
    eur_lex_adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=eur_lex_source.id, legislation_reference="2006/42/EC",
    )

    run_adapter(eur_lex_adapter, db_session)

    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    successor = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")
    predecessors = [
        doc_repo.find_by_designation(
            "CEN", "EN ISO 12100-1:2003, EN ISO 12100-1:2003/A1:2009"
        ),
        doc_repo.find_by_designation(
            "CEN", "EN ISO 12100-2:2003, EN ISO 12100-2:2003/A1:2009"
        ),
        doc_repo.find_by_designation("CEN", "EN ISO 14121-1:2007"),
    ]
    assert successor is not None
    assert all(p is not None for p in predecessors)

    outgoing = edge_repo.list_edges_for_jurisdiction(successor.id, "EU")
    replaces_targets = {
        e.to_document_id for e in outgoing if e.edge_type == EdgeType.REPLACES
    }
    assert replaces_targets == {p.id for p in predecessors}

    # Ambiguous Work signal (three separate pre-existing Works): the
    # successor keeps its own fresh Work rather than silently picking one,
    # and exactly one work_merge case is queued for a curator -- the
    # documented, pre-existing behavior this task's own code newly exercises
    # for the first time on real data.
    assert successor.work_id not in {p.work_id for p in predecessors}
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    cases = identity_repo.list_pending_cases()
    work_merge_cases = [c for c in cases if c.source_work_id == successor.work_id]
    assert len(work_merge_cases) == 1
    assert work_merge_cases[0].target_work_id in {p.work_id for p in predecessors}


def test_eur_lex_does_not_create_a_replaces_edge_for_an_unresolvable_successor(db_session):
    """EN 349:1993+A1:2008 was withdrawn in the real fixture data, but its
    successor is not present in this corpus -- no REPLACES edge should
    exist, and no reference_target_not_found case should be enqueued either
    (Task 1 attaches no reference at all when the successor cannot be
    resolved within the currently-parsed table data, per the spec's
    "no rätselraten" rule -- this differs from the DGUV free-text case in
    Task 2, which DOES attempt resolution and falls through to a curator
    case when it fails)."""
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import PostgresEdgeRepository

    eur_lex_source = _make_source(db_session, jurisdiction="EU")
    eur_lex_adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=eur_lex_source.id, legislation_reference="2006/42/EC",
    )

    run_adapter(eur_lex_adapter, db_session)

    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    withdrawn = doc_repo.find_by_designation("CEN", "EN 349:1993+A1:2008")
    assert withdrawn is not None

    incoming_or_outgoing = edge_repo.list_edges_for_jurisdiction(withdrawn.id, "EU")
    assert all(e.edge_type != EdgeType.REPLACES for e in incoming_or_outgoing)


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
