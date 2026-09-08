# Editionswechsel-Erkennung in Ingestion-Adaptern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `eur_lex.py` and `dguv.py` emit an additional `RawReference(edge_type=EdgeType.REPLACES)` whenever their own source data signals that the ingested document supersedes an earlier one, so that real `REPLACES` edges and Work-merges actually get created on real data (currently zero adapters do this).

**Architecture:** Two fully independent, self-contained adapter changes. `references.py`'s `extract_references` and `work_assignment.py`'s `determine_work_assignment` already dispatch purely on `RawReference.edge_type` — both already handle `EdgeType.REPLACES` correctly today, with zero changes needed. Each task only adds parsing logic to its own adapter file, building the extra `RawReference` from a signal already present in the source PDF, and proves it end-to-end against a real Postgres via the existing `run_adapter` pipeline entry point.

**Tech Stack:** Python 3.12, Docling (PDF extraction, already used by both adapters), pytest, reportlab (synthetic PDF fixture generation, already used by the DGUV tests), SQLAlchemy + Postgres via testcontainers (already used by `test_end_to_end.py`).

## Global Constraints

- No changes to `core/src/normly_core/pipeline/references.py`, `core/src/normly_core/graph/postgres/repositories.py`'s `create_edge`, or any Work-merge logic (`core/src/normly_core/pipeline/work_assignment.py`, `resolve_work_merge_case`) — all confirmed already generic, dispatch purely on `RawReference.edge_type`.
- No changes to `core/src/normly_core/pipeline/adapters/baua.py` — confirmed (via real source PDFs fetched and inspected during brainstorming) that BAuA/TRGS's actual ingested source carries no supersession signal; the only place that wording exists is a separate, unread GMBl publication.
- `RawRecord` (`core/src/normly_core/pipeline/domain.py`) is a **frozen** dataclass — `raw_references` must be set at construction time, inside each adapter's own `_fetch_file`, never assigned after the fact.
- Every new/modified test follows this codebase's TDD discipline: write the failing test first, run it and read the failure, then write the minimal code that makes it pass.
- License headers already present in both files being modified (`eur_lex.py`, `dguv.py`) — no new source files are created by this plan, so no new headers are needed.
- `EdgeType.REPLACES` edges point **from the successor document to the superseded one** (`core/src/normly_core/graph/domain.py:25-30`, direction convention documented throughout the codebase, e.g. `api/src/normly_api/routers/validity.py`). Every new `RawReference` in this plan is attached to the **new/replacing** document's own `RawRecord` — never to the superseded one's.
- **Known, pre-existing, out-of-scope limitation surfaced by this plan's own Task 1 end-to-end test — do not attempt to fix it here:** `work_assignment.determine_work_assignment` (`core/src/normly_core/pipeline/work_assignment.py:23-55`) collects `candidate_work_ids` from every Work-linking reference on a record; if a new document's `raw_references` resolve to targets in **more than one** distinct pre-existing Work, the result is `is_ambiguous=True`, and `runner.py` (lines 94-118) enqueues **exactly one** `work_merge` case — for whichever candidate Work id sorts lexicographically smallest as a string — not one case per conflicting candidate. The other candidate Works are silently left unmerged and unflagged. Task 1's own real-fixture end-to-end test exercises this exact path (one successor standard resolving three separate predecessor Works) and must assert the real, current behavior (one edge per predecessor is still created; only one work_merge case is queued) — not an idealized "all three merge" outcome. This is existing `work_assignment.py` behavior from an already-merged prior sub-project; flag it in your task report as a discovered residual, but do not modify `work_assignment.py` to fix it.

---

### Task 1: EUR-Lex — detect withdrawal/successor pairs via OJ-reference join

