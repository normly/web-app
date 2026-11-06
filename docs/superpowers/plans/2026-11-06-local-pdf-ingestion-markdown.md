# Local PDF Ingestion and Docling Markdown Export Plan

**Status:** implemented and verified with authorized local real-source samples
**Requirement context:** REQ-PIPE-001, REQ-PIPE-002, REQ-PIPE-004, REQ-PIPE-006

## Goal

Make local PDF ingestion use the same explicit Docling PDF settings and pinned
runtime as the pipeline image, and let an operator optionally save Docling's
Markdown representation while the adapter is processing the same conversion.
The Markdown is a local diagnostic artifact, not database state or a new
knowledge-base export.

## Design

- Keep shared Docling runtime configuration in
  `core/src/normly_core/pipeline/docling_extraction.py`. The existing module
  already owns converter construction; make its relevant PDF settings explicit
  and test them: OCR off, table structure on with accurate TableFormer and cell
  matching, CPU execution with four threads. Keep source-specific
  interpretation in the adapters. Do not introduce per-adapter Docling
  profiles unless real-source validation later demonstrates a need.
- Run local ingestion through the existing `pipeline` container, built from the
  locked dependencies and pinned model revisions. Its existing `/data` mount is
  the local input/output boundary.
- Add optional `--docling-markdown-dir PATH` to `ingest`. If omitted, behavior
  and database writes remain unchanged. If set, export the Markdown directly
  from the `DoclingDocument` already used by the adapter; do not re-run Docling
  or reconstruct Markdown from database segments.
- Write one UTF-8 `.md` file per source PDF. Include the source file stem and
  full SHA-256 content hash in the filename so artifacts are traceable and
  unchanged inputs overwrite the same path. Write atomically; do not add
  metadata or headers to the Docling Markdown itself.
- The shared Markdown writer requires a rights rule that permits processing
  and free export. Adapters pass the rule they already derive for the record;
  if it does not permit export, no sidecar is written. Source registration and
  adapter-specific rights classification remain mandatory.
- Do not add a database table, migration, generic PDF adapter, or alternate
  persistence path. Existing adapter mapping and repository behavior stay in
  place.

## Local workflow

Use only a source already registered and legally classified, and only input
that is authorized for local processing. The database and Markdown output must
be on encrypted storage or, for the narrow authorized local-test exception,
on a disposable tmpfs-backed test setup. The bundled Compose PostgreSQL named
volume is persistent and is not automatically encrypted. With the database
started and migrated, and source PDFs staged under local `data/`, run:

```bash
docker compose --profile bundled --profile tools run --rm pipeline \
  ingest baua \
  --directory /data/pdfs \
  --docling-markdown-dir /data/docling-markdown
```

The supported source is selected with the existing adapter name (`baua`,
`dguv`, or `eur-lex`). The pipeline image supplies
`NORMLY_DOCLING_ARTIFACTS_PATH`; its Python packages are installed from
`uv.lock`, and the Docling weights are pinned in `docker/python.Dockerfile`.
Use an immutable image/build when comparing runs. Markdown can contain
extracted source content: keep it local, outside Git and CI, and within the
same legal and storage limits as the input. The local-test exception applies
only to the authorized limited corpus and artifacts directly derived by
explicit local tests; it does not permit licensed-content processing or
general-purpose unencrypted storage.

## Implementation tasks

- [x] Make the shared PDF settings explicit in `docling_extraction.py` and add
  a focused test that verifies the converter receives those settings.
- [x] Add a shared, atomic, content-addressed Markdown writer that enforces the
  supplied rights rule.
- [x] Add the optional CLI flag and pass its destination through
  `build_adapter()` to all existing PDF adapters.
- [x] Have each adapter offer the already-converted `DoclingDocument` to the
  writer before yielding its record; verify the writer declines when the
  source's rule does not allow free export.
- [x] Add tests for the writer and CLI behavior, including repeated ingestion:
  Markdown remains reproducible while unchanged deliveries remain
  deduplicated in the database. Compare the actual adapter sidecar byte-for-byte
  with Markdown exported by the same real Docling document.
- [x] Update Core review/status documentation and complete available Core
  checks.

## Acceptance criteria

- The option is opt-in; without it, ingestion creates no Markdown artifacts
  and existing DB behavior is unchanged.
- With it, the output is produced from the exact `DoclingDocument` instance
  used by the adapter, has a source-content-addressed filename, and is written
  atomically under the requested directory.
- A source whose rule does not permit processing and free export produces no
  Markdown artifact.
- Repeating an ingest with the same input and runtime gives the same Markdown
  bytes and does not create duplicate database deliveries/documents.
- No full text is added to logs, CI fixtures, public artifacts, or database
  schema by this feature.
- Tests use generated/synthetic PDFs in CI. Any real-source validation remains
  local, authorized, and outside the repository.

## Verification

Run from the repository root:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/pytest core
uvx --from 'zensical==0.0.60' --with 'mkdocstrings==1.0.6' \
  --with 'mkdocstrings-python==2.0.8' --with 'griffelib==2.3.0' \
  --with 'pymdown-extensions==12.1' zensical build
```

Review `core/REVIEW.md` for any source-adapter-specific validation required by
the adapters touched. Report real-source checks as outstanding if authorized
local samples or model artifacts are unavailable; synthetic tests do not
replace them.

## Implementation status

- Added `--docling-markdown-dir` to the existing ingestion CLI and wired it to
  BAuA, DGUV, and EUR-Lex. The default remains off.
- The sidecar is written atomically with the source SHA-256 in its filename and
  only when the source rule permits processing and free export. The same
  `DoclingDocument` feeds the adapter and Markdown exporter.
- The shared PDF configuration explicitly disables OCR, enables table
  structure extraction with accurate TableFormer and cell matching, and fixes
  CPU execution to four threads. The Docling package stays pinned by `uv.lock`;
  model revisions stay pinned in the pipeline image. Local exploratory cache
  mode is documented as not equivalent to the pinned image.
- Core verification with Hugging Face and Transformers offline and all local
  BAuA checks enabled: **773 passed, 0 skipped**.
- The actual Docling document used by `DguvAdapter` and by all three BAuA
  real-source canaries is captured; the sidecar's SHA-256 is compared with the
  hash of that document's `export_to_markdown()` result without logging text.
- The authorized private `web-app-raw-data` submodule was initialized for the
  local checks. TRGS-401, TRGS-402, and TRGS-001 Markdown equality checks passed,
  as did the tmpfs-backed full-pipeline BAuA test and offline-network test.
- Documentation build completed with the existing three known broken-link
  warnings in older superpowers specifications.
