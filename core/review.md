# Core review and testing requirements

This guide records review and testing requirements for the Core module. It
supplements, but does not replace, [`CONTRIBUTING.md`](../CONTRIBUTING.md) or
the authoritative requirements and architecture documents.

## Test strategy

### Adapter status documentation is required

Every change to an adapter or to a shared interface/behavior that affects an
adapter must update its status note in
[`docs/guide/adapters/`](../docs/guide/adapters/index.md) in the same change.
This includes changes to supported inputs, acquisition, metadata mapping,
identity or section extraction, rights behavior, failure handling, and test
coverage. Update the capability states, requirement mapping, evidence, layout
assumptions, and open-work disposition affected by the change. For shared
pipeline changes, review every affected adapter note. Do not leave a stale
status note on the assumption that the code or tests speak for themselves.
Update the affected note's review/evidence date in the same change even when
the capability state does not change.

Use [`docs/guide/adapters/TEMPLATE.md`](../docs/guide/adapters/TEMPLATE.md) for
new adapter notes. Do not claim an unrun check; if a required validation was
unavailable, record it as outstanding in the adapter note and change review.

### Synthetic tests: default and CI-safe

- Keep ordinary adapter tests synthetic and generate test inputs rather than
  committing publisher documents. Follow the applicable adapter status note
  for format-specific and local-source validation.
- For pipeline, persistence, or retrieval changes, test the affected boundaries
  through the runner and repositories where applicable. The shared `db_session`
  fixture uses a disposable PostgreSQL container with pgvector and requires
  Docker.
- A deterministic test embedder can verify ingestion, persistence, and
  similarity-search wiring. It does **not** establish that the production
  embedding model understands semantic similarity.
- The existing
  [`tests/graph/test_segment_similarity_search.py`](tests/graph/test_segment_similarity_search.py)
  covers database ranking and rights/model filters with controlled vectors.
  Keep that focused repository coverage alongside any pipeline-level test.
- Run the core suite from the repository root with `(cd core &&
  ../.venv/bin/pytest)`, as documented in the contribution guide.

### Adapter-specific validation

Before changing an adapter or a shared interface used by one, consult that
adapter's status note for its required tests and local validation. If required
source-specific checks cannot be run, record them as outstanding; do not
substitute synthetic tests and report the source-specific check as passed.
Keep original publisher documents and extracted full text outside the
repository and CI, and process source material only under its applicable legal
classification.

### Real embedding-model checks

Do not make ordinary CI tests download the embedding model from Hugging Face.
Use deterministic synthetic embeddings to test persistence and retrieval
plumbing in CI. That is not a semantic-quality test.

When validating actual embedding quality locally, use the configured local
model artifact (`NORMLY_EMBEDDING_MODEL_PATH`) and a synthetic query/document
pair. CI and production must use model artifacts provisioned before runtime, in
line with the repository-wide model-provider restriction.
