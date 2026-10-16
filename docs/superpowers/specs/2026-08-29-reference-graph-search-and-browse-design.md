# Reference graph search/browsing — Design

Sub-project 2 of the frontend. Sub-project 1 (app shell + chat) is complete and
merged into `main`. This document describes search, browsing by publisher and a
clickable document detail page on top of the existing `api/` service — without a language model.

## Decided with the owner

1. **Scope of functions:** search + document detail page with graph browsing (references,
   validity status) + a dedicated browse view by publisher, independent of a
   search input.
2. **Rate limiting:** build a simple server-side rate limiting into `api/` now
   (Postgres-backed), instead of deferring it further as an open item —
   the searchable catalog view is a considerably more attractive target for
   automated bulk queries than the chat so far.
3. **Session attribute for rate limiting:** REQ-ACC-003 requires counting
   "based on an assigned session attribute in combination with the client IP address"
   — not the client IP address alone. Instead of leaving that as an open item,
   the frontend BFF assigns a new, separate anonymous identifier cookie
   (`normly_anon_id`, separate from the chat/account session, intended only for rate
   limiting), which is sent along as a header with every `api/` call. `api/`'s
   rate limiting keys on (anon ID + client IP address) instead of only the
   client IP address.
4. **Jurisdiction:** becomes app-wide state (new `normly_jurisdiction` cookie,
   analogous to the existing `normly_locale`), applies to chat **and** search/browsing
   together. Incidentally fixes the previously hard-coded `"DE"` default in the chat call.
   Initial selection: DE (default) and EU — both already represented in existing test
   data.

## Architecture

Two building blocks: a small backend extension in `api/` (new search/browse endpoint
plus rate limiting) and new frontend pages following the same BFF pattern as
sub-project 1 — no direct client access to `api/`, every call goes through a
Next.js Route Handler under `/api/*`.

### Backend (`api/`)

**New endpoint `GET /v1/documents/search`** — covers full-text search and
browse-by-publisher with one endpoint, instead of building two separate ones:

- Query parameters: `jurisdiction` (required, as with all existing endpoints),
  `q` (optional, free text over `DocumentDesignation.designation` and
  `DocumentTitle.title`, `ILIKE`-based — no full-text index needed for the current
  data volume), `issuer` (optional, exact filter on `DocumentDesignation.issuer`),
  `limit` (default 20, upper limit 100), `offset` (default 0).
- Response: `{ results: list[DocumentResponse], total: int }` — reuse of the
  existing `DocumentResponse` schema instead of a new, almost identical
  summary type (YAGNI).
- Rights gate: the same jurisdiction-bound visibility check as the
  existing endpoints (`get_document_for_jurisdiction` equivalent per hit) —
  only what the single retrieval would let through anyway appears in the hit list.
- Builds on `DocumentRepository.list_documents_for_jurisdiction` — already
  documented in the protocol as the sanctioned path for exactly this purpose, but
  not wired to any router so far. The repository layer gets an
  extension with `q`/`issuer` filters and pagination — no new abstraction, no
  breach of ADR-006 (database access only through the repository layer).

**Rate limiting** — now fully covers REQ-ACC-003 (session attribute **and**
client IP address together), not just one partial aspect:

- Postgres-backed counter (no Redis — not part of the approved stack under
  CLAUDE.md; Postgres is the shared data store anyway and therefore also works
  correctly across several `api/` replicas, unlike a pure
  in-memory counter per process).
- Key: the combination of an anonymous session attribute (see below) and the
  client IP address, read from `X-Forwarded-For` (set by the upstream reverse
  proxy) with a fallback to the direct connection address.
- **Session attribute:** `api/` itself deliberately stays stateless — assigning an
  anonymous identifier conceptually belongs at the edge of the application, not in the
  core data service. The frontend BFF therefore assigns a new,
  separate cookie `normly_anon_id` on the first visit (httpOnly, random value, ~1 year lifetime
  — separate from `normly_session`/`normly_account_session`, exclusively for
  rate limiting, no link to chat history or account) and passes it through as the header
  `X-Normly-Anon-Id` with every `api/` call. `api/`'s
  rate-limiting dependency reads this header, if present, and keys
  on `(anon_id, client IP address)`; if the header is missing (e.g. a hypothetical
  future direct access without the frontend BFF), it falls back to the client IP address
  alone instead of rejecting the request.
- Fixed time window (300 anonymous requests/minute per key, across all
  `api/` endpoints, not just search) as a reusable
  FastAPI dependency. Originally 60; a single detail page costs 3+N
  requests (document, edges, validity, one resolution per edge), so
  ordinary browsing would have used up the old quota. The value is
  a starting point with headroom, not derived from measured traffic.

### Frontend

**Anonymous identifier for rate limiting:** since Next.js Server Components cannot set
cookies during rendering, a new, minimal
`middleware.ts` (not present in the project so far) takes this on — it runs before every request,
checks for `normly_anon_id` and sets it once if missing. This way the cookie is
set regardless of which page is visited first, without every single
BFF route handler duplicating this logic.

**New pages:**
- `/search` — search input + paginated hit list, filter by publisher. Without
  a search input, with only the publisher filter set, the same page covers "browse
  by publisher" — no separate page needed for it.
