# Design: Edition-aware identity resolution

## Context

The just-merged sub-project "Edition change detection in ingestion
adapters" (PR #14) taught EUR-Lex and DGUV to create real `REPLACES`
edges from signals in their respective source data. During
this work, a deeper, previously unreachable defect in
`core/src/normly_core/pipeline/identity.py` was discovered and provisionally
defused through a guard in `references.py` (self-referential edge
prevented), but the actual cause was deliberately left open: **`identity.
resolve()` is edition-blind.**

Concretely: `resolve()` decides purely by string equality of
`(issuer, raw_designation)` whether an incoming document is the same as an
already known one. `record.content_hash` is not read anywhere in the process —
the content hash comparison happens one level higher in `runner.py`, but only
to skip a *byte-identical* re-delivery of the same file.
As soon as the bytes differ even slightly (a real new edition),
a new `Delivery` is created, but `resolve()` still matches on
the same `(issuer, designation)` and treats the new edition as an
*update* of the existing document — not as a new one.

This concretely affects DGUV: every real DGUV Vorschrift carries a
"vom `<date>`" issue date (i.e. "of <date>"), which the adapter already parses via regex
(`_ISSUE_DATE_PREFIX`) — but only to cut it off during the title line heuristic check,
never to capture it as a value of its own. `RawRecord`
currently has no `edition` field; `runner.py` sets
`add_designation(..., edition=None, ...)` hard-wired for every adapter.
For sub-project 4 (watchlist/notification) this is a real problem: a
new DGUV Vorschrift edition — the main case for which DGUV's own
edition change detection was built — currently triggers **no** recognizable
new edition. The system simply writes the new edition as an
additional, delivery-bound set of segments onto the same existing
`Document`.

`find_by_designation(issuer, designation)` — used both by
`identity.resolve()` and by `references.extract_references()` for
edge target lookups — likewise filters only on
`DocumentDesignationORM.issuer`/`.designation`; `DocumentDesignationORM.
edition` and `DocumentORM.edition` are ignored completely. A
database-wide unique constraint `uq_designation_issuer_designation` on
`(issuer, designation)` (without edition) would moreover prevent every attempt to keep two
editions as separate `DocumentDesignation` rows with an
`IntegrityError`, even if `resolve()` were corrected.

EUR-Lex is practically unaffected by this problem: its
designations already encode the edition in the string itself
(`"EN ISO 12100:2003"` vs. `"EN ISO 12100:2010"` are different
strings, so `(issuer, designation)` equality tells them apart
automatically). BAuA currently has no edition change detection and is
deliberately left out here.

## Goal of this sub-project

1. Actually capture DGUV's already parsed issue date as the edition
   and pass it through to the database.
2. Make `identity.resolve()` and `find_by_designation` edition-aware,
   so that two editions of the same designation are recognized as two separate
   `Document`s — without changing the existing behavior for
   adapters/callers without an edition concept (EUR-Lex, BAuA, unqualified
   predecessor references).
3. When a new edition is recognized, automatically adopt the correct `work_id`
   and create a `REPLACES` edge to the previous edition —
   so that a new DGUV edition is immediately a real, discoverable
   edition change, not just a new, isolated Document.

## Non-goals

- **No backfill** for already ingested data — only a dev/test
  database state, no production collection to take into account.
- **No edition population for EUR-Lex/BAuA.** EUR-Lex does not need it
  (edition already encoded in the designation); BAuA has no
  edition change detection and stays unchanged.
