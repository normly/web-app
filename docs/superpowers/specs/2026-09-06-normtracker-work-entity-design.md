# Design: Work entity (Normtracker foundation, part 1/5)

## Context

With "Search & document detail" (so far Plan 6 of the
shadcn frontend redesign, see
`docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`),
the owner plans to actually build the first foundation of the Normtracker — not just a
re-theming. Before the frontend is touched, the backend data model
should be in place. This spec is the first of five planned sub-projects:

1. **Work entity** (this spec) — the foundation for all of the following.
2. Semantic search (embedding-based, replaces today's ILIKE).
3. Document detail page (edition history, national versions,
   references, rights classification per jurisdiction).
4. Watchlist/notification (favorites, change triggers, email sending).
5. Frontend (brings 1–4 together, last cycle).

**Starting point:** ADR-011 and `CLAUDE.md` require "One standard = one
node, language-independent" — DIN EN ISO 9001 and BS EN ISO 9001 are
the same document. The actually implemented `Document` type
(`core/src/normly_core/graph/domain.py`), however, is keyed by
`(origin_issuer, origin_number, edition, part)`: every
edition/national version is its own row with its own UUID, only linked via
`Edge` (`REPLACES`, `WITHDRAWN_BY`, `ADOPTED_FROM`). REQ-GRAPH-005
additionally explicitly requires an acceptance test that is not
fulfilled today as a result: "A standard with adoptions by at least three national
bodies is represented as one node with assigned adoptions."

An alternative model draft submitted for review during this session
(`Norm`/`NormVersion`/`NormWatchlist`/`Notification`/
`ImportBatch`) was reviewed and rejected because it would not extend the existing model
but replace it, and in doing so would downgrade several already
accepted requirements: global instead of
jurisdiction-dependent license classification (contradicts REQ-GRAPH-006), a
single `successor_norm_id` field instead of the typed reference graph
(contradicts REQ-GRAPH-001, ADR-007), no lineage chain down to individual
fields (contradicts the non-negotiable `CLAUDE.md` rule
"Carry lineage along"), and no multilingualism per node (contradicts
REQ-GRAPH-005). Two ideas from this draft are good on their own, however, and
flow into later sub-projects: a change summary per
edition (sub-project 3) and watchlist/notification (sub-project 4).

## Goal of this sub-project

Introduce a new `Work` entity that represents the logical identity of a
standard across all editions and national adoptions,
so that REQ-GRAPH-005 is fulfilled and later sub-projects (search,
document detail, watchlist) can refer to "one standard" instead of "one document row".

## Non-goals

- No change to `RightsClassification` (stays per document/jurisdiction).
- No switch of the search to work grouping (sub-project 2).
- No UI/API workflow for the normal case of ingestion beyond
  what is needed for work assignment.
- No automated number similarity matching (see section
  "Assignment logic").

## Architecture

### Data model

```
Work (neu)
  id: UUID (PK, surrogate — kein natürlicher Schlüssel, da ein Work
      bewusst mehrere Herausgeber/Nummern überspannen kann)
  status: enum(active, merged)
  merged_into_work_id: UUID | None (FK → Work, self-ref; nur bei
      status=merged gesetzt)
  created_at: datetime
  created_via: enum(auto_matched, manual)

Document (bestehend, erweitert)
  + work_id: UUID (FK → Work, NOT NULL)
```

`Work` deliberately carries **no** title, designation or other
metadata fields. Display data (title, current status) are derived at runtime
from the primary designation/title of the most recent, non-withdrawn
`Document` of the work — no data duplication, no
sync problem between the work and the underlying documents.
`RightsClassification` remains unchanged at the `Document` level, because
license terms can differ between publishers/editions of the same work.

### Assignment logic during ingestion

For every newly ingested `Document`, the ingestion checks whether the delivery
itself contains an explicit derivation statement pointing to an already known document
(e.g. "this edition replaces X", "this national version adopts
X"):

- **Signal present and unambiguously resolvable:** the new document receives the
  `work_id` of the target document; in addition, as before, the concrete
  `Edge` (`REPLACES`, `WITHDRAWN_BY` or `ADOPTED_FROM`) between the two
  documents is created.
- **No signal, or the signal points to no known document:** the
  new document gets a **new** work (1:1). No guessing via
  number similarity — text-based matching (part numbers,
  hyphen variants) is error-prone; a wrong automatic
  link in the open, share-alike-licensed graph weighs more heavily than
  an additional case in the queue.
- **Signal present, but ambiguous** (e.g. an ambiguous target statement):
  `IdentityResolutionCase` as today (see below); the document temporarily
  gets its own new work until the queue decision is made.

**Only `REPLACES`, `WITHDRAWN_BY` and `ADOPTED_FROM` trigger a shared
work assignment.** `REFERENCES` and `BASED_ON_LAW` connect recognizably
different standards (a norm that cites another; a
law that refers to a norm) and must never result in the same work.

### Extension of IdentityResolutionCase

`IdentityResolutionCase` (existing) gets a second case type:

```
IdentityResolutionCase (erweitert)
  ...
  case_type: enum(new_document, work_merge)
  # bei case_type=work_merge:
  source_work_id: UUID | None
  target_work_id: UUID | None
```

- `new_document`: as today — a newly delivered document waits for
  assignment to an existing `resolved_document_id` (and thus its
  work).
- `work_merge`: a curator determines that two already **existing,
  independently created** works are the same standard (e.g. the
  DIN and BS versions were initially created separately for lack of a signal, and a
  later delivery does prove the connection). On resolution: all
  `Document.work_id` of the `source_work_id` are
  rewritten to `target_work_id`, `source_work_id` is set to `status=merged` with
  `merged_into_work_id=target_work_id` — never deleted, for the sake of
  traceability/lineage.

## Migration & backfill

For existing data, `work_id` is filled via an Alembic migration: via the
transitive closure of existing `REPLACES`/`WITHDRAWN_BY`/`ADOPTED_FROM` edges
(union-find) — every connected group of existing documents gets
a shared new work, every unconnected document gets its
own new work. This is deterministic and uses exactly the edges that
already express the belonging-together today — no manual rework
needed.

## Error handling

- `work_id` is `NOT NULL` — a document without a resolvable work must never
  be committed. The ingestion must have assigned a work before the commit
  (newly created or existing), analogous to the existing rule:
  missing classification means "do not process", not
  "provisionally allowed".
- Access to a document whose work has `status=merged` is
  transparently redirected to `merged_into_work_id` (never a dead link).
- A `work_merge` case with contradictory/cyclic targets (A merge→B,
  B merge→A) is rejected on resolution, not committed.

## Test concept

- Unit: union-find backfill logic against a fixture set of known chains
  (edition A→B→C via `REPLACES`, national version D via `ADOPTED_FROM` from
  B) — expects one shared work for all four.
- Unit: ingestion with an unambiguous signal → correct `work_id` adoption;
  without a signal → new work; ambiguous → `IdentityResolutionCase`.
- Integration: `work_merge` case resolution moves all documents
  correctly and marks the source as `merged`.
- Repository test: access to a document of a `merged` work
  transparently returns the target work.
- Repository test: `REFERENCES`/`BASED_ON_LAW` edges demonstrably trigger
  **no** shared work assignment.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-GRAPH-005 | The acceptance test ("one node with assigned adoptions") is fulfilled for the first time by `Work` — previously unfulfilled, since `Document` did not represent this aggregation. The SRS is extended with a reference to `Work`. |
| ADR-011 | "One standard = one node" is extended with an addendum that documents the concrete implementation (work entity as a logical identity across several document rows, not a single DB row in the literal sense). |
| REQ-GRAPH-001/002/006 | Unchanged — reference graph edge types, free/commercial layering and jurisdiction classification remain at the `Document`/`Edge` level as before. |
| CLAUDE.md "Carry lineage along" | `Work` itself has no lineage of its own (carries no content); every `Document` keeps its existing `created_via_delivery_id`. `merged` works are kept instead of deleted for traceability reasons. |

## Open items / follow-up work

- **Semantic search** (sub-project 2): search hits are to be grouped per
  work in future (one hit = one standard, editions/national
  versions expandable) — depends directly on this spec, but is not part
  of it.
- **Document detail page** (sub-project 3): shows the edition history,
  national versions, references and rights classification per jurisdiction
  for a work.
- **Watchlist/notification** (sub-project 4): users follow a work
  (not a single document edition); the change trigger depends on newly
  created `REPLACES`/`WITHDRAWN_BY` edges within a work.
- **Frontend** (sub-project 5, last cycle): brings 1–4 together.
- **Work merge admin interface.** This spec only defines the
  data model/the case resolution logic for `work_merge`; a
  dedicated curation UI for it is not part of this cycle.
