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
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
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


def test_dguv_replaces_edge_is_created_for_a_modern_designation_predecessor(db_session, tmp_path):
    """A publication that retires an already-known, modern-numbered
    Vorschrift by its full designation resolves cleanly: unlike Task 1's
    multi-predecessor EUR-Lex case, this is the clean single-predecessor
    path -- a real, unambiguous Work merge.

    The successor is deliberately given its OWN, different designation
    ("DGUV Vorschrift 12") rather than literally re-using "DGUV Vorschrift
    2" for both documents: this adapter's `add_designation(...,
    edition=None, ...)` call means `identity.resolve()` (unchanged,
    out of scope for this task) matches purely on (issuer, designation), so
    a second record sharing the exact same designation as an existing
    document would resolve to that SAME document (`is_new=False`,
    `documents_created == 0` on the second run) rather than create a
    distinct new one -- verified directly against this codebase's actual
    identity-resolution behaviour before writing this test. Reusing "DGUV
    Vorschrift 2" for both would make the predecessor reference this
    task's new code attaches point at the very document being ingested,
    producing a self-referential REPLACES edge instead of exercising the
    real successor/predecessor case this feature exists for.
    """
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import PostgresEdgeRepository
    from pipeline.test_dguv_adapter import _write_publication_pdf, _write_publication_pdf_with_sections

    dguv_source = _make_source(db_session, jurisdiction="DE")
    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_2_old.pdf", "DGUV Vorschrift 2", "Betriebsärzte"
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
    old_document = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 2")
    assert old_document is not None
    (tmp_path / "dguv_vorschrift_2_old.pdf").unlink()

    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_12_new.pdf",
        "DGUV Vorschrift 12", "Betriebsärzte und Fachkräfte für Arbeitssicherheit",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Dezember 2025 in Kraft. "
                "Gleichzeitig tritt die DGUV Vorschrift 2 vom 1. Januar 2011 außer Kraft.",
            ),
        ],
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)

    new_document = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 12")
    assert new_document is not None
    assert new_document.id != old_document.id

    outgoing = edge_repo.list_edges_for_jurisdiction(new_document.id, "DE")
    assert any(
        e.edge_type == EdgeType.REPLACES and e.to_document_id == old_document.id
        for e in outgoing
    )
    assert new_document.work_id == old_document.work_id


def test_dguv_free_text_predecessor_falls_through_to_the_existing_unresolved_case_path(
    db_session, tmp_path
):
    """The predecessor named only by its pre-reform free-text title will not
    resolve (it was never ingested under that title) -- no edge should be
    created, and the existing, unmodified reference_target_not_found path
    (references.py, unchanged by this plan) should be the only thing that
    reacts.

    The successor's OWN title is "Bauarbeiten allgemein", not the single
    word "Bauarbeiten" the real-world predecessor is quoted under below --
    see the matching comment in test_dguv_adapter.py's own version of this
    fixture for why a lone single-word title/designation block gets
    excluded entirely from Docling's default iteration (not merely
    misclassified as a page header) for this specific synthetic PDF
    layout, leaving `_fetch_file`'s `lines[0]` holding the next heading
    instead of the designation."""
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import (
        PostgresEdgeRepository,
        PostgresIdentityResolutionRepository,
    )
    from pipeline.test_dguv_adapter import _write_publication_pdf_with_sections

    dguv_source = _make_source(db_session, jurisdiction="DE")
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_38.pdf",
        "DGUV Vorschrift 38", "Bauarbeiten allgemein",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Oktober 2020 in Kraft. "
                "Gleichzeitig tritt die Unfallverhuetungsvorschrift 'Bauarbeiten' vom "
                "September 1976 in der Fassung vom Januar 1997 außer Kraft.",
            ),
        ],
    )
    adapter = DguvAdapter(directory=tmp_path, source_id=dguv_source.id)

    run_adapter(adapter, db_session)

    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    document = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 38")
    assert document is not None
    edges = edge_repo.list_edges_for_jurisdiction(document.id, "DE")
    assert all(e.edge_type != EdgeType.REPLACES for e in edges)

    # The SAME existing fallback Task 1's own "unresolvable successor" case
    # documents (references.py's reference_target_not_found path, unchanged
    # by this plan): the quoted-title target "Bauarbeiten" was never
    # ingested under that exact designation, so extract_references()
    # enqueues a NEW_DOCUMENT case for it instead of creating an edge.
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    cases = identity_repo.list_pending_cases()
    unresolved = [
        c for c in cases
        if c.raw_designation == "Bauarbeiten" and c.reason == "reference_target_not_found"
    ]
    assert len(unresolved) == 1
    assert unresolved[0].raw_issuer == "DGUV"