**Files:**
- Modify: `core/src/normly_core/pipeline/adapters/eur_lex.py:34-36` (column constants), `:90-122` (`_fetch_file`'s table loop)
- Test: `core/tests/pipeline/test_eur_lex_adapter.py` (new tests appended)
- Test: `core/tests/pipeline/test_end_to_end.py` (new test appended)

**Interfaces:**
- Consumes: `core/src/normly_core/pipeline/domain.py`'s `RawReference(target_issuer: str, target_designation: str, edge_type: EdgeType)` (unchanged), `core/src/normly_core/graph/domain.py`'s `EdgeType.REPLACES` (unchanged, already exists).
- Produces: nothing any later task in this plan consumes — Task 1 and Task 2 are fully independent.
- No new files, no new fixtures. This task reads the **existing, real, already-committed** fixture `core/tests/fixtures/eur_lex_machinery_summary.pdf` — confirmed this session (rendered directly through this worktree's own Docling installation) to already contain a real, verifiable withdrawal/successor pattern, so no fixture change of any kind is needed.

**Ground truth, verified this session by rendering the real fixture through Docling** (`python -c "from normly_core.pipeline.docling_extraction import extract_document; ..."` against `core/tests/fixtures/eur_lex_machinery_summary.pdf`) — two tables, 12 columns each (`grid[0]` is the header row in both):

Table 0 (1 data row):
```
['2006/42/EC', 'CEN', 'EN ISO 12100:2010', 'Safety of machinery - General principles for design - Risk assessment and risk reduction (ISO 12100:2010)', 'A', '08/04/2011', 'OJ C 110 - 08/04/2011', '-', '', '-', '', '-']
```

Table 1 (6 data rows):
```
['2006/42/EC', 'CEN', 'EN ISO 12100-1:2003, EN ISO 12100-1:2003/A1:2009', 'Safety of machinery - Basic concepts, general principles for design - Part 1: Basic terminology, methodology (ISO 12100-1:2003)', 'A', '29/12/2009', 'OJ C 309 - 18/12/2009', '-', '', '-', '30/11/2013', 'OJ C 110 - 08/04/2011']
['2006/42/EC', 'CEN', 'EN ISO 12100-2:2003, EN ISO 12100-2:2003/A1:2009', 'Safety of machinery - Basic concepts, general principles for design - Part 2: Technical principles (ISO 12100- 2:2003)', 'A', '29/12/2009', 'OJ C 309 - 18/12/2009', '-', '', '-', '30/11/2013', 'OJ C 110 - 08/04/2011']
['2006/42/EC', 'CEN', 'EN ISO 14121-1:2007', 'Safety of machinery - Risk assessment - Part 1: Principles (ISO 14121- 1:2007)', 'A', '29/12/2009', 'OJ C 214 - 08/09/2009', '-', '', '-', '30/11/2013', 'OJ C 110 - 08/04/2011']
['2006/42/EC', 'CEN', 'EN 349:1993+A1:2008', 'Safety of machinery - Minimum gaps to avoid crushing of parts of the human body', 'B', '29/12/2009', 'OJ C 214 - 08/09/2009', '-', '', '-', '03/09/2022', 'OJ L 072 - 03/03/2021']
['2006/42/EC', 'CEN', 'EN 547-1:1996+A1:2008', 'Safety of machinery - Human body measurements - Part 1: Principles for determining the dimensions required for openings for whole body access into machinery', 'B', '29/12/2009', 'OJ C 214 - 08/09/2009', '-', '', '-', '', '-']
['2006/42/EC', 'CEN', 'EN 547-2:1996+A1:2008', 'Safety of machinery - Human body measurements - Part 2: Principles for determining the dimensions required for access openings', 'B', '29/12/2009', 'OJ C 214 - 08/09/2009', '-', '', '-', '', '-']
```

Column indices (0-based, matches the existing `_COLUMN_ESO = 1`/`_COLUMN_STANDARD_REFERENCE = 2`/`_COLUMN_TITLE = 3` convention already in the file): index 6 = "OJ reference for publication in OJ", index 11 = "OJ reference for withdrawal from OJ".

Reading the data: `EN ISO 12100:2010`'s own column 6 is `'OJ C 110 - 08/04/2011'`. Three different rows — `EN ISO 12100-1:2003, ...`, `EN ISO 12100-2:2003, ...`, `EN ISO 14121-1:2007` — each carry that **exact same string** in column 11 (their withdrawal reference). `EN 349:1993+A1:2008` is also withdrawn (column 11 = `'OJ L 072 - 03/03/2021'`), but no row in either table carries that value in column 6 — its successor is not present in this fixture. `EN 547-1:1996+A1:2008` and `EN 547-2:1996+A1:2008` were never withdrawn (column 10 is empty, column 11 is `'-'`).

This gives exactly the three cases needed for testing, natively, with zero fixture changes: (a) one successor resolving **three** separate predecessors (the ambiguous-Work-signal case called out in Global Constraints above), (b) a withdrawn standard whose successor is absent from the corpus (no reference should be created), (c) standards never withdrawn at all (no reference, unchanged from today).

- [ ] **Step 1: Write the failing unit test for reference-list content**

Add to `core/tests/pipeline/test_eur_lex_adapter.py`:

```python
def test_fetch_attaches_a_replaces_reference_per_matching_withdrawn_predecessor():
    """EN ISO 12100:2010's own 'OJ reference for publication' (column 6)
    matches the 'OJ reference for withdrawal' (column 11) of three separate
    rows in the real fixture -- it consolidated all three into one standard.
    Each of those three withdrawn rows must turn into its own REPLACES
    RawReference on the successor's record, in addition to the existing
    BASED_ON_LAW reference."""
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())
    successor = next(
        r for r in records if r.raw_designation == "EN ISO 12100:2010"
    )

    based_on_law = [r for r in successor.raw_references if r.edge_type == EdgeType.BASED_ON_LAW]
    replaces = [r for r in successor.raw_references if r.edge_type == EdgeType.REPLACES]
    assert len(based_on_law) == 1
    assert {r.target_designation for r in replaces} == {
        "EN ISO 12100-1:2003, EN ISO 12100-1:2003/A1:2009",
        "EN ISO 12100-2:2003, EN ISO 12100-2:2003/A1:2009",
        "EN ISO 14121-1:2007",
    }
    assert all(r.target_issuer == "CEN" for r in replaces)


def test_fetch_does_not_attach_a_replaces_reference_when_the_successor_is_absent():
    """EN 349:1993+A1:2008 was withdrawn (real data), but no row in this
    fixture carries its withdrawal OJ reference as its own publication OJ
    reference -- its successor was never ingested. No REPLACES reference
    should be fabricated; the record keeps only its BASED_ON_LAW reference."""
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())
    withdrawn_without_successor = next(
        r for r in records if r.raw_designation == "EN 349:1993+A1:2008"
    )

    assert len(withdrawn_without_successor.raw_references) == 1
    assert withdrawn_without_successor.raw_references[0].edge_type == EdgeType.BASED_ON_LAW


def test_fetch_does_not_attach_a_replaces_reference_for_a_never_withdrawn_standard():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())
    never_withdrawn = next(
        r for r in records if r.raw_designation == "EN 547-1:1996+A1:2008"
    )

    assert len(never_withdrawn.raw_references) == 1
    assert never_withdrawn.raw_references[0].edge_type == EdgeType.BASED_ON_LAW
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest core/tests/pipeline/test_eur_lex_adapter.py -v -k replaces_reference`
Expected: all three FAIL. The first two fail on the `len(...) == 1`/`{...} == {...}` assertions (today every record has exactly one `BASED_ON_LAW` reference and nothing else, so `replaces` is empty and the "absent successor" record's own assertion already passes today — re-read the actual failures once you run this: the third test may already PASS before your change, since it asserts *no* REPLACES reference exists yet — that's fine, it becomes a real regression guard once Step 3 lands and must still pass afterwards).

- [ ] **Step 3: Implement the two-pass column read**

In `core/src/normly_core/pipeline/adapters/eur_lex.py`, replace lines 34-36:

```python
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3
```

with:

```python
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3
# "OJ reference for publication in OJ" -- a standard's own first-publication
# reference. "OJ reference for withdrawal from OJ" -- set once the standard
# is superseded, carrying the SAME OJ reference as whichever later row's own
# column 6 announced its successor (both are announced in one OJ notice).
# Verified against the real fixture PDF's Docling table extraction: EN ISO
# 12100-1/-2:2003 and EN ISO 14121-1:2007 each carry 'OJ C 110 -
# 08/04/2011' in column 11; EN ISO 12100:2010 (their consolidating
# successor) carries that exact string in column 6.
_COLUMN_OJ_PUBLICATION = 6
_COLUMN_OJ_WITHDRAWAL = 11
```

Replace lines 90-122 (the existing `seen_designations`/table loop through the closing `)` of the `yield RawRecord(...)` call) with:

```python
        # Pass 1: index every withdrawn row by the OJ reference that
        # announced its withdrawal, across ALL tables -- a successor can
        # land on a different page/table than the standard(s) it replaces.
        # A single OJ notice commonly retires more than one standard at
        # once (a consolidating successor), so each key maps to a LIST.
        withdrawal_index: dict[str, list[tuple[str, str]]] = {}
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_OJ_WITHDRAWAL:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                withdrawal_cell = row[_COLUMN_OJ_WITHDRAWAL]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                withdrawal_ref = (withdrawal_cell.text if withdrawal_cell else "").strip()
                if not eso or not designation or eso.startswith("ESO"):
                    continue
                if not withdrawal_ref or withdrawal_ref == "-":
                    continue
                withdrawal_index.setdefault(withdrawal_ref, []).append((designation, eso))

        seen_designations: set[str] = set()
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_OJ_WITHDRAWAL:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                title_cell = row[_COLUMN_TITLE]
                publication_cell = row[_COLUMN_OJ_PUBLICATION]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                title = (title_cell.text if title_cell else "").strip()
                publication_ref = (publication_cell.text if publication_cell else "").strip()
                if not eso or not designation or eso.startswith("ESO"):
                    continue
                if designation in seen_designations:
                    continue
                seen_designations.add(designation)

                references = [
                    RawReference(
                        target_issuer="EU",
                        target_designation=self.legislation_reference,
                        edge_type=EdgeType.BASED_ON_LAW,
                    )
                ]
                if publication_ref and publication_ref != "-":
                    for old_designation, old_eso in withdrawal_index.get(publication_ref, []):
                        references.append(
                            RawReference(
                                target_issuer=old_eso,
                                target_designation=old_designation,
                                edge_type=EdgeType.REPLACES,
                            )
                        )

                yield RawRecord(
                    source_id=self.source_id,
                    content_hash=f"{content_hash}:{designation}",
                    raw_designation=designation,
                    raw_issuer=eso,
                    raw_title=title or None,
                    full_text=None,
                    language="en",
                    raw_references=references,
                    fetched_at=now,
                )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest core/tests/pipeline/test_eur_lex_adapter.py -v`
Expected: every test in the file PASSES, including the three new ones and all pre-existing ones (`test_fetch_yields_the_legal_act_record_first`, `test_fetch_yields_standard_records_with_based_on_law_reference`, etc. — that second one in particular asserts `len(first.raw_references) == 1` for `standard_records[0]`, which is whatever row Docling's grid iteration yields first; confirm which designation that actually is and that it is NOT `EN ISO 12100:2010` — if it is, that pre-existing test now needs `len(...) == 1` widened to reflect the new REPLACES references, and that is a legitimate, expected plan-defect fix, not a regression to work around. Check this before moving on).

- [ ] **Step 5: Write the failing end-to-end test**

Add to `core/tests/pipeline/test_end_to_end.py`:

```python
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
```

Repository method/field names used above are confirmed (verified directly against `core/src/normly_core/graph/domain.py:659-695` and `core/src/normly_core/graph/postgres/repositories.py:1476-1531` this session): `PostgresIdentityResolutionRepository.list_pending_cases() -> list[IdentityResolutionCase]`; `IdentityResolutionCase` is a frozen dataclass with fields `id`, `delivery_id`, `case_type`, `raw_designation`, `raw_issuer`, `reason`, `status`, `resolved_document_id`, `source_work_id`, `target_work_id`, `resolved_at`, `resolved_by`, `created_at` — all used correctly above.

- [ ] **Step 6: Run the end-to-end tests to verify they fail correctly, then pass**

Run: `.venv/bin/pytest core/tests/pipeline/test_end_to_end.py -v -k eur_lex_replaces`
Expected: since Step 3's implementation already landed, these should mostly just confirm real behavior end-to-end — but verify each test actually exercises the new code path before trusting a PASS: temporarily comment out the `withdrawal_index` lookup in `eur_lex.py` (or the `references.append(...)` call inside it), confirm `replaces_targets` comes back empty, then restore it and confirm PASS.

Run full suite: `.venv/bin/pytest core/tests/pipeline -v` and `.venv/bin/pytest core/tests -q`
Expected: all pass, no regressions elsewhere.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/pipeline/adapters/eur_lex.py core/tests/pipeline/test_eur_lex_adapter.py core/tests/pipeline/test_end_to_end.py
git commit -s -m "feat(core): detect EUR-Lex withdrawal/successor pairs via OJ reference join"
```

---

### Task 2: DGUV — detect predecessor from the Inkrafttreten/Außerkrafttreten section

**Files:**
- Modify: `core/src/normly_core/pipeline/adapters/dguv.py:374-403` (`_fetch_file`), add new module-level helper function and regex constants near the top of the file (after the existing `_DESIGNATION_PATTERN`/`_ISSUE_DATE_PREFIX` constants, before `_FILE_PATTERN`).
- Test: `core/tests/pipeline/test_dguv_adapter.py` (new tests appended, new fixture-writing helper added)
- Test: `core/tests/pipeline/test_end_to_end.py` (new test appended)

**Interfaces:**
- Consumes: same `RawReference`/`EdgeType.REPLACES` as Task 1. Fully independent of Task 1 — different file, no shared state, may be executed in either order relative to it.
- Produces: nothing any later task in this plan consumes.
- Reuses (does not modify) `dguv.py`'s existing `_HEADING_PATTERN` (matches a full line that is a "§ N [optional title]" heading) and `_DESIGNATION_PATTERN` (matches "DGUV Vorschrift N" / "DGUV Regel NNN-NNN" / etc., with an optional trailing title) — both already defined in the file, read them yourself before writing the new regexes below to confirm they still match exactly what this plan describes.

**Ground truth found this session:**
- The real, committed fixture `core/tests/fixtures/dguv_sample_vorschrift.pdf` has exactly 3 sections (`§ 1 Geltungsbereich`, `§ 2 Pflichten des Unternehmers`, `§ 3 Pflichten der Versicherten`, confirmed via `test_extract_structure_splits_on_paragraph_headings`) — **no** Inkrafttreten/Außerkrafttreten section. This task needs new, dedicated fixture PDF(s); the existing fixture and every test built on it must keep passing unmodified.
- A real DGUV Vorschrift 38 PDF's own §13 reads (verified this session by fetching and reading the actual published PDF): *"Diese Unfallverhütungsvorschrift tritt am ersten Tag des auf die Veröffentlichung folgenden Monats in Kraft. Gleichzeitig tritt die Unfallverhütungsvorschrift „Bauarbeiten" vom September 1976 in der Fassung vom Januar 1997 außer Kraft."* — using German curly quotes (U+201E `„` / U+201C `"`) around the old title.
- **Verified empirically this session**: `reportlab.pdfgen.canvas`'s default Helvetica font does NOT render `„`/`"` correctly when the resulting PDF is run through this project's own Docling extraction — both characters come back as a plain straight apostrophe `'` (tested directly: `„Bauarbeiten"` round-tripped through `extract_document()` came back as `'Bauarbeiten'`, both quote marks collapsed to `'`). This means: the new **synthetic test fixture** (built with the same reportlab helper style the existing DGUV tests already use) will only ever produce straight `'`-quoted text, never real curly quotes — but a **real production PDF** (professionally typeset, embedded fonts) does carry real curly quotes, as directly confirmed against the actual DGUV Vorschrift 38 PDF. The implementation must normalize quote characters before matching, so it works correctly against both.

- [ ] **Step 1: Write the failing unit tests**

First, read `core/src/normly_core/pipeline/adapters/dguv.py`'s `_HEADING_PATTERN` (`^{_PARAGRAPH_MARKER}(?:\s+\S.*)?$`) and `_DESIGNATION_PATTERN` yourself to confirm they are unchanged from this plan's description before writing regexes against them.

Add to `core/tests/pipeline/test_dguv_adapter.py`, near the existing `_write_publication_pdf`/`_write_continuous_publication_pdf` helpers:

```python
def _write_publication_pdf_with_sections(path, designation: str, title: str, sections: list[tuple[str, str]]) -> None:
    """Like `_write_publication_pdf`, but with an arbitrary list of
    (heading, body) sections instead of the fixed single `§ 1
    Geltungsbereich`. `heading` must already include its `§ N` marker,
    e.g. `"§ 13 Inkrafttreten/Außerkrafttreten"`."""
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    lines = [designation, title, ""]
    for heading, body in sections:
        lines.append(heading)
        lines.append(body)
        lines.append("")
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()


def test_fetch_attaches_a_replaces_reference_for_a_modern_designation_predecessor(tmp_path):
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_2.pdf",
        "DGUV Vorschrift 2",
        "Betriebsärzte und Fachkräfte für Arbeitssicherheit",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Dezember 2025 in Kraft. "
                "Gleichzeitig tritt die DGUV Vorschrift 2 vom 1. Januar 2011 außer Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    references = records[0].raw_references
    assert len(references) == 1
    assert references[0].target_issuer == "DGUV"
    assert references[0].target_designation == "DGUV Vorschrift 2"
    from normly_core.graph.domain import EdgeType
    assert references[0].edge_type == EdgeType.REPLACES


def test_fetch_attaches_a_replaces_reference_for_a_free_text_title_predecessor(tmp_path):
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_38.pdf",
        "DGUV Vorschrift 38",
        "Bauarbeiten",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am ersten Tag des auf die "
                "Veroeffentlichung folgenden Monats in Kraft. Gleichzeitig tritt die "
                "Unfallverhuetungsvorschrift 'Bauarbeiten' vom September 1976 in der "
                "Fassung vom Januar 1997 außer Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    references = records[0].raw_references
    assert len(references) == 1
    assert references[0].target_issuer == "DGUV"
    assert references[0].target_designation == "Bauarbeiten"
    from normly_core.graph.domain import EdgeType
    assert references[0].edge_type == EdgeType.REPLACES


def test_fetch_attaches_no_reference_when_there_is_no_inkrafttreten_section(tmp_path):
    """A first edition, or any Vorschrift whose PDF simply lacks this
    section, must not error and must not fabricate a reference."""
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_references == []


def test_fetch_attaches_no_reference_when_the_section_names_no_predecessor(tmp_path):
    """An Inkrafttreten/Außerkrafttreten section can exist and simply not
    retire anything (a genuine first edition still states when it takes
    effect) -- no 'tritt ... außer Kraft' clause means no match, not an
    error."""
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_5.pdf",
        "DGUV Vorschrift 5",
        "Erste Hilfe",
        [
            (
                "§ 9 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Januar 2026 in Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_references == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest core/tests/pipeline/test_dguv_adapter.py -v -k "replaces_reference or no_reference"`
Expected: the first two FAIL with `assert 1 == 0` or similar (today `raw_references` is never populated — `RawRecord` defaults it to `[]`); the last two currently PASS already (there's nothing yet that could add a reference) — note that, they become real regression guards once Step 3 lands.

- [ ] **Step 3: Implement the predecessor-detection helper and wire it into `_fetch_file`**

In `core/src/normly_core/pipeline/adapters/dguv.py`, add these new imports at the top (alongside the existing `from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule`):

```python
from normly_core.graph.domain import EdgeType
from normly_core.pipeline.domain import RawRecord, RawReference, RawSection, RightsRule
```

Add these new module-level constants, placed after the existing `_ISSUE_DATE_PREFIX` constant and before `_FILE_PATTERN` (i.e. after the block ending `)` for `_ISSUE_DATE_PREFIX = re.compile(...)`):

```python
# The Inkrafttreten/Außerkrafttreten section's heading -- matched by
# substring, case-insensitively, since the exact surrounding wording
# ("Inkrafttreten/Außerkrafttreten" vs. a future publication phrasing it
# slightly differently) is not itself the signal; "inkrafttreten" appearing
# in a §-heading reliably is.
_TAKES_EFFECT_HEADING = re.compile("inkrafttreten", re.IGNORECASE)

# Isolates the clause naming whoever is being retired: "tritt ... außer
# Kraft" is this section's one fixed phrase for it, regardless of how the
# surrounding sentence is otherwise worded ("Gleichzeitig tritt ... außer
# Kraft", "... tritt gleichzeitig außer Kraft", etc.) -- non-greedy so it
# stops at the FIRST "außer Kraft" rather than swallowing the rest of the
# section if the phrase repeats.
_RETIRING_CLAUSE = re.compile(r"tritt\s+(.+?)\s+außer\s+Kraft", re.IGNORECASE | re.DOTALL)

# A predecessor named by its own modern DGUV designation (rare today, common
# once this system re-ingests a later edition of an already-known
# Vorschrift/Regel/Information/Grundsatz) -- reuses _DESIGNATION_PATTERN's
# own designation shape, unanchored so it can be found anywhere inside the
# retiring clause rather than only at its start.
_MODERN_PREDECESSOR = re.compile(
    r"DGUV (?:Vorschrift \d+|(?:Regel|Information|Grundsatz) \d{3}-\d{3})"
)

# The far more common case: a predecessor from before the DGUV numbering
# reform, named only by its free-text title in quotes ("„Bauarbeiten"" in a
# real, professionally typeset PDF; a reportlab-generated test fixture's
# Helvetica font cannot render „/" at all and collapses both to a plain "'"
# -- _normalise_quotes() below unifies every quote-like character to "'"
# before this pattern ever runs, so it only has to handle one form.
_QUOTED_PREDECESSOR_TITLE = re.compile(r"'([^']+)'")

# Every quote-like character this text might contain, normalised to a
# single straight apostrophe before pattern-matching: German „low-high"
# double quotes and their single-quote counterpart (‚...') as real PDFs set
# them, plain typographic single quotes ('...'), and the plain ASCII quotes
# a reportlab-generated fixture actually produces.
_QUOTE_CHARACTERS = "„“‚‘’\"'"


def _normalise_quotes(text: str) -> str:
    for character in _QUOTE_CHARACTERS:
        text = text.replace(character, "'")
    return text


def _extract_predecessor_reference(lines: list[str]) -> RawReference | None:
    """Find the Inkrafttreten/Außerkrafttreten section within an already
    logical-line-split document (see `_logical_lines`) and, if it names a
    predecessor being retired, return the RawReference for it.

    Mirrors extract_structure()'s own heading-boundary walk (a section runs
    from its own heading line up to, but not including, the next heading
    line) rather than diverging from it -- this has to run here, before
    `RawRecord` is constructed, since `RawRecord` is frozen and
    `extract_structure()` itself is only called later, separately, by the
    runner.
    """
    section_body: list[str] = []
    in_target_section = False
    for line in lines:
        if _HEADING_PATTERN.match(line):
            if in_target_section:
                break
            in_target_section = bool(_TAKES_EFFECT_HEADING.search(line))
            continue
        if in_target_section:
            section_body.append(line)

    if not section_body:
        return None

    text = " ".join(section_body)
    clause_match = _RETIRING_CLAUSE.search(text)
    if clause_match is None:
        return None
    clause = clause_match.group(1)

    modern_match = _MODERN_PREDECESSOR.search(clause)
    if modern_match is not None:
        return RawReference(
            target_issuer="DGUV", target_designation=modern_match.group(0),
            edge_type=EdgeType.REPLACES,
        )

    quoted_match = _QUOTED_PREDECESSOR_TITLE.search(_normalise_quotes(clause))
    if quoted_match is not None:
        return RawReference(
            target_issuer="DGUV", target_designation=quoted_match.group(1),
            edge_type=EdgeType.REPLACES,
        )

    return None
```

Then modify `_fetch_file` (currently lines 374-403): immediately after the existing loop that builds `lines` (i.e. right after the `for item, _level in document.iterate_items(): ...` block, and before `first = lines[0] if lines else ""`), add:

```python
        predecessor_reference = _extract_predecessor_reference(lines)
```

And change the final `yield RawRecord(...)` call (currently ending `language="de", fetched_at=datetime.now(timezone.utc),`) to add the new field:

```python
        yield RawRecord(
            source_id=self.source_id,
            content_hash=content_hash,
            raw_designation=designation,
            raw_issuer="DGUV",
            raw_title=title,
            full_text=full_text,
            language="de",
            raw_references=[predecessor_reference] if predecessor_reference else [],
            fetched_at=datetime.now(timezone.utc),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest core/tests/pipeline/test_dguv_adapter.py -v`
Expected: every test in the file PASSES, including all four new ones and every pre-existing one (in particular `test_fetch_yields_one_record_per_pdf_with_full_text`, which uses the real fixture with no Inkrafttreten section — confirm it still asserts nothing about `raw_references` or that it's now `[]`, consistent with the new no-signal path).

- [ ] **Step 5: Write the failing end-to-end tests**

Add to `core/tests/pipeline/test_end_to_end.py`:

```python
def test_dguv_replaces_edge_is_created_for_a_modern_designation_predecessor(db_session, tmp_path):
    """A later edition of an already-known, modern-numbered Vorschrift
    resolves cleanly: unlike Task 1's multi-predecessor EUR-Lex case, this
    is the clean single-predecessor path -- a real, unambiguous Work merge."""
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import PostgresEdgeRepository
    from test_dguv_adapter import _write_publication_pdf, _write_publication_pdf_with_sections

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
        tmp_path / "dguv_vorschrift_2_new.pdf",
        "DGUV Vorschrift 2", "Betriebsärzte und Fachkräfte für Arbeitssicherheit",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Dezember 2025 in Kraft. "
                "Gleichzeitig tritt die DGUV Vorschrift 2 vom 1. Januar 2011 außer Kraft.",
            ),
        ],
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)

    # Both documents now carry the IDENTICAL primary designation "DGUV
    # Vorschrift 2" -- this adapter never sets an `edition` on its
    # designations (`add_designation(..., edition=None, ...)` in
    # `_fetch_file`, unrelated to and unchanged by this plan). A second
    # `find_by_designation("DGUV", "DGUV Vorschrift 2")` call at this point
    # would raise (its query uses `.scalar_one_or_none()`, which requires at
    # most one match) -- the new document has to be found by elimination
    # instead of by name.
    all_documents = doc_repo.list_documents_for_jurisdiction("DE")
    new_document = next(d for d in all_documents if d.id != old_document.id)

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
    reacts."""
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import (
        PostgresEdgeRepository,
        PostgresIdentityResolutionRepository,
    )
    from test_dguv_adapter import _write_publication_pdf_with_sections

    dguv_source = _make_source(db_session, jurisdiction="DE")
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_38.pdf",
        "DGUV Vorschrift 38", "Bauarbeiten",
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
```

- [ ] **Step 6: Run the end-to-end tests to verify they pass**

Run: `.venv/bin/pytest core/tests/pipeline/test_end_to_end.py -v -k dguv`
Expected: PASS (after resolving the repository-method-name notes above against the real code).

Run full suite: `.venv/bin/pytest core/tests -q`
Expected: all pass, no regressions — including Task 1's tests if Task 1 already landed on this branch, or independently if this task is executed first.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/pipeline/adapters/dguv.py core/tests/pipeline/test_dguv_adapter.py core/tests/pipeline/test_end_to_end.py
git commit -s -m "feat(core): detect DGUV predecessor from the Inkrafttreten/Außerkrafttreten section"
```

---

## Model Selection Note (for subagent-driven-development execution)

Both tasks give complete reference code (exact regexes, exact column indices, exact new/modified functions) — but neither is pure transcription:

- **Task 1** requires the implementer to actually run the real fixture through Docling themselves (Step 4's instruction to check which designation `standard_records[0]` actually is, and whether a pre-existing test assertion needs updating) and to verify real repository method names against actual code (Step 5's explicit note) rather than trusting this plan's names blindly.
- **Task 2** requires understanding and correctly reusing existing heading-boundary-walk logic (mirroring, not diverging from, `extract_structure`'s own section-splitting semantics) and correctly reasons about Docling/reportlab's real, empirically-verified quote-character behavior — a subtlety a naive transcription would likely get wrong (e.g. writing a regex for `„..."` that would never match against the actual synthetic test fixture's own straight-quote output).

**Both tasks: standard model, not the cheapest tier** — consistent with this roadmap's established practice for tasks that require verifying assumptions against real fixture/tool behavior rather than pure transcription of complete, self-contained reference code. Task reviewers: also standard model (each diff is single-file, but correctness depends on tracing real Docling/regex behavior, not just reading the diff in isolation). Final whole-branch review: most capable available model, per this roadmap's established pattern for every sub-project so far.

## Self-Review

**Spec coverage:** the spec's two Architecture sections (EUR-Lex, DGUV) are each covered by one task; the spec's Non-Ziele (no BAuA change, no `references.py`/`create_edge`/Work-merge change, no backfill mechanism, no Watchlist code) are all satisfied by construction — no task touches any of those. The spec's Tests section is covered: EUR-Lex's match/no-match/never-withdrawn cases (Task 1, Steps 1 and 5), DGUV's modern/free-text/no-section/no-predecessor cases (Task 2, Steps 1 and 5).

**Placeholder scan:** none found. The two repository-method-name gaps found during the first self-review pass (`PostgresIdentityResolutionRepository`'s read-side method and `IdentityResolutionCase`'s fields) were resolved by reading the actual code (`core/src/normly_core/graph/domain.py:659-695`, `core/src/normly_core/graph/postgres/repositories.py:1476-1531`) before finalizing this plan — both tests now use the real name (`list_pending_cases`) and real fields directly, no "verify yourself" notes remain. A separate gap found the same way (`find_by_designation`'s `.scalar_one_or_none()` would raise once two documents share an identical designation, which Task 2's modern-designation end-to-end test's original draft would have triggered) was also fixed inline, by locating the new document via `list_documents_for_jurisdiction` and elimination instead.

**Type consistency:** `RawReference(target_issuer: str, target_designation: str, edge_type: EdgeType)` used identically in both tasks. `EdgeType.REPLACES` used identically in both tasks and matches the existing enum (`core/src/normly_core/graph/domain.py:25-30`, confirmed this session). Both tasks attach references only to the new/successor record, never the superseded one, consistent with the documented edge direction.

**Ambiguity/contradiction check:** found and fixed one real self-contradiction during this review: `_RETIRING_CLAUSE`'s regex requires the literal string `außer` (ß), but Task 2's two free-text-title-predecessor test fixtures (Step 1's unit test, Step 5's end-to-end test) originally spelled it `ausser` (ASCII `ss`) — an inconsistency with the rest of the plan's own test text, which correctly writes `außer Kraft` everywhere else, including the real quoted example this design is based on. Both occurrences corrected to `außer` (ß) — reportlab's default Helvetica font already renders ß correctly (Latin-1/WinAnsiEncoding), so there was no technical reason for the substitution in the first place, and the fix keeps the fixture text in the same orthography the regex, the real-world example, and every other test in this plan already use. Also fixed a duplicate character (`„` appeared twice) in `_QUOTE_CHARACTERS`'s literal.
