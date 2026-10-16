# Design: Semantic search (Normtracker foundation, part 2/5)

## Context

Sub-project 1 ([[docs/superpowers/specs/2026-09-06-normtracker-work-entity-design.md]],
merged) introduced the `Work` entity — a logical identity for a
standard across several editions and national adoptions. This
sub-project builds directly on it: today's search
(`api/src/normly_api/routers/search.py`,
`PostgresDocumentRepository.search_documents_for_jurisdiction`) is pure
ILIKE text matching on `DocumentDesignation`/`DocumentTitle`, returns a
flat, per-`Document` hit list and uses no embedding — although
pgvector and a local embedding model (`intfloat/multilingual-e5-large`,
1024-dim, `core/src/normly_core/pipeline/embeddings.py`) are already in use for
chat segments.

Two decisions from the sub-project 1 brainstorming session are to be
implemented here: the search is switched to semantic (embedding-based) similarity,
and hits are grouped per `Work` instead of per `Document`.

## Goal of this sub-project

1. A hybrid search: exact text matches (as today, ILIKE) first,
   supplemented by semantically similar hits that ILIKE does not find (synonyms,
   paraphrases, thematic proximity).
2. Hits are grouped by `Work` — one search result per standard,
   not per edition/national version.
3. A new embedding maintained per `Document`, created/updated
   during ingestion as well as retroactively via backfill for already
   existing documents.

## Non-goals

- No complete edition/adoption list in the search result — that is
  sub-project 3 (document detail page). This sub-project only provides
  a counter ("+2 more editions").
- No embeddings at the full-text/segment level for the document search —
  the existing `Embedding`/`EmbeddingRepository` (segment-bound, for
  chat) remains unchanged and untouched.
- No new search service, no external search engine — stays entirely
  in `core`/`api`, the same pgvector setup as for chat.
- No change to the rights classification gate logic — as today, search filters
  exclusively jurisdiction-visible, `may_process=True` documents.

## Architecture

### Two-tier search

**Tier 1 (exact):** ILIKE on `DocumentDesignation.designation` and
`DocumentTitle.title`, as implemented today. Hits get rank 0.

**Tier 2 (semantic):** the search query is translated into a vector with `EmbeddingModel.embed_query()`
(query prefix, not `embed()`/passage prefix — the e5 model distinguishes
both roles in the same vector space) and sorted by
pgvector cosine distance (`DocumentEmbedding.vector.cosine_distance(...)`)
against all rights-classified documents. Hits get rank 1
with ascending distance as the secondary sort.

