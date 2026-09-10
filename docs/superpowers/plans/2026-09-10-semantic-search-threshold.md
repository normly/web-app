# Semantic Search Threshold and Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "no relevant match" a reachable outcome at both semantic-search query sites, and add an ANN index to both vector columns so query cost stops scaling linearly with corpus size.

**Architecture:** Two independent `.where(...)` clauses added to two existing repository queries, each gated by its own named distance-threshold constant; plus one new Alembic migration adding an HNSW index to each of the two vector columns. No shared code between the two changes — they only share a spec.

**Tech Stack:** SQLAlchemy Core (`cosine_distance` from pgvector's SQLAlchemy integration), Alembic, pytest against real Postgres.

## Global Constraints

- `_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE = 0.6` and `_CHAT_SEGMENT_MAX_COSINE_DISTANCE = 0.75` — two separate named module-level constants, not one shared value, not environment variables.
- Applied as `.where(...)` clauses on the existing query (not a Python-side post-filter).
- HNSW (not IVFFlat) indexes on `document_embedding.vector` and `embedding.vector`, using pgvector's `vector_cosine_ops` operator class, default build parameters (no `m`/`ef_construction` tuning).
- Out of scope: no configurable/per-request threshold override, no HNSW parameter tuning, no change to `_SEMANTIC_CANDIDATE_POOL` or the chat `find_similar_segments_for_jurisdiction`'s `limit` default.
- DCO `Signed-off-by` via `git commit -s` (added automatically — never type a literal `Signed-off-by:` line), Conventional Commits, every commit ends with a `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
- Repository access only through the repository layer — already satisfied here, both changes live inside existing repository methods.

---

## File Structure

- Modify `core/src/normly_core/graph/postgres/repositories.py`: add both threshold constants; add one `.where(...)` condition each to `search_works_for_jurisdiction`'s Tier-2 query and to `find_similar_segments_for_jurisdiction`.
- Modify `core/tests/graph/test_work_search.py`: one new test proving Tier-2 exclusion beyond the threshold.
- Modify `core/tests/graph/test_segment_similarity_search.py`: one new test proving chat-segment exclusion beyond the threshold.
- Create `core/migrations/versions/0031_add_hnsw_indexes.py`: the new HNSW indexes.

No new production files — both application changes are one-line additions to existing methods; the migration is the only new file.

---

### Task 1: Distance thresholds at both query sites

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py:91` (add `_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE`), `:762-767` (Tier-2 `.where(...)`), `:1596` (add `_CHAT_SEGMENT_MAX_COSINE_DISTANCE` just above the class), `:1690-1696` (`find_similar_segments_for_jurisdiction`'s `.where(...)`)
- Test: `core/tests/graph/test_work_search.py`, `core/tests/graph/test_segment_similarity_search.py`

**Interfaces:**
- Consumes: nothing from another task.
- Produces: nothing a later task consumes — Task 2 (the migration) is independent.

- [ ] **Step 1: Write the two failing tests**

Open `core/tests/graph/test_work_search.py`. Add this test after the existing `test_semantic_tier_finds_a_document_with_no_exact_text_match` (which ends at line 101 with `assert hits[0].best_match.id == document.id`):

```python
def test_semantic_tier_excludes_a_document_beyond_the_distance_threshold(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-semantic-far")
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 39",
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.0, 1.0] + [0.0] * 1022,
    )

    hits, total = PostgresDocumentRepository(db_session).search_works_for_jurisdiction(
        "DE", q="kein Treffer im Titel",
        query_vector=[1.0] + [0.0] * 1023, embedding_model_name="test-model",
    )

    assert total == 0
    assert hits == []
```

This uses a query vector `[1.0, 0.0, ...]` against a stored embedding `[0.0, 1.0, 0.0, ...]` — two orthogonal unit vectors, giving `cosine_distance` of exactly `1.0`, which exceeds `_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE = 0.6`. The `q` text ("kein Treffer im Titel") does not match the document's designation ("DGUV Vorschrift 39"), so Tier 1 also finds nothing — `total` must be `0`. No new imports needed: `PostgresDocumentEmbeddingRepository` and `PostgresDocumentRepository` are already imported in this file, and `_make_delivery`/`_make_visible_document` are this file's own existing helpers.

Open `core/tests/graph/test_segment_similarity_search.py`. Add this test after the existing `test_finds_the_closest_segment_first` (which ends at line 68 with `assert [s.id for s in results] == [close.id]`):

```python
def test_excludes_a_segment_beyond_the_distance_threshold(db_session):
    document, delivery = _make_classified_document(
        db_session, jurisdiction="DE", may_process=True, may_index_fulltext=True,
    )
    _add_segment_with_embedding(
        db_session, document, delivery, text="fern", vector=[0.0, 1.0] + [0.0] * 1022,
    )

    repo = PostgresSegmentRepository(db_session)
    results = repo.find_similar_segments_for_jurisdiction([1.0] + [0.0] * 1023, "DE", _MODEL)
    assert results == []
```

Same vector pair (orthogonal, `cosine_distance == 1.0`), which exceeds `_CHAT_SEGMENT_MAX_COSINE_DISTANCE = 0.75`. No new imports needed: `PostgresSegmentRepository`, `_make_classified_document`, `_add_segment_with_embedding`, and `_MODEL` are already defined/imported in this file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_search.py::test_semantic_tier_excludes_a_document_beyond_the_distance_threshold tests/graph/test_segment_similarity_search.py::test_excludes_a_segment_beyond_the_distance_threshold -v`

Expected: both FAIL — `test_semantic_tier_excludes_a_document_beyond_the_distance_threshold` fails with `assert 1 == 0` (the orthogonal document is currently still returned, since there's no threshold yet); `test_excludes_a_segment_beyond_the_distance_threshold` fails with `assert [<Segment ...>] == []` (same reason).

- [ ] **Step 3: Add the document-search threshold**

In `core/src/normly_core/graph/postgres/repositories.py`, add this constant immediately after the existing `_SEMANTIC_CANDIDATE_POOL = 200` (currently line 91), before the blank line that follows it:

```python

# Above this cosine distance (0 = identical, 2 = opposite), a Tier-2 match is
# noise, not a result -- a fallback tier feeding a ranked list the user
# visually scans can tolerate a borderline match; this cutoff exists so a
# query with no genuinely close match returns nothing instead of the
# nearest-available row regardless of how far it actually is. Starting
# point, not derived from real-corpus measurement -- revisit once real
# query logs exist to tune against.
_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE = 0.6
```

Then change `search_works_for_jurisdiction`'s `tier2_query` `.where(...)` clause (currently):

```python
                .where(
                    RightsClassificationORM.jurisdiction == jurisdiction,
                    RightsClassificationORM.may_process.is_(True),
                    RightsClassificationORM.revoked_at.is_(None),
                    DocumentEmbeddingORM.model_name == embedding_model_name,
                )
```

to:

```python
                .where(
                    RightsClassificationORM.jurisdiction == jurisdiction,
                    RightsClassificationORM.may_process.is_(True),
                    RightsClassificationORM.revoked_at.is_(None),
                    DocumentEmbeddingORM.model_name == embedding_model_name,
                    DocumentEmbeddingORM.vector.cosine_distance(query_vector)
                    <= _DOCUMENT_SEARCH_MAX_COSINE_DISTANCE,
                )
```

- [ ] **Step 4: Add the chat-segment threshold**

In the same file, add this constant immediately before `class PostgresSegmentRepository:` (currently line 1596), with a blank line on each side unchanged:

```python
# Above this cosine distance (0 = identical, 2 = opposite), a chat-segment
# match is not close enough to feed into an LLM-synthesized answer
# presented as fact -- an irrelevant passage there produces a
# wrong-sounding confident answer, which is worse than "no results" (the
# caller already has a fallback path for an empty result). Lower than the
# document-search threshold since a wrong citation is more costly than a
# low-ranked search hit. Starting point, not derived from real-corpus
# measurement -- revisit once real query logs exist to tune against.
_CHAT_SEGMENT_MAX_COSINE_DISTANCE = 0.75


class PostgresSegmentRepository:
```

Then change `find_similar_segments_for_jurisdiction`'s `.where(...)` clause (currently):

```python
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
                EmbeddingORM.model_name == model_name,
            )
```

to:

```python
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
                EmbeddingORM.model_name == model_name,
                EmbeddingORM.vector.cosine_distance(query_vector)
                <= _CHAT_SEGMENT_MAX_COSINE_DISTANCE,
            )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_search.py tests/graph/test_segment_similarity_search.py -v`

Expected: PASS, every test in both files — including the two new ones and every pre-existing test (the pre-existing near-case tests, `test_semantic_tier_finds_a_document_with_no_exact_text_match` and `test_finds_the_closest_segment_first`, use identical query/embedding vectors, i.e. `cosine_distance == 0`, which is well under both new thresholds, so they must still pass unchanged).

- [ ] **Step 6: Run the chat package's own test suite**

Run: `cd chat && .venv/bin/pytest tests/ -v` (`chat/` has its own venv, already provisioned).

Expected: PASS, no regressions — `chat/tests/test_synthesis.py::test_no_segments_returns_a_fallback_without_calling_ollama` already mocks the segment repository to return `[]` directly rather than exercising the real threshold, so it is unaffected by this change and needs no modification.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_work_search.py core/tests/graph/test_segment_similarity_search.py
git commit -s -m "$(cat <<'EOF'
feat(core): add distance thresholds to semantic search

Both document-search Tier-2 and chat-segment search currently return
their top-N nearest rows no matter how distant, so "no relevant
match" is unreachable once enough rows exist. Add two independent
cosine-distance cutoffs (0.6 for document search, 0.75 for chat,
which feeds an LLM-synthesized answer and tolerates less noise) as
named constants, applied as SQL WHERE clauses.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: HNSW indexes on both vector columns

**Files:**
- Create: `core/migrations/versions/0031_add_hnsw_indexes.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: nothing a later task consumes.