def test_dguv_new_edition_is_recognised_shares_the_work_and_gets_a_replaces_edge(
    db_session, tmp_path
):
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import PostgresEdgeRepository
    from pipeline.test_dguv_adapter import _write_publication_pdf

    dguv_source = _make_source(db_session, jurisdiction="DE")
    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1_2013.pdf", "DGUV Vorschrift 1",
        "vom 1. November 2013 Grundsätze der Prävention",
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
    old_document = doc_repo.find_by_designation(
        "DGUV", "DGUV Vorschrift 1", edition="2013-11-01"
    )
    assert old_document is not None
    (tmp_path / "dguv_vorschrift_1_2013.pdf").unlink()

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1_2022.pdf", "DGUV Vorschrift 1",
        "vom 1.6.2022 Grundsätze der Prävention",
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
    new_document = doc_repo.find_by_designation(
        "DGUV", "DGUV Vorschrift 1", edition="2022-06-01"
    )
    assert new_document is not None
    assert new_document.id != old_document.id

    assert new_document.work_id == old_document.work_id

    outgoing = edge_repo.list_edges_for_jurisdiction(new_document.id, "DE")
    assert any(
        e.edge_type == EdgeType.REPLACES and e.to_document_id == old_document.id
        for e in outgoing
    )


def test_dguv_edition_lineage_and_inkrafttreten_predecessor_mechanisms_do_not_double_up(
    db_session, tmp_path
):
    """Reproduces the review's Important finding scenario: a new DGUV edition
    shares its predecessor's exact designation (so Task 4's edition-lineage
    mechanism in identity.resolve()/runner.py fires) AND its own
    Inkrafttreten/Außerkrafttreten section names that SAME bare designation
    as the document it retires (so the pre-existing Inkrafttreten-based
    mechanism in references.py would ALSO try to fire). Before the fix,
    references.py's edition-blind find_by_designation lookup for that
    self-naming reference would nondeterministically resolve to either the
    record's own just-created document (tripping the self_referential_
    reference guard -- a false curator case) or some other row picked by
    insertion order -- across repeated runs of the identical input. After
    the fix, extract_references() skips a reference naming the record's own
    (issuer, designation) outright, leaving Task 4's own mechanism as the
    sole source of the REPLACES edge.

    Run 3 times (fresh designation per iteration to keep runs independent
    within one db_session/transaction) rather than once: the review's own
    reproduction of the nondeterministic case needed multiple runs to catch
    it, so a single green iteration would not be evidence the nondeterminism
    is actually gone.
    """
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import (
        PostgresEdgeRepository,
        PostgresIdentityResolutionRepository,
    )
    from pipeline.test_dguv_adapter import _write_publication_pdf, _write_publication_pdf_with_sections

    dguv_source = _make_source(db_session, jurisdiction="DE")
    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)

    # Designations 3-5 (not 1, already used by other tests in this module's
    # session-shared style, and not an arbitrary range -- empirically
    # confirmed stable across repeated Docling extraction runs before being
    # chosen here; some other designation numbers were observed to make
    # Docling's layout model intermittently drop the "vom ..." issue-date
    # line from its own text extraction, unrelated to this fix).
    for i, designation in enumerate(["DGUV Vorschrift 3", "DGUV Vorschrift 4", "DGUV Vorschrift 5"]):
        old_path = tmp_path / f"dguv_{i}_old.pdf"
        new_path = tmp_path / f"dguv_{i}_new.pdf"

        _write_publication_pdf(
            old_path, designation, "vom 1. November 2013 Grundsätze der Prävention",
        )
        run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
        old_document = doc_repo.find_by_designation(
            "DGUV", designation, edition="2013-11-01"
        )
        assert old_document is not None
        old_path.unlink()

        _write_publication_pdf_with_sections(
            new_path, designation, "vom 1.6.2022 Grundsätze der Prävention",
            [
                (
                    "§ 13 Inkrafttreten/Außerkrafttreten",
                    "Diese Unfallverhuetungsvorschrift tritt am 1. Juni 2022 in Kraft. "
                    f"Gleichzeitig tritt die {designation} vom 1. November 2013 außer Kraft.",
                ),
            ],
        )
        run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
        new_path.unlink()
        new_document = doc_repo.find_by_designation(
            "DGUV", designation, edition="2022-06-01"
        )
        assert new_document is not None
        assert new_document.id != old_document.id
        assert new_document.work_id == old_document.work_id

        outgoing = edge_repo.list_edges_for_jurisdiction(new_document.id, "DE")
        replaces_edges = [
            e for e in outgoing
            if e.edge_type == EdgeType.REPLACES and e.to_document_id == old_document.id
        ]
        assert len(replaces_edges) == 1, (
            f"iteration {i}: expected exactly one REPLACES edge "
            f"{new_document.id} -> {old_document.id}, found {len(replaces_edges)}"
        )

        pending = identity_repo.list_pending_cases()
        false_self_referential_cases = [
            c for c in pending
            if c.reason == "self_referential_reference" and c.raw_designation == designation
        ]
        assert false_self_referential_cases == [], (
            f"iteration {i}: unexpected self_referential_reference case(s) for "
            f"{designation!r}: {false_self_referential_cases}"
        )
