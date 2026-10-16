# Design: Data Model & Reference Graph Schema

**Date:** 2026-08-11
**Status:** for review
**Sub-project:** first of several for implementing the normly MVP (free core)

## Context

normly currently has no code base, only documentation (`docs/adr/`, `docs/srs/`). The
full SRS comprises 78 requirements covering the entire target state — free core and
commercial layer, partner portal, DRM, native app, third-party integrations. That is
not a scope for a single sub-project.

**Decided with the owner:**

1. Only the MVP scope is implemented: free core, standalone web application, chat via
   an open-source LLM, reference graph from freely accessible sources (category A/B). No
   accounts, no billing, no DRM, no native app.
2. First sub-project within the MVP: **data model & reference graph schema**. API,
   ingestion pipeline and chat frontend build on it and are treated as separate
   sub-projects with their own spec→plan→implementation cycle.
3. Backend stack for this sub-project: **Python**, SQLAlchemy, Alembic.

## Goal of this sub-project

A PostgreSQL schema (with pgvector, ADR-006) for the norm reference graph, plus a
repository layer that fully separates the domain logic from the concrete storage technology
(REQ-GRAPH-004). The schema covers: globally unique, language-independent
node identity (REQ-GRAPH-005), edges with a jurisdiction and layering attribute
(REQ-GRAPH-002/006), rights classification as a processing gate (REQ-PIPE-004), and
complete lineage of every derived artifact to a source delivery
(REQ-PIPE-005/006).

## Non-goals

Deliberately not part of this sub-project — each a separate later sub-project:

- **Ingestion pipeline:** ingest adapters, identity resolution, structure and
  reference extraction, segmentation, embedding (REQ-PIPE-001). This sub-project only
  creates the target tables a pipeline later writes into.
