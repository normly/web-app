# BAuA Full-Pipeline Retrieval Test Plan

**Status:** Implemented as a local-only opt-in test; no CI configuration was
changed. Functional local validation passed on 2026-11-06. The local-only
storage exception is documented in ADR-021 and REQ-SEC-001; the execution
record below notes the conditions of the run.

## Goal

Extend the existing local BAuA extraction canaries so the selected real PDFs
from the private test corpus pass through persistence, actual local embeddings,
and retrieval:

```text
private local BAuA PDFs (TRGS-401, TRGS-402, TRGS-001)
  → temporary symlink staging (no PDF copies)
  → current BauaAdapter extraction and sectioning
  → run_adapter
  → actual local embedding model
  → ephemeral PostgreSQL/pgvector test storage (no retained database)
  → actual query embedding and repository retrieval
```

This is a local-only check of adapter-to-storage-to-retrieval wiring and real
model behavior. CI remains synthetic and must not initialize or access the
private data submodule.

## Current coverage on the rebased `develop`

- `core/src/normly_core/pipeline/adapters/baua.py` searches bounded front matter
  for one designation, uses a filename only as a corroborated hint, fails
  closed with an empty designation when identity is unresolved, and splits
  confidently detected numbered headings into `RawSection`s.
- `core/tests/pipeline/test_baua_adapter.py` covers synthetic PDF extraction,
  designation and title handling, sectioning, ambiguity, and fallbacks.
  `baua_test_support.py` shares selected first/last heading canaries between
  generated and local real-document checks.
- `core/tests/pipeline/test_baua_adapter_real.py` already checks designation
  and section extraction for private local samples, but does not run the
  pipeline, write to a database, create embeddings, or retrieve results. The
  full-pipeline test extends those same samples and reuses the heading canaries,
  rather than adding new real PDFs or duplicating extraction assertions.
- `test_main_ingests_a_baua_directory_end_to_end` in
  `core/tests/pipeline/test_cli.py` sends a generated PDF through the CLI and
  checks that its designation is persisted. It does not assert stored sections
  or embeddings, or retrieve a BAuA result.
- Generic runner and similarity-search tests cover persistence and pgvector
  ranking separately. The opt-in local test now covers BAuA persistence and
  retrieval with real samples and embeddings; `docs/guide/adapters/baua.md`
  keeps the separate deterministic CI plumbing test open.

## Local data boundary and cleanup

The test uses only the three BAuA samples already authorized for local testing
in the private `web-app-raw-data` corpus and processes them under the existing
BAuA source-register entry and rights gate (Category A, `DE`). This is not
permission to use other source material or licensed content in development or
testing. The BAuA status note records tension between the website rights notice
and the Category A classification; this plan relies on the current registered
basis and local-test-corpus authorization for these specific samples. Database
cleanup does not broaden those rights. If the source-register basis or corpus
authorization no longer permits this processing, stop.

Database writes are allowed here only as local test state. Use a test-specific
PostgreSQL fixture with `PGDATA` on `tmpfs`, no bind or named database volume,
and container memory/swap limits that prevent the database container from
swapping. Roll back the test transaction and remove the container and any
anonymous volume on both success and failure. Do not create dumps, backups,
logs, or other artifacts containing source text or embeddings. The local-only
storage exception permits the source corpus and directly derived test state to
reside on contributor-controlled developer machines in Europe, including local
disk and host-managed swap; it does not permit reuse in CI, logs,
public/production artifacts, production, or backups.

Keep the private source PDFs in the submodule only. Do not copy them into this
repository, CI, Docker images, logs, or public artifacts. Do not print extracted
full text or use assertions that cause pytest to display it. Teardown removes
the explicit database container and temporary symlinks; the host operating
system may retain pages in swap, which is permitted only within the local-test
storage exception and is not a substitute for test cleanup.

## Local-only implementation

1. Add `core/tests/pipeline/test_baua_full_pipeline_local.py`, following the
   opt-in pattern in `test_baua_adapter_real.py`. Require both
   `NORMLY_RUN_LOCAL_BAUA_PIPELINE_TEST=1` and
   `BAUA_REAL_DOCUMENTS_DIR`. With either unset, ordinary local and CI runs must
   skip before loading models or opening the database fixture. If explicitly
   enabled but a required sample is missing, fail clearly rather than silently
   skipping it. Provide a test-specific `db_session` fixture backed by the
   ephemeral PostgreSQL configuration above; do not use disk-backed storage
   for these real samples.
