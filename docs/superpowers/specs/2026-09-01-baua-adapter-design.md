# Design: BAuA adapter (TRGS/TRBS/TRBA)

## Context

REQ-PIPE-009 (initial collection from freely accessible sources) names, besides the
lists of harmonized norms (EUR-Lex, already built as `EurLexAdapter`)
and the standards registers of DGUV (already built as `DguvAdapter`),
explicitly also the **standards registers of BAuA**. Both existing
adapters have run since the Docling migration
(`2026-08-30-docling-migration-design.md`) via the shared layer
`core/src/normly_core/pipeline/docling_extraction.py` and follow the same
ingestion model: no live scraping, an operator places source files in a
local directory, the CLI (`python -m normly_core.pipeline ingest ...`)
reads from there.

This task was selected in consultation with the owner over two
alternatives (a review interface for unclear identity resolution under
REQ-PIPE-007; building a CI/CD pipeline under REQ-BUILD-002/003) — as the
direct content continuation of the just completed Docling migration,
with the same adapter pattern and the same extraction layer.

**BAuA publishes three standards series relevant here**, all from the
same publisher, all with a comparable numbering scheme and
publication path:

- **TRGS** — Technische Regeln für Gefahrstoffe (Technical Rules for Hazardous
  Substances), drawn up by the Ausschuss für Gefahrstoffe (AGS, Committee on
  Hazardous Substances).
- **TRBS** — Technische Regeln für Betriebssicherheit (Technical Rules for
  Operational Safety), drawn up by the Ausschuss für Betriebssicherheit (ABS,
  Committee on Operational Safety).
- **TRBA** — Technische Regeln für Biologische Arbeitsstoffe (Technical Rules for
  Biological Agents), drawn up by the Ausschuss für Biologische Arbeitsstoffe (ABAS,
  Committee on Biological Agents).

All three are published by BAuA in the Gemeinsames Ministerialblatt (GMBl,
Joint Ministerial Gazette).

## Goal of this sub-project

- A new `BauaAdapter` that reads in all three series under one shared
  register entry (publisher `"BAuA"`) — analogous to `DguvAdapter`,
  which likewise bundles several publication series of the same publisher
  (Vorschrift/Regel/Information/Grundsatz) under one entry.
- A new register entry in `sources.py`, key `"baua"`,
  legal basis category A.
- CLI wiring (`build_adapter()` in `cli.py`) analogous to the existing
  sources.
- A first, deliberately simple iteration of the full-text structure (see
  "Decision: structure depth phase 1" below) — no repetition of the
  laborious heading regex iteration that the DGUV adapter
  had to go through.

## Non-goals

- **No automated retrieval from baua.de.** The site sits behind
  a JavaScript-based bot protection (Bunny Shield) — both `WebFetch`
  and `curl` (with a realistic browser user agent) returned HTTP 403 for every
  URL tested during the design, including the direct
  `TRBS-Bekanntmachungen.pdf` index link. An attempt to circumvent it
  was deliberately not made. Retrieval stays manual in this sub-project
  — congruent with the existing model for DGUV and EUR-Lex,
  where the operator places files in the ingest directory themselves. **Not intended
  as a permanent state:** manual retrieval does not scale to three
  continuously extended standards series with irregular new publications
  — automated retrieval is planned as a separate follow-up task, see
  "Open items".
- **No fine-grained section detection** (numbered headings such as
  "1 Zielsetzung", "2.1 Begriffsbestimmungen") in this pass — see
  Architecture. Deliberately deferred as a separate follow-up task.
- **No renewed check under REQ-PIPE-003** (rights reservation). Its
  wording ties the check to the "automated acquisition of freely accessible
  sources" — here there is neither an automated acquisition nor a
  copyright-protected work to which a rights reservation under
  § 44b Abs. 3 UrhG (German Copyright Act) could apply at all (see Legal basis below).
- **No new abstraction** between `DoclingDocument` and the
  domain objects. As laid down by the Docling migration, the adapter itself remains
  responsible for its small mapping logic.

## Architecture

New file `core/src/normly_core/pipeline/adapters/baua.py`, class
`BauaAdapter(directory, source_id)` — same form as `DguvAdapter` and
`EurLexAdapter`. Uses the same shared `docling_extraction.extract_document()`.

### File convention

Three file prefixes for the three series, one adapter reads all three:

```python
_FILE_PATTERNS = ("baua_trgs_*.pdf", "baua_trbs_*.pdf", "baua_trba_*.pdf")
```

`fetch()` collects all three globs together, sorted, and processes — as
with DGUV, unlike EUR-Lex — one PDF as one document, not as a
summary table with many rows.

### Designation detection