- **A Perinorm/DIN Media format adapter.** Publishers that in future deliver collections in a
  Perinorm-like field format are connected via a separate ingest adapter
  that maps onto this generic schema — but only once a
  category C contract with the respective publisher is in place (REQ-PIPE-002). The
  core schema itself stays publisher- and format-neutral: it is published under ODbL
  (REQ-GRAPH-001), and modeling it on the license-protected
  Perinorm field schema (Annex 1 to the "Metadata License Agreement" of AFNOR/BSI/DIN) would
  touch both its copyright reservation ("no further processing without prior written
  approval") and ADR-012 (no replication of commercially exploited catalog collections).
- **Segment and embedding tables** for full-text processing. ADR-006 provides for graph and
  embeddings in the same database, but populating these tables is
  pipeline work. The schema is designed so that a segment/embedding table can be
  added later without changing the core schema (same lineage pattern:
  its own `delivery_id` per row).
- **Public API and chat core logic.** They consume this schema via the
  repository interface, but are a separate sub-project.

## Architecture

### Repository pattern

Three approaches were weighed:

1. SQLAlchemy Core without ORM, repository interfaces as `Protocol`.
2. SQLAlchemy ORM models directly as domain models.
3. **SQLAlchemy ORM internally, mapped to plain domain dataclasses at the repository
   boundary.**

Decided: **approach 3.** It fulfills the acceptance test of REQ-GRAPH-004 verbatim
("An architecture review confirms that the domain logic has no knowledge of the concrete
graph technology"), keeps Alembic autogenerate for migrations, and
supports recursive CTEs for replacement chains via SQLAlchemy directly (sufficient for the
present edge depth according to ADR-006).

**Structure:**

- **Domain layer** (`normly_core.graph.domain`): plain Python dataclasses
  (`Document`, `DocumentDesignation`, `DocumentTitle`, `Edge`, `RightsClassification`,
  `Source`, `Delivery`) and repository interfaces as `Protocol`
  (`DocumentRepository`, `EdgeRepository`, `RightsRepository`, `SourceRepository`,
  `DeliveryRepository`). No import of SQLAlchemy.
- **Postgres adapter** (`normly_core.graph.postgres`): SQLAlchemy ORM models (private,
  not exported), implementation of the repository interfaces, mapping functions
  ORM ↔ dataclass, Alembic migration directory.
- The domain logic (later sub-projects) imports exclusively from the
  domain layer.

### Rights gate as part of the interface, not as a caller obligation

There is no method in `DocumentRepository` that returns documents without a jurisdiction parameter.
Every reading method requires a jurisdiction and joins internally against
`rights_classification`. This structurally enforces REQ-PIPE-004 ("A missing classification
does not count as provisional permission") — there is no call path that could
bypass it, not just a convention that can be forgotten.

## Data model

### `source` — source register (REQ-PIPE-002)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `publisher` | text | |
| `retrieval_path` | text | |
| `legal_basis_category` | enum(A,B,C,D) | |
| `jurisdiction` | text | ISO 3166-1 alpha-2 |
| `reviewed_at` | date | |
| `responsible_person` | text | |
| `commercial_catalog` | boolean | Default `false` |
| `contract_reference` | text, nullable | Mandatory for category C (CHECK) |
| `tdm_opt_out_checked_at` | date, nullable | REQ-PIPE-003 |
| `tdm_opt_out_result` | enum(none_found, opt_out_present), nullable | |

CHECK constraints: `legal_basis_category = 'D' AND commercial_catalog` is not permitted
(REQ-PIPE-008/ADR-012 — a technical block, not a guideline). Category C without
`contract_reference` is not permitted.

### `delivery` — delivery/ingest run (REQ-PIPE-006)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `source_id` | UUID, FK → `source` | |
| `content_hash` | text | Content addressing; `UNIQUE(source_id, content_hash)` |
| `ingested_at` | timestamptz | |
| `withdrawn_at` | timestamptz, nullable | |

### `document` — node, one standard (REQ-GRAPH-005)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | internal, stable identifier |
| `origin_issuer` | text | publisher of the internationally primary designation |
| `origin_number` | text | |
| `edition` | text | edition |
| `part` | text, nullable | part number |
| `created_via_delivery_id` | UUID, FK → `delivery` | first delivery from which the node originated |
| `created_at` | timestamptz | |

### `document_designation` — national adoptions (REQ-GRAPH-005)

National adoptions and translations are **not separate nodes**, but rows on
a node — this matches the acceptance test verbatim ("one node with
assigned adoptions").

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `issuer` | text | e.g. DIN, BSI, AFNOR |
| `designation` | text | e.g. "DIN EN ISO 9001" |
| `language` | text | ISO 639-1 |
| `edition` | text, nullable | if different from the node |
| `is_primary` | boolean | |
| `delivery_id` | UUID, FK → `delivery` | |
| `created_at` | timestamptz | |

`UNIQUE(issuer, designation)`.

### `document_title` — multilingual designations (REQ-GRAPH-005)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `language` | text | ISO 639-1 |
| `title` | text | |
| `delivery_id` | UUID, FK → `delivery` | |

### `edge` — edges (REQ-GRAPH-001/002)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `from_document_id` | UUID, FK → `document` | |
| `to_document_id` | UUID, FK → `document` | |
| `edge_type` | enum | `references`, `replaces`, `withdrawn_by`, `based_on_law`, `adopted_from` |
| `jurisdiction` | text, nullable | `NULL` = globally valid |
| `layer` | enum(free, commercial) | Default `free` (REQ-GRAPH-002) |
| `delivery_id` | UUID, FK → `delivery` | |
| `revoked_at` | timestamptz, nullable | |
| `created_at` | timestamptz | |

A partial unique index `(from_document_id, to_document_id, edge_type, jurisdiction)
WHERE revoked_at IS NULL` prevents duplicate active edges.

`adopted_from` covers the case in which identity resolution classifies two documents as
related but not identical (e.g. international base norm vs. regional
adoption with a deviation in content) — as opposed to the pure attribute relationship in
`document_designation`, where both designations mean the same document. The
decision as to which case applies is the task of identity resolution
(REQ-PIPE-007, outside this sub-project).

### `rights_classification` — rights classification per jurisdiction (REQ-GRAPH-006, REQ-PIPE-004)

| Column | Type | Note |
|---|---|---|
| `document_id` | UUID, FK → `document` | part of the composite key |
| `jurisdiction` | text | part of the composite key |
| `may_process` | boolean | |
| `may_index_fulltext` | boolean | |
| `may_cite_passages` | boolean | |
| `may_export_free` | boolean | |
| `legal_basis_reference` | text | |
| `classified_at` | timestamptz | |
| `classified_by` | text | |
| `delivery_id` | UUID, FK → `delivery` | |
| `revoked_at` | timestamptz, nullable | |

If the row for `(document_id, jurisdiction)` is missing, the node counts as blocked for this
jurisdiction — enforced by an inner join in the repository (see
Architecture), not by an application-logic check.

## Data flow: lineage & rights enforcement

**Write path.** Every writing repository method requires `delivery_id` as a
mandatory parameter. There is no path that creates a node, an edge, a designation
or a classification without reference to a delivery. Each of these methods
first checks whether the delivery exists and has not been withdrawn; otherwise
it aborts with `WithdrawnDeliveryError`. Without this check, a repeated
ingest run for a withdrawn delivery would undo the withdrawal.

**Read path.** Every read operation intended for display, quotation or export requires
a jurisdiction parameter and filters internally via `rights_classification`. The
public protocol `DocumentRepository` has no method that returns documents
unfiltered. The concrete implementation additionally carries unfiltered
methods (`get_document_unchecked`, `list_designations`, `list_titles`) for
identity resolution, pipeline and administration — they are deliberately not part of the
protocol and not an output path for content.

**Withdrawal path.** `revoke_delivery(delivery_id)` sets `delivery.withdrawn_at`,
sets `revoked_at` on all associated `edge` and `rights_classification` rows and
deletes the associated `document_designation` and `document_title` rows — all in
one transaction, completely and atomically. The path does **not** write a log entry of its own
today: an audit trail does not yet exist in this sub-project (see
Open items). A `document` node without any remaining active
designation, edge or classification counts as orphaned and is excluded from read results,
but not deleted immediately (traceability). If other
deliveries continue to support the node, it stays untouched — lineage acts at the
artifact level, not at the node level. If another, still active
delivery later classifies the same document/the same jurisdiction again, this deliberately
undoes the previous withdrawal — that is a new, independent rights check (REQ-PIPE-004),
not a second check path around the withdrawal. The only thing prevented is
reusing the same, already withdrawn delivery (`WithdrawnDeliveryError`,
see write path).

## Error handling

| Case | Behavior |
|---|---|
| Write operation without `delivery_id` | Type error at call time (mandatory parameter) |
| Write operation on an unknown or already withdrawn delivery | `WithdrawnDeliveryError` (domain error, not an SQL error) |
| Category D source with `commercial_catalog=true` | DB constraint violation, caught in the repository as its own error type and passed on |
| Category C source without `contract_reference` | DB constraint violation, likewise |
| Read access without classification for the jurisdiction | no error — empty result (normal case, not an exceptional state) |
| Withdrawal of an already withdrawn delivery | idempotent, no error |

## Test concept

Migrations and the repository implementation run against a real PostgreSQL container
(local, Testcontainers — pure test infrastructure, no operations, no conflict with the
STACKIT requirement). Test cases map the acceptance tests of the affected requirements
directly:

- Repeated application of the same migration/ingest fixture produces no deviating
  result (REQ-PIPE-006).
- A node with three national designations is read as **one** node with three
  `document_designation` rows (REQ-GRAPH-005).
- Two jurisdiction exports of the same collection demonstrably deliver different
  result sets (REQ-GRAPH-006).
- Withdrawal of a delivery removes/blocks exactly its artifacts; independently
  supported nodes stay untouched (REQ-PIPE-005).
- A document with no classification row at all appears in no read result
  (REQ-PIPE-004).
- A category D source with `commercial_catalog=true` cannot be created
  (REQ-PIPE-008).
- Architecture test (e.g. import linting): the domain layer does not import
  `sqlalchemy` (REQ-GRAPH-004).

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| REQ-GRAPH-001 | Schema, ODbL-ready, documented |
| REQ-GRAPH-002 | `edge.layer` |
| REQ-GRAPH-004 | Repository pattern, approach 3 |
| REQ-GRAPH-005 | `document`/`document_designation`/`document_title` |
| REQ-GRAPH-006 | `rights_classification`, jurisdiction filtering in the read path |
| REQ-PIPE-002 | `source` |
| REQ-PIPE-003 | `source.tdm_opt_out_*` |
| REQ-PIPE-004 | Rights gate in the read path |
| REQ-PIPE-005 | `delivery_id` on every derived artifact, `revoke_delivery` |
| REQ-PIPE-006 | `delivery.content_hash`, idempotency tests |
| REQ-PIPE-008 | CHECK constraint on `source` |
| REQ-PIPE-009 | Schema is source-agnostic, no compulsion towards category C/D |
| ADR-006 | PostgreSQL + pgvector, repository encapsulation |
| ADR-011 | global identifier scheme, language-independent node identity |
| ADR-012 | technical block for category D + commercial catalogs; no replication of the Perinorm field schema in the open core |

## Open items / follow-up work

- **Audit trail for withdrawals.** The withdrawal path is atomic and complete,
  but leaves no record of its own: there is no audit table, and the
  deleted `document_designation` and `document_title` rows are gone without a trace afterwards.
  Who withdrew which delivery and when cannot be reconstructed from the schema.
  This is deliberately deferred to a later, cross-cutting observability/audit process
  and is not part of this sub-project.
- Concrete Python module layout and package name (part of implementation planning).
- Segment/embedding tables (follows with the ingestion pipeline).
- Perinorm/DIN Media format adapter (follows only with a concrete category C contract).
- Recursive CTE queries for replacement chains are only provided for here as repository-capable,
  not specified in detail — part of implementation planning.
- **`create_edge` reuse silently discards deviating attributes.**
  Creating the same active edge again (`from`/`to`/`edge_type`/`jurisdiction`) returns
  the existing row without checking `layer` or `delivery_id` against the new values
  — a second delivery that confirms the same edge with a different layer
  gains no lineage of its own; if the first delivery later withdraws the edge,
  the second one's contribution is removed along with it. This errs in the same, deliberately safe
  direction as the deduplication for `document_designation`/`document_title` (rather too
  much than too little withdrawn), but is not specified further.
- **`_require_active_delivery` has a theoretical TOCTOU window.** The check reads
  the delivery status without a row lock; under READ COMMITTED a concurrently
  running `revoke_delivery` transaction could commit between check and write. With the
  currently assumed single-writer pipeline this is not exploitable; as soon as a
  concurrent ingest exists, the check needs `SELECT … FOR SHARE` or an
  equivalent lock.