2. Initialize the private submodule from the repository root and point
   `BAUA_REAL_DOCUMENTS_DIR` at `web-app-raw-data/raw_data_test/BAuA`. This
   requires authorized read access to `normly/web-app-raw-data`. Do not
   initialize the submodule in CI.
3. Before database ingestion, run the existing opt-in extraction canaries with
   the locked Docling version and require all three samples to pass with zero
   skips. Use the actual `TRGS-401.pdf`, `TRGS-402.pdf`, and `TRGS-001.pdf`
   from the submodule; do not fetch more PDFs.
4. For the pipeline run, stage temporary symlinks in `tmp_path` with the
   adapter's expected names (`baua_trgs_401.pdf`, `baua_trgs_402.pdf`, and
   `baua_trgs_001.pdf`). Do not copy the PDFs. Build the adapter with
   `build_adapter("baua", directory=tmp_path, session=db_session)` so the
   existing BAuA source-register entry and its Category A / `DE` classification
   are used; do not substitute a generic test source.
5. Require `NORMLY_EMBEDDING_MODEL_PATH` and
   `NORMLY_DOCLING_ARTIFACTS_PATH` to point to existing, locally provisioned
   artifact directories. Run with `HF_HUB_OFFLINE=1` and
   `TRANSFORMERS_OFFLINE=1`; never fall back to hosted model IDs or download
   artifacts during the test.
6. Pass the adapter to `run_adapter(adapter, db_session)` without replacing
   embedding computation with deterministic vectors. Load one real
   `EmbeddingModel` and reuse that instance for passage and query embeddings to
   avoid loading the large model twice. If needed, patch only the runner's
   constructor to return this real model instance.
7. Assert through repositories that TRGS-401 and TRGS-402 have their expected
   documents, stored sections, and segment embeddings under `MODEL_NAME`. Reuse
   the shared first/last heading canaries from `baua_test_support.py` to check
   the persisted section boundaries. Inspect stored vector dimensions (1024)
   and non-zero values without printing vector contents or source text.
8. Treat TRGS-001 as the fail-closed control: its unresolved designation must
   be sent to identity review and must not create a document, segment, or
   embedding. Do not assert on, log, or display its extracted full text.
9. Use the real model's `embed_query()` with a short synthetic query targeted
   at a known heading canary, then call
   `PostgresSegmentRepository.find_similar_segments_for_jurisdiction()` with
   `MODEL_NAME`, jurisdiction `DE`, and a top-five limit. Assert retrieval
   using segment IDs and sample names only, not object representations that
   might expose text. Avoid brittle exact-distance or unrelated-result ordering
   assertions; this remains a retrieval canary, not a semantic-quality test.

The test must use the existing repository interfaces for persistence and
retrieval. It must not use a production database, add SQL to pipeline/domain
logic, start API/chat services, or call an external LLM. Docker is required for
the disposable pgvector test database.

## Prepare the local model artifacts

The test needs both the E5 embedding weights and Docling's PDF layout models.
Prepare them once before the test; model retrieval is a setup-time action, not
part of test execution. Use the same pinned revisions and directory layout as
the `weights` stage in `docker/python.Dockerfile` (the source of truth if those
revisions change). Do not use the older unpinned `docling-tools models
download` command for this test setup.

The revisions below match the current Dockerfile. Run from the repository root
in the shared `.venv`; this fetches public model artifacts but sends no PDF,
query, or other test data:

```bash
HF_HUB_DISABLE_TELEMETRY=1 .venv/bin/python - <<'PY'
from pathlib import Path

from huggingface_hub import snapshot_download

root = Path("/tmp/opencode/baua-full-pipeline-models")

snapshot_download(
    repo_id="intfloat/multilingual-e5-large",
    revision="3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3",
    local_dir=str(root / "multilingual-e5-large"),
    ignore_patterns=[
        "onnx/*", "openvino/*", "pytorch_model.bin", ".eval_results/*", "*.md"
    ],
)

for repo_id, revision in (
    (
        "docling-project/docling-layout-heron",
        "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
    ),
    (
        "docling-project/docling-layout-heron-onnx",
        "40bde044036bb181c130ddf6c51792187268748f",
    ),
    (
        "docling-project/docling-models",
        "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
    ),
):
    snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=str(root / "docling" / repo_id.replace("/", "--")),
    )
PY
```