- [ ] **Step 1: Write the migration**

Create `core/migrations/versions/0031_add_hnsw_indexes.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add HNSW indexes on document_embedding.vector and embedding.vector

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-10
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


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

`vector_cosine_ops` matches this codebase's exclusive use of `cosine_distance` at both query sites touched in Task 1 (and every other `cosine_distance` call site in the repository layer) — no other pgvector distance operator is in use anywhere in this codebase, so no second operator class is needed.

- [ ] **Step 2: Run the migration round-trip test**

Run: `cd core && .venv/bin/pytest tests/graph/test_migration_determinism.py -v`

Expected: PASS. This test's `migrated_engine` fixture is session-scoped and already runs every migration (including the new 0031) to head before any test in the suite executes; this specific test additionally downgrades to base and re-upgrades to head, comparing the table set before and after — proving 0031's `upgrade`/`downgrade` pair is syntactically valid and round-trips cleanly. No new test is needed beyond this — it covers every migration in the chain automatically, including this one, by construction.

- [ ] **Step 3: Run the full core/ test suite**

Run: `cd core && .venv/bin/pytest tests/`

Expected: PASS, no regressions and no change in test count from Task 1's final count (this task adds a migration file, not a test function).

- [ ] **Step 4: Commit**

```bash
git add core/migrations/versions/0031_add_hnsw_indexes.py
git commit -s -m "$(cat <<'EOF'
feat(core): add HNSW indexes on document_embedding and embedding

