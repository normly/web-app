# Design: User data on import of the knowledge base

As of: 2026-10-09 · Status: implemented. Follows TP4
(`docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`,
ADR-025). Part B (lifecycle of user data as a whole) is a separate,
later design.

## Goal and motivation

The import of a knowledge base dump (`replace_knowledge_base`) currently aborts
with `ImportBlockedError` as soon as user data still points to a row that
the new dump no longer contains (ADR-025, open item). That is wrong for
a **legally required withdrawal** (delivery withdrawn, classification
revoked): a reference in `watchlist`, `notification` or
`chat_message_citation` must never prevent the withdrawal (CLAUDE.md:
"Carry lineage along. … the promised withdrawal"). At the same time,
user data must not be lost just because the knowledge base changes.

**Finding from the code:** No user data table stores copyrighted
content. They are references (`work_id`, `edge_id`, `document_id`,
`segment_id`). The text of a citation is fetched from `segment` only when it is read.
A withdrawal therefore leaves no text remnants in user data,
only references to rows that may or should no longer exist.

## Decision (chosen by the owner: tombstones for IDs, deletion for content)

**A withdrawal always wins; a user reference never blocks an import.**
Knowledge base rows that a dump no longer contains are handled
by class:

| Class | Tables | Handling |
|---|---|---|
| Tombstone (ID, no content) | `work`, `document`, `edge` | Row stays; column `retired_at` is set. User references remain valid. If the row appears in the dump again later, `retired_at` becomes `NULL` again. A retired **edge** is additionally revoked (`revoked_at = COALESCE(revoked_at, import time)`), because `revoked_at` is the only read gate for edges; if it returns, the upsert writes `revoked_at` from the dump (`NULL`) back. |
| Provenance | `delivery`, `source` | Stays (tombstones point to it). A delivery missing in the dump receives `withdrawn_at`, if still empty. |
| Content/derivation | `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` | Is **physically deleted**. (Designations and titles belong here: no user reference points to them, the document keeps publisher/number/edition as its ID, and a re-delivery creates them again with new IDs, which would make old rows collide on the natural unique keys.)  Citations (`chat_message_citation`) lose their `segment_id` in the process (already nullable); the document remains as a tombstone. |

Thus a withdrawn text can no longer be read anywhere (not even from
backups after they expire), and no user reference is lost.

### Why `retired_at` is not a new mandatory filter

