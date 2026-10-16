# Design: Backend API — Deterministic Graph Queries (v1)

**Date:** 2026-08-20
**Status:** for review
**Sub-project:** third of several for implementing the normly MVP (free core)

## Context

The first two sub-projects (data model & reference graph schema, ingestion pipeline)
built the PostgreSQL schema, the repository layer and a populated reference graph with
real data from EUR-Lex and DGUV. The data is in the database, but there is
no way out — no HTTP access, no documentation, no third-party system can
query it.

REQ-INT-001 describes a public, documented HTTP API. SRS chapter 3.1 attaches
further, considerably larger requirements to it: user-based document uploads with
isolation and expiry (REQ-INT-002A/B/C), SSO (REQ-INT-003), an LLM interface for
chat answers (REQ-INT-004, REQ-FUNC-001/002/003). That is too large for one sub-project.

**Decided with the owner:**

1. Scope: only deterministic graph queries (REQ-GRAPH-003) over the already populated
   free collection — search/lookup, references/relationships, replacement/validity chains, as well as
   a complete dump of the free part of the graph (REQ-GRAPH-001). No LLM call, no
   user uploads, no login — in line with ADR-017/REQ-ACC-001 (no account requirement for free
   content).
2. Tech stack: FastAPI (Python), new top-level package `api/`, depending on `normly_core`.
   Generates the OpenAPI specification automatically from the endpoint signatures (fulfills
   REQ-INT-001's acceptance criteria directly), the built-in Swagger UI fulfills SRS 3.6.2's
   "A Swagger instance ... is mandatory".
3. The API is read-only. Ingestion stays CLI-only (ingestion pipeline sub-project).
4. Rate limiting/quota (REQ-SEC-004, server-side quota counting for anonymous
   use) deliberately not part of this sub-project — a separate infrastructure decision, see
   Open items.

## Goal of this sub-project

A public, versioned HTTP API, fully documented as OpenAPI, through which a
third-party system can, without knowledge of the internal implementation, look up norms, query their references
and relationships, check their validity status, see their source of origin (publisher
and retrieval URL) and export the free part of the graph completely — all
answered deterministically from the graph, without a model call (REQ-GRAPH-003).

## Non-goals

- **User uploads, isolation, expiry** (REQ-INT-002A/B/C) — a separate, later
  sub-project.
- **SSO authentication** (REQ-INT-003) — not needed as long as no account-bound
  functions exist.
- **LLM interface / chat answers** (REQ-INT-004, REQ-FUNC-001/002/003) — a separate,
  later sub-project; presumably builds on this API.
- **Rate limiting, quotas, anomaly detection** (REQ-SEC-004) — a separate
  infrastructure decision, see Open items.
- **Writing endpoints.** Ingestion stays CLI-only.
- **Commercial layer** (SLA, section-level references in licensed norms,
  confidence statements) — there are currently no licensed collections in the database
  (only category A sources from the ingestion pipeline sub-project).

## Architecture

### Package structure

Three approaches were weighed:

1. **A separate `api/` directory (FastAPI), depending on `normly_core`.**
2. FastAPI inside `core/` — rejected: mixes two forms of shipping
   (library+CLI vs. web service), pulls web framework dependencies into every installation
   that only needs the library.
3. GraphQL/RPC instead of REST — rejected: REQ-INT-001 explicitly requires an
   OpenAPI-documented HTTP API; classic REST fits third-party system integration
   (CAD/ERP) better than GraphQL. A premature departure from the prescribed path.

**Decided: approach 1.**

```
api/
  pyproject.toml        # own package, depends on normly_core
  src/normly_api/
    main.py             # FastAPI app factory, mounts routers under /v1
    dependencies.py      # DB session dependency (uses normly_core.graph.postgres)
    schemas.py            # Pydantic response models
    routers/
      documents.py        # search, detail
      edges.py             # references/relationships
      validity.py          # replacement/validity status
      export.py            # free dump
  tests/
```

Fits the already visible pattern of separate top-level components with their own
container images (CLAUDE.md "Shipping: signed container images").

### Schema boundary

The API answers with its own Pydantic models, not with the `normly_core.graph.domain`
dataclasses directly. This complies with REQ-GRAPH-004's requirement (domain logic/storage technology
stays behind an abstraction) and lets the API version evolve independently of the core
package:

