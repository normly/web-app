# Core review notes: BAuA extraction and retrieval

This guide covers the current BAuA extraction work and its path through
section storage, embeddings, and semantic retrieval. It supplements, but does
not replace, [`CONTRIBUTING.md`](../CONTRIBUTING.md) or the authoritative
requirements and architecture documents.

## Test strategy

### Synthetic tests: default and CI-safe

- Keep ordinary adapter tests synthetic. The tests in
  [`tests/pipeline/test_baua_adapter.py`](tests/pipeline/test_baua_adapter.py)
  generate small BAuA-shaped PDFs at test time in pytest's temporary directory;
  use this approach for new parser cases rather than committing PDF files.
- For extraction-to-retrieval coverage, extend the synthetic approach through
  `run_adapter()` and the PostgreSQL repositories: verify the section rows and
  their embeddings are stored, then verify a query retrieves the expected
  synthetic section. The shared `db_session` fixture uses a disposable
  pgvector PostgreSQL container and requires Docker.
- A deterministic test embedder may be used for this integration test. It
  should make the expected synthetic query/section pair rank predictably and
  keep unrelated fixture text separate. This checks ingestion, persistence,
  and similarity-search wiring; it does **not** establish that the production
  embedding model understands semantic similarity.
- The existing
  [`tests/graph/test_segment_similarity_search.py`](tests/graph/test_segment_similarity_search.py)
  covers database ranking and rights/model filters with controlled vectors.
  Keep that focused repository coverage alongside any pipeline-level test.
- Run the core suite from the repository root with `(cd core &&
  ../.venv/bin/pytest)`, as documented in the contribution guide.

### Required local validation against original BAuA PDFs

For every change to the BAuA adapter, its section extraction/chunking, or a
related domain interface used by that adapter, run the opt-in real-document
checks against the original local samples before treating the change as
verified. The samples are `TRGS-401.pdf`, `TRGS-402.pdf`, and `TRGS-001.pdf`.
If those local samples are unavailable, record this validation as outstanding;
do not substitute synthetic tests and report the real-document check as
passed.

The opt-in checks are in
[`tests/pipeline/test_baua_adapter_real.py`](tests/pipeline/test_baua_adapter_real.py).
They currently check extracted designations and first/last section headings,
plus that the unresolved-identity sample remains unresolved. They test
extraction only: they do not write to a database, generate embeddings, or test
semantic retrieval.

Run them from the repository root, setting the directory that contains the
local PDFs:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
BAUA_REAL_DOCUMENTS_DIR=/tmp/opencode/baua-review \
PYTHONPATH=core/src \
.venv/bin/pytest core/tests/pipeline/test_baua_adapter_real.py -vv
```

The real-document test stages temporary symlinks and does not copy the PDFs
into the repository. Keep the originals outside the repository and out of CI;
do not add PDFs or extracted full text to tests, fixtures, logs, or review
artifacts. The source must have an applicable legal classification before it
is processed, consistent with the repository's data-source rules.

### Real embedding-model checks

Do not make ordinary CI tests download the embedding model from Hugging Face.
Use deterministic synthetic embeddings to test persistence and retrieval
plumbing in CI. That is not a semantic-quality test.

When validating actual embedding quality locally, use the configured local
model artifact (`NORMLY_EMBEDDING_MODEL_PATH`) and a synthetic query/document
pair. Keep this validation separate from the required original-PDF extraction
check: the real-document test currently does not exercise the model or
database. CI and production must use model artifacts provisioned before
runtime, in line with the repository-wide model-provider restriction.