All reads go through the rights classification (the only gate,
CLAUDE.md). If the classification is deleted, the document disappears from
every gate-bound query. `retired_at` only distinguishes "retired"
from "never classified" and serves the return and a later display ("no
longer available"). No second check path arises.

## Implementation

**Schema:** Migration `0033` adds `retired_at timestamptz NULL` to `work`,
`document` and `edge` (ORM accordingly). `retired_at` is **not an
exchange column**: the dump does not contain it, the exchange format and
`EXCHANGE_SCHEMA_VERSION` remain unchanged. It is state of the
importing instance and is excluded on export
(`exchange_columns`/`iter_exportable_rows`).

**`replace_knowledge_base`** (replaces the three passes from the
TP4 implementation):

1. Load the dump's keys into temporary tables.
2. `chat_message_citation.segment_id` is set to `NULL` for segments that
   the dump no longer contains.
3. Delete the content/derivation class in reverse FK order
   (`document_embedding`, `embedding`, `segment`, `rights_classification`,
   `document_title`, `document_designation`) for all keys that are not in the
   dump.
4. Tombstones **before inserting**: `retired_at = import time` for missing,
   not yet retired `work`/`document`/`edge` (edges additionally
   `revoked_at`, see table). This frees the partial unique index of
   active edges before a newly delivered edge with the same
   endpoints and a new ID is inserted. "Missing" depends only on the
   key tables, so the order does not change which rows
   are retired.
5. A missing `delivery` receives `withdrawn_at`.
6. Insert/update in FK order; for rows of the tombstone classes
   from the dump, `retired_at` is set to `NULL` (return); for edges,
   `revoked_at` from the dump applies.
7. Write the import record; the caller commits as before.

**Protection against an empty dump:** If the dump contains no `document` row while
the database holds documents, `import_dump` refuses the import before the
first write (`ImportRefused`); `allow_empty=True` or the CLI flag
`--allow-empty` lifts this. The protection prevents a faulty
or empty export from retiring all documents at once.

`ImportBlockedError` (with `.step`) remains as a last safeguard for an **unexpected**
foreign key, and is no longer raised in regular operation.
Idempotency remains: a second import of the same version changes nothing
(in particular not `retired_at`).

**Fail-closed test:** A test walks through all foreign keys of tables outside
the knowledge base that point to knowledge base tables. Every target must belong to the
tombstone or provenance class or be on the deletion list with an
explicit resolution rule (today only `chat_message_citation.segment_id`).
A new table with a reference to the knowledge base without a rule makes the
test fail. This also applies to `identity_resolution_case`
(pipeline state), which points to `work` and `document`.

## Tests

- Withdrawal: a document disappears from the dump → segments, embeddings
  and classification are deleted; document and work remain with
  `retired_at`; watch and notification continue to exist; the citation
  loses only the `segment_id`.
- Return: the document returns → `retired_at` is `NULL` again, the
  content is imported anew.
- After the withdrawal, the document appears in no gate-bound query
  (document list, search, export).
- Idempotency (a second import changes nothing).
- User data no longer blocks the import (replaces the previous
  blocking test).
- The export does not contain `retired_at`; an export-import-export is
  row-identical.
- Rollback path: after a rollback (import of the earlier version),
  user references remain valid.

## Documentation

- **ADR-026** "Handling user data on knowledge base import":
  tombstone/provenance/content classes, rationale, what was rejected (blocking
  with a cleanup tool; adjusting/deleting user references; pure
  tombstones for content too, because the withdrawal would then only be logical).
- **ADR-025:** The blocking rule and the associated open item are dropped, with a
  reference to ADR-026; the description of the import (three passes) is
  adjusted.
- **TP4 spec** Part 3, `docs/guide/operations.md`: describe the import behavior
  (tombstones, return); update the ADR register.

## "No longer available" notification (extension)

Because a revocation in production deletes the classification (the rights-change
path of `notify-watchers` then sees nothing more), tombstones report the
loss themselves. Owner decisions:

- New notification type `no_longer_available`.
- **One notification per retired document** (not per work and run).
- Only what was retired **after watching began** is reported
  (as for edges).
- No link: the document can no longer be retrieved through the rights gate.
- Memory against duplicate notifications: new table `notified_retirement`
  (account, work, document, `retired_at`; the timestamp is part of the
  key, so that a withdrawal after a return is reported again).
  The table belongs to the user data; it points only to tombstone classes.
- E-mail: subject "Ein beobachtetes Regelwerk ist nicht mehr verfügbar"
  (In English: A watched standard is no longer available), body as for the other types.
- Interface: entry "Nicht mehr verfügbar" / "No longer available" in the
  bell with its own icon.
- Schema: migration `0034` (table, extension of the CHECK constraint for
  `trigger_type`); `Document` in the domain model receives `retired_at`.

Not included: detail page or link for retired documents,
expiry of tombstones. The rights-change path remains unchanged for the producer.

## Rollback and tombstones (extension 2)

Status: implemented.

The final review showed: the rollback from TP4 rebuilds the database,
imports the older dump version and restores the user data. Tombstones
are in no dump; user rows that point to them then violate the foreign key on
restore (after the tables have been dropped). Owner
decision: solve it completely.

- The backup includes the **retired IDs together with their foreign-key
  parents** as a separate, `age`-encrypted JSON file
  (`<base>.tombstones.age`): all rows with `retired_at` in `work`,
  `document`, `edge` plus the closure over the foreign keys within
  `source`, `delivery`, `work`, `document`, `edge`. Never content, never rights.
- `export-tombstones` / `import-tombstones` in the core (repository layer,
  `ON CONFLICT DO NOTHING`, inserted rows count as retired).
- `normly-backup` uploads the file before the `.sha256` marker; `normly-deploy
  rollback` restores it after the knowledge base import and before the
  user data. Older backups without the file remain usable, with a
  clear warning.

## Non-goals

- Expiry and cleanup of tombstones.
- Link or detail page for retired documents (the bell entry
  "Nicht mehr verfügbar" is shipped).
- Lifecycle of user data as a whole (retention, account deletion,
  access request/export, effect in backups): separate design, Part B.
- Change to the exchange format or the export rules.

## Open items

- Retention of tombstones (unlimited today; identifiers, no
  content): will be decided as part of Part B.
- Whether retired documents get a link or a detail page: the
  bell shows the entry "Nicht mehr verfügbar" (shipped, see the
  "No longer available" notification above); a target for the click is a product decision, not part
  of this change.