- `/documents/[id]` — detail page: designations/title/source (`GET
  /v1/documents/{id}`), validity status (`.../validity`) and outgoing references
  grouped by edge type (`.../edges`). Each reference links to the respective
  target detail page — the reference graph becomes traversable by clicking, not just
  stored in a structured way.

**New BFF route handlers** (same pattern as the existing
`api/documents/[id]/route.ts`, pure proxies passing the status code through):
`GET /api/documents/search`, `GET /api/documents/[id]/edges`,
`GET /api/documents/[id]/validity`. All path and query values are handled with
`encodeURIComponent()` from the start — sub-project 1 had a real
path traversal gap here that was only found in the final review; this time it is
built correctly encoded, not patched afterwards.

**New UI building blocks** (shadcn/ui style, like the existing four — Button/Input/
Dialog/Tabs): a simple table/list for hit lists, a
pagination component, a `Badge` for edge type/validity status. No
autocomplete/command palette — additional scope without an SRS requirement.

**`JurisdictionSwitcher`** in the existing `AppHeader`, analogous to the `LocaleSwitcher`:
sets a `normly_jurisdiction` cookie (not httpOnly, like `normly_locale` — pure
UI state, not a security attribute), read server-side in `layout.tsx`. The
chat call in `home-page-content.tsx` reads this jurisdiction from now on instead of the
hard-coded `"DE"`.

**i18n:** new `search` namespace in `de.json`/`en.json` for the search input,
empty state, pagination, as well as human-readable DE/EN labels for the five
`EdgeType` values (references/replaces/withdrawn_by/based_on_law/adopted_from) and the
three `ValidityResponse` statuses (valid/replaced/withdrawn).

## Data flow

**Search cycle:**
```
Input /search → GET /api/documents/search?q=...&jurisdiction=<cookie>
  → api/'s new endpoint (rate-limiting dependency first)
  → hit list (DocumentResponse[] + total)
Click on a hit → /documents/[id]
  → three parallel BFF calls: detail, edges, validity
  → detail page with clickable references to further detail pages
```

**Jurisdiction change:** `JurisdictionSwitcher` sets the cookie client-side
(`document.cookie`, like the existing `LocaleSwitcher`) → the next server request
(page change or manual reload) reads the new value in `layout.tsx` →
both chat and search/browse calls use it.

## Error handling

| Case | Behavior |
|---|---|
| Rate limit exceeded | `api/` responds 429, BFF passes it through, UI shows a message pointing to sign-in (REQ-ACC-003: "When the quota is reached, the user is referred to sign-in") |
| Empty hit list | Dedicated empty state, not an error |
| Document not found / not rights-cleared | As with the existing citation resolution: 404 is not differentiated (deliberate existing behavior of `api/`, prevents inferring the existence of blocked content); UI shows a generic "not found" |
| `api/` unreachable | As in the chat BFF: status code passed through, UI shows a generic error message |

## Test concept

- **`api/`:** pytest for the new search endpoint (hits/filter/pagination/
  rights gate) and for rate limiting — including a test that actually triggers the
  time window and verifies the 429, as well as a test that
  confirms that two different `X-Normly-Anon-Id` values from the same
  client IP address are counted separately (not just the dependency wiring).
- **`core/`:** repository test for the extended `list_documents_for_jurisdiction`
  (filter and pagination behavior), same pattern as the existing
  repository tests.
- **`frontend/`:** test for the new `middleware.ts` (`normly_anon_id` is set when
  the cookie is missing, left unchanged when the cookie is present),
  Vitest unit tests for the new BFF routes (incl. an encoding test modeled on
  the path traversal fix found in sub-project 1) and components,
  Playwright extension of the existing E2E suite with a search-and-detail run.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-ACC-001 (anonymous base use) | Search/browsing/reference graph queries work without an account |
| REQ-ACC-003 (quota for anonymous use) | Rate limiting covers the session attribute (`normly_anon_id`) **and** the client IP address together, as required by the wording |
| REQ-GRAPH-001/003/004 | New endpoint stays behind the repository abstraction, purely deterministic, no model call |
| REQ-GRAPH-005 (internationalization) | The jurisdiction selection makes the graph modeling, multilingual/multi-jurisdiction-capable from the start, visible in the UI for the first time |
| REQ-GRAPH-006 (jurisdiction-specific classification) | The search endpoint filters strictly by `jurisdiction`, like all existing endpoints |
| REQ-SEC-004 (protection against bulk extraction) | Partially: rate limiting yes, anomaly detection/log analysis no — open item |
| ADR-006 (storage technology interchangeable) | Search filtering stays in the repository layer, no SQL business logic in the router |
| ADR-017 (anonymous use, shared infrastructure with rate limiting) | The new dependency is deliberately designed to be reusable for further `api/` endpoints, not just for search |

## Open items

- Full anomaly detection/log-based analysis per publisher (REQ-SEC-004)
  — only rate limiting is part of this sub-project.
- Further jurisdictions beyond DE/EU — the selection is set up as a simple, extensible
  list, not determined dynamically from the backend.
- Full-text index (instead of `ILIKE`) — sufficient for the current data volume; becomes
  relevant as soon as the catalog grows considerably.
