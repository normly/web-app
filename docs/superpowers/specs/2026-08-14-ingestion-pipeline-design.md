# Design: Ingestion Pipeline (EUR-Lex, DGUV)

**Date:** 2026-08-14
**Status:** for review
**Sub-project:** second of several for implementing the normly MVP (free core)

## Context

The first sub-project (data model & reference graph schema, see
`docs/superpowers/specs/2026-08-11-data-model-reference-graph-schema-design.md`) built the
PostgreSQL schema and the repository layer, but deliberately without ingestion logic and
without segment/embedding tables. The graph is empty.

REQ-PIPE-001 describes an eight-stage processing chain: source register, ingest adapters,
identity resolution, rights classification, structure extraction, reference extraction,
segmentation and embedding, output. That is too large for one sub-project.

**Decided with the owner:**

1. Scope: the full chain up to and including segmentation/embedding, but only for two
   concrete sources — **EUR-Lex** (lists of harmonized norms, metadata/references only, no
   full text) and **DGUV** (regulations, i.e. Vorschriften; real full text). "Output" is explicitly not
   part of this sub-project. For EUR-Lex specifically: the "Summary list of harmonised
   standards" PDFs published by the Commission per directive/regulation (e.g. for the
   Machinery Directive 2006/42/EC under
   `single-market-economy.ec.europa.eu/.../harmonised-standards/machinery-md_en`) — researched
   and verified (a real sample file, actually retrieved), not the CELLAR/SPARQL system, for
   which no comparably clean, documented schema for harmonized norms was
   found.
2. Only DGUV passes through structure extraction, segmentation and embedding — EUR-Lex has no
   full text and only feeds catalog entries and graph edges.
3. Rights classification for both sources runs automatically according to a source-specific rule,
   with no manual approval step.
4. The review interface from REQ-PIPE-007 remains data model + repository
   (queue) in this sub-project, no user interface — that comes with the backend API sub-project.
5. Embedding model: `intfloat/multilingual-e5-large`, locally via `sentence-transformers`,
   no external API. Tests consistently use the real model, no stub.
6. Raw files are stored content-addressed locally on disk. STACKIT Object
   Storage is a later deployment decision.
7. Invocation as a CLI (`python -m normly_core.pipeline ingest <quelle>`), no scheduler.
8. For the start, `adapter.fetch()` reads from a configured local directory
   (EUR-Lex/DGUV files are downloaded there manually for now) instead of retrieving
   over HTTP itself. Reason: automated, recurring retrieval (login session,
   pagination, rate limiting) is a separate, non-trivial piece of work that is independent of the
   actually valuable extraction/parsing logic — the parsing logic itself
   is now specified against real, verified formats (see item 1 and the
   Architecture section), only automated retrieval remains follow-up work. A real
   HTTP fetcher later replaces only this one spot, without touching the parsing logic.

## Goal of this sub-project

A queryable reference graph with real data from EUR-Lex and DGUV: norm nodes,
legal act nodes, replacement/reference edges, rights classification per node and jurisdiction,
and for DGUV additionally full-text segments with embeddings for the later RAG integration.
The adapter abstraction must fulfill REQ-PIPE-001's acceptance test: a new source is
connected without steps behind the adapter having to be adapted.

## Non-goals

- **Output / public API / chat.** Consumes the data created here via the
  repository layer, but is a separate sub-project.
- **User interface for the review queue.** Only data model + repository methods in
  this sub-project; a real UI comes with the backend API/frontend sub-project.
- **Further sources** (BAuA, CEN/CENELEC work programmes, ISO/IEC catalog data). The
  adapter abstraction must be able to take them in without changes to downstream steps,
  but connecting them concretely is follow-up work.
- **Perinorm/category C adapter.** Still tied to a concrete contract
  (see Non-goals of the previous sub-project).
- **STACKIT Object Storage, scheduler/orchestration for production operation.**
  Deployment decisions, not part of this sub-project.
- **Real HTTP connection to EUR-Lex/DGUV.** For the start, `adapter.fetch()` reads from a
  local directory (see Context, item 8) — a later HTTP fetcher is follow-up work.
