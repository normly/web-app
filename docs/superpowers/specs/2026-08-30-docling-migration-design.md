# Design: Switching from pdfplumber to Docling

## Context

The ingestion pipeline (`docs/superpowers/specs/2026-08-14-ingestion-pipeline-design.md`)
currently uses `pdfplumber` for PDF extraction in exactly two adapters:
`DguvAdapter` (plain full text, rule-based §-structure detection via regex)
and `EurLexAdapter` (pure table extraction, no structure). Both call
pdfplumber directly inline in `fetch()` — there is no
abstraction layer in between.

No ADR justifies the choice of pdfplumber; there is accordingly no
documented prior decision that would have to be overruled here.

**Driver for the switch:** future-proofing. DGUV and EUR-Lex currently run
satisfactorily with pdfplumber, but considerably more sources will follow
— further standardization bodies with unknown, partly more complex
layouts, possibly scanned/image-based documents. pdfplumber offers
no document understanding for that, only text and table access.
[Docling](https://github.com/docling-project/docling) (MIT-licensed,
LF AI & Data Foundation, originally IBM Research) provides a
structured `DoclingDocument` with detected headings, sections
and tables, based on a layout detection model and TableFormer
for table structure — both part of the standard pipeline, not just optional
extras.

**Checked empirically, not just assumed:** during the design phase,
Docling (version 2.123.1) was actually run against the two real fixture PDFs
(`core/tests/fixtures/dguv_sample_vorschrift.pdf`,
`eur_lex_machinery_summary.pdf`) in order to verify assumptions about the
actual API and the actual classification behavior instead of
guessing them. The concrete findings directly shape the architecture
and non-goals below.

## Goal of this sub-project

- Replace pdfplumber completely with Docling — in both existing
  adapters, not just for future new sources.
- Introduce a shared Docling extraction layer that is reusable for any
  future adapters without them having to duplicate Docling configuration.
- Switch DGUV's structure detection from manual `.splitlines()` on raw text
  (with all the line-break quirks that pdfplumber brings along) to
  Docling's clean text segmentation — the boundary detection itself
  stays pattern-based (see "Empirical finding" under Architecture, which
  corrected this decision during the design phase).
- Record a documented, repeatable decision procedure with
  which every future adapter can check for itself whether Docling's native
  element classification (`SectionHeaderItem` etc.) works reliably for its source,
  or whether pattern-based boundary detection is needed
  — not just for DGUV/EUR-Lex, but as a reusable procedure.
- Ensure that Docling model weights are **never** fetched over the
  network at runtime (STACKIT-only requirement from `CLAUDE.md`) —
  obtained once at image build, not during operation.

## Non-goals

- **No generic, configurable structure-mapping layer** between
  `DoclingDocument` and the domain objects (`RawRecord`/`RawSection`). With
  currently two very different source forms (running-text-with-
  headings vs. pure table), a "universal" mapping would be
  guessed now, not derived — the ingestion spec has already deliberately rejected a generic,
  configuration-driven adapter once (YAGNI).
  Each adapter remains responsible for its own small mapping logic.
- **No OCR activation** for scanned/image-based PDFs in this
  sub-project. Neither DGUV nor EUR-Lex needs it today; it will only be
  specified when a concrete future source actually needs it.
  **Important, empirically confirmed:** Docling's standard pipeline runs OCR
  automatically, even on pure vector text without any image — the
  `docling_extraction` layer **must** set `PdfPipelineOptions(do_ocr=False)`,
  otherwise Docling downloads additional OCR models from
  **modelscope.cn** on the first run (not Hugging Face — a second, previously
  unconsidered external model source that must not be reachable at runtime
  either).
- **No blind trust in Docling's semantic element classification**
  without an empirical check against a real sample file of the respective
  source. See "Empirical finding" under Architecture — the classification
  is demonstrably not reliable for every source.
- **No switch to Docling's VLM pipeline** (`granite_docling` or similar). The
  standard layout model plus TableFormer is sufficient for today's
  requirements; a VLM would be a considerably heavier dependency and
  operations profile without a current need.
- **No change to ADR-008** (graph-first query processing, no
  language model at query time for structural questions). That decision
  concerns query time exclusively and remains untouched — see
  ADR-018 below for the delimitation.

## Architecture

