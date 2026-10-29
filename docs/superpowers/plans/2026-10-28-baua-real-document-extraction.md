# Handover: BAuA real-document extraction and chunking

## Goal

Improve `BauaAdapter` so real BAuA PDFs are identified and split into useful
numbered sections, while retaining synthetic fixtures as the deterministic
default test suite. Real-document validation must be opt-in and must use PDFs
kept outside the repository.

## Branch and safeguards

- Work on branch `real-baua-test-documents`, based on `develop` at
  `2336847`.
- A worktree-specific `pre-push` hook blocks pushes from this worktree. It is
  an accidental-push safeguard, not an unremovable security boundary.
- Manually downloaded PDFs are in `/tmp/opencode/baua-review/`. Do not add,
  copy, or commit them to the repository. Do not emit extracted full text into
  logs or test artifacts.
- The current worktree was clean when this plan was written.

## Observations so far

- `core/src/normly_core/pipeline/adapters/baua.py` currently assumes the first
  Docling text item contains the designation, and `extract_structure()` returns
  one full-text section with no heading.
- A local, offline spot-check of six PDFs completed in memory using Docling
  2.132.0. All six failed the current first-item designation match; five had a
  designation-like item later in Docling's item sequence, while one had no such
  item. Docling also emitted `section_header` items in these documents, but the
  relationship between those labels and actual numbered headings has not yet
  been validated item by item.
- `uv.lock` pins Docling 2.135.0, so the 2.132.0 observations are exploratory;
  validate behavior against the locked version before treating parser
  boundaries as stable.
- `RawRecord.raw_designation` is required. The identity resolver already
  routes an empty/unparseable designation to manual identity review, which is
  preferable to persisting cover text as a false identity.
- `RawSection` supports nullable headings. The DGUV parser is a useful pattern
  for conservative source-specific parsing, but its `§` rules and reference
  extraction must not be copied into BAuA.

## Proposed implementation

1. **Characterize real samples.** Inspect only structural metadata: page
   provenance, Docling item labels, designation-match locations, and heading
   candidate counts. Do not print or store extracted text. Include full rules,
   amendments/attachments, and available series. Use the locked Docling version
   where possible.
2. **Identify documents from bounded front matter.** Search a small,
   empirically chosen front-matter range for a standalone TRGS/TRBS/TRBA
   designation. Do not search arbitrary body text or accept a filename as
   identity; a recognized filename may only narrow candidates that are also
   present in the extracted front matter. Extract a title only when its
   boundary is confident. If no designation is found, emit an empty
   designation so the existing identity
   review path blocks downstream ingestion; do not substitute the first text
   item.
3. **Create BAuA-specific sections.** Use Docling's section-header label only
   where verified against actual numbered headings, supplemented by a
   conservative pattern for standalone numbered headings (`1`, `1.1`, etc.).
   Avoid splitting ordinary numbered prose. Preserve ambiguous text rather
   than inventing a boundary. Preserve preamble before the first heading in its
   own heading-less section; if no headings are found, retain the full document
   in one section. Keep `RawSection` and the shared database schema unchanged.
4. **Test in two modes.** Keep current synthetic tests and add synthetic edge
   cases for front matter, nested headings, merged text, no-heading documents,
   and preamble preservation. Add a separate local-only real-document test
   module, gated by an environment variable such as
   `BAUA_REAL_DOCUMENTS_DIR=/tmp/opencode/baua-review`; it is skipped when unset
   and uses no committed PDF fixtures. Assert structural invariants and
   designation handling without embedding full-text excerpts.
5. **Verify before larger ingestion.** Run the synthetic adapter suite in the
   repository's locked environment, then run the opt-in local check offline.
   Keep the first real check in memory. A database-backed run is separate and
   requires encrypted local storage.

## Acceptance criteria

- Synthetic tests remain the default and pass without BAuA PDFs.
- Real-document checks are opt-in, read only from the supplied local directory,
  and are skipped when the directory is not configured.
- The adapter no longer promotes cover/page furniture to `raw_designation`;
  unidentifiable documents remain blocked for manual identity review.
- Numbered BAuA sections are split only on strong evidence, in document order,
  without dropping preamble or body text.
- Docling full text is never included in logs, committed fixtures, or generated
  repository artifacts.

## Rights and storage boundary

The PDFs remain local and are not pushed or redistributed. The BAuA website's
rights notice and the existing category-A source classification are in tension;
this parser plan does not resolve that legal question or change the adapter's
rights classification. Do not use a persistent database for the real-document
check unless the required encrypted local storage is available and the rights
gate permits that processing.

## Implementation status

- Implemented bounded front-matter designation discovery, with a filename
  designation used only as a hint corroborated by extracted text. Missing or
  conflicting identities are left empty for the existing manual-review path.
- Implemented conservative numbered-section segmentation using Docling item
  labels, including a heading-less preamble segment and a full-text fallback.
- Added synthetic tests and an opt-in real-document module that asserts
  expected designations and first/last headings for `TRGS-401.pdf` and
  `TRGS-402.pdf`, plus a fail-closed check for `TRGS-001.pdf`; the PDFs
  themselves remain outside the repository.
- With the available Docling 2.132.0 environment, the synthetic adapter suite
  passes (21 passed, 2 opt-in checks skipped), and the explicit local run
  passes the real designation, first/last section-heading, and
  unresolved-identity checks (3 passed). The locked Docling 2.135.0 run remains
  to be verified.
- No persistent database was used, and no rights-classification behavior was
  changed.