- **General, configurable structure/reference extraction.** For the start
  source-specific and rule-based — no generic document understanding.

## Architecture

### Adapter abstraction

Three approaches were weighed:

1. **Protocol-based `SourceAdapter`**, adapters deliver a source-neutral `RawRecord`.
2. Adapters write directly to the database — rejected, violates REQ-PIPE-001's requirement
   that processing from identity resolution onward is independent of the provenance type.
3. A generic, configurable adapter (URL+mapping without code) — rejected for two
   structurally very different sources (EUR-Lex table PDF vs. DGUV running-text PDF); premature
   abstraction.

**Decided: approach 1.**

```python
@dataclass(frozen=True)
class RawRecord:
    source_id: uuid.UUID
    content_hash: str
    raw_designation: str
    raw_issuer: str | None
    raw_title: str | None
    full_text: str | None          # None bei EUR-Lex
    language: str | None           # "en" (EUR-Lex) / "de" (DGUV); Fallback "de" im Runner
    raw_references: list[RawReference]
    fetched_at: datetime

class SourceAdapter(Protocol):
    def fetch(self) -> Iterable[RawRecord]: ...
    def extract_structure(self, record: RawRecord) -> list[RawSection]: ...
    def classify_rights(self, record: RawRecord) -> RightsRule | None: ...
```

`classify_rights` returns `None` if the source cannot assign the case — the
runner then creates no classification row and no derived artifacts, but instead
queues the record in `identity_resolution_case` (`reason="cannot_classify_rights"`).
That is the safe default required in the error handling; originally the
Protocol signature forced every adapter to give an answer, which was corrected in the final
review. Likewise, the runner checks `regel.may_process` before every write access
(`reason="processing_not_permitted"` if `False`) — both adapters currently always deliver a
permissive, complete rule, but the capability now exists in the type system.
`SourceAdapter` actually lives in `pipeline/domain.py` (not in a separate
`adapters/base.py`, see the corrected module layout below).

`fetch()` takes no `since`: a directory adapter lists all
configured files on every run (the folder path comes via the adapter constructor, not via
`fetch()`); which deliveries are actually new is decided by `find_delivery` based on the
content hash (REQ-PIPE-006) — not by a timestamp filter at retrieval.

### EUR-Lex source format: "Summary list of harmonised standards"

Researched and verified with a real sample file, actually retrieved (Commission PDF
for the Machinery Directive 2006/42/EC, generated 15.10.2021, retrievable via
`single-market-economy.ec.europa.eu`). Consistent table structure, one row per norm:

| Column in the PDF | Example | Use |
|---|---|---|
| Legislation reference | `2006/42/EC` | Adapter configuration (one PDF file per legal act), not per row — becomes the `based_on_law` edge |
| ESO | `CEN` | `raw_issuer` |
| Reference number of the standard | `EN ISO 12100:2010` | `raw_designation` |
| Title of the standard | "Safety of machinery - General principles for design..." | `raw_title` |
| Type | `A` / `B` | not modeled for now (YAGNI) |
| Date of start of presumption of conformity | `08/04/2011` | not modeled for now |
| OJ reference for publication in OJ | `OJ C 110 - 08/04/2011` | Evidence for the `based_on_law` edge (not stored as a separate field) |
| Restriction, date/OJ reference for restriction | mostly `-` | not modeled for now |
| Date of withdrawal from OJ | e.g. `03/09/2022` | not modeled for now — the table names no successor norm, only a withdrawal date; a `withdrawn_by` edge would need a target document that cannot be cleanly derived from this alone. A deliberate simplification for the start, see Open items. |

Per row, the following is created: `document_designation` with `(issuer="CEN", designation="EN ISO 12100:2010")`,
`document_title` with the title, and a `RawReference(target_designation="2006/42/EC",
edge_type=EdgeType.BASED_ON_LAW)`. The legal act itself (`2006/42/EC`) is created as its own
`document` node on the first adapter run (publisher "EU", number "2006/42/EC").

