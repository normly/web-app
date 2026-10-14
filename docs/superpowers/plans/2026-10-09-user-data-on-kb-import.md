# Nutzerdaten beim Wissensbestand-Import — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Import eines Wissensbestand-Dumps blockiert nie mehr an Nutzerverweisen: Kennungen (`work`, `document`, `edge`) werden zu Tombstones (`retired_at`), Inhalt und Ableitungen (`segment`, `embedding`, `document_embedding`, `rights_classification`) werden physisch gelöscht, Herkunft (`delivery`, `source`) bleibt. Beobachter erfahren per neuem Benachrichtigungstyp `no_longer_available`, dass ein beobachtetes Dokument zurückgezogen wurde (Tasks 4–5).

**Ausführungsreihenfolge:** Task 1, 2, 4, 5, dann Task 3 (Dokumentation zuletzt, weil ADR-026 die Meldung beschreibt).

**Architecture:** Klassen-Konstanten in `normly_core/exchange/tables.py` (reine Daten, mit Fail-closed-Test gegen die ORM-Fremdschlüssel); Migration 0033 und ORM-Spalte `retired_at` auf drei Tabellen, die aus dem Austauschformat ausgeschlossen bleibt; `replace_knowledge_base` wird von drei Lösch-/Einfügedurchläufen auf einen Ablauf „Zitate lösen → Inhalt löschen → Tombstones setzen → einfügen“ umgestellt. Spec: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`.

**Tech Stack:** Python 3.11+, SQLAlchemy 2 Core, Alembic, pytest + testcontainers (Postgres/pgvector).

## Global Constraints

- Quelldateien tragen Lizenzheader `SPDX-License-Identifier: AGPL-3.0-or-later` / `Copyright (C) 2026 normly contributors` (Migrationen wie die Nachbarn).
- Commits: Englisch, Conventional Commits, `-s` (DCO, Signed-off-by des Menschen), Trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **nie** `git config`; kein Push und kein PR ohne Rückfrage.
- Datenbankzugriff nur in der Repository-Schicht (ADR-006); `normly_core/exchange/` und `graph/domain.py` enthalten kein SQL und kein SQLAlchemy.
- Rechteklassifikation ist das einzige Tor: `retired_at` ist **keine** Filterpflicht für Lesezugriffe; zurückgezogene Dokumente verschwinden, weil ihre Klassifikation gelöscht ist. Keine zweite Prüfung einführen.
- `retired_at` ist keine Austauschspalte: Der Dump, `exchange_columns` und `iter_exportable_rows` enthalten sie nicht; `EXCHANGE_SCHEMA_VERSION` und das Dump-Layout bleiben unverändert.
- Verarbeitungsschritte idempotent: ein zweiter Import derselben Version ändert nichts (auch nicht `retired_at`/`withdrawn_at`).
- Abstammung: `delivery_id` bleibt in jeder Zeile; `delivery`/`source` werden nie gelöscht.
- Klassen (verbindlich): Tombstone = `work`, `document`, `edge` (eine zurückgezogene Kante wird zusätzlich widerrufen: `revoked_at = COALESCE(revoked_at, Importzeit)`); Herkunft = `source`, `delivery` (fehlende Lieferung erhält `withdrawn_at`, falls leer); Inhalt/Ableitung = `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` (werden gelöscht). Ablauf: Schlüssel laden → Zitate lösen → Inhalt löschen (rückwärts) → Tombstones setzen → Lieferungen → Einfügen → Importvermerk. Ein leerer Dump (keine Dokumente) wird bei gefüllter Datenbank verweigert, außer mit `allow_empty`/`--allow-empty`.
- Löseregeln für Nutzerverweise (verbindlich): `chat_message_citation.segment_id` → `NULL` für Segmente, die der Dump nicht mehr enthält. Alle anderen Verweise von Nutzerdaten/Pipeline-Zustand zeigen auf Tombstone- oder Herkunftsklassen und brauchen keine Regel.
- Tests: `cd core && ../.venv/bin/pytest <pfad>`; Skript-Tests separat (`.venv/bin/pytest scripts/tests` im Repo-Root), die beiden conftest-Module dürfen nicht in einem Lauf gemischt werden.
- Dokumentation: ADRs, Spec, Plan, SRS, CLAUDE.md auf Deutsch; `docs/guide/*` auf Englisch.
- ShellCheck wird in diesem Plan nicht berührt; falls doch, mit `koalaman/shellcheck:v0.9.0` prüfen (CI-Version).

## Dateiübersicht

| Datei | Änderung |
|---|---|
| `core/src/normly_core/exchange/tables.py` | + `TOMBSTONE_TABLES`, `RETAINED_TABLES`, `PURGE_TABLES`, `DETACHED_REFERENCES`, `EXCLUDED_EXCHANGE_COLUMNS` |
| `core/tests/exchange/test_tables.py` | + Klassen-Vollständigkeit, Fail-closed-Fremdschlüsseltest |
| `core/migrations/versions/0033_add_retired_at.py` | `retired_at` auf `work`, `document`, `edge` |
| `core/src/normly_core/graph/postgres/orm.py` | `retired_at` in `WorkORM`, `DocumentORM`, `EdgeORM` |
| `core/src/normly_core/graph/postgres/exchange.py` | Export ohne `retired_at`; neuer `replace_knowledge_base` |
| `core/src/normly_core/graph/domain.py` | Docstrings (`ImportBlockedError`, Protocol) |
| `core/src/normly_core/exchange/importer.py` | Docstring (Import blockiert nicht mehr an Nutzerdaten) |
| `core/tests/exchange/test_exchange_repository.py` | alte Blockier-/Lösch-Tests ersetzen, neue Tests |
| `core/tests/exchange/test_takedown.py` | neu: Rücknahme, Wiederkehr, Gate-Abfragen, Nutzerdaten bleiben |
| `docs/adr/README.md`, `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`, `docs/guide/operations.md` | ADR-026, ADR-025 angepasst, Importverhalten |

---

### Task 1: Klassen, Migration, `retired_at`, Export ohne `retired_at`

**Files:**
- Modify: `core/src/normly_core/exchange/tables.py`, `core/tests/exchange/test_tables.py`
- Create: `core/migrations/versions/0033_add_retired_at.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`WorkORM`, `DocumentORM`, `EdgeORM`)
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (`exchange_columns`, `iter_exportable_rows`)
- Test: `core/tests/exchange/test_published_role.py` (bestehend, muss grün bleiben), neu: `core/tests/exchange/test_retired_at_not_exported.py`

**Interfaces:**
- Produces in `tables.py`:
  - `TOMBSTONE_TABLES: tuple[str, ...] = ("work", "document", "edge")`
  - `RETAINED_TABLES: tuple[str, ...] = ("source", "delivery")`
  - `PURGE_TABLES: tuple[str, ...] = ("document_designation", "document_title", "rights_classification", "segment", "embedding", "document_embedding")` — in der Reihenfolge von `KNOWLEDGE_TABLES` (Eltern zuerst); Löschen läuft rückwärts.
  - `DETACHED_REFERENCES: dict[tuple[str, str], str] = {("chat_message_citation", "segment_id"): "segment"}` (Kindtabelle, Spalte → Elterntabelle)
  - `EXCLUDED_EXCHANGE_COLUMNS: dict[str, tuple[str, ...]] = {"work": ("retired_at",), "document": ("retired_at",), "edge": ("retired_at",)}`
- Produces: ORM-Attribut `retired_at: Mapped[datetime | None]` auf den drei Tabellen; `exchange_columns(table)` und `iter_exportable_rows(table)` liefern `retired_at` nicht.

- [ ] **Step 1: Failing tests schreiben**

An `core/tests/exchange/test_tables.py` anhängen:

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

Neue Datei `core/tests/exchange/test_retired_at_not_exported.py`:

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

(`.helpers` wie in den bestehenden Tests dieses Ordners; falls dort ein anderer Importstil verwendet wird, diesen übernehmen.)

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py tests/exchange/test_retired_at_not_exported.py -v` — Expected: FAIL (`AttributeError: module 'normly_core.exchange.tables' has no attribute 'TOMBSTONE_TABLES'`).

- [ ] **Step 3: `tables.py` ergänzen**

Am Ende von `core/src/normly_core/exchange/tables.py` (vor `group_tables` oder danach) einfügen:

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

- [ ] **Step 4: Migration und ORM**

Nachbarmigration lesen (`core/migrations/versions/0032_create_knowledge_base_import.py`: `revision = "0032"`, `down_revision = "0031"`, Lizenzheader). `0033_add_retired_at.py`:

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

In `orm.py` jeweils in `WorkORM`, `DocumentORM`, `EdgeORM` ergänzen:

```python
    #: Set when an import no longer finds this row in the dump (takedown). The
    #: row stays as an identifier tombstone; not part of the exchange format
    #: (ADR-026).
    retired_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
```

- [ ] **Step 5: Export schließt `retired_at` aus**

In `core/src/normly_core/graph/postgres/exchange.py`:
- Importiere `EXCLUDED_EXCHANGE_COLUMNS` aus `normly_core.exchange.tables`.
- Hilfsfunktion:

```python
def _exchange_columns(sa_table: sa.Table) -> list[sa.Column]:
    excluded = set(EXCLUDED_EXCHANGE_COLUMNS.get(sa_table.name, ()))
    return [c for c in sa_table.columns if c.name not in excluded]
```

- `exchange_columns`: `return [ExchangeColumn(c.name, _kind(c)) for c in _exchange_columns(Base.metadata.tables[table])]`.
- `iter_exportable_rows`: Das Statement immer auf die Austauschspalten beschränken (nicht nur bei der Namensmaskierung): `statement = statement.with_only_columns(*[<Maskierungsliteral oder Spalte> for column in _exchange_columns(sa_table)])`. Die bestehende Fail-closed-Maskierung (`sa_table.c[masked_name]`, `PUBLISHED_ROLE`) bleibt unverändert und wird in diese Liste integriert; `order_by(*_primary_key(sa_table))` bleibt.
- Der Import (`_upsert`) wird in Task 2 angepasst; in diesem Task bricht der Import mit den neuen Spalten nicht, solange `_upsert` weiter `sa_table.columns` verwendet — das wäre ein `KeyError` für `retired_at` (die Zeilen aus dem Dump enthalten sie nicht). Deshalb in diesem Task `_upsert` und `_load_keys` bereits so ändern, dass sie `_exchange_columns(sa_table)` statt `sa_table.columns` für die Zeilen benutzen (reiner Spaltenfilter, kein Verhaltenswechsel; `retired_at` wird dann beim Upsert nicht angefasst).

- [ ] **Step 6: Tests**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py tests/graph/test_architecture.py -q` — Expected: PASS (die ORM↔Migrations-Konsistenztests verlangen, dass ORM und Migration 0033 übereinstimmen).

- [ ] **Step 7: Commit**

```bash
git add core
git commit -s -m "feat(exchange): retired_at tombstone column and import classes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Neuer `replace_knowledge_base` und Tests

**Files:**
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (`replace_knowledge_base`, neue Hilfsmethoden, `_delete_missing`/Defer-Logik entfällt)
- Modify: `core/src/normly_core/graph/domain.py`, `core/src/normly_core/exchange/importer.py` (nur Docstrings)
- Modify: `core/tests/exchange/test_exchange_repository.py`
- Create: `core/tests/exchange/test_takedown.py`

**Interfaces:**
- Consumes: Konstanten aus Task 1; `_load_keys` (temporäre Schlüsseltabellen `_kb_keep_<table>` je Wissensbestand-Tabelle), `_upsert`, `_write_record`.
- Produces: unveränderte öffentliche Signatur `replace_knowledge_base(tables, *, record)`; neues Verhalten (siehe unten).

**Ablauf (verbindlich, in dieser Reihenfolge):**
1. `_load_keys` (Schlüssel aus dem Dump in temporäre Tabellen).
2. `_detach_missing_references`: für jeden Eintrag in `DETACHED_REFERENCES`: `UPDATE child SET column = NULL WHERE column IS NOT NULL AND NOT EXISTS (Schlüssel in keep_parent)`.
3. Inhalt löschen, rückwärts durch `PURGE_TABLES`: `DELETE ... WHERE NOT EXISTS (Schlüssel in keep)` — **vor** dem Einfügen, damit natürliche Eindeutigkeitsschlüssel (`segment(document_id, sequence_number)`, `embedding(segment_id, model_name)`, Bezeichnung/Titel) nicht mit alten, ausgedienten Zeilen kollidieren.
4. Tombstones **vor dem Einfügen**: für jede Tabelle in `TOMBSTONE_TABLES`: `UPDATE t SET retired_at = :now WHERE retired_at IS NULL AND NOT EXISTS (Schlüssel in keep)`; `now = record.imported_at`. Für `edge` zusätzlich `revoked_at = COALESCE(revoked_at, :now)` (einziges Lesetor der Kanten; gibt den partiellen Eindeutigkeitsindex aktiver Kanten für eine neu gelieferte Kante frei).
5. Fehlende Lieferungen: `UPDATE delivery SET withdrawn_at = :now WHERE withdrawn_at IS NULL AND NOT EXISTS (Schlüssel in keep)`.
6. Einfügen/Aktualisieren in `KNOWLEDGE_TABLES`-Reihenfolge (`_upsert`); für `TOMBSTONE_TABLES` wird `retired_at = NULL` mitgeschrieben (Wiederkehr); eine wiederkehrende Kante erhält `revoked_at` aus dem Dump (`NULL`).
7. `_write_record(record)`; temporäre Tabellen droppen. Der Aufrufer committet.

Zusätzlich: `import_dump(..., allow_empty=False)` verweigert (`ImportRefused`) einen Dump ohne `document`-Zeilen, wenn `repository.has_documents()`; CLI-Flag `--allow-empty` auf `import`.

Jeder `IntegrityError` in den Schritten 2–6 wird zu `ImportBlockedError(<Tabelle>, <erste Zeile der Fehlermeldung>)` (letzte Sicherung für unerwartete Fremdschlüssel, im Regelbetrieb nicht ausgelöst).

- [ ] **Step 1: Alte Tests anpassen / neue Tests schreiben (RED)**

In `core/tests/exchange/test_exchange_repository.py`:

1. `test_replace_is_idempotent_and_removes_missing_rows`: Die Aussage `str(drop.id) not in _ids(first, "document")` wird zu: das Dokument ist **noch da** (Tombstone) und die `rights_classification` der Dokuments ist **weg**; der Test heißt jetzt `test_replace_is_idempotent_and_retires_missing_rows`. Idempotenz-Assertion (zweiter Import ändert den Snapshot nicht) bleibt; `_snapshot` muss `retired_at` für `work`/`document`/`edge` enthalten, damit „zweiter Import ändert `retired_at` nicht“ geprüft wird.
2. `test_replace_blocks_when_user_data_still_references_a_row`: **ersetzen** durch `test_user_data_never_blocks_an_import` (watchlist auf einen Work, dessen Dokumente nicht mehr im Dump stehen → Import läuft durch, Watchlist-Zeile unverändert, Work mit `retired_at` gesetzt, `imported_version()` gesetzt).
3. Die übrigen Tests (Work-Merge zwischen zwei Importen, Klassifikation wechselt Lieferung, Un-Merge, `begin_nested`-Rollback) auf das neue Verhalten prüfen: Sie müssen **ihre Absicht behalten** (kein falscher Block, Idempotenz, Rollback ohne Änderung bei Fehler); wo sie vorher auf „Zeile gelöscht“ geprüft haben, auf „Tombstone/Inhalt gelöscht“ umstellen. Ein Test, der nur den früheren Drei-Durchläufe-Mechanismus beschrieben hat und kein Verhalten mehr trägt, wird entfernt (mit Begründung im Bericht).

Neue Datei `core/tests/exchange/test_takedown.py` (Fixtures aus `.helpers`; Konten über `PostgresAccountRepository.create_account(email=..., password_hash=...)`, Beobachtung über `PostgresWatchlistRepository.add_watch(account_id=..., work_id=...)`, Segmente über `PostgresSegmentRepository.add_segment(...)`, Einbettungen wie in `test_embedding_roundtrip.py`; Chat-Zitat über die vorhandenen Chat-Repositories — Signaturen vor dem Schreiben mit `grep -n "def create_session\|def add_message\|def add_citation\|def create_message" core/src/normly_core/graph/postgres/repositories.py` prüfen und die Tests an die echten Parameter anpassen, nicht ihre Aussage):

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

Tests (jeder legt ein Szenario mit Quelle, Lieferung, zwei Dokumenten `KEEP`/`DROP`, je einem Segment, einer Klassifikation, einer Kante `KEEP→DROP`, einem Konto, einer Beobachtung auf den Work von `DROP`, einer Benachrichtigung mit `trigger_document_id=DROP`/`trigger_edge_id`, einem `notified_edge`- und `rights_notification_baseline`-Eintrag und einem Chat-Zitat auf das Segment von `DROP` an, importiert zuerst den vollständigen Dump, dann den Dump ohne `DROP`):

- `test_takedown_deletes_content_and_keeps_identifiers`: nach dem zweiten Import existieren für `DROP` **keine** Zeilen in `segment`, `embedding`, `document_embedding`, `rights_classification`; das `document` und sein `work` existieren mit `retired_at IS NOT NULL`; `retired_at` von `KEEP` und dessen Work ist `NULL`; die Kante `KEEP→DROP` existiert mit `retired_at` gesetzt; `delivery` bleibt; `source` bleibt.
- `test_takedown_keeps_user_data_and_only_clears_the_citation_segment`: Beobachtung, Benachrichtigung (inkl. `trigger_*_id`), `notified_edge`, `rights_notification_baseline`, Chat-Nachricht sind **unverändert vorhanden**; das Zitat existiert noch mit `document_id` von `DROP` und `segment_id IS NULL`.
- `test_takedown_removes_the_document_from_every_gated_read`: Nach dem Import erscheint `DROP` weder in `PostgresDocumentRepository(db_session).list_documents_for_jurisdiction("DE")` noch in `search_documents_for_jurisdiction(...)` (passende Signatur prüfen) noch in `list_exportable_documents_for_jurisdiction("DE")` noch in `iter_exportable_rows("document")`; `KEEP` erscheint weiter.
- `test_returning_document_clears_retired_at_and_restores_content`: Dritter Import mit dem vollständigen Dump → `retired_at` wieder `NULL` für `DROP`, Work und Kante; `segment`/`embedding`/`document_embedding`/`rights_classification` wieder da; Beobachtung etc. unverändert; das frühere Zitat hat weiterhin `segment_id IS NULL` (Verweis ist unwiderruflich gelöst).
- `test_withdrawn_delivery_gets_withdrawn_at`: Dump ohne eine ganze Lieferung (alle ihre Zeilen) → `delivery.withdrawn_at IS NOT NULL`; ein zweiter Import ändert den Zeitstempel nicht.
- `test_second_import_changes_nothing`: Nach dem zweiten Import (Dump ohne `DROP`) erzeugt ein dritter Import desselben Dumps einen identischen Snapshot einschließlich `retired_at`-Werten (Zeitstempel bleibt der des ersten Rücknahme-Imports).
- `test_import_inside_a_savepoint_rolls_back_cleanly`: Ein bewusst scheiternder Import (z. B. ein künstlich hinzugefügter Fremdschlüssel von einer Testtabelle auf `segment` ist zu aufwendig — stattdessen: Import in `db_session.begin_nested()`, dann `rollback()`; Snapshot gleich dem vorherigen).
- `test_natural_key_collision_with_a_purged_row_does_not_block`: Ein Segment `(document_id, sequence_number)` fehlt im Dump und ein anderes Segment (neue ID) mit demselben natürlichen Schlüssel kommt im Dump vor → der Import läuft durch (Löschen der Inhaltsklasse vor dem Einfügen).

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_exchange_repository.py tests/exchange/test_takedown.py -v` — Expected: FAIL (alter Algorithmus löscht Tombstone-Klassen bzw. blockiert).

- [ ] **Step 3: `replace_knowledge_base` umbauen**

Ersetze in `graph/postgres/exchange.py` den Rumpf von `replace_knowledge_base` und entferne `_delete_missing` (samt Defer-Logik). Gerüst:

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

Hilfsmethoden (alle nutzen `_primary_key`, `keep.c[...]`-Vergleiche wie bisher):

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

`_upsert` ändern: Für `name in TOMBSTONE_TABLES` jede Zeile um `"retired_at": None` ergänzen und `retired_at` in `value_columns`/`set_` aufnehmen (`value_columns = [c for c in sa_table.columns if c.name not in key_names]` enthält die Spalte bereits; die Zeilen aus dem Dump müssen den Schlüssel `retired_at` mitbringen: `row.setdefault`-artig beim Aufbau der Rows). Der Selbstverweis-Aufschub (`merged_into_work_id`) bleibt. `_from_exchange` ignoriert `None` und braucht für `retired_at` keine Sonderbehandlung.

Entferne ungenutzte Imports (`ImportBlockedError` bleibt). Importiere `PURGE_TABLES`, `TOMBSTONE_TABLES`, `DETACHED_REFERENCES` aus `normly_core.exchange.tables`. Docstring in `graph/domain.py` (`ImportBlockedError`, Protocol `replace_knowledge_base`) und `exchange/importer.py` an das neue Verhalten anpassen („blockiert nicht mehr an Nutzerdaten, nur noch an einem unerwarteten Fremdschlüssel“).

- [ ] **Step 4: Tests grün**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph -q` — Expected: PASS. Dann `cd core && ../.venv/bin/pytest tests -q` (komplette Core-Suite, ca. 4 Minuten) — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core
git commit -s -m "feat(exchange): takedown wins - tombstone identifiers, purge content on import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: ADR-026 und Dokumentation

**Files:**
- Modify: `docs/adr/README.md` (ADR-026 anfügen; ADR-025: Blockierregel, der drei Durchläufe und den offenen Punkt zu Nutzerverweisen anpassen; Register-Zeilen prüfen)
- Modify: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md` (Teil 3, Schritt 4 „Idempotent …“)
- Modify: `docs/guide/operations.md` (Importverhalten)
- Modify: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md` (Status: umgesetzt)

- [ ] **Step 1: ADR-026 schreiben** (Format der Nachbar-ADRs: `## ADR-026 — …`, Status/Datum, Kontext, Entscheidung, Begründung, Verworfen, Folgen). Inhalt:
  - **Titel:** „Umgang mit Nutzerdaten beim Wissensbestand-Import“; Status angenommen 2026-10-09.
  - **Kontext:** `ImportBlockedError` blockierte Importe an Nutzerverweisen; eine rechtlich gebotene Rücknahme darf nicht an Nutzerdaten scheitern (CLAUDE.md „Abstammung mitführen“). Befund: keine Nutzerdaten-Tabelle speichert urheberrechtlich geschützten Inhalt, nur Verweise.
  - **Entscheidung:** Klassen (Tombstone: `work`, `document`, `edge`, Kanten zusätzlich widerrufen; Herkunft: `source`, `delivery`; Inhalt/Ableitung: `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` → gelöscht); Schutz vor leerem Dump (`allow_empty`/`--allow-empty`); `retired_at` (nicht im Austauschformat); Wiederkehr; Zitate verlieren `segment_id`; Fail-closed-Test für Fremdschlüssel; `retired_at` ist keine Filterpflicht, weil das Rechtetor (gelöschte Klassifikation) die Dokumente aus allen tor-gebundenen Abfragen nimmt; Reihenfolge Löschen und Zurückziehen vor Einfügen wegen natürlicher Schlüssel (Neulieferung mit neuen IDs).
  - **Begründung:** Rücknahme gewinnt immer; keine Textreste in Produktion und Sicherungen nach Ablauf; keine Nutzerdaten gehen verloren.
  - **Verworfen:** Blockieren mit Bereinigungswerkzeug (Rücknahme wartet auf einen Menschen); Nutzerverweise anpassen/löschen (Datenverlust ohne Nutzen, da nur Verweise); reine Tombstones auch für Inhalt (Rücknahme nur logisch, Text bliebe lesbar in DB/Sicherungen).
  - **Folgen / offen:** (1) In Produktion verschwindet bei einem Widerruf die Klassifikation; `notify-watchers` (RIGHTS_CHANGE) sieht dann nichts mehr — eine Meldung „nicht mehr verfügbar“ auf Basis von `retired_at` ist Folgearbeit (Produktentscheidung); (2) Aufbewahrung/Alterung von Tombstones offen (Teil B); (3) Dumps müssen aus einer Abstammungslinie mit stabilen IDs stammen: Ein Neuaufbau der Produzenten-Datenbank mit neuen IDs kollidiert mit stehengebliebenen Tombstones (partielle Eindeutigkeit von Kanten, Bezeichner) und bricht mit `ImportBlockedError` ab; (4) Tombstones bleiben in der Datenbank sichtbar für Pipeline-Lesewege ohne Rechtetor (`*_unchecked`); diese dürfen sie nicht als Inhalt ausliefern.
  Folge (1) lautet nach Task 4/5 nicht mehr „offen“: Der Widerruf wird in Produktion als Benachrichtigung `no_longer_available` gemeldet (Erkennung aus `retired_at`, Dedup über `notified_retirement`); offen bleibt nur die RIGHTS_CHANGE-Meldung im engeren Sinn (Rechtewerte ändern sich, ohne dass das Dokument verschwindet) — die entsteht weiter beim Produzenten. Dokumentiere das so.
  Übertrage in ADR-025 den Verweis auf ADR-026 (Import: „Zitate lösen → Inhalt löschen → Tombstones setzen → einfügen“; Blockierregel und der offene Punkt „Nutzerdaten, die auf ersetzte Segmente/Kanten verweisen, können Importe blockieren“ entfallen).
- [ ] **Step 2: TP4-Spec Teil 3 Schritt 4, `docs/guide/operations.md`:** Importverhalten (Tombstones, Wiederkehr, was nach einer Rücknahme in den Nutzerdaten passiert) in zwei bis vier Sätzen beschreiben (Guide Englisch); Spec-Status der neuen Spec auf „umgesetzt“ setzen.
- [ ] **Step 3: Docs-Build wie in CI** (docker `python:3.12` mit `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, dann `zensical build`; Ausgabe muss eine Zeile `3 issues found` enthalten; mit `--user "$(id -u):$(id -g)"` und beschreibbarem HOME laufen lassen und danach `site/` und `.cache/` entfernen, damit keine root-eigenen Dateien bleiben).
- [ ] **Step 4: Commit**

```bash
git add docs
git commit -s -m "docs: ADR-026 user data on knowledge-base import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Selbstprüfung gegen die Spec

| Spec-Abschnitt | Task |
|---|---|
| Entscheidungsklassen (Tombstone / Herkunft / Inhalt) | Task 1 (Konstanten + Test), Task 2 (Verhalten) |
| `retired_at` (Migration, ORM, nicht im Austauschformat) | Task 1 |
| Importablauf (Zitate lösen, Inhalt löschen, einfügen, Tombstones, Lieferungen) | Task 2 |
| Wiederkehr, Idempotenz | Task 2 (`test_returning_document…`, `test_second_import…`) |
| `retired_at` ist keine Filterpflicht (Rechtetor) | Task 2 (`test_takedown_removes_the_document_from_every_gated_read`) |
| Fail-closed-Fremdschlüsseltest | Task 1 |
| Nutzerdaten bleiben / blockieren nicht | Task 2 |
| ADR-026, ADR-025, Spec, Guide | Task 3 |

**Bekannte Lücken, bewusst nicht in diesem Plan:** Alterung/Aufräumen von Tombstones, Anzeige „nicht mehr verfügbar“ und RIGHTS_CHANGE-Meldung bei Widerruf in Produktion (Produktentscheidung, als offene Punkte in ADR-026), Lebenszyklus der Nutzerdaten insgesamt (Teil B). **Risiken beim Bau:** Eindeutigkeitsschlüssel von Tombstone-Klassen können bei neuen IDs kollidieren (ADR-026, Folge 3); Chat-Repositories für das Zitat im Test (Signaturen prüfen); die komplette Core-Suite muss nach der Umstellung grün bleiben (insbesondere die alten Work-Merge-/Lieferungswechsel-Tests).

---

## Erweiterung: Meldung „nicht mehr verfügbar“

Spec-Ergänzung: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`, Abschnitt „Meldung ‚nicht mehr verfügbar‘“. Entscheidungen des Nutzers: **eine Meldung pro zurückgezogenem Dokument**; nur Rücknahmen **nach** dem Beginn der Beobachtung; kein Link; Dedup-Gedächtnis in eigener Tabelle.

### Task 4: Kern — Typ, Tabelle, Erkennung, E-Mail

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (`NotificationTriggerType.NO_LONGER_AVAILABLE = "no_longer_available"`; `Document.retired_at: datetime | None = None` als **letztes** Feld mit Default; neues Protocol `NotifiedRetirementRepository`)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`NotifiedRetirementORM`; die ORM-`Enum` von `NotificationTriggerType` nimmt den neuen Wert automatisch auf)
- Create: `core/migrations/versions/0034_add_no_longer_available.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_document_to_domain` setzt `retired_at`; `PostgresNotifiedRetirementRepository`)
- Modify: `core/src/normly_core/notifications/detection.py` (Schleife, `_EMAIL_SUBJECTS`)
- Modify: `core/src/normly_core/exchange/tables.py` (`USER_TABLES` um `notified_retirement`, nach `notified_edge`)
- Test: `core/tests/notifications/test_no_longer_available.py` (neu), bestehende Tests für Tabellen/Migration/Architektur müssen grün bleiben

**Interfaces:**
- Produces:
  - `NotifiedRetirementRepository` mit `has_been_notified(*, account_id, work_id, document_id, retired_at) -> bool` und `mark_notified(*, account_id, work_id, document_id, retired_at) -> None` (keine `get_`/`list_`-Namen, wegen des Jurisdiktions-Guards in `test_architecture.py`).
  - Tabelle `notified_retirement(account_id UUID FK account, work_id UUID FK work, document_id UUID FK document, retired_at timestamptz, notified_at timestamptz DEFAULT now(), PRIMARY KEY (account_id, work_id, document_id, retired_at))`.
  - `run_notify_watchers` erzeugt `NO_LONGER_AVAILABLE`-Benachrichtigungen (`trigger_document_id` = Dokument, `trigger_edge_id=None`, `trigger_jurisdiction=None`, Rechtefelder `None`) und zählt sie in `notifications_created`/`emails_sent`.

**Verhalten (verbindlich):** Pro Beobachtung und pro Dokument des beobachteten Works aus `list_documents_for_work_unchecked` mit `retired_at is not None` und `retired_at > watch.created_at` und nicht `has_been_notified(...)`: Benachrichtigung anlegen (E-Mail nach Kontoeinstellung wie bei den anderen Typen), dann `mark_notified`. Das Dedup-Schlüsselfeld `retired_at` macht eine spätere erneute Rücknahme nach einer Rückkehr zu einer neuen Meldung. Konten mit `NotificationPreference.NONE` werden wie bisher übersprungen. E-Mail-Betreff: `"Ein beobachtetes Regelwerk ist nicht mehr verfügbar"` (in `_EMAIL_SUBJECTS`), Rumpf wie bei den anderen Typen.

- [ ] **Step 1: Failing tests** in `core/tests/notifications/test_no_longer_available.py`. Szenarien (Fixtures über die vorhandenen Test-Helfer in `core/tests/notifications/` bzw. `core/tests/exchange/helpers.py`; die genauen Konstruktoren der Repositories vor dem Schreiben aus den bestehenden Notification-Tests übernehmen):
  1. Konto + Beobachtung eines Works; danach wird das Dokument zurückgezogen (`UPDATE document SET retired_at = now()` über die ORM-Session im Test, oder über `replace_knowledge_base` mit einem Dump ohne das Dokument — Letzteres ist der Ende-zu-Ende-Test) → `run_notify_watchers` erzeugt **genau eine** `NO_LONGER_AVAILABLE`-Benachrichtigung mit `trigger_document_id`.
  2. Rücknahme **vor** dem Beobachten (`retired_at <= watch.created_at`) → keine Meldung.
  3. Zweiter Lauf → keine zweite Meldung (Idempotenz).
  4. Gelesene Benachrichtigung wird per `delete_read_before(...)` aufgeräumt → nächster Lauf meldet **nicht** erneut.
  5. Dokument kehrt zurück (`retired_at = NULL`) und wird später erneut zurückgezogen (neuer Zeitstempel) → eine **neue** Meldung.
  6. Zwei zurückgezogene Dokumente desselben Works → zwei Meldungen (pro Dokument).
  7. Konto mit `NotificationPreference.NONE` → keine Meldung; Konto mit `EMAIL`/`BOTH` → E-Mail mit dem neuen Betreff an den Fake-`EmailSender`, `emailed_at` gesetzt; `NotifyWatchersSummary` zählt Meldungen und E-Mails.
  8. Ein zurückgezogenes Dokument stört den bestehenden Rechteänderungs-Pfad nicht (kein Fehler, keine Rechteänderungs-Meldung).
  Ferner (in vorhandenen Test-Dateien ergänzen): `PostgresNotifiedRetirementRepository` Roundtrip; ORM↔Migration-Konsistenz (`test_orm_migration_consistency.py`, `test_migration_determinism.py`) bleibt grün; `test_tables.py` kennt `notified_retirement` in `USER_TABLES` in FK-sicherer Reihenfolge.
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/notifications/test_no_longer_available.py -v` — Expected: FAIL (`AttributeError: ... NO_LONGER_AVAILABLE`).
- [ ] **Step 3: Implementierung.** Migration `0034` (Nachbar `0033` für Stil und IDs; `revision = "0034"`, `down_revision = "0033"`): (a) Tabelle `notified_retirement` anlegen (Spalten und Primärschlüssel wie oben); (b) die CHECK-Beschränkung des Enum-Typs `notification_trigger_type` auf `notification` **und** `notified_edge` um `'no_longer_available'` erweitern — dazu den tatsächlichen Constraint-Namen in `0027_create_watchlist_and_notification.py` und `0030_create_notified_edge.py` nachlesen (SQLAlchemy benennt ihn nach dem `name=`-Argument; bei `op.create_table` ist er `notification_trigger_type`; prüfe mit `\d notification` im Testcontainer oder `inspect(...).get_check_constraints`), `op.drop_constraint` + `op.create_check_constraint` mit der erweiterten Wertliste; `downgrade` stellt die alte Liste her (zuvor Zeilen mit dem neuen Wert löschen, sonst scheitert die Beschränkung). Detection: nach der Schleife über Kanten, vor der Rechte-Schleife, eine Schleife über `documents` mit `document.retired_at`; `NotifiedRetirementRepository` im Kopf von `run_notify_watchers` anlegen. Importiere `PostgresNotifiedRetirementRepository`. `Document` in `domain.py` bekommt `retired_at: datetime | None = None` am Ende (keine bestehenden Aufrufer brechen).
- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/notifications tests/exchange tests/graph -q` — Expected: PASS. Danach die komplette Core-Suite `cd core && ../.venv/bin/pytest tests -q`.
- [ ] **Step 5: Commit** `feat(notifications): notify watchers when a watched document is no longer available` (mit `-s` und Trailer).

### Task 5: Frontend — Eintrag in der Glocke

**Files:**
- Modify: `frontend/src/components/page-header.tsx` (`TRIGGER_TYPE_KEYS`, `TRIGGER_TYPE_ICONS`)
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`, `frontend/src/lib/i18n/dictionary-keys.ts` (falls der Schlüssel dort aufgelistet werden muss; Mechanismus vor dem Ändern lesen)
- Test: `frontend/tests/unit/page-header.test.tsx`

**Interfaces:**
- Consumes: API liefert `triggerType: "no_longer_available"` unverändert (Accounts-API gibt den Typ als String durch; keine Änderung dort nötig).
- Produces: i18n-Schlüssel `nav.notificationNoLongerAvailable` mit `de: "Nicht mehr verfügbar"`, `en: "No longer available"`; Icon `FileX` (lucide-react); Mapping `no_longer_available` in beiden Tabellen. Kein Link.

- [ ] **Step 1: Failing test** in `page-header.test.tsx` (bestehendes Muster der Datei übernehmen): Eine Benachrichtigung mit `triggerType: "no_longer_available"` wird mit dem Label „Nicht mehr verfügbar“ (de) bzw. „No longer available“ (en) und ohne Fallback „Benachrichtigungen“ dargestellt; das Icon-Element ist nicht das Standard-`Bell`.
- [ ] **Step 2:** `cd frontend && npx vitest run tests/unit/page-header.test.tsx` — Expected: FAIL (Fallback-Label statt neuem Label). Falls `node_modules` fehlt: `cd frontend && npm ci` (kann dauern; Netz nötig).
- [ ] **Step 3: Implementierung** wie unter Interfaces. Danach `cd frontend && npx vitest run` (komplette Frontend-Testsuite) und, falls im Projekt vorhanden, `npx tsc --noEmit` — Expected: PASS. Falls ein Parity-Test zwischen `de.json` und `en.json` existiert, muss er grün sein.
- [ ] **Step 4: Commit** `feat(frontend): show the no-longer-available notification` (mit `-s` und Trailer).

### Task 6: Dokumentation der Meldung (in Task 3 enthalten)

Der ADR-026-Text (Task 3, Schritt 1) beschreibt die Meldung bereits; zusätzlich in `docs/guide/operations.md` (Englisch) im Abschnitt zum Import einen Satz: Watchers of a withdrawn document receive a "no longer available" notification the next time `notify-watchers` runs. Und im ADR-Register den Eintrag für ADR-026 anlegen, falls das Register Einträge pro ADR führt. Keine eigene Commit-Runde nötig; Teil von Task 3.

## Selbstprüfung der Erweiterung

| Spec-Ergänzung | Task |
|---|---|
| Typ `no_longer_available`, Erkennung nach Beobachtungsbeginn, eine Meldung pro Dokument | Task 4 |
| Gedächtnis `notified_retirement` (inkl. `retired_at` im Schlüssel), Aufräumen löst keine zweite Meldung aus | Task 4 (Tests 3, 4, 5) |
| Migration `0034` (Tabelle, CHECK-Erweiterung) | Task 4 |
| E-Mail-Betreff, Zusammenfassung | Task 4 (Test 7) |
| Glocke: Label de/en, Icon, kein Link | Task 5 |
| ADR-026-Folge 1 gelöst | Task 3 (zuletzt) |

**Risiken:** Der Name der CHECK-Beschränkung und das `downgrade` (Zeilen mit neuem Wert vor dem Wiederherstellen löschen); die Frontend-Dictionary-Mechanik (Schlüssel eventuell generiert/typisiert); `Document` ist ein eingefrorenes Dataclass-Objekt mit Positionsaufrufen in Tests — der neue Wert hat einen Default und steht am Ende.

---

## Erweiterung 2: Tombstone-Kennungen mitsichern (Rollback-Fix)

**Anlass (Abschlussprüfung, I-1):** `normly-deploy rollback` baut die Datenbank neu auf, importiert die ältere Dump-Version und spielt dann die Nutzerdaten ein (`pg_restore --data-only`). Tombstones (`retired_at`) stehen in keinem Dump; Nutzerzeilen, die auf sie zeigen (`watchlist`, `notification`, `notified_*`, `rights_notification_baseline`, `chat_message_citation`), verletzen beim Einspielen den Fremdschlüssel, nach dem Löschen der Tabellen. Entscheidung des Nutzers: **vollständig lösen**. Entwurf (bestätigt): Die Sicherung nimmt die zurückgezogenen Kennungen samt Fremdschlüssel-Eltern als eigene kleine, `age`-verschlüsselte JSON-Datei mit; der Rollback spielt sie nach dem Wissensbestand-Import und vor den Nutzerdaten ein.

**Ausführungsreihenfolge dieser Erweiterung:** Task 7 (Kern), Task 8 (Skripte), Task 9 (Dokumentation und Befunde der Abschlussprüfung). Alle auf dem Branch `feat/user-data-on-import`.

**Global Constraints (zusätzlich):**
- Format der Datei (verbindlich): JSON, UTF-8, `{"format": 1, "created_at": "<ISO-8601 UTC>", "rows": {"source": [...], "delivery": [...], "work": [...], "document": [...], "edge": [...]}}`; die Tabellen in dieser FK-Reihenfolge (entspricht der Reihenfolge von `KNOWLEDGE_TABLES` eingeschränkt auf diese fünf), Zeilen je Tabelle nach Primärschlüssel sortiert; Werte in Austauschtypen (UUID und Enum als String, Zeitstempel/Datum ISO-8601, bool/int/str unverändert); **alle** Spalten der Tabelle einschließlich `retired_at` und `revoked_at` (anders als der öffentliche Dump).
- Inhalt: alle Zeilen mit `retired_at IS NOT NULL` in `work`, `document`, `edge` plus der **Abschluss über Fremdschlüssel-Eltern innerhalb dieser fünf Tabellen** (Work des Dokuments und die `merged_into_work_id`-Kette, `from`/`to`-Dokumente einer Kante samt deren Work, `delivery` und `source` jeder eingeschlossenen Zeile). Der Abschluss wird aus den Fremdschlüsseln der ORM-Metadaten berechnet, nicht hart verdrahtet. Nie Inhalt (kein `segment`, `embedding`, `rights_classification`), keine Nutzerdaten.
- Einspielen (`import-tombstones`): Einfügen in FK-Reihenfolge mit `ON CONFLICT DO NOTHING` (bereits vorhandene Zeilen, z. B. aus dem Dump, werden nie verändert); `work.merged_into_work_id` wird wie im Import aufgeschoben (zuerst NULL, danach setzen). Eingefügte Zeilen der Tombstone-Tabellen bekommen `retired_at = gesicherter Wert`, bei Eltern ohne `retired_at` (lebende Zeilen, die der Rollback-Dump nicht kennt) `retired_at = created_at` der Datei, damit sie als zurückgezogen gelten. Diese Zeilen haben keine Klassifikation, das Rechtetor lässt sie nicht durch. Ein späterer Import, der die Zeile im Dump enthält, setzt `retired_at` wieder auf NULL.
- Kein SQL in `normly_core/exchange/` und `graph/domain.py`; neue Protocol-Methoden ohne `get_`/`list_`-Präfix (`test_architecture.py`); `import-tombstones` und `export-tombstones` committen nicht im Repository, die CLI committet.
- Abwärtskompatibilität: Eine ältere Sicherung ohne `<base>.tombstones.age` ist weiter nutzbar; der Rollback warnt deutlich (Fremdschlüsselfehler beim Einspielen möglich) und läuft weiter.
- Skripte: `.sha256` bleibt Abschlussmarker, die neue Datei wird **vor** ihm hochgeladen; `prune` löscht die neue Datei mit; ShellCheck mit `koalaman/shellcheck:v0.9.0` (CI-Version) prüfen; keine Klartextdatei bleibt zurück; Tests mit den Fake-Binaries aus `scripts/tests/conftest.py`.

### Task 7: Kern — `export-tombstones` und `import-tombstones`

**Files:**
- Create: `core/src/normly_core/exchange/tombstones.py` (Format, (De-)Serialisierung, Orchestrierung ohne SQL)
- Modify: `core/src/normly_core/graph/domain.py` (Protocol `KnowledgeExchangeRepository`: `export_tombstone_support() -> dict[str, list[dict[str, Any]]]`, `restore_tombstone_support(rows: Mapping[str, list[dict[str, Any]]], *, restored_at: datetime) -> None`)
- Modify: `core/src/normly_core/graph/postgres/exchange.py` (Implementierung: Abschluss über Fremdschlüssel, Einfügen mit `ON CONFLICT DO NOTHING`)
- Modify: `core/src/normly_core/exchange/__main__.py` (Subcommands `export-tombstones`, `import-tombstones`)
- Test: `core/tests/exchange/test_tombstones.py`, `core/tests/exchange/test_cli.py` (ergänzen)

**Interfaces:**
- Produces:
  - `tombstones.build_document(rows: Mapping[str, list[dict]], *, created_at: datetime) -> str` und `tombstones.parse_document(text: str) -> tuple[dict[str, list[dict]], datetime]` (wirft `ValueError` bei falschem `format`/Struktur); Konstante `TOMBSTONE_FORMAT = 1`; `TOMBSTONE_SUPPORT_TABLES = ("source", "delivery", "work", "document", "edge")`.
  - CLI: `python -m normly_core.exchange export-tombstones` → JSON auf stdout, Exit 0; `python -m normly_core.exchange import-tombstones` liest JSON von stdin, spielt ein, committet, gibt `restored tombstone support: <n> rows` aus; bei ungültigem Dokument Exit 1 mit klarer Meldung auf stderr, nichts geändert (Rollback der Session).
  - Beide Befehle brauchen `NORMLY_DATABASE_URL` (kein `NORMLY_EMBEDDING_MODEL_REVISION`).
- Details zur Umsetzung: Serialisierung nutzt die Spaltenarten aus `exchange_columns`-Logik (`_kind`), aber über **alle** Spalten der Tabelle; Zeitstempel/Datum ISO-8601 (mit Zeitzone) hin und zurück; keine Vektorspalten in diesen fünf Tabellen (Test, der das absichert: keine Spalte der Art `vector`).

- [ ] **Step 1: Failing tests** (`core/tests/exchange/test_tombstones.py`, Fixtures aus `.helpers` und dem Szenario aus `core/tests/exchange/test_takedown.py`, ggf. die Helfer in `helpers.py` verschieben, wie bei der bisherigen Mehrfachnutzung): (1) Abschluss: nach einer Rücknahme (Import ohne Dokument `DROP`) enthält `export_tombstone_support()` das zurückgezogene `document`, dessen `work`, seine `delivery` und `source`, bei einer zurückgezogenen Kante beide Dokumente samt Works; keine Zeilen ohne Bezug; Werte in Austauschtypen; (2) Inhalt: kein Segment/keine Klassifikation, `retired_at`/`revoked_at` sind enthalten; (3) Round-Trip von `build_document`/`parse_document` (Gleichheit, Zeitzone), Ablehnung falscher `format`-Version und kaputter Struktur; (4) `restore_tombstone_support` in eine leere Wissensbestand-Umgebung: Fremdschlüssel-Reihenfolge, `merged_into_work_id`-Aufschub (Work mit `merged_into` auf Work, der erst danach eingefügt wird), `ON CONFLICT DO NOTHING` (eine vorhandene Zeile mit anderem Inhalt bleibt unverändert), Idempotenz (zweimal einspielen ändert nichts), `retired_at` gesetzt für eingefügte Zeilen (bei lebenden Eltern `restored_at`), eingefügte Zeilen haben keine Klassifikation und erscheinen in keiner rechtegebundenen Abfrage; (5) **Ende-zu-Ende des Rollbacks**: Szenario mit Rücknahme und Nutzerverweisen (Beobachtung, Benachrichtigung mit `trigger_document_id`/`trigger_edge_id`, `notified_*`, Baseline, Chat-Zitat) → `export_tombstone_support()` und die Nutzerzeilen per SQL in Python-Strukturen sichern → alle Nutzerzeilen und den gesamten Wissensbestand in der Testtransaktion löschen → den älteren Dump (vor der Rücknahme exportiert **ohne** das spätere Tombstone? nein: den Dump der Version VOR dem Rollout; er enthält das zurückgezogene Dokument nicht) per `replace_knowledge_base` einspielen → `restore_tombstone_support` → Nutzerzeilen wieder einfügen: **kein** Fremdschlüsselfehler, Zeilenanzahlen gleich; (6) CLI: `export-tombstones` druckt gültiges JSON (mit der Test-DB über die vorhandene CLI-Testmethodik), `import-tombstones` mit Datei über stdin, Ablehnung kaputter Eingabe mit Exit 1 und unveränderter DB, fehlende `NORMLY_DATABASE_URL`; (7) `test_architecture.py` bleibt grün (Methodennamen).
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_tombstones.py -v` — Expected: FAIL (fehlende Module/Methoden). Befehle einzeln, die Maschine ist speicherbegrenzt.
- [ ] **Step 3: Implementierung** wie oben; Abschluss in `PostgresKnowledgeExchangeRepository.export_tombstone_support`: Ausgangsmenge = Primärschlüssel aller Zeilen mit `retired_at IS NOT NULL` in `work`, `document`, `edge`; wiederholt: für jede Tabelle der fünf und jeden Fremdschlüssel einer Spalte auf eine andere dieser Tabellen (oder `work.merged_into_work_id` auf `work`) die Eltern-Schlüssel der eingeschlossenen Kindzeilen hinzufügen, bis sich nichts mehr ändert; danach je Tabelle alle Spalten der eingeschlossenen Zeilen sortiert nach Primärschlüssel lesen. `restore_tombstone_support`: für Tabellen in FK-Reihenfolge `pg_insert(...).on_conflict_do_nothing()` in Blöcken (`_WRITE_BATCH`); Zeilen von `work` mit gesetztem `merged_into_work_id` zuerst mit NULL einfügen und danach per `UPDATE ... WHERE id = :id AND merged_into_work_id IS NULL` nachtragen (nur für Zeilen, die wirklich neu eingefügt wurden — der Aufschub darf vorhandene Zeilen nicht verändern); `retired_at` für eingefügte `work`/`document`/`edge`-Zeilen auf den gesicherten Wert oder `restored_at` setzen (nur beim Einfügen; Bestandszeilen bleiben unverändert).
- [ ] **Step 4:** Fokussiert (`cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_architecture.py -q`), danach die komplette Core-Suite genau einmal (`cd core && ../.venv/bin/pytest tests -q`, ca. 4 Minuten, nichts anderes Schweres parallel).
- [ ] **Step 5: Commit** `feat(exchange): export and restore tombstone support rows` (mit `-s` und Trailer).

### Task 8: Skripte — Sicherung und Rollback

**Files:**
- Modify: `scripts/normly-backup` (Erzeugen, Verschlüsseln, Hochladen von `<base>.tombstones.age`; Upload-Reihenfolge: `meta.json`, `dump.age`, `tombstones.age`, `.sha256` zuletzt; `prune` löscht die neue Datei mit und behandelt Waisen auch dafür)
- Modify: `scripts/normly-deploy` (Rollback: Datei laden und entschlüsseln, nach dem Wissensbestand-Import und vor `pg_restore` einspielen; Warnung bei fehlender Datei)
- Modify: `scripts/tests/conftest.py` (additiv: Fake-Verhalten für `exchange export-tombstones` auf stdout, falls nötig), `scripts/tests/test_backup.py`, `scripts/tests/test_deploy*.py`

**Verhalten (verbindlich):**
- `normly-backup run`: nach `pg_dump`/`age` die Datei im Container erzeugen: `$COMPOSE run --rm --no-deps -T --entrypoint python pipeline -m normly_core.exchange export-tombstones > "$work/$base.tombstones.json"` (stdout, kein Mount; Fehler bricht den Lauf ab, nichts hochgeladen, keine Ausgabe), mit `age -r "$NORMLY_BACKUP_AGE_RECIPIENT"` zu `$base.tombstones.age` verschlüsseln, Klartext sofort löschen. Hochgeladen wird in der Reihenfolge `meta.json`, `dump.age`, `tombstones.age`, `.sha256`. Die Prüfsummendatei deckt beide Dateien ab (`sha256sum "$base.dump.age" "$base.tombstones.age"`). `meta.json` bekommt ein Feld `"tombstones": true`.
- `prune`: Löschreihenfolge `.sha256` zuerst, dann `meta.json`, `tombstones.age`, `dump.age`; Waisenerkennung und „committed“-Logik bleiben (nur Basen mit `.sha256` zählen); `tombstones.age` ist in der Suffix-Liste.
- `normly-deploy rollback`: wenn `<backup>.tombstones.age` im Bucket existiert (Prüfung per `rclone lsf`/`rclone copyto`-Erfolg), herunterladen und mit `--age-identity` in `$work` entschlüsseln (0700-Verzeichnis, Aufräumen im bestehenden Trap); nach dem Wissensbestand-Import und **vor** `pg_restore`: `compose "$previous" run --rm --no-deps -T --entrypoint python pipeline -m normly_core.exchange import-tombstones < "$work/tombstones.json"`. Fehlt die Datei: deutliche Warnung auf stderr („backup has no tombstone file; a foreign-key error is possible while restoring user data that points at withdrawn documents“), der Rollback läuft weiter. Ein Fehler beim Einspielen der Tombstones zählt nach `DESTRUCTIVE=1` wie jeder andere Fehler (Wiederherstellungshinweis).
- Die Wiederherstellungshinweise im Fehlerfall bleiben unverändert korrekt.

- [ ] **Step 1: Failing tests** (Fake-Harness): Backup: Aufrufreihenfolge (Tombstone-Export im Container nach `pg_dump`/`age` des Dumps, `age` für die Tombstone-Datei, Uploads in der geforderten Reihenfolge mit `.sha256` zuletzt), Fehler beim Tombstone-Export (`FAKE_DOCKER_FAIL_ON=export-tombstones`) → Abbruch, kein Upload, keine Ausgabe, kein Klartext; `meta.json` enthält `tombstones: true`; `prune` löscht die neue Datei mit und behandelt Waisen. Rollback: Reihenfolge `psql DROP` < `migrate` < `import --fetch` < `import-tombstones` < `pg_restore`; Datei fehlt → Warnung, Rollback läuft weiter; Datei vorhanden → `import-tombstones` bekommt den entschlüsselten Inhalt über stdin; Fehler in `import-tombstones` → Wiederherstellungshinweis, Zustand unverändert, Lock frei. Bestehende Tests bleiben grün (Harness nur additiv).
- [ ] **Step 2:** `.venv/bin/pytest scripts/tests -q` im Repo-Root — Expected: neue Tests FAIL.
- [ ] **Step 3: Implementierung**, dann `docker run --rm -v "$PWD":/mnt -w /mnt koalaman/shellcheck:v0.9.0 scripts/normly-deploy scripts/normly-backup scripts/normly-env.sh` (clean) und `.venv/bin/pytest scripts/tests -q`.
- [ ] **Step 4: Commit** `feat(backup): back up tombstone support rows and restore them before user data on rollback` (mit `-s` und Trailer).

### Task 9: Dokumentation und Befunde der Abschlussprüfung

**Files:** `docs/adr/README.md` (ADR-026 Folgen/Offen, ADR-024, Register), `docs/guide/operations.md`, `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`, `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`, `core/src/normly_core/exchange/tables.py` (nur Kommentar), `core/src/normly_core/graph/postgres/exchange.py` (nur Docstring)

- [ ] **Step 1: ADR-026 / ADR-024:** Die Einschränkung „Rollback scheitert nach einer Rücknahme“ entfällt; stattdessen die Lösung beschreiben (Tombstone-Datei: Inhalt, Abschluss über Fremdschlüssel, Einspielen vor den Nutzerdaten, `ON CONFLICT DO NOTHING`, Abwärtskompatibilität mit älteren Sicherungen) und was **nicht** wiederhergestellt wird (Inhalt, Rechte; nur Kennungen). Hinweis, dass `revoked_at` an einer zurückgezogenen Kante der Importzeitpunkt ist und kein Ereignisdatum (M-9). ADR-024: Sicherung enthält jetzt eine zweite Datei; Aufbewahrung gilt für beide.
- [ ] **Step 2: `docs/guide/operations.md` (Englisch):** Backup (neue Datei, Reihenfolge, Wiederherstellung), Rollback (Schritt „restore tombstone support“ vor den Nutzerdaten, Verhalten bei fehlender Datei), Restore-Test (zusätzlicher nummerierter Schritt `import-tombstones` zwischen Wissensbestand-Import und `pg_restore`), M-4 (Benachrichtigung „no longer available“ gilt nur für Beobachtungen, die älter als die Rücknahme sind, und für Konten mit eingeschalteter Benachrichtigung).
- [ ] **Step 3: Befunde der Abschlussprüfung:** (M-1) Spec `2026-10-09-user-data-on-kb-import-design.md`: „Nicht-Ziele“ und „Offene Punkte“ passen zur ausgelieferten Glocke (Anzeige ist enthalten; nur Link/Detailseite bleiben ausgenommen); (M-2) TP4-Spec: Nutzerdaten-Gruppe nennt `notified_retirement`; (M-3) ADR-026: der Fail-closed-Test läuft über jede Tabelle außerhalb des Wissensbestands (inklusive `identity_resolution_case`), nicht nur Nutzerdaten-Tabellen; (M-5) Kommentar in `exchange/tables.py` (RETAINED = nur Herkunft) und Docstring von `replace_knowledge_base` (Kante wird beim Zurückziehen auch widerrufen; Zurückziehen läuft vor dem Einfügen) korrigieren.
- [ ] **Step 4:** Docs-Build wie in CI (docker `python:3.12`, `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, `zensical build`, Zeile `3 issues found`; mit `--user "$(id -u):$(id -g)"`, beschreibbarem HOME und venv unter /tmp; danach `site/` und `.cache/` entfernen). Falls die Docstring-/Kommentar-Änderung Tests berührt: `cd core && ../.venv/bin/pytest tests/exchange -q`.
- [ ] **Step 5: Commit** `docs: tombstone support in backup and rollback; align spec and ADR wording` (mit `-s` und Trailer).

## Selbstprüfung der Erweiterung 2

| Anforderung (I-1) | Task |
|---|---|
| Tombstone-Kennungen samt FK-Eltern als eigene verschlüsselte Datei sichern | Task 7 (Kern), Task 8 (Skript) |
| Rollback spielt sie nach dem Wissensbestand und vor den Nutzerdaten ein | Task 8 (Reihenfolgetest), Task 7 (Ende-zu-Ende ohne FK-Fehler) |
| Abwärtskompatibilität mit älteren Sicherungen | Task 8 (Test „Datei fehlt“) |
| Doku: ADR, Guide, Restore-Test, Befunde M-1..M-5, M-9 | Task 9 |

**Risiken:** Der Abschluss über Fremdschlüssel darf nicht zu klein sein (Kante → Dokumente → Works → Lieferungen → Quellen; Test mit Kante) und nicht explodieren (nur Eltern, nie Kinder); `ON CONFLICT DO NOTHING` mit dem Self-FK `merged_into_work_id`; `docker compose run -T` mit stdin-Umleitung im echten Compose (nur gegen Fakes getestet; Live-Abnahme); die Sicherung wird um die Laufzeit des Containerstarts länger (Sekunden).
