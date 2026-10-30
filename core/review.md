# Core review and testing

Supplements [`CONTRIBUTING.md`](../CONTRIBUTING.md) and the authoritative
requirements and architecture documents.

## Review and tests

- For adapter or shared-pipeline changes, update every affected
  [adapter status note](../docs/guide/adapters/index.md), including coverage,
  evidence, open work, and review date. Use the
  [template](../docs/guide/adapters/TEMPLATE.md) for new notes.
- Consult that note for required checks. Report unavailable checks as
  outstanding; synthetic tests do not replace real-source validation.
- Generate synthetic test inputs; never commit publisher PDFs or extracted
  full text. Process source material only under its registered legal basis.
- For pipeline/database changes, exercise the runner and repositories as
  appropriate. `db_session` uses disposable PostgreSQL with pgvector and needs
  Docker. Deterministic embeddings test plumbing, not semantic quality; keep
  the focused
  [similarity-search tests](tests/graph/test_segment_similarity_search.py).
- Run the Core suite from the repository root: `(cd core && ../.venv/bin/pytest)`.

## Adapter test layers

Use the layers appropriate to each source; the linked
[adapter status notes](../docs/guide/adapters/index.md) specify its fixtures
and required commands:

- **Unit:** test parsing and mapping with controlled inputs.
- **Synthetic integration (CI):** generate safe fixtures and pass them through
  the production extractor and adapter to check domain outputs. Never put
  publisher documents or full text in CI.
- **Pipeline integration:** when persistence or retrieval changes, test the
  runner and repositories. Deterministic embeddings validate wiring, not
  semantic quality.
- **Real-source canaries (local):** where authorized samples are available,
  test source-specific extraction behavior locally. Reuse assertions shared
  with synthetic fixtures where possible. Report missing or skipped required
  checks as outstanding; synthetic tests are not substitutes.

## Embedding models

CI must not download the embedding model. Use deterministic vectors for
ingestion/retrieval plumbing; assess semantic quality locally with the
pre-provisioned `NORMLY_EMBEDDING_MODEL_PATH` artifact and a synthetic
query/document pair. CI and production must have model artifacts available
before runtime.