Accompanying helper types (also in `pipeline.domain`, no SQLAlchemy dependency):

```python
@dataclass(frozen=True)
class RawReference:
    target_designation: str        # Bezeichnung des Zieldokuments, roh
    edge_type: EdgeType            # aus graph.domain, z. B. REFERENCES, REPLACES

@dataclass(frozen=True)
class RawSection:
    sequence_number: int
    heading: str | None
    text: str

@dataclass(frozen=True)
class RightsRule:
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str

@dataclass(frozen=True)
class IdentityResolution:
    document_id: uuid.UUID | None  # None, wenn neu anzulegen
    is_new: bool
    is_ambiguous: bool
    reason: str | None             # gesetzt, wenn is_ambiguous
```

`extract_structure` always returns an empty list for EUR-Lex (no full text).
`classify_rights` encapsulates the source-specific rights rule (see Data flow) — every
adapter knows its own legal situation; the pipeline itself contains no source-specific
case distinction.

### Module layout

Part of the same `core` package, no new top-level component:

```
core/src/normly_core/pipeline/
  domain.py          # RawRecord, RawSection, RawReference, RightsRule,
                       # IdentityResolution, SourceAdapter Protocol
  sources.py           # Quellregister (Publisher -> Kategorie/Rechtsraum/Meta),
                       # resolve_source() legt fehlende Registereinträge idempotent an
  adapters/
    __init__.py
    eur_lex.py
    dguv.py
  identity.py         # Bezeichnung parsen + gegen document_designation abgleichen
  references.py       # RawReference -> edge (Layer aus RightsRule.may_export_free)
  embeddings.py        # EmbeddingModel-Wrapper um sentence-transformers,
                       # optionaler lokaler model_path (siehe unten)
  runner.py           # Orchestrierung (siehe Datenfluss)
  cli.py              # build_adapter(), main()
  __main__.py          # `python -m normly_core.pipeline ingest <quelle>`
```

Deviation from the original draft: `SourceAdapter` lives in `domain.py` instead of in a
separate `adapters/base.py` (consistent with `graph.domain`, which likewise keeps its Protocols
next to the dataclasses). `cli.py` alone is not enough for `python -m` — `-m`
needs a `__main__.py`; that was not provided for in the original module layout and was
added during implementation.

**Source register (`sources.py`).** CLAUDE.md requires a register entry with a category
for every source. `resolve_source(publisher, session)` looks up an existing `source` row via
`SourceRepository.find_by_publisher` and otherwise creates it with hard-coded metadata
(EUR-Lex: category A, jurisdiction EU; DGUV: category A, jurisdiction DE). The lookup goes via
the bare `publisher` name, not via the complete register entry (category/
jurisdiction/retrieval path) — unproblematic for the two current, hard-wired sources,
but a later hardening (unique index over the full combination) is open, see
Open items.

`pipeline.domain` stays free of SQLAlchemy, like `graph.domain` — the same boundary.
Adapter-specific dependencies (HTTP client, `lxml`, PDF extraction) are confined to the
respective adapter file.

### Testing philosophy

As in the previous sub-project: no mocking of the database (real PostgreSQL with `pgvector`
via Testcontainers) and no mocking of the embedding model (real
`multilingual-e5-large`). Adapter tests run against real sample files recorded
once (the real EUR-Lex "Summary list" PDF, a DGUV PDF), no live network calls.

## Data model extension

### `segment` — full-text section (DGUV only)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `delivery_id` | UUID, FK → `delivery` | Lineage |
| `sequence_number` | int | Order in the document |
| `heading` | text, nullable | e.g. "§ 3 Grundpflichten" |
| `text` | text | |
| `language` | text | ISO 639-1 |
| `created_at` | timestamptz | |

Segment boundaries follow the natural structural units of the source (§ paragraphs in
DGUV regulations) — no separate chunking stage for the start (YAGNI, see
Pipeline stages).