```python
class DesignationResponse(BaseModel):
    issuer: str
    designation: str
    language: str
    is_primary: bool

class TitleResponse(BaseModel):
    language: str
    title: str

class SourceResponse(BaseModel):
    publisher: str
    retrieval_path: str        # origin URL of the source
    legal_basis_category: str  # A/B/C/D, see source register
    jurisdiction: str

class DocumentResponse(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    designations: list[DesignationResponse]
    titles: list[TitleResponse]
    source: SourceResponse

class EdgeResponse(BaseModel):
    edge_type: str
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    jurisdiction: str | None
    layer: str

class ValidityResponse(BaseModel):
    document_id: uuid.UUID
    status: Literal["valid", "replaced", "withdrawn"]
    replaced_by: list[uuid.UUID]
    withdrawn_reference: str | None

class LicenseNotice(BaseModel):
    license_name: str          # "ODbL-1.0"
    license_url: str
    attribution: str

class ExportResponse(BaseModel):
    license: LicenseNotice
    schema_version: str
    jurisdiction: str
    generated_at: datetime
    documents: list[DocumentResponse]
    edges: list[EdgeResponse]
```

Every endpoint takes `jurisdiction` as a required query parameter — the
rights classification depends on the jurisdiction (REQ-GRAPH-006), and the existing
repository methods are already built jurisdiction-scoped; the API only passes this
parameter through, no classification logic of its own.

**The one gate — six variants, one principle.** `DocumentRepository`'s own docstring
explicitly marks `list_designations`, `list_titles`, `find_by_designation` and
`get_document_unchecked` as *not* jurisdiction-filtered and *not* intended for public
read paths (exception: `get_document_unchecked` as a pure existence check, see
below) — only the following six methods filter via the rights classification and may
determine the respective visibility result:

| Method | In addition to `may_process`/`revoked_at` | Used by |
|---|---|---|
| `get_document_for_jurisdiction` | — | Search, detail, validity (existence+visibility) |
| `list_documents_for_jurisdiction` | — | (internal/pipeline, no HTTP endpoint) |
| `list_exportable_documents_for_jurisdiction` | `may_export_free=True` | `/v1/export` |
| `list_edges_for_jurisdiction` / `list_incoming_edges_for_jurisdiction` | — | (internal/pipeline, no HTTP endpoint) |
| `list_free_layer_edges_for_jurisdiction` / `list_free_layer_incoming_edges_for_jurisdiction` | `layer=FREE` | `/v1/documents/{id}/edges`, `/v1/documents/{id}/validity` |
| `list_exportable_edges_for_jurisdiction` | `layer=FREE` **and** `may_export_free=True` (both sides) | `/v1/export` |

This table was added afterwards in the final review: the first implementation state
had accidentally wired `edges`/`validity` to the *unfiltered* variants —
`layer=COMMERCIAL` edges would have been visible via the anonymous, public API, exactly the
error the final review had already found and fixed once for `/v1/export`,
only in the two sibling endpoints. `may_export_free` (visibility in the bulk export)
and `layer` (membership in the free vs. commercial layer of the graph itself,
REQ-GRAPH-002) are two separate concepts — the `free_layer_*` methods check only `layer`,
not `may_export_free`, so that a `may_process=True, may_export_free=False` document can still show its
free relationships via the general read endpoints without appearing in the
bulk export.

Every endpoint that returns a document must first pass through one of the six gates. For
search/detail/validity that means: `get_document_for_jurisdiction(document_id, jurisdiction)`;
if that returns `None`, the endpoint answers with 404 — regardless of whether the document
exists. Only after this one gate call may the ungated methods be called for enrichment
(designations, titles) of the same, already authorized document. For
search (`find_by_designation`) this means two stages: first resolve the identity
(`find_by_designation`, returns only a `document_id`), then check the gate
(`get_document_for_jurisdiction`) — the search result comes exclusively from the second
call, `find_by_designation` serves only identity resolution, never the visibility check.
`/v1/documents/{id}/edges` is a deliberate exception: it uses `get_document_unchecked`
as a pure existence check (404 for an unknown `document_id`, without revealing any rights
content), followed by the actual content gate — see Error handling.

**Source resolution.** `document.created_via_delivery_id` points to the delivery that
originally created the document; via it `DeliveryRepository.get_delivery(...).source_id`
and `SourceRepository.get_source(...)` — both methods already exist, no new
repository method needed. This returns the source that created the document node, not
necessarily every source that has ever contributed data to this document (a document
could in principle be enriched via several deliveries from different sources) —
for the current collection (EUR-Lex, DGUV) this amounts to the same thing, see Open items.

## Endpoints (v1)