- **No general fix for a possible edition blindness of BAuA's own** —
  BAuA is excluded from the entire edition change detection
  (see the predecessor project's spec); this sub-project changes nothing about
  that.
- **No change to the existing Inkrafttreten section detection**
  (`_extract_predecessor_reference`) — it keeps running unchanged for
  the case of a predecessor with a *different* designation (free-text old title
  or modern designation of a different standard). The new
  auto-REPLACES mechanism in this sub-project is an additional,
  independent path for the case of the *same* designation, different edition.

## Architecture

### 1. `RawRecord` gets a new field

`core/src/normly_core/pipeline/domain.py`, `RawRecord` (frozen dataclass):
new optional field `edition: str | None = None`. A generic channel —
every adapter can populate it, only DGUV does so for now.

### 2. DGUV really captures the issue date

`core/src/normly_core/pipeline/adapters/dguv.py`: `_ISSUE_DATE_PREFIX`
gets a capture group around the date part. It is applied in `_fetch_file`
(not just in the existing `_is_publication_title_line` heuristic);
the matched date is ISO-normalized (`"2013-11-01"`) and set as
`RawRecord.edition`. If the "vom `<date>`" pattern is missing (e.g. a
publication without this field), `edition=None` remains — no error.

### 3. `find_by_designation` becomes edition-aware

`DocumentRepository.find_by_designation` (Protocol in `domain.py`) gets
a new optional parameter: `edition: str | None = None`.

- With `edition` set: exact matching on
  `(issuer, designation, edition)`.
- Without `edition` (the default, covers every existing caller): still returns
  `Document | None`, but now deterministically — with several
  editions of the same designation, the **newest** one (sorted by `created_at`
  descending, `LIMIT 1`), instead of an unspecified hit.
  For designations with only one edition (today's normal case for
  EUR-Lex/BAuA and for DGUV before this sub-project), nothing changes in the
  result.

Both existing callers (`identity.resolve()`, `references.
extract_references()`) keep calling without an `edition` argument, except
`identity.resolve()` itself (see item 4).

### 4. `identity.resolve()` recognizes edition changes

`core/src/normly_core/pipeline/identity.py`: if `record.edition` is set,
`resolve()` first calls `find_by_designation(issuer, designation,
edition=record.edition)`:

- Hit → as today, `is_new=False` (exact re-ingestion of the same
  edition).
- No hit, but `find_by_designation(issuer, designation)` (without
  edition, returns the newest existing edition) still finds something
  → **new edition recognized**: `is_new=True`, plus a new field on
  `IdentityResolution`: `previous_edition_document_id: uuid.UUID | None`,
  set to the Document found (now the previous one).
- No hit at all → `is_new=True`,
  `previous_edition_document_id=None` (a genuine first occurrence of this
  designation, as today).

If `record.edition` is not set (EUR-Lex, BAuA, DGUV publications
without a recognizable date), `resolve()` behaves exactly as today —
no behavior change for these cases.

### 5. Runner: work adoption + auto-REPLACES edge

`core/src/normly_core/pipeline/runner.py`: if
`result.previous_edition_document_id` is set,

- the new Document is created directly with the `work_id` of the previous edition
  (not via the RawReference-based
  `work_assignment.determine_work_assignment` machinery — the
  edition chain *is* by definition the same standard, not an
  ambiguity case),
- additionally a real `REPLACES` edge from the new to the previous
  Document is created via `edge_repo.create_edge(...)` (the same
  mechanism that `references.py` uses for RawReference-based edges;
  `create_edge`'s existing dedup logic prevents duplicate edges
  if the Inkrafttreten detection additionally finds the same connection).

This path runs independently of, and in addition to, the existing
`_extract_predecessor_reference`/`references.extract_references` chain.

### 6. Database migration

New Alembic migration: unique constraint
`uq_designation_issuer_designation` on `DocumentDesignationORM` extended from
`(issuer, designation)` to `(issuer, designation, edition)`.
A pure schema change without backfill (only a dev/test state, confirmed by
owner decision).

## Tests

- `identity.py`: new test for "same `(issuer, designation)`, different
  edition, different `content_hash`" → `is_new=True`,
  `previous_edition_document_id` set correctly. The existing test for
  "no edition" stays green unchanged (regression protection).
- `find_by_designation`: new test for "several editions, no
  edition parameter → returns the newest"; existing edition-less calls
  stay green unchanged.
- DGUV adapter: new test that the "vom `<date>`" date arrives correctly as an
  ISO-normalized `RawRecord.edition`; edge case without a
  recognizable date → `edition=None`, no error.
- End-to-end: two DGUV PDFs with an identical designation, different
  edition, really run through the pipeline — checks the new Document, `work_id`
  identical to the previous edition, a real `REPLACES` edge between
  the two.
- Migration test: confirms that the extended constraint allows two
  editions of the same designation as separate `DocumentDesignation`
  rows.
- No regression risk for the EUR-Lex/BAuA tests — their calls stay
  edition-less; their observable behavior does not change.