Uniqueness over `(document_id, delivery_id, sequence_number)`, not just
`(document_id, sequence_number)` — the latter would, on a re-delivery of the same
document (e.g. a changed DGUV PDF), have silently discarded the new section texts
and returned the row of the first delivery, with the same consequences for the
cascading withdrawal as for `document_designation`/`document_title` in the previous
sub-project. Corrected in the final review (migration `0012`). Read accesses do
not yet filter by the currently active delivery — with a second, not yet
withdrawn delivery of the same document, both sets of rows would be returned
together. Open item, see below.

### `embedding` — vector representation of a segment

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `segment_id` | UUID, FK → `segment` | |
| `delivery_id` | UUID, FK → `delivery` | Lineage |
| `model_name` | text | e.g. "intfloat/multilingual-e5-large" |
| `vector` | `vector(1024)` (pgvector) | |
| `created_at` | timestamptz | |

`UNIQUE(segment_id, model_name)` — a segment can have several embeddings from different
model versions without the text having to be extracted again.

Both tables get the same idempotency handling (`_require_active_delivery`,
select-before-insert with `IntegrityError` recovery) and withdrawal handling
(cascading blocking/deletion on `revoke_delivery`) as the existing tables. The
drift guard test from the previous sub-project must be extended to cover these two tables
— it deliberately fails until that happens.

**New repository interfaces:** `SegmentRepository` (`add_segment`,
`list_segments_for_jurisdiction` — rights-gated following the same pattern as
`list_documents_for_jurisdiction`) and `EmbeddingRepository` (`add_embedding`,
`get_embedding`).

**Small, non-breaking extension to `DeliveryRepository`:** a new method
`find_delivery(source_id, content_hash) -> Delivery | None`, which the pipeline calls before
`record_delivery` in order to skip unchanged deliveries without expensive further processing
(REQ-PIPE-006). `record_delivery` itself stays unchanged — no intervention in
already accepted, merged code.

### `identity_resolution_case` — review queue (REQ-PIPE-007)

| Column | Type | Note |
|---|---|---|
| `id` | UUID, PK | |
| `delivery_id` | UUID, FK → `delivery` | |
| `raw_designation` | text | |
| `raw_issuer` | text, nullable | |
| `reason` | text | e.g. "unparseable_designation" |
| `status` | enum(pending, resolved, rejected) | |
| `resolved_document_id` | UUID, FK → `document`, nullable | |
| `resolved_at` | timestamptz, nullable | |
| `resolved_by` | text, nullable | |
| `created_at` | timestamptz | |

No rights gate needed — an internal administrative process, no content is served. New
repository interface `IdentityResolutionRepository` (`enqueue_case`,
`list_pending_cases`, `resolve_case`, `reject_case`).

## Pipeline stages

**Identity resolution.** The incoming designation is parsed into publisher/number/edition
and matched exactly against `document_designation` (`(issuer, designation)`).
Match → existing node. No match → new node. Not parseable → case in
`identity_resolution_case`; the rest of the collection continues unaffected.

**Rights classification.** Automatic, but source-specific, not a blanket rule by
category: EUR-Lex norm nodes (no full text known) get `may_process=true`,
`may_export_free=true`, but `may_index_fulltext=false`, `may_cite_passages=false`.
DGUV documents (real, free full text, § 5 UrhG (German Copyright Act)) get all four flags `true`.

**Structure extraction (DGUV only).** PDF text is extracted and split into segments based on the usual
DGUV structure (§ paragraphs, numbered sections) — rule-based,
no generic layout understanding.

**Reference extraction.** EUR-Lex: the legal act node (also a `document`, category A)
gets `based_on_law` edges to listed norm nodes. DGUV: cited norms/laws yield
`references` edges, the version history yields `replaces`/`withdrawn_by`.

**Segmentation and embedding (DGUV only).** Every extracted segment is embedded via
`multilingual-e5-large` and stored as an `embedding` row.

## Data flow