New, shared layer: `core/src/normly_core/pipeline/docling_extraction.py`.
It encapsulates the Docling configuration (model path, `TableFormerMode`) in
one place and provides a function that returns a
`DoclingDocument` from a file path — format-independent, since Docling's
`DocumentConverter` detects the source format itself (PDF today, DOCX/HTML/etc.
without additional effort for future sources that are not PDF).

Each adapter remains responsible for translating the `DoclingDocument` into its own
domain objects:

- **DGUV** runs over the detected section/heading nodes.
- **EUR-Lex** reads `DoclingDocument.tables` position-based, as before.

This matches the existing architecture principle from the ingestion spec
("adapter-specific dependencies stay in the respective adapter"), but
lifts the actual Docling mechanics (model configuration, error paths) to
a reusable level — a third, fourth, ... adapter does not
duplicate them again.

### Empirical finding: Docling's element classification is not always reliable

During the design phase, Docling (2.123.1) was run directly against the real
DGUV fixture, with the following reproducible result:

```
[TextItem]        level=1 text='DGUV Vorschrift 1 Grundsätze der Prävention'
[ListItem]         level=2 text='§ 1 Geltungsbereich'
[TextItem]        level=1 text='Diese Vorschrift gilt für alle Unternehmen und Versicherte.'
[ListItem]         level=2 text='§ 2 Pflichten des Unternehmers'
...
```

The `§ N ...` headings come back as `ListItem`, **not** as
`SectionHeaderItem` — reproducibly, also with `do_ocr=False`. Docling
apparently classifies them as numbered list entries because there are no
visual distinguishing features (larger font, bold, spacing)
by which its layout model could recognize a real heading.
This is plausibly not a fixture artifact but real behavior with
plainly formatted German administrative/legal texts — the originally
assumed expectation "Docling detects structure automatically for every future source"
cannot be met for this document type, regardless of the
implementation.

**Consequence for DGUV:** `extract_structure()` continues to iterate over
Docling's segmented text elements (`document.iterate_items()`) — that is
already a real gain over pdfplumber, since Docling does the
line splitting more cleanly than manual `.splitlines()` on raw
text. The decision "is this element a section boundary", however, stays
pattern-based (the same `§ N` regex as today), applied per element
instead of on a raw text blob — **not** Docling's semantic
classification (`SectionHeaderItem` vs. `ListItem` vs. `TextItem`).

### Decision procedure for future adapters

So that this finding does not have to be painstakingly rediscovered for every new source,
the same documented procedure applies to every future adapter:

1. **Run Docling against a real sample file of the new source**
   (do not guess, do not extrapolate from DGUV/EUR-Lex) and
   inspect `document.iterate_items()`.
2. **Check whether the source's actual headings reliably come back as
   `SectionHeaderItem`:**
   - **Yes** — the adapter can build directly on
     `isinstance(item, SectionHeaderItem)`; Docling's automatic
     structure detection actually works for this source as
     originally hoped.
   - **No** (as with DGUV) — the adapter still iterates over Docling's
     segmented elements, but decides "is this a boundary" via a
     source-specific text pattern, following exactly the same pattern as
     `DguvAdapter.extract_structure()`.
3. **This behavior is pinned down by a test against a real fixture file
   of the new source**, not just checked manually once —
   so that a future Docling version change that alters the
   classification behavior shows up in the test instead of silently producing
   wrong (empty) structure in production. Task template: a test
   that calls `document.iterate_items()` against the fixture and explicitly
   asserts the expected element kind of the known headings — if
   the test breaks on a future Docling update, that is a deliberate
   signal, not a silent behavior change.

## Components

| File | Change |
|---|---|
| `core/src/normly_core/pipeline/docling_extraction.py` | **New.** Encapsulates the `DocumentConverter` call with `do_ocr=False` and a local `artifacts_path`, a uniform error class for broken/unreadable files. |
| `core/src/normly_core/pipeline/adapters/dguv.py` | `fetch()` uses the new layer instead of `pdfplumber.open()`, iterates `document.iterate_items()` instead of `page.extract_text()` + `.splitlines()`. `raw_designation`/`raw_title` separated by pattern from the first element (see Data flow). `extract_structure()` continues to run pattern-based (`§ N` regex) — now applied per Docling element instead of on a raw text blob (see "Empirical finding" under Architecture: Docling's `SectionHeaderItem` classification is not reliable for this document type, `§ N` lines come back as `ListItem`). |
| `core/src/normly_core/pipeline/adapters/eur_lex.py` | `_fetch_file()` uses the same layer, reads `table.data.grid` (2D list of `TableCell`, `.text` attribute per cell) instead of `page.extract_tables()`. The column index logic (`_COLUMN_ESO` etc.) stays unchanged — empirically confirmed identical column order. The `.startswith("ESO")` workaround for embedded line breaks is dropped: Docling's cells contain no line break (`"ESO (B)"` instead of pdfplumber's `"ESO\n(B)"`), a simple comparison is sufficient. |
| `core/pyproject.toml` | `pdfplumber` removed, `docling` as a new dependency (set the version range during implementation against the stable version current at that time). |
| Build/CI (Dockerfile or pipeline definition) | New step: obtain the Docling model weights once (`docling-tools models download` or equivalent) and bake them into the image. No network access to Hugging Face at runtime. Model updates will in future run by re-executing this step on Docling version updates, not automatically. |
| `docs/adr/README.md` | New entry ADR-018 (see below). |

