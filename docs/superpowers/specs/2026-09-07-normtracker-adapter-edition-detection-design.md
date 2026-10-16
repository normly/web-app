# Design: Edition change detection in ingestion adapters

## Context

Sub-project 1 brought the `Work` entity: several `Document` rows
share one `Work` as soon as a `REPLACES`, `WITHDRAWN_BY` or
`ADOPTED_FROM` edge is created between them — the mechanism for this is
finished, tested, merged (`core/src/normly_core/pipeline/references.py`,
`create_edge`, the automatic work merge). Sub-project 3 builds the
edition history/national versions display exactly on top of it.

So far, however, **no** ingestion adapter ever emits any of these three
edge types on real data. The only adapter that sets
`raw_references` at all is `eur_lex.py`, and it only ever does so with
`EdgeType.BASED_ON_LAW` (norm → underlying legal act) — an edge
that by definition never triggers work membership. On real data,
every ingested document therefore gets its own 1:1 `Work` today. For the
watchlist/notification building block planned as
sub-project 4 ("message on a
new edition"), this is the main trigger — without it, this feature would
have practically no triggers on real data. This sub-project closes exactly
this gap, as a precondition for sub-project 4.

## Research result: which adapters are suitable candidates?

Three adapters exist: `eur_lex.py`, `baua.py`, `dguv.py` (all in
`core/src/normly_core/pipeline/adapters/`). For each, we checked whether
its **actually ingested source** (not a separate, unconnected
publication) contains a structurally recognizable signal for
edition changes:

- **EUR-Lex — yes, confirmed.** The "Summary of references of harmonised
  standards" table published by the Commission (Docling table,
  currently only columns 1–3 are read) contains, in column 10/11, a
  withdrawal date plus the OJ reference of the withdrawal, and in column 6 the
  OJ reference of the entry's own publication. Verified on the real fixture PDF:
  `EN ISO 12100-1:2003`/`-2:2003` carry in column 11 exactly the
  OJ reference that `EN ISO 12100:2010` (another row of the same table)
  carries in column 6 as its own publication reference — a direct,
  structurally reliable join.
