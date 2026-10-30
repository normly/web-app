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
- A conservative, source-specific parser for BAuA designations and numbered
  section headings, derived from local real-document observations and guarded
  by synthetic and opt-in real-document tests.

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
- **No rights reclassification in this parser change.** Manual local testing
  does not itself settle the source's rights status. The registered legal
  category and permitted processing/export steps remain subject to the source
  register and REQ-PIPE-003/004; this design change only covers extraction and
  section boundaries.
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
(prefix + number, optionally "Teil N", e.g. "TRGS 500 Teil 1"). The adapter
searches a bounded front-matter range for a unique designation. A recognized
filename may narrow candidates only when the designation is also present in
the extracted front matter:

```python
_DESIGNATION_SEARCH_PATTERN = re.compile(
    r"(?<!\w)(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)(?!\w)",
    re.IGNORECASE,
)
```

Docling may merge the designation, title, and following text into one item.
The title is therefore retained only when it is short and its boundary is
clear; otherwise `raw_title` is `None`. `full_text` retains all extracted
content regardless.

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

### Decision: designation and numbered-section extraction

BAuA PDFs can place cover and publication-information items before the
designation. The adapter searches a bounded front-matter range for a unique
designation-shaped item instead of treating the first Docling text item as the
identity. A designation encoded in the configured filename can narrow the
candidates, but is accepted only when it is also present in extracted
front matter. Competing or missing candidates fail closed to an empty
designation, which the existing identity resolver routes to manual review.
Titles are retained only when their boundary is clear.

TRGS/TRBS/TRBA are structured into numbered headings (for example, "1
Zielsetzung" and "2.1 Begriffsbestimmungen"), not into `§` paragraphs like
DGUV. The adapter uses Docling's ordered items and their labels only for short,
standalone numbered headings. SectionHeader items are the primary signal;
nested numbered ListItems can also be accepted. Ambiguous numbered prose
remains body text. This is a conservative source-specific rule, not a copy of
DGUV's `§` parser.

`extract_structure()` emits sections in document order. Preamble before the
first recognized heading is retained as a heading-less section; if no heading
is recognized, the complete text remains one heading-less section. The
numbering remains in each heading, so hierarchy is represented without a
shared schema change. Docling item boundaries are carried into the raw text
using whitespace-only separators; extracted words are not dropped.

Initial local observations from six PDFs using Docling 2.132.0 found that the
first-item designation assumption failed in every sample, while five contained
a designation-like item later in the extracted order. Docling also emitted
`section_header` items, but the real-document test remains opt-in and the
behavior must be checked with the repository's locked Docling version 2.135.0.

## Components

| File | Change |
|---|---|
| `core/src/normly_core/pipeline/adapters/baua.py` | `BauaAdapter` — `fetch()`, designation extraction, conservative numbered-section segmentation, and `classify_rights()`. |
| `core/src/normly_core/pipeline/sources.py` | New entry `"baua"` in `SOURCE_REGISTRY`: publisher `"BAuA"`, category A, jurisdiction `"DE"`. |
| `core/src/normly_core/pipeline/cli.py` | `build_adapter()` extended by the `"baua"` branch, `argparse` choices supplemented by `"baua"`. |
| `core/tests/pipeline/test_baua_adapter.py` | Synthetic unit tests for designation identification and conservative numbered-section splitting. |
| `core/tests/pipeline/test_baua_adapter_real.py` | **New.** Opt-in local checks against PDFs outside the repository; skipped unless `BAUA_REAL_DOCUMENTS_DIR` is set. |
| `core/tests/fixtures/baua_trgs_sample.pdf`, `baua_trbs_sample.pdf`, `baua_trba_sample.pdf` | **New.** Synthetic fixtures generated via `reportlab` at test time (as with DGUV) — not copied from the real site. |

## Data flow

File → `docling_extraction.extract_document()` → `DoclingDocument` →
the adapter inspects a bounded front-matter range for a unique designation,
collects every text item, and carries verified Docling item boundaries into
the raw text for conservative numbered-heading recognition.
`extract_structure()` splits only verified standalone headings and retains
preamble/body text. If identity is unclear, the empty designation routes to
manual review. Rights classification remains a separate processing gate.

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

`core/tests/pipeline/test_baua_adapter.py` keeps synthetic fixtures generated
via `reportlab` (one per series), analogous to the approach for
`dguv_sample_vorschrift.pdf`. These remain the default tests. They cover:

- `fetch()` returns one record per file, across all three file prefixes
  together.
- Designation/title are separated correctly, for all three prefixes
  (TRGS/TRBS/TRBA) as well as for the "Teil N" suffix case.
- `classify_rights()` always returns the same category A rule, never `None`.
- Designation identification after cover matter; missing or competing
  front-matter candidates fail closed rather than creating a false identity.
- `extract_structure()` splits short numbered headings (`1`, `2.1`, etc.),
  retains preamble text, and falls back to one complete segment when no
  heading is recognized; for `full_text=None` it returns an empty list.
- An unreadable file is skipped, the others are processed nonetheless
  (as in the existing DGUV test).
- A `PipelineInitializationError` still aborts the run instead of
  being silently skipped (as in the existing DGUV test).

`core/tests/pipeline/test_baua_adapter_real.py` is opt-in through
`BAUA_REAL_DOCUMENTS_DIR`; it stages links in pytest's temporary directory and
asserts the expected designation and first/last section headings for selected
local samples. It also checks that a document without a corroborated
designation remains unresolved. It does not include or print extracted
document text. Ordinary CI and synthetic tests do not depend on this directory.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-PIPE-009 | Directly fulfilled — BAuA is specifically named there as a category A/B initial collection source. |
| REQ-PIPE-002 | New register entry with complete mandatory fields (publisher, retrieval path, category, jurisdiction, check date, responsible person). |
| REQ-PIPE-003 | Rights-reservation status remains a source-register concern; manual local testing does not bypass it. |
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
  justification becomes necessary. Automated acquisition needs its own
  REQ-PIPE-003 review and source-register update. Manual acquisition and local
  testing remain subject to the source's registered rights classification.
  Separate design/spec, not part of this adapter.
- **Locked-version real-document verification.** The initial local spot-check
  used Docling 2.132.0, while `uv.lock` pins 2.135.0. Run the opt-in test with
  the locked version and validate that designation and heading classification
  remain stable before any larger ingestion. Spot-checking the first real
  pipeline run remains a prerequisite because a false identity can persist a
  wrongly assigned document.
- **Heading residual risk.** Conservative item-level matching can miss a
  heading merged with body prose or a heading Docling classifies outside the
  accepted labels. Such text remains in the neighboring segment rather than
  being split speculatively. Expand the parser only when additional real
  samples demonstrate a safe boundary signal.
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