| Endpoint | Purpose | Repository method(s) |
|---|---|---|
| `GET /v1/documents?designation=&issuer=&jurisdiction=` | Search/lookup by designation | `find_by_designation` (identity) + `get_document_for_jurisdiction` (gate, see "The one gate") |
| `GET /v1/documents/{id}?jurisdiction=` | Document detail (designations, multilingual titles, source of origin incl. URL) | `get_document_for_jurisdiction` (gate) first, then `list_designations`/`list_titles` (enrichment), `get_delivery`/`get_source` via `document.created_via_delivery_id` |
| `GET /v1/documents/{id}/edges?jurisdiction=&edge_type=` | References/relationships (references, based_on_law, adopted_from) | `get_document_unchecked` (existence) + `list_free_layer_edges_for_jurisdiction` (gate) |
| `GET /v1/documents/{id}/validity?jurisdiction=` | Derived validity status | `get_document_for_jurisdiction` (gate) first, then evaluates `replaces`/`withdrawn_by` edges from `list_free_layer_incoming_edges_for_jurisdiction` |
| `GET /v1/export?jurisdiction=&format=json` | Complete dump of the free part of the graph (REQ-GRAPH-001) | `list_exportable_documents_for_jurisdiction` + `list_exportable_edges_for_jurisdiction` |

`edge_type` is typed as `EdgeType | None` (not as a raw string) — an invalid
value returns 400 instead of a silently empty list.

The `validity` endpoint is deliberately a separate, derived endpoint instead of "derive it yourself from the
edges" — REQ-INT-001 requires that a third-party system can query without knowledge of the internal
implementation; nobody outside this repository should need to know the `replaces`/`withdrawn_by` semantics.

## Export format (`GET /v1/export`)

REQ-GRAPH-001 only requires an "open, documented format" with a machine-readable
license notice — it does not prescribe a concrete format. Decided: simple, documented
JSON (no JSON-LD/RDF — premature complexity for the start, YAGNI), with an embedded
license block (`LicenseNotice`, see above). With the currently small collections (only
EUR-Lex/DGUV) a single JSON response is enough; pagination/streaming is YAGNI for the
start, see Open items.

## Data flow

Example `GET /v1/documents/{id}/edges`:

```
Router accepts jurisdiction, edge_type (optional)
    -> get_document_unchecked(id) is None? -> 404
    -> EdgeRepository(session).list_free_layer_edges_for_jurisdiction(id, jurisdiction)
    -> Python-side filter on edge_type, if set (no repository parameter)
    -> domain edges -> mapped to an EdgeResponse list
    -> 200 with a (possibly empty) list
```

`edge_type` is NOT passed through to the repository method — `list_free_layer_edges_for_jurisdiction`
has no such parameter; the filtering happens in the router on the already loaded list.

No endpoint writes.

## Error handling

Two different behavior patterns, depending on the response form — both deliberate, not
contradictory:

- **Single resources** (`/v1/documents/{id}`, `/v1/documents/{id}/validity`, as well as search):
  `get_document_for_jurisdiction` returns `None` both for an unknown `document_id` and
  for a missing classification — both cases uniformly result in 404, deliberately
  indistinguishable (otherwise the response would reveal whether a document exists that
  remains hidden from the requester).
- **List resource** (`/v1/documents/{id}/edges`): an unknown `document_id` results in 404
  (its own existence check via `get_document_unchecked`, which reveals no rights content),
  a known `document_id` that is not classified in the requested jurisdiction results in 200
  with an empty list — for a list, "no visible entries" is a normal result, not an
  erroneous one.

| Case | Behavior |
|---|---|
| Unknown `document_id` (single resource) | 404 with a structured error body (`ErrorResponse`), indistinguishable from "exists, but not classified" |
| Unknown `document_id` (`/edges`) | 404, own existence check, see above |
| `document_id` known, but `jurisdiction` without classification (`/edges`) | 200 with an empty result |
| Missing/invalid `jurisdiction` parameter | 400 — required parameter, no silent default (otherwise the wrong jurisdiction slips through by accident) |
| Invalid `edge_type` value | 400 (enum validation by FastAPI, no more silent empty-list return) |
| Database connection down (SQLAlchemy/OS error) | 503, no detail leak |
| Unexpected internal error (e.g. unresolvable origin) | 500 — deliberately NOT masked as 503; only real infrastructure errors (database, connection) result in 503, a programming error should stay visible instead of suggesting a retry |
| `format` parameter on `/v1/export` other than `json` | 400 — for the start `json` is the only valid value; the parameter exists for later formats (see Open items) without the endpoint path changing |

All 400/404/503 responses are documented via `ErrorResponse` (`{"detail": str}`) in the
OpenAPI specification — both globally (400/503 via `include_router(...,
responses=...)`) and per endpoint for the 404 cases.