```
für jeden RawRecord aus adapter.fetch():
    wenn delivery_repo.find_delivery(source_id, content_hash) vorhanden: weiter  # REQ-PIPE-006
    versuche (in einem Savepoint, siehe Fehlerbehandlung):
        delivery = delivery_repo.record_delivery(source_id, content_hash, ingested_at)

        regel = adapter.classify_rights(raw_record)
        wenn regel ist None ODER regel.may_process ist False:
            identity_resolution_repo.enqueue_case(delivery_id, raw_designation, raw_issuer, reason)
            Savepoint erfolgreich beenden, nächster Datensatz  # keine Artefakte angelegt

        ergebnis = identity.resolve(raw_record)
        wenn ergebnis uneindeutig:
            identity_resolution_repo.enqueue_case(delivery_id, raw_designation, raw_issuer, reason)
            Savepoint erfolgreich beenden, nächster Datensatz

        document = ergebnis.document ODER document_repo.create_document(..., delivery_id)
        document_repo.add_designation(document.id, ..., sprache=raw_record.language, delivery_id)

        rights_repo.classify(document.id, regel.jurisdiction, regel.may_process, ..., delivery_id)

        für jede RawReference in raw_record.raw_references:
            references.extract(raw_record, document, regel, delivery_id)  # Layer aus regel.may_export_free

        wenn raw_record.full_text ist nicht None:
            für jeden RawSection in adapter.extract_structure(raw_record):
                segment = segment_repo.add_segment(document.id, delivery_id, ..., abschnitt)
                vektor = embeddings.embed(segment.text)
                embedding_repo.add_embedding(segment.id, delivery_id, modell_name, vektor)
    außer Exception:
        Savepoint zurückrollen (inkl. der `delivery`-Zeile — sonst gilt der Datensatz beim
        nächsten Lauf fälschlich als bereits verarbeitet), records_failed zählen, weiter
```

Every write call with `delivery_id` passes through the already existing
`_require_active_delivery` guard — no change to its semantics needed; the new
repository methods simply fall into line.

The original draft provided no error isolation per record (`record_delivery` sat
outside any transaction boundary). Corrected in the final review: the entire
processing of a record — including `record_delivery` itself — runs in a
`session.begin_nested()` savepoint, so that an error anywhere in the record does not leave behind a
half-created `delivery` row that would make the record wrongly appear
"already processed" on the next run.

## Error handling

| Case | Behavior |
|---|---|
| `adapter.fetch()` fails (network/API) | Run aborts for this source, no partial results; next run tries again |
| A single record raises an exception (any cause) | The savepoint for this record rolls back completely (incl. `delivery`), `records_failed` counted, run continues with the next record — real repeatability on the next run |
| Designation not parseable / identity ambiguous | `identity_resolution_case`, blocks only this document |
| Structure/reference extraction fails for a record | Same queue, same isolation |
| Automatic rights classification cannot assign the case (`classify_rights` returns `None`) | No classification row, no derived artifacts — `identity_resolution_case` with `reason="cannot_classify_rights"`, document stays blocked (safe default) |
| `regel.may_process` is `False` | Same queue, `reason="processing_not_permitted"` |
| Embedding fails for a segment | Segment without embedding, error logged, next run catches up (`add_embedding` idempotent via `(segment_id, model_name)`) |
| Write operation on a withdrawn delivery | `WithdrawnDeliveryError` (existing mechanism) |

## Test concept

- The test container switches to a pgvector-capable PostgreSQL image; a new migration
  activates the `vector` extension and creates `segment`, `embedding`,
  `identity_resolution_case`.
- Adapter tests against real, checked-in sample files (real EUR-Lex "Summary list" PDF,
  DGUV PDF) — both official category A works, unproblematic to check in.
- Identity resolution tested in isolation: clean match, new node, not parseable.
- End-to-end test: full pipeline against both sample files, checks the
  rights gate asymmetry directly (EUR-Lex nodes not full-text-indexed, DGUV nodes with
  real embedding vectors) as well as `find_delivery`'s skip behavior on a repeated run.
- Cascading withdrawal extended to segments/embeddings and tested, same pattern as
  the existing `revoke_delivery` test.
