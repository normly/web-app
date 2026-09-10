# Semantic Search Threshold and Index — Design

## Problem

Two query sites use pgvector's `cosine_distance` with no distance threshold,
only a `LIMIT`:

1. Document search Tier-2 (semantic fallback), in
   `search_works_for_jurisdiction`
   (`core/src/normly_core/graph/postgres/repositories.py:784-785`) — orders
   by `DocumentEmbeddingORM.vector.cosine_distance(query_vector)`, limited to
   `_SEMANTIC_CANDIDATE_POOL = 200`.
2. Chat segment search,
   `find_similar_segments_for_jurisdiction`
   (`core/src/normly_core/graph/postgres/repositories.py:1640-1667`) — orders
   by `EmbeddingORM.vector.cosine_distance(query_vector)`, limited to the
   caller's `limit` (default 5). Called from
   `chat/src/normly_chat/synthesis.py`'s `build_synthesis_answer`, which
   already has a `if not segments: return _fallback(language)` path for an
   empty result.

`cosine_distance` returns 0 (identical) to 2 (opposite). With no threshold,
both sites always return their top-N nearest rows *no matter how distant*,
so "no relevant match" is structurally unreachable once enough rows exist —
a nonsense query returns confidently-presented, irrelevant results instead
of "nothing found."

Additionally, `document_embedding` (migration `0025_create_document_embedding.py`)
and `embedding` have no vector index — every such query is an exact KNN via
full table scan. Harmless today (corpus is tiny — 2 real fixture PDFs), but
would degrade as the corpus grows.

## Goals

- Make "no good match" a reachable, correct outcome at both query sites.
- Add an approximate-nearest-neighbor index to both vector columns so query
  cost doesn't scale linearly with corpus size as ingestion grows it.
- Values are explicit, documented starting points — not derived from
  real-corpus measurement, since the real corpus doesn't exist yet at
  meaningful scale.

## Design

### Two separate thresholds

Document search and chat segment search get **independent** threshold
constants, not one shared value — they serve different purposes with
different tolerances: document search is a fallback tier feeding a ranked
results *list* the user visually scans (a borderline-relevant document
low in the list is low-cost noise), while chat segment search feeds
passages directly into an LLM-synthesized answer presented as fact (an
irrelevant passage there produces a wrong-sounding confident answer, which
is worse than "no results").

```python
# core/src/normly_core/graph/postgres/repositories.py, near _SEMANTIC_CANDIDATE_POOL
_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE = 0.6

# near find_similar_segments_for_jurisdiction
_CHAT_SEGMENT_MAX_COSINE_DISTANCE = 0.75
```

Both are named module-level constants (not environment variables) — no
deployment-time reason to vary them yet, and a constant is one line to
change later once real query logs exist to tune against. Both carry a
comment stating they're starting points pending real corpus/usage data, not
values derived from measurement.

Applied as a `.where(...)` clause added to each query (not a post-filter in
Python — keeps it a single indexed query):

```python
.where(
    DocumentEmbeddingORM.vector.cosine_distance(query_vector)
    <= _DOCUMENT_SEARCH_MAX_COSINE_DISTANCE
)
```

```python
.where(
    EmbeddingORM.vector.cosine_distance(query_vector)
    <= _CHAT_SEGMENT_MAX_COSINE_DISTANCE
)
```

Chat's existing `if not segments: return _fallback(language)` in
`synthesis.py` already handles the now-reachable empty-result case
correctly with no changes needed there. Document search's Tier-2 becomes
"zero or more" results merged into `ordered_documents`, same as it already
handles zero rows from a narrow `issuer` filter today — no behavioral
change needed at that call site either, since it already tolerates an empty
Tier-2 result.

### Index: HNSW

Both `document_embedding.vector` and `embedding.vector` get an HNSW index
(pgvector's `vector_cosine_ops` operator class, matching `cosine_distance`
usage), not IVFFlat. HNSW builds incrementally as rows are inserted — index
quality doesn't depend on how much data existed *at build time*, unlike
IVFFlat, which clusters against whatever data is present when the index is
built and needs periodic `REINDEX` as the table grows past what the
original clustering represented well. Given the corpus starts at 2
documents and grows via ongoing ingestion (no bulk-load moment where an
IVFFlat build would have enough data to cluster well), HNSW avoids a reindex
maintenance task entirely.

New Alembic migration (DDL change, unlike the previous batch's `onupdate`
fix) adding both indexes:

```python
def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_document_embedding_vector_hnsw ON document_embedding "
        "USING hnsw (vector vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_embedding_vector_hnsw ON embedding "
        "USING hnsw (vector vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_embedding_vector_hnsw")
    op.execute("DROP INDEX ix_document_embedding_vector_hnsw")
```

Default HNSW build parameters (`m=16, ef_construction=64`) are used — no
tuning inputs exist yet (no real corpus, no measured recall/latency
tradeoff), so overriding the defaults would be speculative.

## Out of scope

- No configurable/per-request threshold override.
- No HNSW parameter tuning (`m`, `ef_construction`, `hnsw.ef_search`) — left
  at pgvector's defaults until real query data justifies tuning.
- No change to `_SEMANTIC_CANDIDATE_POOL` or the chat `limit` default — the
  threshold and the candidate-pool size are independent controls (pool size
  bounds query cost before filtering; the threshold decides relevance after
  it).

## Testing

- Unit tests seed a handful of deliberately-placed synthetic embeddings
  (e.g. one at distance ~0 from the query vector, one at ~0.5, one at
  ~0.9) directly via the repository, independent of any real corpus/adapter
  — proving the cutoff logic itself, not corpus quality:
  - Document search: a query near an embedded document returns it; a query
    far from every embedded document returns an empty Tier-2 result (not an
    error, not an arbitrary nearest match).
  - Chat segment search: same shape — a near match returns; a far query
    returns an empty list, and (at the `chat/` integration level, if a test
    exists there) `build_synthesis_answer` falls back correctly.
- Migration: the existing migration-history test (verifies every revision
  applies cleanly in sequence) covers the new migration automatically; no
  new test needed beyond confirming `alembic upgrade head` / `downgrade -1`
  round-trips cleanly, which that suite already does for every migration.