## Data flow

- **DGUV:** file → `docling_extraction` → `DoclingDocument` → the adapter
  iterates `document.iterate_items()`, collects element texts, applies the
  `§ N` regex per element to detect section boundaries (pattern-based,
  not Docling's element type classification — see Architecture). From this it builds
  `RawSection` objects (title = text of the boundary-setting element, content =
  text of the following elements up to the next boundary).
  **Further empirically confirmed deviation:** Docling merges visually
  adjacent lines into one block — the designation and
  title lines of the fixture ("DGUV Vorschrift 1" / "Grundsätze der
  Prävention", two separate lines in the PDF) come back as **one** element,
  not as two. `raw_designation`/`raw_title` are therefore separated from
  the first element by pattern (`^(DGUV Vorschrift \d+)\s*(.*)$`),
  not by index access to two separate elements.
- **EUR-Lex:** file → `docling_extraction` → `DoclingDocument` → the adapter
  iterates `.tables`, continues to read cells position-based via `table.data.grid`,
  builds `RawRecord`s. `extract_structure()` stays `[]`
  (no structure for pure catalog data — unchanged from today).

### Decision: deliveries already ingested from the pdfplumber era

`run_adapter()` skips a source file whose content hash is already recorded as a
delivery. This hash describes only the source file, not
the extraction engine — a change of engine therefore triggers **no** renewed
extraction. Already ingested collections thus keep their
pdfplumber provenance, while new deliveries go through Docling: a
corpus of mixed provenance.

Decided for this migration: there is no production collection yet,
only a development database. Its content is **reset manually
and the ingestion re-run completely**; the result is a corpus of
purely Docling-based provenance. A backfill or
re-extraction mechanism is deliberately **not** built for this — it would
have no collection to apply to today.

To be reassessed as soon as a real production collection exists and an
engine change has to happen without a complete re-ingestion. That will require
an explicit mechanism (for instance the extraction engine and version as
part of the delivery lineage, plus a targeted re-extraction run) —
this decision is deliberately deferred here, not overlooked.

## Error handling

- Broken/unreadable file: Docling raises its own exceptions. The
  `docling_extraction` layer catches them and raises a normly-specific,
  adapter-independent error class — both of today's adapters and all future
  adapters handle the same error path uniformly, instead of
  passing Docling exceptions straight through.
- Missing model weights at runtime (should not occur thanks to image baking,
  but to be safeguarded defensively): a clear, immediate error instead of
  a silent attempt to download models. Docling must never attempt
  network access to a model repository during operation.

## Test concept

- Existing fixture tests (`test_dguv_adapter.py`, `test_eur_lex_adapter.py`)
  run unchanged against the same fixture PDFs. Since they check
  adapter output (not pdfplumber internals), they are a real
  regression safeguard for the switch — assertions stay unchanged,
  since the adapter output (designation, title, section boundaries) stays the same with
  the same pattern-based approach.
- EUR-Lex's column/line-break quirk is **empirically resolved**:
  Docling's cells no longer contain an embedded line break
  (`"ESO (B)"` instead of pdfplumber's `"ESO\n(B)"`), column indexes have
  stayed identical (verified against the real fixture). The
  `.startswith("ESO")` workaround can be simplified as soon as this is confirmed against
  the final adapter code.
- The DGUV test fixture generated at runtime via `reportlab` is
  **empirically confirmed** to be read correctly by Docling (conversion
  `ConversionStatus.SUCCESS`, all text lines arrive) — the
  headings only come back with a different element type than originally
  assumed (see Architecture), no readability problems.
- **New test per adapter (part of the decision procedure above):** calls
  `document.iterate_items()` against the real fixture and explicitly asserts
  the actual element kind of the known headings (for
  DGUV: `ListItem`, not `SectionHeaderItem` — this is a deliberate,
  documented assertion, not an accidental finding). If this test breaks on
  a future Docling version update, that is a deliberate signal
  that the classification behavior has changed and the
  boundary detection strategy must be reassessed — not a silent
  behavior change that only becomes apparent through empty section lists in production.
- New test, analogous to the existing architecture drift test
  (`test_pipeline_domain_does_not_import_sqlalchemy` in
  `test_architecture.py`): ensures that Docling does not
  try to download models over the network during the test run (e.g. through a
  network block in the test context) — enforces the "no runtime fetch" requirement
  permanently.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-PIPE-001 | Pipeline stages unchanged; only the extraction engine within the structure/reference extraction stage changes. |
| ADR-006 | Untouched — data storage/repository layer does not change. |
| ADR-008 | Untouched in its actual scope (no language model at query time). See ADR-018 for the delimitation: Docling is a deterministic, discriminative layout/table model at **ingestion** time, not a generative language model at query time — the query itself continues to be answered exclusively graph-based. |
| **ADR-018 (new)** | Documents the decision to include ML-based structure detection in the ingestion pipeline — reverses the non-goal explicitly recorded so far in the ingestion spec ("no generic document understanding"). |
| CLAUDE.md, "No US services for operations, build, data, secrets or deployment" (wording at the time) | Docling model weights are obtained once and baked into the image; no runtime access to Hugging Face. The one-time retrieval during the build is a deliberate, documented exception for the build process itself (comparable to obtaining PyPI packages during the build) — operations remain free of US services. |

## Open items / follow-up work

- **Open item, named and tracked: the offline test currently runs
  nowhere.** `core/tests/pipeline/test_docling_offline.py` — the only
  automated proof of the strictest requirement from `CLAUDE.md` (no
  US services in operation, no runtime network access to model sources) —
  is bound to `NORMLY_DOCLING_ARTIFACTS_PATH` via `skipif`. This
  variable is set nowhere in the repository, and a CI does not exist
  yet (deliberately outside the scope of this migration). In every environment
  in which the test suite runs today, the test therefore silently skips itself:
  the requirement currently has **no** automated safeguard. To be fixed
  with the containerization/CI that is planned anyway — there,
  `NORMLY_DOCLING_ARTIFACTS_PATH` must point to the pre-obtained models
  so that the test actually runs instead of continuing to skip.
- The exact Docling version range for `core/pyproject.toml` is set during
  implementation against the stable version current at that time.
- OCR activation for future scanned/image-based sources — deliberately
  deferred until a concrete source needs it (see Non-goals).
- Should a third, fourth source with a structure similar
  to DGUV or EUR-Lex appear in the future, it can be checked whether a real, derived (not guessed)
  mapping abstraction is worthwhile given the several examples then available
  — deliberately not anticipated (see Non-goals).
- **Known, deliberately accepted residual gap in the DGUV heading detection
  (`_is_publication_title_line()` / `_heading_has_a_title()` in
  `core/src/normly_core/pipeline/adapters/dguv.py`).** After five rounds of fixes
  and adversarial re-review, a narrow case remains in which a real
  designation+title line — without sentence-ending punctuation in between —
  is immediately followed by a cross-reference to another standard
  whose introduction consists exclusively of lowercase function words
  (e.g. "in Verbindung mit"). Such introductions do not trigger the
  existing sentence-start/word-list safeguards, so that the
  cross-reference can wrongly be detected as a separate `§ N` section.
  Example that still reproduces the case: "DGUV Vorschrift 1 Grundsätze
  der Prävention in Verbindung mit ArbSchG § 5 Gefährdungsbeurteilung der
  Arbeitsplätze". A further tightening (e.g. a stricter
  upper limit on title length) was deliberately not made, since in return it
  would wrongly reject real, longer DGUV publication titles — a
  worse trade than the remaining narrow residual risk. The gap is
  limited in its effect: `full_text`/`raw_title` keep the
  complete text in every case; the error manifests exclusively as a wrongly
  assigned section (the sentence following the cross-reference lands in the
  fabricated section instead of the one it actually belongs to), never as a loss
  or falsification of content. Follow-up work: during the first real (not
  fixture-based) DGUV corpus acquisition, spot-check whether the case
  occurs in practice, and pick it up again if needed.