Before running the integration test, verify the E5 directory loads without
network access and produces the expected vector dimension:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
NORMLY_EMBEDDING_MODEL_PATH=/tmp/opencode/baua-full-pipeline-models/multilingual-e5-large \
PYTHONPATH=core/src \
.venv/bin/python -c 'from normly_core.pipeline.embeddings import EmbeddingModel; assert len(EmbeddingModel().embed_query("synthetic test query")) == 1024'
```

Verify the Docling directory with the existing offline extraction test; it
blocks socket connections during extraction:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
NORMLY_DOCLING_ARTIFACTS_PATH=/tmp/opencode/baua-full-pipeline-models/docling \
PYTHONPATH=core/src \
.venv/bin/pytest core/tests/pipeline/test_docling_offline.py -v
```

Keep downloaded model directories outside Git. Once prepared, the real-document
pipeline test uses these paths with offline mode enabled, so test execution
requires no model downloads.

## Explicitly deferred: CI plumbing test

The local real-model check above does **not** close the separate CI coverage gap
recorded in `docs/guide/adapters/baua.md`. That note calls for a synthetic
pipeline integration test using deterministic embeddings to verify runner,
database insertion, and retrieval plumbing in CI. Keep that as a distinct
follow-up; it is intentionally not implemented or enabled in CI now. The local
test uses actual samples and actual embeddings; deterministic CI vectors cannot
establish real-model semantic retrieval quality.

## Local invocation

Initialize the private corpus from the repository root when you have authorized
read access (ordinary clones intentionally leave it uninitialized):

```bash
git submodule update --init web-app-raw-data
```

The local-test storage exception permits the authorized private corpus and
directly derived test artifacts on contributor-controlled developer machines
in Europe without at-rest encryption, including local disk and host swap. It
does not permit the corpus or derivatives in CI, logs, public/production
artifacts, production, or backups. The existing source-registration and rights
gate still apply; this storage exception grants no additional processing
rights.

Then, from the repository root, first run the existing extraction canaries and
require all three to pass without skips:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
BAUA_REAL_DOCUMENTS_DIR=web-app-raw-data/raw_data_test/BAuA \
PYTHONPATH=core/src \
.venv/bin/pytest core/tests/pipeline/test_baua_adapter_real.py -vv
```

Run the full-pipeline check explicitly, using the test-specific `tmpfs`-backed
database fixture and no persistent database volume:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
NORMLY_RUN_LOCAL_BAUA_PIPELINE_TEST=1 \
BAUA_REAL_DOCUMENTS_DIR=web-app-raw-data/raw_data_test/BAuA \
NORMLY_EMBEDDING_MODEL_PATH=/tmp/opencode/baua-full-pipeline-models/multilingual-e5-large \
NORMLY_DOCLING_ARTIFACTS_PATH=/tmp/opencode/baua-full-pipeline-models/docling \
PYTHONPATH=core/src \
.venv/bin/pytest core/tests/pipeline/test_baua_full_pipeline_local.py -v
```

The source PDFs remain in the private submodule and are symlinked only into
temporary staging directories. The test must not initialize the submodule in
CI, create persistent database volumes or dumps, or emit full text in logs or
artifacts.

## Execution record (2026-11-06)

- Added `core/tests/pipeline/test_baua_full_pipeline_local.py` with a
  `tmpfs`-backed PostgreSQL data directory and an opt-in gate. Updated the
  existing real-source canary test to resolve relative corpus paths before
  creating symlinks.
- Prepared the E5 and Docling artifacts at the pinned revisions above. Model
  loading passed in offline mode; the Docling offline test passed.
- The real-source extraction canaries passed: 3 passed, zero skips with locked
  Docling 2.135.0. The full-pipeline test passed: 1 passed. The full Core suite
  passed with the local test opt-in unset: 757 passed, 4 skipped.
- Testcontainers removed the PostgreSQL container after the run, and no
  container based on `pgvector/pgvector:pg16` remained. The host uses an ext4
  filesystem and an active swap file; unencrypted local disk and swap are
  expressly covered by the storage exception adopted in ADR-021 and REQ-SEC-001.
  The exception applies only on developer machines in Europe, and physical host
  location was not independently verified from the available environment
  metadata. The full-pipeline test was rerun after adding equal container memory
  and memory+swap limits and passed (1 passed, 4 Pydantic deprecation warnings).
  The private submodule checkout remains local and uncommitted.

## Out of scope

- Implementing or enabling the separate deterministic CI integration test.
- Retaining database rows, embeddings, dumps, or backups after the local run.
- Downloading model weights or BAuA documents during the test.
- Committing real publication PDFs, extracted full text, embeddings, or database
  dumps.
- Changing adapter behavior, the ingestion runner, embedding model, database
  schema, retrieval API, or BAuA status note.