- Embedding tests use the real model throughout, no stub (decision with the
  owner, see Context) — test run time is correspondingly higher than in the previous
  sub-project.

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| REQ-PIPE-001 | Adapter abstraction, provenance-type-independent processing from identity resolution onward |
| REQ-PIPE-002 | `source` entries for EUR-Lex/DGUV (already in the schema, populated here) |
| REQ-PIPE-003 | TDM rights-reservation check documented at source registration (field already present) |
| REQ-PIPE-004 | Automatic, source-specific rights classification per document/jurisdiction |
| REQ-PIPE-005 | `delivery_id` on `segment`/`embedding`, cascading withdrawal extended |
| REQ-PIPE-006 | `find_delivery` skip, idempotent `add_segment`/`add_embedding` |
| REQ-PIPE-007 | `identity_resolution_case` queue, isolated blocking per document |
| REQ-PIPE-009 | EUR-Lex and DGUV are both category A/B, no category C/D access |
| REQ-GRAPH-001 | Legal acts as separate `document` nodes, `based_on_law` edges |
| ADR-006 | pgvector in the same database as the graph |
| ADR-008 | Structure/reference data flows into the graph, no LLM call for replacement/reference questions |
| ADR-012 | Neither EUR-Lex nor DGUV are commercially exploited catalogs — unproblematic |

## Open items / follow-up work

- **Further adapters** (BAuA, CEN/CENELEC, ISO/IEC catalog data) — the abstraction is designed
  for them, but they are not part of this sub-project.
- **Chunking beyond structural boundaries**, in case individual DGUV sections are too long for meaningful
  embeddings — not yet observable with the two chosen sources, therefore
  not specified here.
- **User interface for `identity_resolution_case`** — backend API/frontend sub-project.
- **Scheduler/automation of the CLI run** — a deployment decision, not part of this
  sub-project.
- **STACKIT Object Storage for raw files** instead of local disk storage — likewise a
  later deployment decision, analogous to the database question from the previous sub-project.
- **EUR-Lex withdrawal date without a successor norm.** For withdrawn norms, the "Summary list" table
  names only a date and an OJ reference, no successor norm — but a
  `withdrawn_by` edge would need a target document. For the start, the withdrawal date
  is not modeled; a later refinement could keep the referenced decision
  (OJ reference) itself as a node.
- **Real HTTP fetch for EUR-Lex/DGUV** — the parsing formats are now verified (see
  Architecture); automated retrieval itself (login/pagination/rate limiting) remains
  follow-up work.
- **Obtaining the embedding model touches a US-service question.** `EmbeddingModel` loads the
  model from `huggingface.co` by default (inference itself runs locally, as required by
  CLAUDE.md — only the one-time weight download does not). In the
  final review, an optional `model_path`/`NORMLY_EMBEDDING_MODEL_PATH` was added:
  a STACKIT deployment must provide the weights in advance (e.g. in the container image or
  via STACKIT Object Storage) and never load them from Hugging Face at runtime. The
  actual provisioning pipeline for this is not part of this sub-project.
- **`resolve_source` matches only on `publisher`**, not on the complete
  register entry (category/jurisdiction/retrieval path). Unproblematic for the two current sources
  hard-coded in the code; as soon as a publisher can have several, differently
  classified register entries, a unique index over the
  full combination is needed instead of the bare publisher string.
- **`list_segments_for_jurisdiction` does not filter by the currently active delivery.**
  Since migration `0012`, a document with two active, non-withdrawn
  deliveries (e.g. a corrected re-delivery) can return segments from both deliveries
  at the same time. Before a production API on this read method, either a
  "latest active delivery" filter or an explicit
  withdrawal step for the previous delivery on a re-delivery of the same document is needed.
- **The architecture drift test for the jurisdiction requirement** (`test_architecture.py`) checks only
  `get_*`/`list_*` methods on the repository Protocols, not `find_*` — both the
  existing `DocumentRepository.find_by_designation` and the new
  `SourceRepository.find_by_publisher` are ungated and thereby escape the test. Should
  be fixed in the test code itself at the next opportunity.
- **`RunSummary.records_processed` also counts records that later fail** (the
  counter is incremented before the actual processing attempt) — `processed` and `failed`
  from the CLI output therefore do not add up cleanly to the total.
