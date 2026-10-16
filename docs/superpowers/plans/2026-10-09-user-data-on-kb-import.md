# User data on knowledge base import — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The import of a knowledge base dump never again blocks on user references: IDs (`work`, `document`, `edge`) become tombstones (`retired_at`), content and derivations (`segment`, `embedding`, `document_embedding`, `rights_classification`) are physically deleted, provenance (`delivery`, `source`) stays. Watchers learn through a new notification type `no_longer_available` that a watched document has been retired (Tasks 4–5).

**Execution order:** Tasks 1, 2, 4, 5, then Task 3 (documentation last, because ADR-026 describes the notification).

**Architecture:** Class constants in `normly_core/exchange/tables.py` (pure data, with a fail-closed test against the ORM foreign keys); migration 0033 and ORM column `retired_at` on three tables, which stays excluded from the exchange format; `replace_knowledge_base` is switched from three delete/insert passes to a single procedure "detach citations → delete content → set tombstones → insert". Spec: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`.

**Tech Stack:** Python 3.11+, SQLAlchemy 2 Core, Alembic, pytest + testcontainers (Postgres/pgvector).

## Global Constraints

- Source files carry the license header `SPDX-License-Identifier: AGPL-3.0-or-later` / `Copyright (C) 2026 normly contributors` (migrations like their neighbors).
- Commits: English, Conventional Commits, `-s` (DCO, the human's Signed-off-by), trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **never** `git config`; no push and no PR without asking first.
- Database access only in the repository layer (ADR-006); `normly_core/exchange/` and `graph/domain.py` contain no SQL and no SQLAlchemy.
- Rights classification is the only gate: `retired_at` is **not** a mandatory filter for reads; retired documents disappear because their classification is deleted. Do not introduce a second check.
- `retired_at` is not an exchange column: the dump, `exchange_columns` and `iter_exportable_rows` do not contain it; `EXCHANGE_SCHEMA_VERSION` and the dump layout remain unchanged.
- Processing steps idempotent: a second import of the same version changes nothing (not even `retired_at`/`withdrawn_at`).
- Lineage: `delivery_id` stays in every row; `delivery`/`source` are never deleted.
- Classes (binding): tombstone = `work`, `document`, `edge` (a retired edge is additionally revoked: `revoked_at = COALESCE(revoked_at, import time)`); provenance = `source`, `delivery` (a missing delivery receives `withdrawn_at`, if empty); content/derivation = `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` (are deleted). Procedure: load keys → detach citations → delete content (in reverse) → set tombstones → deliveries → insert → import record. An empty dump (no documents) is refused when the database is populated, except with `allow_empty`/`--allow-empty`.
- Detach rules for user references (binding): `chat_message_citation.segment_id` → `NULL` for segments that the dump no longer contains. All other references from user data/pipeline state point to tombstone or provenance classes and need no rule.
- Tests: `cd core && ../.venv/bin/pytest <path>`; script tests separately (`.venv/bin/pytest scripts/tests` in the repo root), the two conftest modules must not be mixed in one run.
- Documentation: ADRs, spec, plan, SRS, CLAUDE.md in German; `docs/guide/*` in English.
- ShellCheck is not touched by this plan; if it is after all, check with `koalaman/shellcheck:v0.9.0` (CI version).

## File overview

| File | Change |
|---|---|
| `core/src/normly_core/exchange/tables.py` | + `TOMBSTONE_TABLES`, `RETAINED_TABLES`, `PURGE_TABLES`, `DETACHED_REFERENCES`, `EXCLUDED_EXCHANGE_COLUMNS` |
| `core/tests/exchange/test_tables.py` | + class completeness, fail-closed foreign-key test |
| `core/migrations/versions/0033_add_retired_at.py` | `retired_at` on `work`, `document`, `edge` |
| `core/src/normly_core/graph/postgres/orm.py` | `retired_at` in `WorkORM`, `DocumentORM`, `EdgeORM` |
| `core/src/normly_core/graph/postgres/exchange.py` | Export without `retired_at`; new `replace_knowledge_base` |
| `core/src/normly_core/graph/domain.py` | Docstrings (`ImportBlockedError`, Protocol) |
| `core/src/normly_core/exchange/importer.py` | Docstring (import no longer blocks on user data) |
| `core/tests/exchange/test_exchange_repository.py` | replace old blocking/deletion tests, new tests |
| `core/tests/exchange/test_takedown.py` | new: withdrawal, return, gate queries, user data stays |
| `docs/adr/README.md`, `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`, `docs/guide/operations.md` | ADR-026, ADR-025 adjusted, import behavior |

---

### Task 1: Classes, migration, `retired_at`, export without `retired_at`

**Files:**
- Modify: `core/src/normly_core/exchange/tables.py`, `core/tests/exchange/test_tables.py`
- Create: `core/migrations/versions/0033_add_retired_at.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`WorkORM`, `DocumentORM`, `EdgeORM`)
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (`exchange_columns`, `iter_exportable_rows`)
- Test: `core/tests/exchange/test_published_role.py` (existing, must stay green), new: `core/tests/exchange/test_retired_at_not_exported.py`

**Interfaces:**
- Produces in `tables.py`:
  - `TOMBSTONE_TABLES: tuple[str, ...] = ("work", "document", "edge")`
  - `RETAINED_TABLES: tuple[str, ...] = ("source", "delivery")`
  - `PURGE_TABLES: tuple[str, ...] = ("document_designation", "document_title", "rights_classification", "segment", "embedding", "document_embedding")` — in the order of `KNOWLEDGE_TABLES` (parents first); deletion runs in reverse.
  - `DETACHED_REFERENCES: dict[tuple[str, str], str] = {("chat_message_citation", "segment_id"): "segment"}` (child table, column → parent table)
  - `EXCLUDED_EXCHANGE_COLUMNS: dict[str, tuple[str, ...]] = {"work": ("retired_at",), "document": ("retired_at",), "edge": ("retired_at",)}`
- Produces: ORM attribute `retired_at: Mapped[datetime | None]` on the three tables; `exchange_columns(table)` and `iter_exportable_rows(table)` do not return `retired_at`.

- [ ] **Step 1: Write failing tests**

Append to `core/tests/exchange/test_tables.py`:

```python
def test_every_knowledge_table_has_exactly_one_import_class():
    classes = [
        set(tables.TOMBSTONE_TABLES),
        set(tables.RETAINED_TABLES),
        set(tables.PURGE_TABLES),
    ]
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            assert a.isdisjoint(b)
    assert set().union(*classes) == set(tables.KNOWLEDGE_TABLES)


def test_purge_tables_keep_knowledge_table_order():
    order = [t for t in tables.KNOWLEDGE_TABLES if t in set(tables.PURGE_TABLES)]
    assert list(tables.PURGE_TABLES) == order


def test_every_foreign_key_from_outside_the_knowledge_base_has_a_rule():
    """
    Fail-closed: a table outside the knowledge base that points into it must
    point at a tombstone/retained table (the row survives a takedown), or be
    listed in DETACHED_REFERENCES (the reference is cleared when the target is
    purged). A new table with a reference but no rule fails this test.
    """
    kept = set(tables.TOMBSTONE_TABLES) | set(tables.RETAINED_TABLES)
    knowledge = set(tables.KNOWLEDGE_TABLES)
    for table in Base.metadata.sorted_tables:
        if table.name in knowledge:
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                target = fk.column.table.name
                if target not in knowledge:
                    continue
                if target in kept:
                    continue
                assert (table.name, column.name) in tables.DETACHED_REFERENCES, (
                    f"{table.name}.{column.name} -> {target} has no import rule"
                )
                assert tables.DETACHED_REFERENCES[(table.name, column.name)] == target
                assert column.nullable, f"{table.name}.{column.name} cannot be cleared"


def test_detached_references_point_at_purge_tables():
    for (child, column), parent in tables.DETACHED_REFERENCES.items():
        assert parent in tables.PURGE_TABLES
        assert column in Base.metadata.tables[child].columns
```

New file `core/tests/exchange/test_retired_at_not_exported.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange.tables import EXCLUDED_EXCHANGE_COLUMNS
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from normly_core.graph.postgres.orm import Base

from .helpers import make_delivery, make_document, make_source


@pytest.mark.parametrize("table", sorted(EXCLUDED_EXCHANGE_COLUMNS))
def test_retired_at_exists_in_the_orm_but_not_in_the_exchange(db_session, table):
    assert "retired_at" in Base.metadata.tables[table].columns
    repository = PostgresKnowledgeExchangeRepository(db_session)
    assert "retired_at" not in {c.name for c in repository.exchange_columns(table)}


@pytest.mark.parametrize("table", sorted(EXCLUDED_EXCHANGE_COLUMNS))
def test_exported_rows_do_not_carry_retired_at(db_session, table):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "x")
    make_document(db_session, delivery, "TRGS 900")
    repository = PostgresKnowledgeExchangeRepository(db_session)
    rows = [row for batch in repository.iter_exportable_rows(table) for row in batch]
    assert rows
    assert all("retired_at" not in row for row in rows)
```

(`.helpers` as in the existing tests of this folder; if a different import style is used there, adopt it.)

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py tests/exchange/test_retired_at_not_exported.py -v` — Expected: FAIL (`AttributeError: module 'normly_core.exchange.tables' has no attribute 'TOMBSTONE_TABLES'`).

- [ ] **Step 3: Extend `tables.py`**

Insert at the end of `core/src/normly_core/exchange/tables.py` (before or after `group_tables`):

```python
# --- Import classes (ADR-026) -------------------------------------------------
# What an import does with a knowledge-base row that the new dump no longer
# contains. A takedown always wins: user references never block an import.

#: Identifier rows without content. They stay with `retired_at` set, so that
#: user data pointing at them (watchlist, notification, citation) stays valid.
TOMBSTONE_TABLES: tuple[str, ...] = ("work", "document", "edge")

#: Provenance and identifier-only rows that are never deleted by an import
#: (tombstones reference them). A missing delivery gets `withdrawn_at`.
RETAINED_TABLES: tuple[str, ...] = ("source", "delivery")

#: Content and derivations. Physically deleted when missing from the dump, so
#: withdrawn text can no longer be read (also not from backups once they
#: expire). Same relative order as KNOWLEDGE_TABLES (parents first); deletes
#: run in reverse.
PURGE_TABLES: tuple[str, ...] = (
    "document_designation",
    "document_title",
    "rights_classification",
    "segment",
    "embedding",
    "document_embedding",
)

#: (child table, column) -> purge table it points at. The column is set to
#: NULL when the target row is purged. Every foreign key from outside the
#: knowledge base into a purge table must be listed here (test_tables.py).
DETACHED_REFERENCES: dict[tuple[str, str], str] = {
    ("chat_message_citation", "segment_id"): "segment",
}

#: Columns that exist in the database but are not part of the exchange format:
#: instance state of the importing side, never exported.
EXCLUDED_EXCHANGE_COLUMNS: dict[str, tuple[str, ...]] = {
    "work": ("retired_at",),
    "document": ("retired_at",),
    "edge": ("retired_at",),
}
```

- [ ] **Step 4: Migration and ORM**

Read the neighboring migration (`core/migrations/versions/0032_create_knowledge_base_import.py`: `revision = "0032"`, `down_revision = "0031"`, license header). `0033_add_retired_at.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add retired_at to work, document and edge

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

_TABLES = ("work", "document", "edge")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "retired_at")
```

In `orm.py`, add to each of `WorkORM`, `DocumentORM`, `EdgeORM`:

```python
    #: Set when an import no longer finds this row in the dump (takedown). The
    #: row stays as an identifier tombstone; not part of the exchange format
    #: (ADR-026).
    retired_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
```

- [ ] **Step 5: Export excludes `retired_at`**

In `core/src/normly_core/graph/postgres/exchange.py`:
- Import `EXCLUDED_EXCHANGE_COLUMNS` from `normly_core.exchange.tables`.
- Helper function:

```python
def _exchange_columns(sa_table: sa.Table) -> list[sa.Column]:
    excluded = set(EXCLUDED_EXCHANGE_COLUMNS.get(sa_table.name, ()))
    return [c for c in sa_table.columns if c.name not in excluded]
```

- `exchange_columns`: `return [ExchangeColumn(c.name, _kind(c)) for c in _exchange_columns(Base.metadata.tables[table])]`.
- `iter_exportable_rows`: Always restrict the statement to the exchange columns (not only when masking names): `statement = statement.with_only_columns(*[<masking literal or column> for column in _exchange_columns(sa_table)])`. The existing fail-closed masking (`sa_table.c[masked_name]`, `PUBLISHED_ROLE`) stays unchanged and is integrated into this list; `order_by(*_primary_key(sa_table))` stays.
- The import (`_upsert`) is adjusted in Task 2; in this task the import does not break with the new columns as long as `_upsert` keeps using `sa_table.columns` — that would be a `KeyError` for `retired_at` (the rows from the dump do not contain it). Therefore, already in this task, change `_upsert` and `_load_keys` so that they use `_exchange_columns(sa_table)` instead of `sa_table.columns` for the rows (pure column filter, no change in behavior; `retired_at` is then not touched by the upsert).

- [ ] **Step 6: Tests**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py tests/graph/test_architecture.py -q` — Expected: PASS (the ORM↔migration consistency tests require ORM and migration 0033 to match).

- [ ] **Step 7: Commit**

```bash
git add core
git commit -s -m "feat(exchange): retired_at tombstone column and import classes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: New `replace_knowledge_base` and tests

**Files:**
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (`replace_knowledge_base`, new helper methods, `_delete_missing`/defer logic is dropped)
- Modify: `core/src/normly_core/graph/domain.py`, `core/src/normly_core/exchange/importer.py` (docstrings only)
- Modify: `core/tests/exchange/test_exchange_repository.py`
- Create: `core/tests/exchange/test_takedown.py`

**Interfaces:**
- Consumes: constants from Task 1; `_load_keys` (temporary key tables `_kb_keep_<table>` per knowledge base table), `_upsert`, `_write_record`.
- Produces: unchanged public signature `replace_knowledge_base(tables, *, record)`; new behavior (see below).

**Procedure (binding, in this order):**
1. `_load_keys` (keys from the dump into temporary tables).
2. `_detach_missing_references`: for every entry in `DETACHED_REFERENCES`: `UPDATE child SET column = NULL WHERE column IS NOT NULL AND NOT EXISTS (key in keep_parent)`.
3. Delete content, in reverse through `PURGE_TABLES`: `DELETE ... WHERE NOT EXISTS (key in keep)` — **before** inserting, so that natural unique keys (`segment(document_id, sequence_number)`, `embedding(segment_id, model_name)`, designation/title) do not collide with old, obsolete rows.
4. Tombstones **before inserting**: for every table in `TOMBSTONE_TABLES`: `UPDATE t SET retired_at = :now WHERE retired_at IS NULL AND NOT EXISTS (key in keep)`; `now = record.imported_at`. For `edge` additionally `revoked_at = COALESCE(revoked_at, :now)` (the only read gate of edges; frees the partial unique index of active edges for a newly delivered edge).
5. Missing deliveries: `UPDATE delivery SET withdrawn_at = :now WHERE withdrawn_at IS NULL AND NOT EXISTS (key in keep)`.
6. Insert/update in `KNOWLEDGE_TABLES` order (`_upsert`); for `TOMBSTONE_TABLES`, `retired_at = NULL` is written as well (return); a returning edge receives `revoked_at` from the dump (`NULL`).
7. `_write_record(record)`; drop the temporary tables. The caller commits.

Additionally: `import_dump(..., allow_empty=False)` refuses (`ImportRefused`) a dump without `document` rows if `repository.has_documents()`; CLI flag `--allow-empty` on `import`.

Every `IntegrityError` in steps 2–6 becomes `ImportBlockedError(<table>, <first line of the error message>)` (last safeguard for unexpected foreign keys, not raised in regular operation).

- [ ] **Step 1: Adjust old tests / write new tests (RED)**

In `core/tests/exchange/test_exchange_repository.py`:

1. `test_replace_is_idempotent_and_removes_missing_rows`: The assertion `str(drop.id) not in _ids(first, "document")` becomes: the document is **still there** (tombstone) and the document's `rights_classification` is **gone**; the test is now called `test_replace_is_idempotent_and_retires_missing_rows`. The idempotency assertion (a second import does not change the snapshot) stays; `_snapshot` must contain `retired_at` for `work`/`document`/`edge`, so that "a second import does not change `retired_at`" is checked.
2. `test_replace_blocks_when_user_data_still_references_a_row`: **replace** with `test_user_data_never_blocks_an_import` (watchlist on a work whose documents are no longer in the dump → import goes through, watchlist row unchanged, work with `retired_at` set, `imported_version()` set).
3. Check the remaining tests (work merge between two imports, classification changes delivery, un-merge, `begin_nested` rollback) against the new behavior: they must **keep their intent** (no false block, idempotency, rollback without change on error); where they previously checked for "row deleted", switch to "tombstone/content deleted". A test that only described the former three-pass mechanism and no longer carries any behavior is removed (with a rationale in the report).

New file `core/tests/exchange/test_takedown.py` (fixtures from `.helpers`; accounts via `PostgresAccountRepository.create_account(email=..., password_hash=...)`, watch via `PostgresWatchlistRepository.add_watch(account_id=..., work_id=...)`, segments via `PostgresSegmentRepository.add_segment(...)`, embeddings as in `test_embedding_roundtrip.py`; chat citation via the existing chat repositories — check the signatures before writing with `grep -n "def create_session\|def add_message\|def add_citation\|def create_message" core/src/normly_core/graph/postgres/repositories.py` and adapt the tests to the real parameters, not their assertion):

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Takedown semantics of the knowledge-base import (ADR-026)."""

import sqlalchemy as sa

from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import ImportRecord
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository

from .helpers import NOW, make_delivery, make_document, make_source

RECORD = ImportRecord("2026.10.2", 1, "rev", NOW)


def _dump(repository):
    return {
        t: [row for batch in repository.iter_exportable_rows(t) for row in batch]
        for t in KNOWLEDGE_TABLES
    }


def _frozen(dump):
    return {t: (lambda rows=rows: iter([rows])) for t, rows in dump.items()}


def _without_document(dump, document_id):
    """The dump as if `document_id` had been taken down at the source."""
    drop = str(document_id)
    out = {t: list(rows) for t, rows in dump.items()}
    segment_ids = {r["id"] for r in out["segment"] if r["document_id"] == drop}
    out["document"] = [r for r in out["document"] if r["id"] != drop]
    out["rights_classification"] = [
        r for r in out["rights_classification"] if r["document_id"] != drop
    ]
    out["segment"] = [r for r in out["segment"] if r["document_id"] != drop]
    out["embedding"] = [r for r in out["embedding"] if r["segment_id"] not in segment_ids]
    out["document_embedding"] = [
        r for r in out["document_embedding"] if r["document_id"] != drop
    ]
    out["edge"] = [
        r for r in out["edge"]
        if drop not in (r["from_document_id"], r["to_document_id"])
    ]
    return out
```

Tests (each sets up a scenario with source, delivery, two documents `KEEP`/`DROP`, one segment each, a classification, an edge `KEEP→DROP`, an account, a watch on the work of `DROP`, a notification with `trigger_document_id=DROP`/`trigger_edge_id`, a `notified_edge` and a `rights_notification_baseline` entry and a chat citation on the segment of `DROP`, first imports the complete dump, then the dump without `DROP`):

- `test_takedown_deletes_content_and_keeps_identifiers`: after the second import there are **no** rows for `DROP` in `segment`, `embedding`, `document_embedding`, `rights_classification`; the `document` and its `work` exist with `retired_at IS NOT NULL`; `retired_at` of `KEEP` and its work is `NULL`; the edge `KEEP→DROP` exists with `retired_at` set; `delivery` stays; `source` stays.
- `test_takedown_keeps_user_data_and_only_clears_the_citation_segment`: watch, notification (incl. `trigger_*_id`), `notified_edge`, `rights_notification_baseline`, chat message are **present unchanged**; the citation still exists with `document_id` of `DROP` and `segment_id IS NULL`.
- `test_takedown_removes_the_document_from_every_gated_read`: After the import, `DROP` appears neither in `PostgresDocumentRepository(db_session).list_documents_for_jurisdiction("DE")` nor in `search_documents_for_jurisdiction(...)` (check the matching signature) nor in `list_exportable_documents_for_jurisdiction("DE")` nor in `iter_exportable_rows("document")`; `KEEP` still appears.
- `test_returning_document_clears_retired_at_and_restores_content`: Third import with the complete dump → `retired_at` `NULL` again for `DROP`, its work and the edge; `segment`/`embedding`/`document_embedding`/`rights_classification` back again; watch etc. unchanged; the earlier citation still has `segment_id IS NULL` (the reference is irrevocably detached).
- `test_withdrawn_delivery_gets_withdrawn_at`: Dump without an entire delivery (all its rows) → `delivery.withdrawn_at IS NOT NULL`; a second import does not change the timestamp.
- `test_second_import_changes_nothing`: After the second import (dump without `DROP`), a third import of the same dump produces an identical snapshot including the `retired_at` values (the timestamp stays that of the first withdrawal import).
- `test_import_inside_a_savepoint_rolls_back_cleanly`: A deliberately failing import (e.g. an artificially added foreign key from a test table to `segment` is too elaborate — instead: import in `db_session.begin_nested()`, then `rollback()`; snapshot equal to the previous one).
- `test_natural_key_collision_with_a_purged_row_does_not_block`: A segment `(document_id, sequence_number)` is missing from the dump and another segment (new ID) with the same natural key appears in the dump → the import goes through (the content class is deleted before inserting).

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_exchange_repository.py tests/exchange/test_takedown.py -v` — Expected: FAIL (the old algorithm deletes tombstone classes or blocks).

- [ ] **Step 3: Rebuild `replace_knowledge_base`**

In `graph/postgres/exchange.py`, replace the body of `replace_knowledge_base` and remove `_delete_missing` (together with the defer logic). Skeleton:

```python
    def replace_knowledge_base(
        self, tables: Mapping[str, RowBatches], *, record: ImportRecord
    ) -> None:
        """
        A takedown always wins: user data never blocks an import (ADR-026).
        What the dump no longer contains is handled by class:

        * content and derivations (PURGE_TABLES) are deleted physically,
          after user references to purged segments were cleared;
        * identifier rows (TOMBSTONE_TABLES) stay with `retired_at` set, so
          watchlists, notifications and citations keep their targets; a row
          that returns clears `retired_at` again;
        * provenance (delivery, source) stays; a missing delivery gets
          `withdrawn_at`.

        Content is deleted BEFORE the upsert so that a purged row cannot
        collide with a new row on a natural unique key. Nothing is committed.
        ImportBlockedError remains only as a last guard for an unexpected
        foreign key; after it the caller must roll back (or use a savepoint).
        """
        connection = self._session.connection()
        now = record.imported_at or datetime.now(timezone.utc)
        keep_tables = self._load_keys(connection, tables)
        step = "load"
        try:
            step = "detach"
            self._detach_missing_references(connection, keep_tables)
            for name in reversed(PURGE_TABLES):
                step = name
                self._delete_missing(connection, name, keep_tables)
            for name in KNOWLEDGE_TABLES:
                step = name
                self._upsert(connection, name, tables[name])
            for name in TOMBSTONE_TABLES:
                step = name
                self._retire_missing(connection, name, keep_tables, now)
            step = "delivery"
            self._withdraw_missing_deliveries(connection, keep_tables, now)
        except IntegrityError as exc:
            raise ImportBlockedError(step, str(exc.orig).splitlines()[0]) from exc
        self._write_record(record)
        for keep in keep_tables.values():
            keep.drop(connection)
```

Helper methods (all use `_primary_key`, `keep.c[...]` comparisons as before):

```python
    def _missing(self, sa_table, keep):
        match = sa.and_(*[keep.c[c.name] == c for c in _primary_key(sa_table)])
        return ~sa.exists().where(match)

    def _delete_missing(self, connection, name, keep_tables):
        sa_table = Base.metadata.tables[name]
        connection.execute(sa.delete(sa_table).where(self._missing(sa_table, keep_tables[name])))

    def _detach_missing_references(self, connection, keep_tables):
        for (child_name, column_name), parent_name in DETACHED_REFERENCES.items():
            child = Base.metadata.tables[child_name]
            parent = Base.metadata.tables[parent_name]
            keep = keep_tables[parent_name]
            (parent_key,) = _primary_key(parent)
            referenced = child.c[column_name]
            connection.execute(
                sa.update(child)
                .where(
                    referenced.is_not(None),
                    ~sa.exists().where(keep.c[parent_key.name] == referenced),
                )
                .values({column_name: None})
            )

    def _retire_missing(self, connection, name, keep_tables, now):
        sa_table = Base.metadata.tables[name]
        connection.execute(
            sa.update(sa_table)
            .where(sa_table.c.retired_at.is_(None), self._missing(sa_table, keep_tables[name]))
            .values(retired_at=now)
        )

    def _withdraw_missing_deliveries(self, connection, keep_tables, now):
        delivery = Base.metadata.tables["delivery"]
        connection.execute(
            sa.update(delivery)
            .where(delivery.c.withdrawn_at.is_(None), self._missing(delivery, keep_tables["delivery"]))
            .values(withdrawn_at=now)
        )
```

Change `_upsert`: for `name in TOMBSTONE_TABLES`, extend every row with `"retired_at": None` and include `retired_at` in `value_columns`/`set_` (`value_columns = [c for c in sa_table.columns if c.name not in key_names]` already contains the column; the rows from the dump must bring the key `retired_at` along: `row.setdefault`-style when building the rows). The self-reference deferral (`merged_into_work_id`) stays. `_from_exchange` ignores `None` and needs no special handling for `retired_at`.

Remove unused imports (`ImportBlockedError` stays). Import `PURGE_TABLES`, `TOMBSTONE_TABLES`, `DETACHED_REFERENCES` from `normly_core.exchange.tables`. Adapt the docstrings in `graph/domain.py` (`ImportBlockedError`, Protocol `replace_knowledge_base`) and `exchange/importer.py` to the new behavior ("no longer blocks on user data, only on an unexpected foreign key").

- [ ] **Step 4: Tests green**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph -q` — Expected: PASS. Then `cd core && ../.venv/bin/pytest tests -q` (complete core suite, about 4 minutes) — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core
git commit -s -m "feat(exchange): takedown wins - tombstone identifiers, purge content on import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: ADR-026 and documentation

**Files:**
- Modify: `docs/adr/README.md` (append ADR-026; ADR-025: adjust the blocking rule, the three passes and the open item on user references; check the register rows)
- Modify: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md` (Part 3, step 4 "Idempotent …")
- Modify: `docs/guide/operations.md` (import behavior)
- Modify: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md` (status: implemented)

- [ ] **Step 1: Write ADR-026** (format of the neighboring ADRs: `## ADR-026 — …`, status/date, context, decision, rationale, rejected, consequences). Content:
  - **Title:** "Handling user data on knowledge base import"; status accepted 2026-10-09.
  - **Context:** `ImportBlockedError` blocked imports on user references; a legally required withdrawal must not fail because of user data (CLAUDE.md "Carry lineage along"). Finding: no user data table stores copyrighted content, only references.
  - **Decision:** Classes (tombstone: `work`, `document`, `edge`, edges additionally revoked; provenance: `source`, `delivery`; content/derivation: `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` → deleted); protection against an empty dump (`allow_empty`/`--allow-empty`); `retired_at` (not in the exchange format); return; citations lose `segment_id`; fail-closed test for foreign keys; `retired_at` is not a mandatory filter, because the rights gate (deleted classification) takes the documents out of all gate-bound queries; deleting and retiring run before inserting because of natural keys (re-delivery with new IDs).
  - **Rationale:** A withdrawal always wins; no text remnants in production and in backups after they expire; no user data is lost.
  - **Rejected:** Blocking with a cleanup tool (the withdrawal waits for a human); adjusting/deleting user references (data loss without benefit, since they are only references); pure tombstones for content too (withdrawal only logical, the text would remain readable in the DB/backups).
  - **Consequences / open:** (1) In production a revocation makes the classification disappear; `notify-watchers` (RIGHTS_CHANGE) then sees nothing any more — a "no longer available" notification based on `retired_at` is follow-up work (product decision); (2) retention/expiry of tombstones open (Part B); (3) dumps must come from one lineage with stable IDs: a rebuild of the producer database with new IDs collides with leftover tombstones (partial uniqueness of edges, designations) and aborts with `ImportBlockedError`; (4) tombstones stay visible in the database to pipeline read paths without the rights gate (`*_unchecked`); these must not serve them as content.
  After Task 4/5, consequence (1) is no longer "open": in production the revocation is reported as a `no_longer_available` notification (detection from `retired_at`, dedup via `notified_retirement`); only the RIGHTS_CHANGE notification in the narrower sense remains open (rights values change without the document disappearing) — it continues to arise at the producer. Document it that way.
  Carry the reference to ADR-026 into ADR-025 (import: "detach citations → delete content → set tombstones → insert"; the blocking rule and the open item "user data that points to replaced segments/edges can block imports" are dropped).
- [ ] **Step 2: TP4 spec Part 3 step 4, `docs/guide/operations.md`:** Describe the import behavior (tombstones, return, what happens in the user data after a withdrawal) in two to four sentences (guide in English); set the status of the new spec to "implemented".
- [ ] **Step 3: Docs build as in CI** (docker `python:3.12` with `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, then `zensical build`; the output must contain a line `3 issues found`; run with `--user "$(id -u):$(id -g)"` and a writable HOME, and afterwards remove `site/` and `.cache/`, so that no root-owned files remain).
- [ ] **Step 4: Commit**

```bash
git add docs
git commit -s -m "docs: ADR-026 user data on knowledge-base import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review against the spec

| Spec section | Task |
|---|---|
| Decision classes (tombstone / provenance / content) | Task 1 (constants + test), Task 2 (behavior) |
| `retired_at` (migration, ORM, not in the exchange format) | Task 1 |
| Import procedure (detach citations, delete content, insert, tombstones, deliveries) | Task 2 |
| Return, idempotency | Task 2 (`test_returning_document…`, `test_second_import…`) |
| `retired_at` is not a mandatory filter (rights gate) | Task 2 (`test_takedown_removes_the_document_from_every_gated_read`) |
| Fail-closed foreign-key test | Task 1 |
| User data stays / does not block | Task 2 |
| ADR-026, ADR-025, spec, guide | Task 3 |

**Known gaps, deliberately not in this plan:** Expiry/cleanup of tombstones, the "no longer available" display and the RIGHTS_CHANGE notification on revocation in production (product decision, as open items in ADR-026), lifecycle of user data as a whole (Part B). **Risks during the build:** Unique keys of tombstone classes can collide with new IDs (ADR-026, consequence 3); chat repositories for the citation in the test (check signatures); the complete core suite must stay green after the switch (in particular the old work-merge/delivery-change tests).

---

## Extension: "No longer available" notification

Spec addition: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`, section on the "No longer available" notification. Owner decisions: **one notification per retired document**; only withdrawals **after** watching began; no link; dedup memory in its own table.

### Task 4: Core — type, table, detection, e-mail

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (`NotificationTriggerType.NO_LONGER_AVAILABLE = "no_longer_available"`; `Document.retired_at: datetime | None = None` as the **last** field with a default; new Protocol `NotifiedRetirementRepository`)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`NotifiedRetirementORM`; the ORM `Enum` of `NotificationTriggerType` picks up the new value automatically)
- Create: `core/migrations/versions/0034_add_no_longer_available.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_document_to_domain` sets `retired_at`; `PostgresNotifiedRetirementRepository`)
- Modify: `core/src/normly_core/notifications/detection.py` (loop, `_EMAIL_SUBJECTS`)
- Modify: `core/src/normly_core/exchange/tables.py` (`USER_TABLES` extended by `notified_retirement`, after `notified_edge`)
- Test: `core/tests/notifications/test_no_longer_available.py` (new), existing tests for tables/migration/architecture must stay green

**Interfaces:**
- Produces:
  - `NotifiedRetirementRepository` with `has_been_notified(*, account_id, work_id, document_id, retired_at) -> bool` and `mark_notified(*, account_id, work_id, document_id, retired_at) -> None` (no `get_`/`list_` names, because of the jurisdiction guard in `test_architecture.py`).
  - Table `notified_retirement(account_id UUID FK account, work_id UUID FK work, document_id UUID FK document, retired_at timestamptz, notified_at timestamptz DEFAULT now(), PRIMARY KEY (account_id, work_id, document_id, retired_at))`.
  - `run_notify_watchers` creates `NO_LONGER_AVAILABLE` notifications (`trigger_document_id` = document, `trigger_edge_id=None`, `trigger_jurisdiction=None`, rights fields `None`) and counts them in `notifications_created`/`emails_sent`.

**Behavior (binding):** Per watch and per document of the watched work from `list_documents_for_work_unchecked` with `retired_at is not None` and `retired_at > watch.created_at` and not `has_been_notified(...)`: create a notification (e-mail according to the account setting, as for the other types), then `mark_notified`. The dedup key field `retired_at` turns a later renewed withdrawal after a return into a new notification. Accounts with `NotificationPreference.NONE` are skipped as before. E-mail subject: `"Ein beobachtetes Regelwerk ist nicht mehr verfügbar"` (In English: A watched standard is no longer available; in `_EMAIL_SUBJECTS`), body as for the other types.

- [ ] **Step 1: Failing tests** in `core/tests/notifications/test_no_longer_available.py`. Scenarios (fixtures via the existing test helpers in `core/tests/notifications/` or `core/tests/exchange/helpers.py`; take the exact repository constructors from the existing notification tests before writing):
  1. Account + watch on a work; afterwards the document is retired (`UPDATE document SET retired_at = now()` via the ORM session in the test, or via `replace_knowledge_base` with a dump without the document — the latter is the end-to-end test) → `run_notify_watchers` creates **exactly one** `NO_LONGER_AVAILABLE` notification with `trigger_document_id`.
  2. Withdrawal **before** watching began (`retired_at <= watch.created_at`) → no notification.
  3. Second run → no second notification (idempotency).
  4. A read notification is cleaned up via `delete_read_before(...)` → the next run does **not** notify again.
  5. The document returns (`retired_at = NULL`) and is later retired again (new timestamp) → a **new** notification.
  6. Two retired documents of the same work → two notifications (per document).
  7. Account with `NotificationPreference.NONE` → no notification; account with `EMAIL`/`BOTH` → e-mail with the new subject to the fake `EmailSender`, `emailed_at` set; `NotifyWatchersSummary` counts notifications and e-mails.
  8. A retired document does not disturb the existing rights-change path (no error, no rights-change notification).
  Furthermore (add to existing test files): `PostgresNotifiedRetirementRepository` round trip; ORM↔migration consistency (`test_orm_migration_consistency.py`, `test_migration_determinism.py`) stays green; `test_tables.py` knows `notified_retirement` in `USER_TABLES` in FK-safe order.
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/notifications/test_no_longer_available.py -v` — Expected: FAIL (`AttributeError: ... NO_LONGER_AVAILABLE`).
- [ ] **Step 3: Implementation.** Migration `0034` (neighbor `0033` for style and IDs; `revision = "0034"`, `down_revision = "0033"`): (a) create the table `notified_retirement` (columns and primary key as above); (b) extend the CHECK constraint of the enum type `notification_trigger_type` on `notification` **and** `notified_edge` by `'no_longer_available'` — to do so, look up the actual constraint name in `0027_create_watchlist_and_notification.py` and `0030_create_notified_edge.py` (SQLAlchemy names it after the `name=` argument; with `op.create_table` it is `notification_trigger_type`; check with `\d notification` in the test container or `inspect(...).get_check_constraints`), `op.drop_constraint` + `op.create_check_constraint` with the extended value list; `downgrade` restores the old list (delete rows with the new value first, otherwise the constraint fails). Detection: after the loop over edges, before the rights loop, a loop over `documents` with `document.retired_at`; create the `NotifiedRetirementRepository` at the top of `run_notify_watchers`. Import `PostgresNotifiedRetirementRepository`. `Document` in `domain.py` gets `retired_at: datetime | None = None` at the end (no existing callers break).
- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/notifications tests/exchange tests/graph -q` — Expected: PASS. Then the complete core suite `cd core && ../.venv/bin/pytest tests -q`.
- [ ] **Step 5: Commit** `feat(notifications): notify watchers when a watched document is no longer available` (with `-s` and trailer).

### Task 5: Frontend — entry in the bell

**Files:**
- Modify: `frontend/src/components/page-header.tsx` (`TRIGGER_TYPE_KEYS`, `TRIGGER_TYPE_ICONS`)
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`, `frontend/src/lib/i18n/dictionary-keys.ts` (if the key has to be listed there; read the mechanism before changing it)
- Test: `frontend/tests/unit/page-header.test.tsx`

**Interfaces:**
- Consumes: the API returns `triggerType: "no_longer_available"` unchanged (the accounts API passes the type through as a string; no change needed there).
- Produces: i18n key `nav.notificationNoLongerAvailable` with `de: "Nicht mehr verfügbar"`, `en: "No longer available"`; icon `FileX` (lucide-react); mapping `no_longer_available` in both tables. No link.

- [ ] **Step 1: Failing test** in `page-header.test.tsx` (adopt the existing pattern of the file): A notification with `triggerType: "no_longer_available"` is shown with the label "Nicht mehr verfügbar" (de) or "No longer available" (en) and without the fallback "Benachrichtigungen" (i.e. Notifications); the icon element is not the default `Bell`.
- [ ] **Step 2:** `cd frontend && npx vitest run tests/unit/page-header.test.tsx` — Expected: FAIL (fallback label instead of the new label). If `node_modules` is missing: `cd frontend && npm ci` (may take a while; network needed).
- [ ] **Step 3: Implementation** as under Interfaces. Then `cd frontend && npx vitest run` (complete frontend test suite) and, if present in the project, `npx tsc --noEmit` — Expected: PASS. If a parity test between `de.json` and `en.json` exists, it must be green.
- [ ] **Step 4: Commit** `feat(frontend): show the no-longer-available notification` (with `-s` and trailer).

### Task 6: Documentation of the notification (included in Task 3)

The ADR-026 text (Task 3, step 1) already describes the notification; additionally, in `docs/guide/operations.md` (English), in the section on the import, one sentence: Watchers of a withdrawn document receive a "no longer available" notification the next time `notify-watchers` runs. And create the entry for ADR-026 in the ADR register, if the register keeps entries per ADR. No separate commit round needed; part of Task 3.

## Self-review of the extension

| Spec addition | Task |
|---|---|
| Type `no_longer_available`, detection after watching began, one notification per document | Task 4 |
| Memory `notified_retirement` (incl. `retired_at` in the key), cleanup does not trigger a second notification | Task 4 (tests 3, 4, 5) |
| Migration `0034` (table, CHECK extension) | Task 4 |
| E-mail subject, summary | Task 4 (test 7) |
| Bell: label de/en, icon, no link | Task 5 |
| ADR-026 consequence 1 resolved | Task 3 (last) |

**Risks:** The name of the CHECK constraint and the `downgrade` (delete rows with the new value before restoring); the frontend dictionary mechanics (key possibly generated/typed); `Document` is a frozen dataclass object with positional calls in tests — the new value has a default and comes last.

---

## Extension 2: Back up tombstone IDs too (rollback fix)

**Occasion (final review, I-1):** `normly-deploy rollback` rebuilds the database, imports the older dump version and then restores the user data (`pg_restore --data-only`). Tombstones (`retired_at`) are in no dump; user rows that point to them (`watchlist`, `notification`, `notified_*`, `rights_notification_baseline`, `chat_message_citation`) violate the foreign key on restore, after the tables have been dropped. Owner decision: **solve it completely**. Draft (confirmed): the backup includes the retired IDs together with their foreign-key parents as a separate small, `age`-encrypted JSON file; the rollback restores it after the knowledge base import and before the user data.

**Execution order of this extension:** Task 7 (core), Task 8 (scripts), Task 9 (documentation and findings of the final review). All on the branch `feat/user-data-on-import`.

**Global Constraints (additional):**
- Format of the file (binding): JSON, UTF-8, `{"format": 1, "created_at": "<ISO-8601 UTC>", "rows": {"source": [...], "delivery": [...], "work": [...], "document": [...], "edge": [...]}}`; the tables in this FK order (corresponds to the order of `KNOWLEDGE_TABLES` restricted to these five), rows per table sorted by primary key; values in exchange types (UUID and enum as string, timestamp/date ISO-8601, bool/int/str unchanged); **all** columns of the table including `retired_at` and `revoked_at` (unlike the public dump).
- Content: all rows with `retired_at IS NOT NULL` in `work`, `document`, `edge` plus the **closure over foreign-key parents within these five tables** (the document's work and the `merged_into_work_id` chain, the `from`/`to` documents of an edge together with their works, `delivery` and `source` of every included row). The closure is computed from the foreign keys of the ORM metadata, not hard-wired. Never content (no `segment`, `embedding`, `rights_classification`), no user data.
- Restore (`import-tombstones`): insert in FK order with `ON CONFLICT DO NOTHING` (rows already present, e.g. from the dump, are never changed); `work.merged_into_work_id` is deferred as in the import (first NULL, set afterwards). Inserted rows of the tombstone tables get `retired_at = backed-up value`; for parents without `retired_at` (living rows that the rollback dump does not know) `retired_at = created_at` of the file, so that they count as retired. These rows have no classification; the rights gate does not let them through. A later import that contains the row in the dump sets `retired_at` back to NULL.
- No SQL in `normly_core/exchange/` and `graph/domain.py`; new Protocol methods without a `get_`/`list_` prefix (`test_architecture.py`); `import-tombstones` and `export-tombstones` do not commit in the repository, the CLI commits.
- Backward compatibility: an older backup without `<base>.tombstones.age` remains usable; the rollback warns clearly (foreign-key error possible on restore) and continues.
- Scripts: `.sha256` stays the completion marker, the new file is uploaded **before** it; `prune` deletes the new file too; check ShellCheck with `koalaman/shellcheck:v0.9.0` (CI version); no plaintext file remains; tests with the fake binaries from `scripts/tests/conftest.py`.

### Task 7: Core — `export-tombstones` and `import-tombstones`

**Files:**
- Create: `core/src/normly_core/exchange/tombstones.py` (format, (de)serialization, orchestration without SQL)
- Modify: `core/src/normly_core/graph/domain.py` (Protocol `KnowledgeExchangeRepository`: `export_tombstone_support() -> dict[str, list[dict[str, Any]]]`, `restore_tombstone_support(rows: Mapping[str, list[dict[str, Any]]], *, restored_at: datetime) -> None`)
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (implementation: closure over foreign keys, insert with `ON CONFLICT DO NOTHING`)
- Modify: `core/src/normly_core/exchange/__main__.py` (subcommands `export-tombstones`, `import-tombstones`)
- Test: `core/tests/exchange/test_tombstones.py`, `core/tests/exchange/test_cli.py` (extend)

**Interfaces:**
- Produces:
  - `tombstones.build_document(rows: Mapping[str, list[dict]], *, created_at: datetime) -> str` and `tombstones.parse_document(text: str) -> tuple[dict[str, list[dict]], datetime]` (raises `ValueError` on a wrong `format`/structure); constant `TOMBSTONE_FORMAT = 1`; `TOMBSTONE_SUPPORT_TABLES = ("source", "delivery", "work", "document", "edge")`.
  - CLI: `python -m normly_core.exchange export-tombstones` → JSON on stdout, exit 0; `python -m normly_core.exchange import-tombstones` reads JSON from stdin, restores it, commits, prints `restored tombstone support: <n> rows`; on an invalid document exit 1 with a clear message on stderr, nothing changed (rollback of the session).
  - Both commands need `NORMLY_DATABASE_URL` (no `NORMLY_EMBEDDING_MODEL_REVISION`).
- Implementation details: serialization uses the column kinds from the `exchange_columns` logic (`_kind`), but over **all** columns of the table; timestamp/date ISO-8601 (with time zone) there and back; no vector columns in these five tables (a test that guarantees this: no column of kind `vector`).

- [ ] **Step 1: Failing tests** (`core/tests/exchange/test_tombstones.py`, fixtures from `.helpers` and the scenario from `core/tests/exchange/test_takedown.py`, if necessary move the helpers into `helpers.py`, as with earlier shared use): (1) closure: after a withdrawal (import without document `DROP`), `export_tombstone_support()` contains the retired `document`, its `work`, its `delivery` and `source`, for a retired edge both documents together with their works; no unrelated rows; values in exchange types; (2) content: no segment/no classification, `retired_at`/`revoked_at` are included; (3) round trip of `build_document`/`parse_document` (equality, time zone), rejection of a wrong `format` version and of a broken structure; (4) `restore_tombstone_support` into an empty knowledge base environment: foreign-key order, `merged_into_work_id` deferral (a work with `merged_into` pointing to a work that is inserted only afterwards), `ON CONFLICT DO NOTHING` (an existing row with different content stays unchanged), idempotency (restoring twice changes nothing), `retired_at` set for inserted rows (`restored_at` for living parents), inserted rows have no classification and appear in no rights-bound query; (5) **end to end of the rollback**: scenario with a withdrawal and user references (watch, notification with `trigger_document_id`/`trigger_edge_id`, `notified_*`, baseline, chat citation) → back up `export_tombstone_support()` and the user rows via SQL into Python structures → delete all user rows and the entire knowledge base in the test transaction → restore the older dump (exported before the withdrawal **without** the later tombstone? no: the dump of the version BEFORE the rollout; it does not contain the retired document) via `replace_knowledge_base` → `restore_tombstone_support` → re-insert the user rows: **no** foreign-key error, row counts equal; (6) CLI: `export-tombstones` prints valid JSON (with the test DB via the existing CLI test methodology), `import-tombstones` with a file via stdin, rejection of broken input with exit 1 and an unchanged DB, missing `NORMLY_DATABASE_URL`; (7) `test_architecture.py` stays green (method names).
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_tombstones.py -v` — Expected: FAIL (missing modules/methods). Run commands one at a time, the machine is memory-limited.
- [ ] **Step 3: Implementation** as above; closure in `PostgresKnowledgeExchangeRepository.export_tombstone_support`: starting set = primary keys of all rows with `retired_at IS NOT NULL` in `work`, `document`, `edge`; repeatedly: for every table of the five and every foreign key of a column onto another of these tables (or `work.merged_into_work_id` onto `work`), add the parent keys of the included child rows, until nothing changes any more; then, per table, read all columns of the included rows sorted by primary key. `restore_tombstone_support`: for the tables in FK order, `pg_insert(...).on_conflict_do_nothing()` in batches (`_WRITE_BATCH`); insert rows of `work` with `merged_into_work_id` set first with NULL and fill the value in afterwards via `UPDATE ... WHERE id = :id AND merged_into_work_id IS NULL` (only for rows that were actually newly inserted — the deferral must not change existing rows); set `retired_at` for inserted `work`/`document`/`edge` rows to the backed-up value or `restored_at` (only on insert; existing rows stay unchanged).
- [ ] **Step 4:** Focused (`cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_architecture.py -q`), then the complete core suite exactly once (`cd core && ../.venv/bin/pytest tests -q`, about 4 minutes, nothing else heavy in parallel).
- [ ] **Step 5: Commit** `feat(exchange): export and restore tombstone support rows` (with `-s` and trailer).

### Task 8: Scripts — backup and rollback

**Files:**
- Modify: `scripts/normly-backup` (creating, encrypting and uploading `<base>.tombstones.age`; upload order: `meta.json`, `dump.age`, `tombstones.age`, `.sha256` last; `prune` deletes the new file too and handles orphans for it as well)
- Modify: `scripts/normly-deploy` (rollback: load and decrypt the file, restore it after the knowledge base import and before `pg_restore`; warning if the file is missing)
- Modify: `scripts/tests/conftest.py` (additive: fake behavior for `exchange export-tombstones` on stdout, if needed), `scripts/tests/test_backup.py`, `scripts/tests/test_deploy*.py`

**Behavior (binding):**
- `normly-backup run`: after `pg_dump`/`age`, create the file in the container: `$COMPOSE run --rm --no-deps -T --entrypoint python pipeline -m normly_core.exchange export-tombstones > "$work/$base.tombstones.json"` (stdout, no mount; an error aborts the run, nothing uploaded, no output), encrypt it with `age -r "$NORMLY_BACKUP_AGE_RECIPIENT"` to `$base.tombstones.age`, delete the plaintext immediately. The upload order is `meta.json`, `dump.age`, `tombstones.age`, `.sha256`. The checksum file covers both files (`sha256sum "$base.dump.age" "$base.tombstones.age"`). `meta.json` gets a field `"tombstones": true`.
- `prune`: deletion order `.sha256` first, then `meta.json`, `tombstones.age`, `dump.age`; the orphan detection and "committed" logic stay (only bases with `.sha256` count); `tombstones.age` is in the suffix list.
- `normly-deploy rollback`: if `<backup>.tombstones.age` exists in the bucket (checked via `rclone lsf`/`rclone copyto` success), download it and decrypt it with `--age-identity` in `$work` (0700 directory, cleanup in the existing trap); after the knowledge base import and **before** `pg_restore`: `compose "$previous" run --rm --no-deps -T --entrypoint python pipeline -m normly_core.exchange import-tombstones < "$work/tombstones.json"`. If the file is missing: a clear warning on stderr ("backup has no tombstone file; a foreign-key error is possible while restoring user data that points at withdrawn documents"), the rollback continues. An error while restoring the tombstones counts, after `DESTRUCTIVE=1`, like any other error (recovery hint).
- The recovery hints in the error case remain correct without change.

- [ ] **Step 1: Failing tests** (fake harness): Backup: call order (tombstone export in the container after `pg_dump`/`age` of the dump, `age` for the tombstone file, uploads in the required order with `.sha256` last), error in the tombstone export (`FAKE_DOCKER_FAIL_ON=export-tombstones`) → abort, no upload, no output, no plaintext; `meta.json` contains `tombstones: true`; `prune` deletes the new file too and handles orphans. Rollback: order `psql DROP` < `migrate` < `import --fetch` < `import-tombstones` < `pg_restore`; file missing → warning, the rollback continues; file present → `import-tombstones` receives the decrypted content via stdin; error in `import-tombstones` → recovery hint, state unchanged, lock released. Existing tests stay green (harness only additive).
- [ ] **Step 2:** `.venv/bin/pytest scripts/tests -q` in the repo root — Expected: new tests FAIL.
- [ ] **Step 3: Implementation**, then `docker run --rm -v "$PWD":/mnt -w /mnt koalaman/shellcheck:v0.9.0 scripts/normly-deploy scripts/normly-backup scripts/normly-env.sh` (clean) and `.venv/bin/pytest scripts/tests -q`.
- [ ] **Step 4: Commit** `feat(backup): back up tombstone support rows and restore them before user data on rollback` (with `-s` and trailer).

### Task 9: Documentation and findings of the final review

**Files:** `docs/adr/README.md` (ADR-026 consequences/open, ADR-024, register), `docs/guide/operations.md`, `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`, `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`, `core/src/normly_core/exchange/tables.py` (comment only), `core/src/normly_core/graph/postgres/exchange.py` (docstring only)

- [ ] **Step 1: ADR-026 / ADR-024:** The limitation "rollback fails after a withdrawal" is dropped; instead describe the solution (tombstone file: content, closure over foreign keys, restore before the user data, `ON CONFLICT DO NOTHING`, backward compatibility with older backups) and what is **not** restored (content, rights; only IDs). Note that `revoked_at` on a retired edge is the import time and not an event date (M-9). ADR-024: the backup now contains a second file; retention applies to both.
- [ ] **Step 2: `docs/guide/operations.md` (English):** Backup (new file, order, recovery), rollback (step "restore tombstone support" before the user data, behavior when the file is missing), restore test (additional numbered step `import-tombstones` between the knowledge base import and `pg_restore`), M-4 (the "no longer available" notification applies only to watches older than the withdrawal and to accounts with notifications enabled).
- [ ] **Step 3: Findings of the final review:** (M-1) spec `2026-10-09-user-data-on-kb-import-design.md`: "Non-goals" and "Open items" match the shipped bell (the display is included; only link/detail page stay excluded); (M-2) TP4 spec: the user data group names `notified_retirement`; (M-3) ADR-026: the fail-closed test runs over every table outside the knowledge base (including `identity_resolution_case`), not only user data tables; (M-5) correct the comment in `exchange/tables.py` (RETAINED = provenance only) and the docstring of `replace_knowledge_base` (an edge is also revoked when it is retired; retiring runs before inserting).
- [ ] **Step 4:** Docs build as in CI (docker `python:3.12`, `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, `zensical build`, line `3 issues found`; with `--user "$(id -u):$(id -g)"`, a writable HOME and the venv under /tmp; afterwards remove `site/` and `.cache/`). If the docstring/comment change touches tests: `cd core && ../.venv/bin/pytest tests/exchange -q`.
- [ ] **Step 5: Commit** `docs: tombstone support in backup and rollback; align spec and ADR wording` (with `-s` and trailer).

## Self-review of extension 2

| Requirement (I-1) | Task |
|---|---|
| Back up tombstone IDs together with their FK parents as a separate encrypted file | Task 7 (core), Task 8 (script) |
| Rollback restores them after the knowledge base and before the user data | Task 8 (order test), Task 7 (end to end without FK error) |
| Backward compatibility with older backups | Task 8 (test "file missing") |
| Docs: ADR, guide, restore test, findings M-1..M-5, M-9 | Task 9 |

**Risks:** The closure over foreign keys must not be too small (edge → documents → works → deliveries → sources; test with an edge) and must not explode (only parents, never children); `ON CONFLICT DO NOTHING` with the self-FK `merged_into_work_id`; `docker compose run -T` with stdin redirection in the real Compose (only tested against fakes; live acceptance); the backup takes longer by the start-up time of the container (seconds).