Both tiers run against the same rights-classified document set
(identical gating to today's `search_documents_for_jurisdiction`).
The combined hit list, sorted by `(rank, distance)`, is
then reduced via `DISTINCT ON (work_id)` to one hit per `Work`
— the top-ranked document per work wins.

An empty search query (`q=None`) skips tier 2 entirely (no text
to embed) and behaves like today's unfiltered, paginated
listing.

### Data model

```
DocumentEmbedding (new)
  document_id: UUID (FK → document.id)
  model_name: str
  vector: Vector(1024)
  delivery_id: UUID (FK → delivery.id)   # lineage — which delivery
                                          # produced the underlying text
  created_at: datetime
  UNIQUE(document_id, model_name)
```

Deliberately a separate table, not an extension of the existing
`Embedding` table (which is bound to `segment_id`) — a document
identity embedding and a chat segment embedding are
different concepts in domain terms; a shared table with mutually
exclusive foreign keys would be less clean than two small, focused
tables.

**Embedding content:** one embedding per `Document`, formed from the
primary `DocumentDesignation` plus the primary `DocumentTitle`
(`"<Designation> — <Title>"`, e.g. `"EN ISO 9001:2018 — Qualitätsmanagement-
systeme"`). Not one embedding per title/language — keeps maintenance limited to one
embedding per document.

Neither designation nor title is guaranteed to be present at ingestion time
(`add_title` is only called when `raw_title` is present,
`add_designation` only when `raw_issuer` is present): if the title is missing,
only the designation is embedded (`"<Designation>"` without a suffix); if the
primary designation is missing as well (no `raw_issuer` in this run),
embedding creation is skipped entirely for this run — until a later run
with a designation, the document remains findable only via tier 1
(if there is text then) or not at all, which is consistent
with the existing behavior (without a designation, a document is already
not findable via `find_by_designation` today).

### Ingestion & backfill

In `core/src/normly_core/pipeline/runner.py`'s `process()`, after the
existing designation/title step (for new and re-found
documents alike), the current primary designation and title text is
read, embedded and written to `DocumentEmbedding` via upsert (`ON CONFLICT (document_id, model_name) DO
UPDATE`) — on every run, not just
the first. This is idempotent by nature (the same text yields
the same vector) and keeps the embedding up to date automatically if a
later run changes the primary title, without its own
change detection.

For already existing documents without an embedding: a new CLI subcommand
(`python -m normly_core.pipeline backfill-document-embeddings`, analogous to the
existing `ingest` subcommand in `core/src/normly_core/pipeline/cli.py`)
creates embeddings for all documents without a `DocumentEmbedding` for the
current model. Deliberately **no** Alembic migration (unlike the
union-find backfill in sub-project 1) — loading and calling an
ML model does not belong in a migration (slow, file system/
model dependent), but in pipeline code like any other ingestion
step.

### API response

```
WorkSearchResultResponse
  work_id: UUID
  best_match: DocumentResponse   # best-ranked Document of this Work
  other_editions_count: int       # number of further Documents in the same Work
WorkSearchResponse
  results: list[WorkSearchResultResponse]
  total: int   # number of DISTINCT Works, not raw hits
```

Replaces today's `DocumentSearchResponse { results: list[DocumentResponse],
total }`. `GET /v1/documents/search` remains the endpoint path (no
switch to `/v1/works/search` in this sub-project — renaming to
a work-centric URL structure is a frontend/API naming question that is
better decided together with sub-project 5 (frontend), not in isolation
here).

## Error handling

- Empty search query: no ILIKE filter, no embedding computed, tier 2
  is skipped, pure jurisdiction/issuer-filtered listing (as today).
- A document without an existing `DocumentEmbedding` (yet) (e.g. backfill
  not run yet) does not appear in tier 2, but remains findable via tier 1
  (ILIKE) — a deliberate, harmless degradation.
- Errors loading/calling the embedding model: no new
  fallback path — behaves like the existing code for chat embeddings
  (`EmbeddingModel`), no special handling for the search.

## Test concept

- Unit: hybrid merge logic (tier 1 before tier 2, no duplicates between the
  tiers); the `DISTINCT ON work_id` grouping returns exactly one hit per
  work.
- Integration: the pipeline creates documents + embeddings; the repository search
  returns hits correctly grouped by work and correctly sorted against
  a real Postgres/pgvector instance.
- Backfill CLI: documents without an embedding get one; a second run
  creates nothing new (idempotent).
- A dedicated test proving that the query uses `embed_query()` (query
  prefix), not `embed()` (passage prefix) — otherwise the
  model returns wrongly oriented vectors and the similarity search becomes
  meaningless, without any other test making this visible.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-GRAPH-005 | `Work` grouping of the search results is the first user-visible consequence of the work identity introduced in sub-project 1. |
| ADR-006 | pgvector remains the only vector infrastructure (no Neo4j, no external search engine) — this sub-project adds a second pgvector use (document embeddings) alongside the existing one (segment embeddings), without new technology. |
| — | There is currently no REQ-SEARCH-* entry in the SRS (`docs/srs/03-requirements.md`) for the search itself — this design fills a requirement not formalized so far. Recommendation as follow-up work: add a REQ-SEARCH-001 that records the hybrid search and the work grouping as an acceptance test. |

## Open items / follow-up work

- **Add REQ-SEARCH-001** (see above) — a documentation addendum, no
  code impact.
- **Document detail page** (sub-project 3): provides the full
  edition/adoption list that this sub-project deliberately only shows as a
  counter.
- **URL structure `/v1/works/...`**: whether the search endpoint (and others) switch to
  work-centric path naming is decided with sub-project 5
  (frontend), not here.
- **Embedding model versioning**: `model_name` is already part of the
  unique key (as with `Embedding`), so that a model change later is possible without
  data loss — a migration path for an actual
  model change (recomputing all vectors) is not part of this
  sub-project.