## Test concept

- FastAPI `TestClient`/`httpx` against the app directly, no real network calls.
- Real PostgreSQL via the same Testcontainer approach as in `core/tests/conftest.py`
  (no mocking of the database, consistent with the project style so far).
- Test data is built directly via the repository layer (not via ingestion) —
  fast, focused on API behavior.
- One test fetches `/openapi.json` and checks that it is a valid OpenAPI document with the
  expected paths — mechanical acceptance of REQ-INT-001's "fully documented ... as an
  OpenAPI specification".
- Rights classification asymmetry tested explicitly: the same endpoint returns data for
  jurisdiction A, not for B (analogous to the existing pattern from the previous
  sub-projects).

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| REQ-INT-001 | Public, OpenAPI-documented, versioned HTTP API (`/v1/`) |
| REQ-GRAPH-001 | `/v1/export` — complete dump, open JSON format, machine-readable license notice |
| REQ-GRAPH-002 | Export AND the general read endpoints filter on `layer=FREE`; `/v1/export` additionally on `may_export_free`. Corrected in the final review: the original assumption "no licensed collections present, therefore trivially fulfilled" was the cause of a real leak (COMMERCIAL edges were publicly visible via `/edges`/`/validity`) — fulfillment is now enforced structurally by the layer-filtered repository methods, not by the incidental absence of licensed test data |
| REQ-GRAPH-003 | All endpoints answered deterministically from the graph, no model call |
| REQ-GRAPH-004 | Pydantic response models instead of direct domain/ORM objects — the storage technology stays behind the repository layer |
| REQ-GRAPH-006 | `jurisdiction` required parameter on every endpoint, jurisdiction-filtered repository methods |
| ADR-017 / REQ-ACC-001 | No account requirement — the API works completely without login |

## Open items / follow-up work

- **Rate limiting/quota** (REQ-SEC-004, server-side quota counting for anonymous
  use) — a separate infrastructure decision (counting mechanism without cookies/session), not
  part of this sub-project.
- **User uploads, SSO, LLM chat** (REQ-INT-002A/B/C, REQ-INT-003, REQ-INT-004,
  REQ-FUNC-001/002/003) — separate, later sub-projects.
- **Pagination/streaming for `/v1/export`** — not needed with the currently small collections (EUR-Lex,
  DGUV); as soon as further adapters/sources are added, this must be
  caught up on.
- **Several sources per document.** `source` on `DocumentResponse` currently shows only the
  creating source (`created_via_delivery_id`). As soon as a document is actually enriched via several
  sources, this needs either a `sources: list[SourceResponse]` field
  or a separate `/v1/documents/{id}/sources` endpoint — not observable with the current collection,
  therefore not specified here.
- **Commercial layer** (SLA, section-level references, confidence statements,
  industry-specific enrichments from REQ-GRAPH-002) — there are currently no licensed
  collections; as soon as some are added via REQ-INT-002/REQ-PART-001, the API needs its own,
  access-protected endpoints for them.
- **Deployment/reverse proxy configuration** — CLAUDE.md requires operation behind any
  reverse proxy in the container; the concrete STACKIT pipeline connection is a later
  deployment decision, analogous to the previous sub-projects.
- **OpenAPI documents a 422 that never occurs.** FastAPI automatically adds a
  422 entry for every endpoint with validated parameters; however, the `RequestValidationError` handler
  converts every such case into 400 at runtime, so 422 is never actually
  returned — a dead schema element (its own `HTTPValidationError` component schema,
  structurally different from `ErrorResponse`) for generated clients. From the final review,
  deliberately not fixed: would need an `app.openapi()` override for schema post-processing.
- **`/v1/documents/{id}/edges` and single resources have different
  404-vs-200-empty semantics**, see Error handling — deliberate, but an API consumer should
  be able to learn this from the documentation, not only from the behavior.
- **`/v1/documents` (search) returns a single object, not a list**, even though the path looks like
  a collection. As long as "search" only supports exact designation+publisher, this is
  unambiguous; as soon as fuzzy/ambiguous search is added, `list[DocumentResponse]` would be
  a breaking change — setting it up that way proactively now, while nothing depends on it, would
  be worth considering.
- **N+1 queries in the export** — `list_exportable_edges_for_jurisdiction` is called individually for each document.
  Unproblematic with the currently small collections; to be addressed with a growing collection before
  pagination (see above).
- **`SET TRANSACTION READ ONLY`** would be a structural (instead of only review-enforced)
  safeguard of "the API is read-only" — currently no code path enforces this property
  technically, only the absence of writing repository calls in the source code.