Both vector columns had no index -- every semantic-search query was
an exact KNN via full table scan. HNSW builds incrementally from
empty, unlike IVFFlat, which needs pre-existing data to cluster
against and periodic reindexing as the corpus grows -- the right
choice given ingestion adds rows continuously with no bulk-load
moment. Default build parameters; no tuning data exists yet.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** "Two separate thresholds" (design section) → Task 1 Steps 3-4, two distinct named constants with distinct values and rationale comments, copied verbatim from the spec. "Applied as a `.where(...)` clause" → Task 1 Steps 3-4's exact diffs, not a Python post-filter. "Index: HNSW" with exact migration code → Task 2 Step 1, copied verbatim from the spec. Testing section's synthetic-embedding approach (near case returns, far case returns empty) → Task 1's new tests (far case) plus the untouched pre-existing tests (near case, already proven not to regress). Testing section's migration note (no new test needed beyond the round-trip) → Task 2 Step 2, using the actual existing test file rather than inventing one. Out-of-scope items (no per-request override, no HNSW tuning, no `_SEMANTIC_CANDIDATE_POOL`/`limit` change) — no task touches any of them.

**Placeholder scan:** No TBD/TODO; every step has literal code or an exact command, not a description of one.

**Type consistency:** `_DOCUMENT_SEARCH_MAX_COSINE_DISTANCE` and `_CHAT_SEGMENT_MAX_COSINE_DISTANCE` are each defined once (Task 1, Steps 3 and 4 respectively) and referenced exactly once each, at their own query site — no cross-task signature to keep consistent, since Task 2 is a pure schema migration with no Python interface at all.