One shared pattern for all three series, since the numbering scheme is identical
(prefix + number, optionally "Teil N", e.g. "TRGS 500 Teil 1"):

```python
_DESIGNATION_PATTERN = re.compile(r"^(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)\s*(.*)$")
```

As empirically confirmed for DGUV/EUR-Lex: Docling merges visually adjacent
lines (designation and title line) into one text element. The title
is therefore formed from the rest of the same first element after the
designation match — unlike DGUV, deliberately **without** its
sentence-boundary heuristic (`_SENTENCE_OPENERS`, word-list check etc.). This
is an accepted risk, not carelessness: with a heavily
merged Docling text block, the title can contain remnants of running text.
Same category as the residual risk already accepted in the DGUV adapter — documented
there in its "Open items". `full_text` is unaffected by this
and contains the complete text in every case.

### Legal basis: category A

TRGS/TRBS/TRBA are drawn up by BAuA expert committees (AGS/ABS/ABAS) and
published by BAuA in the GMBl. Unlike DGUV-Vorschriften, they are
not legal norms — employers who do not establish the "presumed" (not mandatory)
conformity via a TRGS/TRBS/TRBA must demonstrate equivalent
protection by other means ("Vermutungswirkung", presumption of conformity). This changes nothing about
the classification under § 5 Abs. 1 UrhG: its "Bekanntmachungen" (official notices) element
does not presuppose that the content has the character of a legal norm, but covers the
official notice as such — here by a federal higher authority in the
GMBl. This means the same category as the existing DGUV and
EUR-Lex register entries:

```python
def classify_rights(self, record: RawRecord) -> RightsRule:
    return RightsRule(
        jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG — amtliche Bekanntmachung (TRGS/TRBS/TRBA, BAuA im GMBl)",
    )
```

As with DGUV/EUR-Lex, narrower than the protocol (`RightsRule | None`): every
record of this source is classifiable, there is no "cannot
classify" case.

### Decision: structure depth phase 1

TRGS/TRBS/TRBA are structured internally into numbered sections
("1 Zielsetzung", "2.1 Begriffsbestimmungen", ...), not into
§ paragraphs like DGUV. Building robust boundary detection for this scheme
against real document variance takes the same effort as the
DGUV heading detection, which needed five iteration rounds plus adversarial
re-review and left an accepted residual risk behind in the process (see
the "Open items" there). Repeating this iteration in this pass
— without having first checked the real document variance against at least a single
real copy, which `baua.de`'s bot protection prevents here
— was deliberately rejected together with the owner.

Instead, in this first iteration `extract_structure()` returns exactly one
segment with the complete document text:

```python
def extract_structure(self, record: RawRecord) -> list[RawSection]:
    if record.full_text is None:
        return []
    return [RawSection(sequence_number=1, heading=None, text=record.full_text)]
```

