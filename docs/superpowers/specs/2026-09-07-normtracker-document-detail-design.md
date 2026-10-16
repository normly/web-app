# Design: Document detail page (Normtracker foundation, part 3/5)

## Context

Sub-project 1 ([[docs/superpowers/specs/2026-09-06-normtracker-work-entity-design.md]])
and sub-project 2 ([[docs/superpowers/specs/2026-09-07-normtracker-semantic-search-design.md]]),
both merged, brought the `Work` entity and a work-grouped search.
This sub-project makes the third extension sketched in the original work entity spec:
the document detail page shows the edition history,
national versions, references and rights classification per jurisdiction for
a work.

A document detail page already exists
(`frontend/src/app/documents/[id]/document-detail-content.tsx`), built
against the existing endpoints `GET /v1/documents/{id}`, `GET
/v1/documents/{id}/edges` and `GET /v1/documents/{id}/validity`. It is
functional, but entirely without a work reference (purely document-centric), shows
all edge types ungrouped in one list and shows no
rights classification. Rights classification is currently not reachable over
HTTP at all — only `RightsRepository.get_classification` exists at the
repository level.

## Goal of this sub-project

1. Provide the edition history (the complete REPLACES/WITHDRAWN_BY chain, not just
   the direct predecessor/successor) and national versions (the complete
   ADOPTED_FROM chain) for the work of a document via a new
   endpoint.
2. Provide the rights classification per (currently selected) jurisdiction via a new
   endpoint.
3. Extend the existing document detail page so that it correctly displays this new
   information.

## Non-goals

- **No visual redesign.** No tab layout, no new choice of components
  beyond the set already in use. The existing, plain styling
  remains — the tab view with a well-thought-out design is explicitly
  reserved for sub-project 5.
- **No AI-generated change summary** between editions.
  It needs full-text access to both editions plus an LLM connection (similar to the
  chat infrastructure) — a separate, later sub-project.
- **No multi-jurisdiction view.** Rights classification is only shown for
  the currently selected jurisdiction, consistent with every other
  endpoint of this app (search, edges, validity all take exactly one
  `jurisdiction` parameter). A "show all jurisdictions" view would be a
  new UI concept that occurs nowhere else.
- **No new/changed `/edges` endpoint.** It remains unchanged — after the
  lesson from sub-project 2 (a changed response shape broke an
  existing page whose own test did not notice it), deliberately, no existing endpoint in
  productive use is changed here when a
  purely client-side regrouping suffices.

## Architecture

### Two new endpoints

Both attached to the existing document detail route (`/v1/documents/{id}/...`),
as `/edges` and `/validity` already are.

**`GET /v1/documents/{id}/work?jurisdiction=X`** — returns the work structure
of the document:

```
WorkStructureEntry
  document_id: UUID
  origin_issuer: str
  origin_number: str
  edition: str
  designation: str | None   # primary designation, if present
  status: "valid" | "replaced" | "withdrawn"

WorkStructureResponse
  work_id: UUID
  editions: list[WorkStructureEntry]
  national_adoptions: list[WorkStructureEntry]
```

Within the (bounded) set of all documents with the same `work_id`,
two subgraphs are formed, depending on the edge type:

- **`editions`**: all documents connected to the document under consideration via
  a chain of **only** REPLACES/WITHDRAWN_BY edges
  (typically the same publisher over time). Each edition gets
  a status, computed exactly as in the existing `/validity` endpoint
  (check incoming edges: if a newer edition points to this one via REPLACES/
  WITHDRAWN_BY, it is `replaced`/`withdrawn`), only for every
  element of the chain instead of just for one document.
- **`national_adoptions`**: everything else in the same work — every document
  that is not part of the edition chain, with its own publisher/designation/
  status. Together, both lists always cover the complete
  work document set, no overlap, no document that appears in neither
  list.

Both lists include the document currently under consideration itself (at
its correct position in the chain, with its own status) — not
just its siblings. This avoids special handling in the frontend
("is this the edition I am currently looking at?") and provides a
complete, self-contained list.

Deliberately **no unbounded graph traversal**: the underlying
DB query is a simple, bounded set query (all documents with
this `work_id`, all edges *between exactly these* documents) — the
multi-step chain building then happens in Python over a small,
already loaded set. In the sense of ADR-006 this stays "shallow", because it
uses the work grouping from sub-project 1 to bound the set from the outset,
instead of running recursively over the whole graph.

Rights gating as everywhere: only documents/edges that are visible in `jurisdiction`
(`may_process=true`, free layer) are included.

**`GET /v1/documents/{id}/rights?jurisdiction=X`** — a thin wrapper around the
already existing `RightsRepository.get_classification`, returns
`may_process`, `may_index_fulltext`, `may_cite_passages`, `may_export_free`
and `legal_basis_reference`.

### Frontend

`document-detail-content.tsx` gets two new `fetch` calls (work structure,
rights) in parallel to the existing ones. References continue to be built from the
existing `/edges` data, but are now filtered client-side: only
REFERENCES/BASED_ON_LAW appear in the "References" list; REPLACES/
WITHDRAWN_BY/ADOPTED_FROM are hidden there (they appear
instead in structured form in the new editions/versions lists). No
new layout — the edition history and national versions appear as
simple lists built with the existing components (`Badge`, `Link`),
in the same plain style as the existing sections.

## Error handling

- `/work`: a document without work siblings returns both lists empty
  (no error) — the page then simply hides the corresponding
  sections.
- `/rights`: no classification for the requested jurisdiction → 404,
  the same pattern as `/validity` ("no document" and "not classified"
  remain indistinguishable from the outside).
- Both endpoints gate as everywhere: only documents/edges with
  `may_process=true` in the requested jurisdiction are included.

## Test concept

- Repository/integration: an edition chain over 3+ generations (2010→2015→2018)
  sorted correctly with the correct status per link; national versions
  correctly separated from the edition chain; a work without siblings
  returns empty lists; rights gating excludes non-visible
  work members from the results.
- API: `/rights` returns 404 if the classification is missing, otherwise the
  correct fields; `/work` returns the correct JSON schema incl. empty
  lists for a solo document.
- Frontend: the existing test (`document-detail-content.test.tsx` or similar,
  if present — otherwise to be created) is extended with the new sections
  (edition list, national versions, rights badge); the
  references filtering (work-internal edge types are hidden from the
  references list) gets its own test.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-GRAPH-005 | The editions/versions view is the second user-visible consequence of the work identity (after the search grouping from sub-project 2) — makes "one standard, several versions" directly visible to users. |
| REQ-GRAPH-002 | `/work` and `/rights` respect the same free/commercial layering as `/edges` — only the `may_process`-visible free layer is included. |
| ADR-006 | The bounded work set query plus in-memory chain building remains consistent with "graph first, shallow queries" — no unbounded recursive traversal. |

## Open items / follow-up work

- **AI change summary** (a separate, later sub-project): needs
  full-text access to both editions plus an LLM connection.
- **Tab layout and visual redesign**: sub-project 5.
- **Multi-jurisdiction view**: if wanted later, needs a
  new `list_classifications_for_document`-style repository method (today
  only `get_classification` for exactly one jurisdiction) and a new
  UI concept.