- **DGUV — yes, confirmed (with a limitation, see below).** Every real
  DGUV Vorschrift ends with its own § section "Inkrafttreten/
  Außerkrafttreten" (entry into force/expiry) that explicitly names the predecessor. Verified on the
  real PDF of DGUV Vorschrift 38 ("Bauarbeiten" (construction work), Nov. 2019):
  > "Diese Unfallverhütungsvorschrift tritt am ersten Tag des auf die
  > Veröffentlichung folgenden Monats in Kraft. Gleichzeitig tritt die
  > Unfallverhütungsvorschrift „Bauarbeiten" vom September 1976 in der
  > Fassung vom Januar 1997 außer Kraft."

  (In English: "This accident prevention regulation enters into force on the
  first day of the month following its publication. At the same time, the
  accident prevention regulation "Bauarbeiten" of September 1976, in the
  version of January 1997, ceases to have effect.")

  `dguv.py` already splits the running text into §-numbered sections
  today — this section is therefore already isolated during parsing.
- **BAuA/TRGS — no, rejected.** The official announcement of a
  new TRGS version does contain the wording "ersetzt die TRGS 905
  Ausgabe März 2014" (replaces TRGS 905, edition March 2014) — but only in the separate GMBl publication.
  Verified on a real TRGS 905 PDF (the source that `baua.py`
  actually ingests): it contains **no** replacement notice, only
  "Ausgabe: &lt;Datum&gt;" (edition: &lt;date&gt;). Connecting a new source (GMBl) would be a
  project of its own, not an adapter fix — it stays out of scope here.

## Goal of this sub-project

Extend `eur_lex.py` and `dguv.py` so that, on detecting an
edition change signal in their respective source, they emit an additional
`RawReference` with `EdgeType.REPLACES` — pointing from the new
(succeeding) document to the old (superseded) one, analogous to the existing
direction convention. `references.py`, `create_edge` and the
work merge logic are already generic enough (they only dispatch on
`RawReference.edge_type`) and need no change.

## Non-goals

- **No BAuA/TRGS fix.** The signal demonstrably does not exist in the
  ingested document (see above).
- **No new source.** Neither the GMBl nor any other publication not connected
  so far is connected in this sub-project.
- **No backfill mechanism.** According to
  CLAUDE.md, re-running the ingestion is idempotent — a new `ingest` run over already existing
  PDFs creates the new edges retroactively via the existing
  `create_edge`/work merge mechanism. No separate script needed.
- **No watchlist/notification code.** That remains the actual next
  sub-project — this one is only its precondition.
- **No change to `references.py`, `create_edge`, work merge.** Already
  generic, reused unchanged.

## Architecture: EUR-Lex

`_fetch_file` today reads columns 1 (ESO), 2 (number), 3 (title) and builds
a `BASED_ON_LAW` reference per row. Extension:

1. Two new column constants: column 6 ("OJ reference for publication in
   OJ") and column 11 ("OJ reference for withdrawal from OJ") — verify the indexes
   against the real fixture PDF, analogous to the existing
   verification of columns 1–3.
2. **Two passes** over `document.tables` instead of one: the first builds
   a map `OJ reference (column 6) → (designation, eso)` across **all**
   tables/rows (a successor can be on a different page/
   table than its predecessor). The second (the existing
   yield loop) checks per row: is its own column 6 reference present as a
   key in this map? If so, this row is the successor of the
   entry that carries exactly this OJ reference in column 11 as its
   withdrawal reference — in addition to the
   existing `BASED_ON_LAW` reference, the row gets a
   `RawReference(target_issuer=<old eso>, target_designation=<old
   designation>, edge_type=EdgeType.REPLACES)`.
3. No match within the currently loaded table(s) → create no
   reference. No guessing; it stays open until a later ingestion run
   also acquires the successor.
4. Empty/`"-"` cells in column 6/11 count as "no value", not as a
   match candidate.

## Architecture: DGUV

`_fetch_file` builds `lines`/`full_text` via the existing
`_logical_lines`/`_HEADING_PATTERN` machinery before the (immutable)
`RawRecord` is constructed. `extract_structure` — which performs the § split into
`RawSection`s — is only called by the runner afterwards, separately;
`raw_references`, however, must already be set when the `RawRecord` is
constructed. Extension:

1. After building `lines`, before constructing the `RawRecord`: find
   the line whose heading matches `§ N Inkrafttreten/Außerkrafttreten`
   (the same `_HEADING_PATTERN` detection, brought forward here), and take its
   running text up to the next heading line.
2. Two regex variants on this section text, depending on the form of the
   named predecessor:
   - **Modern reference** (rare, but real — e.g. a new "DGUV
     Vorschrift 2" supersedes an older "DGUV Vorschrift 2" that is also already
     numbered in the modern way): the text after "außer Kraft" contains a
     pattern conforming to `_DESIGNATION_PATTERN` → `target_designation` =
     exactly this pattern.
   - **Free-text old title** (more frequent — the predecessor dates from before
     the DGUV numbering reform, e.g. „Bauarbeiten" vom September 1976):
     pattern `„<title>" vom <date>[ in der Fassung vom <date>]` →
     `target_designation` = the title string, `target_issuer` = `"DGUV"`.
3. In both cases: `RawReference(target_issuer=..., target_designation=...,
   edge_type=EdgeType.REPLACES)`, attached to the `RawRecord` of the
   document that contains the section itself (the new, superseding
   document) — the edge direction is thus automatically correct (points from the
   successor to the predecessor).
4. No recognizable pattern in the section (e.g. a first edition without a predecessor,
   or unknown wording) → no reference, no error.

**A deliberately accepted property, not a defect:** on real data, the
free-text old title variant will mostly NOT resolve via
`find_by_designation`, because the originally referenced
old document was never ingested into this system under this title (rather than under its then
BGV/GUV-V ID). This is not a
setback: `references.py`'s existing `reference_target_not_found` path
already catches it (a curator case instead of an error or guessing) — the
signal value comes from the fact that an edition change event becomes
visible at all, even if its target resolution does not (yet) succeed
automatically. Modern DGUV Vorschrift to DGUV Vorschrift successions (the
normal case once this system, over the years, adds newly appearing editions
of already known regulations) resolve normally, by contrast.

## Tests

- **EUR-Lex:** extend the existing fixture (or a new one) with a
  withdrawal/successor row pair, as found in the real PDF
  (`EN ISO 12100-1/-2:2003` → `EN ISO 12100:2010`). The test checks: exactly the
  successor row carries, in addition to the `BASED_ON_LAW` reference, a
  `REPLACES` `RawReference` with the correct `target_designation`; the
  two withdrawn rows themselves get no additional reference.
  An end-to-end test (like the existing `test_eur_lex_adapter.py` tests)
  confirms: with an existing target document, a real
  `REPLACES` edge is created via `create_edge`, and both documents end up in the
  same `Work`.
- **DGUV:** a new synthetic reportlab fixture (consistent with the
  existing BAuA fixtures, no copyright risk) with a "§ N
  Inkrafttreten/Außerkrafttreten" section in both variants — real
  wording as found in the real DGUV Vorschrift 38 PDF, once with a
  modern predecessor, once with a free-text old title predecessor. An end-to-end test
  confirms: with an existing target document, the modern reference creates a
  real `REPLACES` edge and a work merge; the free-text reference
  ends up as a curator case (no error, no wrong edge).
- No regression risk for `references.py`/`create_edge`/work merge — they
  remain unchanged, their existing tests run along untouched.
- No regression risk for `baua.py` — unchanged.