The full text is thus searchable and citable from day one (`may_index_fulltext`
is `True`, see Legal basis) — just without granular section boundaries.
Finer segmentation is a deliberately deferred follow-up task (see "Open
items"), not a forgotten one.

## Components

| File | Change |
|---|---|
| `core/src/normly_core/pipeline/adapters/baua.py` | **New.** `BauaAdapter` — `fetch()`, `extract_structure()` (phase 1: one full-text segment), `classify_rights()` (category A, always classifiable). |
| `core/src/normly_core/pipeline/sources.py` | New entry `"baua"` in `SOURCE_REGISTRY`: publisher `"BAuA"`, category A, jurisdiction `"DE"`. |
| `core/src/normly_core/pipeline/cli.py` | `build_adapter()` extended by the `"baua"` branch, `argparse` choices supplemented by `"baua"`. |
| `core/tests/pipeline/test_baua_adapter.py` | **New.** See Test concept. |
| `core/tests/fixtures/baua_trgs_sample.pdf`, `baua_trbs_sample.pdf`, `baua_trba_sample.pdf` | **New.** Synthetic fixtures generated via `reportlab` at test time (as with DGUV) — not copied from the real site. |

## Data flow

File → `docling_extraction.extract_document()` → `DoclingDocument` →
the adapter takes the text of the first element, separates designation and title via
`_DESIGNATION_PATTERN`, collects all the remaining text unchanged as
`full_text` (no line-structure rebuild needed as with DGUV — phase 1 needs
no line boundaries, only the complete text). `extract_structure()` builds
the one segment from it; `classify_rights()` always returns the same category
A rule.

The rest of the data flow (delivery deduplication via content hash,
identity resolution, segment/embedding generation) runs unchanged via
`runner.run_adapter()` — the adapter itself knows none of these stages.

## Error handling

Identical to `DguvAdapter`/`EurLexAdapter`:

- An unreadable/broken PDF costs only that file — `DocumentExtractionError`
  is caught per file, logged via `report_skipped_source()`,
  `fetch()` continues reading the remaining files.
- A `PipelineInitializationError` (misconfigured Docling models) is
  **not** caught — it would affect every file equally and should abort the run
  visibly instead of faking an empty "success".

## Test concept

`core/tests/pipeline/test_baua_adapter.py`, with three fixtures generated via `reportlab`
(one per series), analogous to the approach for
`dguv_sample_vorschrift.pdf`. Cases:

- `fetch()` returns one record per file, across all three file prefixes
  together.
- Designation/title are separated correctly, for all three prefixes
  (TRGS/TRBS/TRBA) as well as for the "Teil N" suffix case.
- `classify_rights()` always returns the same category A rule, never `None`.
- `extract_structure()` returns, for a record with `full_text`, exactly one
  segment with the complete text; for `full_text=None` an empty list.
- An unreadable file is skipped, the others are processed nonetheless
  (as in the existing DGUV test).
- A `PipelineInitializationError` still aborts the run instead of
  being silently skipped (as in the existing DGUV test).

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-PIPE-009 | Directly fulfilled — BAuA is specifically named there as a category A/B initial collection source. |
| REQ-PIPE-002 | New register entry with complete mandatory fields (publisher, retrieval path, category, jurisdiction, check date, responsible person). |
| REQ-PIPE-003 | Not applicable — see Non-goals. |
| REQ-PIPE-005 | Untouched — lineage runs via the same `Delivery` mechanism as with the existing adapters, adapter-independent. |
| ADR-018 (Docling migration) | The new adapter builds from the start on the `docling_extraction` layer introduced there, duplicates no Docling configuration. |

## Open items / follow-up work

- **Automated retrieval as a separate follow-up task.** The manual
  retrieval path of this sub-project (the operator downloads PDFs, places them
  in the ingest directory) does not scale permanently: BAuA publishes new
  and revised TRGS/TRBS/TRBA versions continuously and irregularly across
  three series — unlike a once-maintained
  initial collection source, this needs a repeatable retrieval process.
  Realistically, that is only feasible with automation. `baua.de`'s bot protection
  (Bunny Shield, see Non-goals) prevents a naive scraper — to be
  clarified as soon as this task is tackled: whether BAuA offers an official
  access path without bot protection (e.g. a data exchange interface
  or an RSS/newsletter feed for new publications), or whether a
  browser-based retrieval with a documented, legally reviewed
  justification becomes necessary. As soon as automated acquisition is due,
  REQ-PIPE-003 (check for a machine-readable rights reservation) also becomes
  really relevant for this source — excluded here as a non-goal only
  because acquisition stays manual in this sub-project (see there).
  Separate design/spec, not part of this adapter.
- **Unchecked against a real document.** Neither the designation pattern nor
  the title extraction nor the assumption about Docling's element merging
  were verified against a real TRGS/TRBS/TRBA PDF — `baua.de`'s
  bot protection prevented that during the design. If the first
  Docling text element of a real document does not match
  `_DESIGNATION_PATTERN` (e.g. cover page instead of designation text), the
  result is silently a regularly ingested document with garbage data as
  `raw_designation` — not an automatic review case. Because `runner.py` writes the
  delivery (content hash) in the same transaction as the document,
  such a faulty first run cannot simply and cheaply be re-imported after an
  adapter correction; the operator
  first has to delete the affected delivery/document rows by hand.
  Precisely for this reason, spot-checking the first real run is not
  an optional extra, but a prerequisite *before* any larger ingest: as soon as the
  operator obtains the first real files, this first run must be
  spot-checked before larger quantities are read in.
- **Fine-grained section detection** (numbered headings) is
  deliberately deferred (see "Decision: structure depth phase 1"). A separate
  follow-up task as soon as real documents are available for deriving patterns.
- **No structured "Teil N" / part-number field.** `TRGS 500 Teil 1` and
  `TRGS 500 Teil 2` thereby become two unconnected document nodes:
  `RawRecord` has no `part` field, `runner.py` always writes `part` as
  `None`. The adapter itself correctly records "Teil N" as part of the
  designation string — the gap lies below the adapter, in the
  shared `RawRecord`/`runner.py` layer, and only becomes visible through BAuA as
  the first source with part-numbered designations. A separate
  follow-up task at pipeline level, not specific to this adapter.
- **File naming convention** (`baua_trgs_*.pdf` etc.) is an assumption of this
  design, not a convention prescribed by BAuA — the operator has to name
  the files accordingly when placing them. Easily extensible if needed
  (e.g. further prefixes for future series), without breaking the existing ones.
