# TP4 Deployment-Automatisierung — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neue Versionen werden pull-basiert auf die VM ausgerollt und lassen sich zurücknehmen, Nutzerdaten werden verschlüsselt gesichert, und der freie Wissensbestand wird als signierter, schemaunabhängiger Parquet-Dump im Object Storage verteilt und importiert.

**Architecture:** Drei getrennt abnehmbare Teile. (A) Austauschformat im Kern: `normly_core.exchange` (Tabellengruppen, Manifest, Ed25519-Signatur, Parquet-Export/-Import) über eine neue Repository-Schnittstelle `KnowledgeExchangeRepository`. (B) `normly-backup` (Bash + stdlib-Python für die Aufbewahrung). (C) `normly-deploy` (Bash) mit `cosign verify`, Pre-Rollout-Sicherung, Rollback durch Schema-Neuaufbau. Deploy-Dateien (Compose, Caddyfile, Skripte) reisen im signierten `pipeline`-Image.

**Tech Stack:** Python 3.11+, SQLAlchemy 2 Core, Alembic, pyarrow (Parquet), cryptography (Ed25519), pytest + testcontainers; Bash, age, rclone, cosign, pg_dump/psql/pg_restore, systemd.

Spec: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md` (Entscheidungen D1–D6 gelten unverändert).

## Global Constraints

- Quelldateien tragen einen Lizenzheader: `SPDX-License-Identifier: AGPL-3.0-or-later` und `Copyright (C) 2026 normly contributors` (Kern, Skripte, Deploy-Dateien).
- Commits: Englisch, Conventional Commits, `-s` (DCO, Signed-off-by des Menschen), Trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **nie** `git config` ausführen; kein Push und kein PR ohne Rückfrage (CI ist abgerechnet).
- Datenbankzugriff nur über die Repository-Schicht (ADR-006): kein SQL in `normly_core/exchange/`. `test_architecture.py` verlangt für jede Protocol-Methode mit Präfix `get_`/`list_` einen `jurisdiction`-Parameter — die neue Schnittstelle benutzt deshalb **keine** Methoden mit diesen Präfixen.
- Rechteklassifikation ist das einzige Tor: fehlende Klassifikation heißt nicht exportieren; nur Quellen der Kategorien A, B, D, nie `commercial_catalog`.
- Verarbeitungsschritte idempotent; jedes abgeleitete Artefakt trägt `delivery_id` (Abstammung bleibt in jeder Exportzeile erhalten).
- Alles Persistierte verschlüsselt; der private `age`-Schlüssel und der private Signaturschlüssel liegen **nie** auf der VM und nie im Repository.
- Keine Secrets im Code, auch nicht in Tests (Tests erzeugen Schlüssel zur Laufzeit).
- Dokumentation (`docs/guide/`) auf Englisch; ADRs, Spec, Plan auf Deutsch (ADR-020).
- Python-Tests laufen mit `cd core && ../.venv/bin/pytest <pfad>`; Docker muss laufen (testcontainers).
- Dump-Layout: `<version>/manifest.json`, `<version>/manifest.json.sig` (64 Rohbytes Ed25519), `<version>/tables/<tabelle>/part-NNNN.parquet`.
- Tabellenreihenfolge im Wissensbestand ist FK-sicher (Eltern zuerst): `source, delivery, work, document, document_designation, document_title, rights_classification, edge, segment, embedding, document_embedding`.
- Objekt-Layout im Backup-Bucket: `backups/<YYYYMMDDTHHMMSSZ>-<kind>.dump.age` (+ `.meta.json`, `.sha256`), `kind` = `daily` oder `pre-<tag>`.
- Aufbewahrung: 7 tägliche (eine je Kalendertag), 2 monatliche (jeweils neuester Tagesstand der 2 jüngsten Kalendermonate), 3 Pre-Rollout-Stände.
- Image-Tags tragen kein `v`-Präfix (`0.1.2`); die Skripte akzeptieren `v0.1.2` und `0.1.2`.

## Dateiübersicht

| Datei | Verantwortung |
|---|---|
| `core/src/normly_core/exchange/tables.py` | Tabellengruppen (Wissensbestand / Nutzerdaten / Pipeline-Zustand), FK-Reihenfolge |
| `core/src/normly_core/exchange/manifest.py` | Manifest-Datenmodell, Prüfsummen, (De-)Serialisierung |
| `core/src/normly_core/exchange/signing.py` | Ed25519 Schlüsselerzeugung, Signieren, Prüfen |
| `core/src/normly_core/exchange/parquet_io.py` | Parquet-Schreiben/-Lesen mit festem Schema je Spaltenart |
| `core/src/normly_core/exchange/exporter.py` | Export-Orchestrierung über die Repository-Schnittstelle |
| `core/src/normly_core/exchange/importer.py` | Import-Orchestrierung (Signatur, Modell, Prüfsummen, Austausch) |
| `core/src/normly_core/exchange/fetch.py` | Dump per HTTPS laden |
| `core/src/normly_core/exchange/__main__.py` | CLI: `keygen`, `export`, `import`, `info`, `tables` |
| `core/src/normly_core/graph/domain.py` | + `ExchangeColumn`, `ImportRecord`, `ImportBlockedError`, `KnowledgeExchangeRepository` |
| `core/src/normly_core/graph/postgres/exchange.py` | `PostgresKnowledgeExchangeRepository` (Gate-Abfragen, atomarer Austausch) |
| `core/src/normly_core/graph/postgres/orm.py` + `core/migrations/versions/0032_create_knowledge_base_import.py` | Tabelle `knowledge_base_import` (importierte Version) |
| `docker/python.Dockerfile` | `pipeline`-Stage: `NORMLY_EMBEDDING_MODEL_REVISION`, Deploy-Dateien nach `/app/deploy` |
| `compose.yaml`, `.env.example` | Profil `kb-import` bzw. Dienst, `NORMLY_KB_BASE_URL` |
| `scripts/normly-backup`, `scripts/normly-backup-retention.py` | Sicherung, Verschlüsselung, Upload, Aufbewahrung |
| `scripts/normly-deploy` | `deploy`, `rollback`, `status` |
| `scripts/tests/` | pytest-Harness mit Fake-Binaries für beide Skripte |
| `deploy/systemd/normly-backup.{service,timer}` | täglicher Timer |
| `docs/guide/operations.md`, `docs/guide/self-hosting.md` | Betrieb und Dump-Import (Englisch) |
| `docs/adr/README.md`, `CLAUDE.md`, `docs/srs/…` | ADR-024, ADR-025, ADR-021-Nachtrag, Verweise |

---

## Teil A — Austauschformat im Kern

### Task 1: Tabellengruppen und Vollständigkeitstest

**Files:**
- Create: `core/src/normly_core/exchange/__init__.py`
- Create: `core/src/normly_core/exchange/tables.py`
- Test: `core/tests/exchange/__init__.py`, `core/tests/exchange/test_tables.py`

**Interfaces:**
- Produces: `KNOWLEDGE_TABLES: tuple[str, ...]`, `USER_TABLES: tuple[str, ...]`, `PIPELINE_STATE_TABLES: tuple[str, ...]`, `SYSTEM_TABLES: tuple[str, ...]` (`knowledge_base_import`; `alembic_version` ist nicht im ORM und steht in `UNMANAGED_TABLES`), `group_tables(name: str) -> tuple[str, ...]` für `knowledge|user|pipeline|all`.

- [ ] **Step 1: Failing test schreiben**

`core/tests/exchange/test_tables.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange import tables
from normly_core.graph.postgres import orm  # noqa: F401  (registers all tables)
from normly_core.graph.postgres.orm import Base


def test_every_orm_table_belongs_to_exactly_one_group():
    groups = [
        set(tables.KNOWLEDGE_TABLES),
        set(tables.USER_TABLES),
        set(tables.PIPELINE_STATE_TABLES),
        set(tables.SYSTEM_TABLES),
    ]
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert a.isdisjoint(b)
    assert set().union(*groups) == set(Base.metadata.tables)


def _foreign_targets(table_name):
    table = Base.metadata.tables[table_name]
    return {fk.column.table.name for column in table.columns for fk in column.foreign_keys}


@pytest.mark.parametrize("group", [tables.KNOWLEDGE_TABLES, tables.USER_TABLES])
def test_group_order_is_foreign_key_safe(group):
    seen = set()
    for name in group:
        in_group_parents = _foreign_targets(name) & set(group) - {name}
        assert in_group_parents <= seen, f"{name} listed before {in_group_parents - seen}"
        seen.add(name)


def test_knowledge_tables_never_reference_user_tables():
    for name in tables.KNOWLEDGE_TABLES:
        assert _foreign_targets(name).isdisjoint(tables.USER_TABLES)


def test_group_tables_lookup():
    assert tables.group_tables("knowledge") == tables.KNOWLEDGE_TABLES
    assert set(tables.group_tables("all")) >= set(tables.USER_TABLES) | {"alembic_version"}
    with pytest.raises(ValueError):
        tables.group_tables("nope")
```

Der Test setzt `knowledge_base_import` aus Task 3 voraus; bis dahin schlägt der erste Test an genau dieser Stelle fehl. Deshalb wird Step 3 in diesem Task die Tabelle schon in `SYSTEM_TABLES` führen, und Task 3 legt ORM/Migration an; **Task 1 ist erst nach Task 3 vollständig grün** — der Test für „jede ORM-Tabelle genau einmal“ wird in Task 1 mit `pytest.mark.xfail(strict=True, reason="knowledge_base_import arrives in Task 3")` markiert und in Task 3 Step 6 entmarkiert.

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'normly_core.exchange'`

- [ ] **Step 3: Implementierung**

`core/src/normly_core/exchange/__init__.py`: nur Lizenzheader.

`core/src/normly_core/exchange/tables.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Which table belongs to which backup/exchange group.

Three groups (TP4 spec, Teil 2):

* knowledge -- the free knowledge base. Reproducible from source deliveries,
  distributed as a versioned dump (Teil 3), never part of the daily backup.
* user -- accounts, chats, watchlists, notifications. Small, irreplaceable,
  backed up daily. Rows reference knowledge rows by foreign key, which is why
  the dump must keep IDs unchanged.
* pipeline -- state of the local ingestion (review queue). Neither exported
  nor backed up.

Both lists are ordered parents-first so inserts can run front to back and
deletes back to front. `test_tables.py` fails when a table is added to the ORM
without being placed here.
"""

KNOWLEDGE_TABLES: tuple[str, ...] = (
    "source",
    "delivery",
    "work",
    "document",
    "document_designation",
    "document_title",
    "rights_classification",
    "edge",
    "segment",
    "embedding",
    "document_embedding",
)

USER_TABLES: tuple[str, ...] = (
    "account",
    "account_session",
    "account_google_identity",
    "account_token",
    "oauth_state",
    "watchlist",
    "notification",
    "rights_notification_baseline",
    "notified_edge",
    "chat_session",
    "chat_message",
    "chat_message_citation",
    "rate_limit_bucket",
)

PIPELINE_STATE_TABLES: tuple[str, ...] = ("identity_resolution_case",)

#: Written by the dump import itself; belongs to no group above.
SYSTEM_TABLES: tuple[str, ...] = ("knowledge_base_import",)

#: Exists in the database but not in the ORM metadata.
UNMANAGED_TABLES: tuple[str, ...] = ("alembic_version",)


def group_tables(name: str) -> tuple[str, ...]:
    if name == "knowledge":
        return KNOWLEDGE_TABLES
    if name == "user":
        return USER_TABLES
    if name == "pipeline":
        return PIPELINE_STATE_TABLES
    if name == "all":
        return (
            *USER_TABLES,
            *reversed(KNOWLEDGE_TABLES),
            *PIPELINE_STATE_TABLES,
            *SYSTEM_TABLES,
            *UNMANAGED_TABLES,
        )
    raise ValueError(f"unknown table group: {name!r}")
```

Hinweis zu `all`: Die Reihenfolge ist „Kinder zuerst“ und wird für `DROP TABLE … CASCADE` im Rollback benutzt; CASCADE macht sie unkritisch.

- [ ] **Step 4: Test laufen lassen**

Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py -v`
Expected: PASS für die Reihenfolgetests; der markierte Vollständigkeitstest XFAIL.

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/exchange core/tests/exchange
git commit -s -m "feat(exchange): table groups for backup and knowledge-base dump

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Manifest und Ed25519-Signatur

**Files:**
- Create: `core/src/normly_core/exchange/manifest.py`, `core/src/normly_core/exchange/signing.py`
- Modify: `core/pyproject.toml` (Abhängigkeiten `pyarrow>=17,<20`, `cryptography>=43,<46`), danach `uv lock`
- Test: `core/tests/exchange/test_manifest.py`, `core/tests/exchange/test_signing.py`

**Interfaces:**
- Produces:
  - `EXCHANGE_SCHEMA_VERSION = 1`, `EMBEDDING_DIMENSION = 1024`
  - `FileEntry(path: str, sha256: str, rows: int)`; `DeliveryEntry(delivery_id: str, publisher: str, legal_basis_category: str)`
  - `Manifest(exchange_schema_version: int, dump_version: str, created_at: str, embedding_models: list[str], embedding_model_revision: str, embedding_dimension: int, deliveries: list[DeliveryEntry], tables: dict[str, list[FileEntry]])` mit `to_bytes() -> bytes` (kanonisches JSON, `sort_keys=True`, UTF-8) und `Manifest.from_bytes(data: bytes) -> Manifest`
  - `sha256_file(path: Path) -> str`
  - `generate_keypair() -> tuple[bytes, bytes]` (PEM privat, PEM öffentlich), `sign(private_pem: bytes, data: bytes) -> bytes`, `verify(public_pem: bytes, data: bytes, signature: bytes) -> None` (wirft `SignatureError`)

- [ ] **Step 1: Tests schreiben**

`core/tests/exchange/test_signing.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange.signing import SignatureError, generate_keypair, sign, verify


def test_sign_and_verify_roundtrip():
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, b"manifest")
    assert len(signature) == 64
    verify(public_pem, b"manifest", signature)


def test_verify_rejects_tampered_data():
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, b"manifest")
    with pytest.raises(SignatureError):
        verify(public_pem, b"manifesT", signature)


def test_verify_rejects_other_key():
    private_pem, _ = generate_keypair()
    _, other_public = generate_keypair()
    with pytest.raises(SignatureError):
        verify(other_public, b"m", sign(private_pem, b"m"))
```

`core/tests/exchange/test_manifest.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.exchange.manifest import (
    DeliveryEntry,
    FileEntry,
    Manifest,
    sha256_file,
)


def _manifest() -> Manifest:
    return Manifest(
        exchange_schema_version=1,
        dump_version="2026.10.1",
        created_at="2026-10-09T10:00:00+00:00",
        embedding_models=["intfloat/multilingual-e5-large"],
        embedding_model_revision="3d7cfbd",
        embedding_dimension=1024,
        deliveries=[DeliveryEntry("d-1", "BAuA", "A")],
        tables={"source": [FileEntry("tables/source/part-0000.parquet", "ab", 3)]},
    )


def test_roundtrip_is_lossless():
    manifest = _manifest()
    assert Manifest.from_bytes(manifest.to_bytes()) == manifest


def test_serialisation_is_canonical():
    assert _manifest().to_bytes() == _manifest().to_bytes()
    assert b'"dump_version": "2026.10.1"' in _manifest().to_bytes()


def test_sha256_file(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    assert sha256_file(path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
```

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange -v` — erwartet FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementierung**

`core/pyproject.toml`, in `dependencies` ergänzen: `"pyarrow>=17,<20",` und `"cryptography>=43,<46",`. Dann im Repo-Root `uv lock` ausführen und `git diff uv.lock` auf nur erwartete Zusätze prüfen.

`signing.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Ed25519 signing of the dump manifest.

Why in-process and not cosign/minisign: the import runs inside the `pipeline`
image and at self-hosters; one more binary would grow the image and add an
install step. The format is a raw 64-byte signature over the exact bytes of
manifest.json. The private key is held offline by the maintainers.
"""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class SignatureError(Exception):
    """The manifest signature does not match the public key."""


def generate_keypair() -> tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign(private_pem: bytes, data: bytes) -> bytes:
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    return key.sign(data)


def verify(public_pem: bytes, data: bytes, signature: bytes) -> None:
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("not an Ed25519 public key")
    try:
        key.verify(signature, data)
    except InvalidSignature as exc:
        raise SignatureError("manifest signature does not match the public key") from exc
```

`manifest.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

#: Version of the dump layout, independent of the Alembic revision. Bump when
#: manifest or Parquet column semantics change incompatibly.
EXCHANGE_SCHEMA_VERSION = 1
EMBEDDING_DIMENSION = 1024


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    rows: int


@dataclass(frozen=True)
class DeliveryEntry:
    delivery_id: str
    publisher: str
    legal_basis_category: str


@dataclass(frozen=True)
class Manifest:
    exchange_schema_version: int
    dump_version: str
    created_at: str
    embedding_models: list[str]
    embedding_model_revision: str
    embedding_dimension: int
    deliveries: list[DeliveryEntry]
    tables: dict[str, list[FileEntry]]

    def to_bytes(self) -> bytes:
        return (json.dumps(asdict(self), sort_keys=True, indent=2) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Manifest":
        raw = json.loads(data.decode("utf-8"))
        return cls(
            exchange_schema_version=raw["exchange_schema_version"],
            dump_version=raw["dump_version"],
            created_at=raw["created_at"],
            embedding_models=list(raw["embedding_models"]),
            embedding_model_revision=raw["embedding_model_revision"],
            embedding_dimension=raw["embedding_dimension"],
            deliveries=[DeliveryEntry(**d) for d in raw["deliveries"]],
            tables={
                name: [FileEntry(**f) for f in files]
                for name, files in raw["tables"].items()
            },
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — erwartet PASS.

- [ ] **Step 5: Commit**

```bash
git add core/pyproject.toml uv.lock core/src/normly_core/exchange core/tests/exchange
git commit -s -m "feat(exchange): dump manifest and Ed25519 signing

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Repository-Schnittstelle, Migration und Postgres-Implementierung

Der größte Task. Er liefert: Tabelle `knowledge_base_import`, Protocol, Gate-Abfragen und den atomaren Austausch — alles mit echten Daten gegen Postgres getestet.

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (Dataclasses + Protocol am Dateiende)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`KnowledgeBaseImportORM`)
- Create: `core/migrations/versions/0032_create_knowledge_base_import.py`
- Create: `core/src/normly_core/graph/postgres/exchange.py`
- Modify: `core/tests/exchange/test_tables.py` (xfail entfernen)
- Test: `core/tests/exchange/test_exchange_repository.py`

**Interfaces:**
- Produces (in `normly_core.graph.domain`):

```python
@dataclass(frozen=True)
class ExchangeColumn:
    name: str
    kind: str   # "string"|"bool"|"int"|"float"|"timestamp"|"date"|"vector"

@dataclass(frozen=True)
class ImportRecord:
    dump_version: str
    exchange_schema_version: int
    embedding_model_revision: str
    imported_at: datetime

class ImportBlockedError(Exception):
    def __init__(self, table: str, detail: str): ...

RowBatches = Callable[[], Iterator[list[dict[str, Any]]]]

class KnowledgeExchangeRepository(Protocol):
    def exchange_columns(self, table: str) -> list[ExchangeColumn]: ...
    def iter_exportable_rows(self, table: str, *, batch_size: int = 5000) -> Iterator[list[dict[str, Any]]]: ...
    def exportable_deliveries(self) -> list[tuple[str, str, str]]: ...   # (delivery_id, publisher, category)
    def replace_knowledge_base(self, tables: Mapping[str, RowBatches], *, record: ImportRecord) -> None: ...
    def imported_version(self) -> ImportRecord | None: ...
```

  Zeilen sind `dict[str, Any]` mit Austauschtypen: UUID → `str`, Enum → `str` (`.value`), Vektor → `list[float]`, sonst native Python-Typen (`datetime` mit Zeitzone, `date`, `bool`, `int`, `str`).
- Produces (in `normly_core.graph.postgres.exchange`): `PostgresKnowledgeExchangeRepository(session: Session)`.
- Die Methoden committen nie; der Aufrufer committet.

- [ ] **Step 1: ORM, Migration, Entmarkierung**

Am Ende von `orm.py` anfügen:

```python
class KnowledgeBaseImportORM(Base):
    """Single-row record of which knowledge-base dump is currently imported."""

    __tablename__ = "knowledge_base_import"

    id: Mapped[int] = mapped_column(primary_key=True)
    dump_version: Mapped[str]
    exchange_schema_version: Mapped[int]
    embedding_model_revision: Mapped[str]
    imported_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (sa.CheckConstraint("id = 1", name="ck_knowledge_base_import_single_row"),)
```

`0032_create_knowledge_base_import.py` (Revision-IDs aus Nachbarmigration übernehmen; `down_revision` ist die ID der Migration `0031_add_hnsw_indexes` — mit `grep -n "^revision" core/migrations/versions/0031_add_hnsw_indexes.py` nachsehen):

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create knowledge_base_import

Revision ID: 0032
Revises: <revision id of 0031>
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "<revision id of 0031>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_import",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dump_version", sa.String, nullable=False),
        sa.Column("exchange_schema_version", sa.Integer, nullable=False),
        sa.Column("embedding_model_revision", sa.String, nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_knowledge_base_import_single_row"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_base_import")
```

In `core/tests/exchange/test_tables.py` den `xfail`-Marker (Step 1 aus Task 1) entfernen. Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v` — Expected: PASS.

- [ ] **Step 2: Domain-Typen und Protocol**

An `core/src/normly_core/graph/domain.py` anhängen (Imports `Any, Callable, Iterator, Mapping` aus `typing`/`collections.abc` ergänzen, falls fehlend; **kein** SQLAlchemy-Import):

```python
@dataclass(frozen=True)
class ExchangeColumn:
    name: str
    kind: str


@dataclass(frozen=True)
class ImportRecord:
    dump_version: str
    exchange_schema_version: int
    embedding_model_revision: str
    imported_at: datetime


class ImportBlockedError(Exception):
    """
    The import would delete a knowledge-base row that user data still points
    at (e.g. a watched Work the new dump no longer contains). Nothing was
    changed.
    """

    def __init__(self, table: str, detail: str):
        super().__init__(f"import blocked while deleting from {table}: {detail}")
        self.table = table
        self.detail = detail


RowBatches = Callable[[], Iterator[list[dict[str, Any]]]]


class KnowledgeExchangeRepository(Protocol):
    """
    Bulk access to the free knowledge base for the versioned dump (ADR-025).

    Deliberately no `get_`/`list_` names: those prefixes trigger the
    jurisdiction guard in test_architecture.py, and the export gate here is
    the rights classification itself (may_process AND may_export_free, not
    revoked, delivery not withdrawn, source category A/B/D and not a
    commercial catalogue), evaluated across all jurisdictions.
    """

    def exchange_columns(self, table: str) -> list[ExchangeColumn]: ...

    def iter_exportable_rows(
        self, table: str, *, batch_size: int = 5000
    ) -> Iterator[list[dict[str, Any]]]: ...

    def exportable_deliveries(self) -> list[tuple[str, str, str]]: ...

    def replace_knowledge_base(
        self, tables: Mapping[str, RowBatches], *, record: ImportRecord
    ) -> None: ...

    def imported_version(self) -> ImportRecord | None: ...
```

- [ ] **Step 3: Failing tests für das Repository**

Zuerst `core/tests/exchange/helpers.py` (Fixture-Muster aus `tests/graph/test_jurisdiction_export.py`; wird auch von Task 4 genutzt):

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def make_source(session, category=LegalBasisCategory.A, commercial=False, publisher="BAuA"):
    return PostgresSourceRepository(session).create_source(
        publisher=publisher, retrieval_path="https://example.org",
        legal_basis_category=category, jurisdiction="DE", reviewed_at=date(2026, 1, 1),
        responsible_person="J. Weber", commercial_catalog=commercial,
        contract_reference="V-1" if category == LegalBasisCategory.C else None,
    )


def make_delivery(session, source, tag):
    return PostgresDeliveryRepository(session).record_delivery(
        source_id=source.id, content_hash=f"sha256:{tag}", ingested_at=NOW
    )


def make_document(session, delivery, number, *, export=True, process=True, jurisdiction="DE"):
    document = PostgresDocumentRepository(session).create_document(
        origin_issuer="BAuA", origin_number=number, edition="2026", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=process,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=export,
        legal_basis_reference="§ 5 UrhG", classified_at=NOW, classified_by="J. Weber",
        delivery_id=delivery.id,
    )
    return document
```

Dann `core/tests/exchange/test_exchange_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest
import sqlalchemy as sa

from tests.exchange.helpers import NOW, make_delivery as _delivery, make_document as _document, make_source as _source

from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import (
    EdgeType,
    ImportBlockedError,
    ImportRecord,
    Layer,
    LegalBasisCategory,
)
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresSegmentRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)


def _all_rows(repository, table):
    return [row for batch in repository.iter_exportable_rows(table) for row in batch]


def test_export_contains_only_exportable_rows(db_session):
    free = _source(db_session)
    delivery = _delivery(db_session, free, "free")
    shown = _document(db_session, delivery, "TRGS 900")
    hidden = _document(db_session, delivery, "TRGS 901", export=False)
    unclassified = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="BAuA", origin_number="TRGS 902", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    commercial = _source(db_session, LegalBasisCategory.C, publisher="DIN")
    commercial_delivery = _delivery(db_session, commercial, "c")
    licensed = _document(db_session, commercial_delivery, "DIN 1")

    repository = PostgresKnowledgeExchangeRepository(db_session)
    document_ids = {row["id"] for row in _all_rows(repository, "document")}

    assert document_ids == {str(shown.id)}
    assert str(hidden.id) not in document_ids
    assert str(unclassified.id) not in document_ids
    assert str(licensed.id) not in document_ids
    assert {row["publisher"] for row in _all_rows(repository, "source")} == {"BAuA"}
    assert {str(d) for d, _, _ in repository.exportable_deliveries()} == {str(delivery.id)}


def test_withdrawn_delivery_is_excluded(db_session):
    source = _source(db_session)
    delivery = _delivery(db_session, source, "w")
    _document(db_session, delivery, "TRGS 900")
    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    repository = PostgresKnowledgeExchangeRepository(db_session)
    assert _all_rows(repository, "document") == []
    assert _all_rows(repository, "delivery") == []


def test_edges_need_both_endpoints_exportable(db_session):
    source = _source(db_session)
    delivery = _delivery(db_session, source, "e")
    a = _document(db_session, delivery, "A")
    b = _document(db_session, delivery, "B")
    private = _document(db_session, delivery, "C", export=False)
    edges = PostgresEdgeRepository(db_session)
    kept = edges.create_edge(
        from_document_id=a.id, to_document_id=b.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edges.create_edge(
        from_document_id=a.id, to_document_id=private.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edges.create_edge(
        from_document_id=b.id, to_document_id=a.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.COMMERCIAL, delivery_id=delivery.id,
    )

    repository = PostgresKnowledgeExchangeRepository(db_session)
    assert [row["id"] for row in _all_rows(repository, "edge")] == [str(kept.id)]


def test_row_types_are_exchange_types(db_session):
    source = _source(db_session)
    delivery = _delivery(db_session, source, "t")
    document = _document(db_session, delivery, "A")
    PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="h", text="body", language="de",
    )

    repository = PostgresKnowledgeExchangeRepository(db_session)
    row = _all_rows(repository, "source")[0]
    assert isinstance(row["id"], str)
    assert row["legal_basis_category"] == "A"
    assert isinstance(row["reviewed_at"], date)
    kinds = {c.name: c.kind for c in repository.exchange_columns("embedding")}
    assert kinds["vector"] == "vector" and kinds["id"] == "string"


def _snapshot(session):
    return {
        table: sorted(
            session.execute(sa.text(f'SELECT id::text FROM "{table}"')).scalars()
        )
        for table in ("source", "delivery", "document", "segment")
    }


def _batches(repository):
    return {
        table: (lambda t=table: repository.iter_exportable_rows(t))
        for table in KNOWLEDGE_TABLES
    }


def _record():
    return ImportRecord("2026.10.1", 1, "rev", NOW)


def test_replace_is_idempotent_and_removes_missing_rows(db_session):
    source = _source(db_session)
    delivery = _delivery(db_session, source, "r")
    keep = _document(db_session, delivery, "KEEP")
    drop = _document(db_session, delivery, "DROP")
    PostgresSegmentRepository(db_session).add_segment(
        document_id=keep.id, delivery_id=delivery.id, sequence_number=1,
        heading=None, text="t", language="de",
    )
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump = {t: _all_rows(repository, t) for t in KNOWLEDGE_TABLES}

    # remove one document from the dump; the import must delete it
    dump["document"] = [r for r in dump["document"] if r["id"] != str(drop.id)]
    dump["rights_classification"] = [
        r for r in dump["rights_classification"] if r["document_id"] != str(drop.id)
    ]
    frozen = {t: (lambda rows=rows: iter([rows])) for t, rows in dump.items()}

    repository.replace_knowledge_base(frozen, record=_record())
    first = _snapshot(db_session)
    repository.replace_knowledge_base(frozen, record=_record())

    assert _snapshot(db_session) == first
    assert str(drop.id) not in first["document"]
    assert str(keep.id) in first["document"]
    assert repository.imported_version().dump_version == "2026.10.1"


def test_replace_blocks_when_user_data_still_references_a_row(db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    source = _source(db_session)
    delivery = _delivery(db_session, source, "b")
    document = _document(db_session, delivery, "A")
    work = PostgresWorkRepository(db_session).get_work(document.work_id)
    account = PostgresAccountRepository(db_session).create_account(
        email="a@example.org", password_hash="x"
    )
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=work.id
    )
    repository = PostgresKnowledgeExchangeRepository(db_session)
    empty = {t: (lambda: iter([])) for t in KNOWLEDGE_TABLES}

    with pytest.raises(ImportBlockedError) as blocked:
        repository.replace_knowledge_base(empty, record=_record())
    assert "work" in blocked.value.table or "document" in blocked.value.table
```

Hinweis: Die Signatur von `PostgresAccountRepository.create_account` und `PostgresSegmentRepository.add_segment` ist vor dem Schreiben mit `grep -n "def create_account\|def add_segment" core/src/normly_core/graph/postgres/repositories.py` zu prüfen und der Test an die tatsächlichen Parameter anzupassen (Parameternamen, nicht die Aussage der Tests).

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange/test_exchange_repository.py -v` — erwartet FAIL (`ModuleNotFoundError: normly_core.graph.postgres.exchange`).

- [ ] **Step 5: Implementierung**

`core/src/normly_core/graph/postgres/exchange.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Postgres implementation of KnowledgeExchangeRepository.

The export gate is evaluated here, in one place (rights classification is the
only gate): a document is exportable when at least one of its classifications
has may_process AND may_export_free, is not revoked, and descends from a
delivery that is not withdrawn and whose source is category A/B/D and not a
commercial catalogue. Every other exported row is derived from exportable
documents, so no exported row can point at a missing parent.
"""

import enum
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import (
    ExchangeColumn,
    ImportBlockedError,
    ImportRecord,
    LegalBasisCategory,
    RowBatches,
)
from normly_core.graph.postgres.orm import (
    Base,
    DeliveryORM,
    DocumentORM,
    EdgeORM,
    KnowledgeBaseImportORM,
    RightsClassificationORM,
    SegmentORM,
    SourceORM,
    WorkORM,
)

_FREE_CATEGORIES = (LegalBasisCategory.A, LegalBasisCategory.B, LegalBasisCategory.D)
_WRITE_BATCH = 2000


def _eligible_deliveries():
    return (
        select(DeliveryORM.id)
        .join(SourceORM, SourceORM.id == DeliveryORM.source_id)
        .where(
            DeliveryORM.withdrawn_at.is_(None),
            SourceORM.legal_basis_category.in_(_FREE_CATEGORIES),
            SourceORM.commercial_catalog.is_(False),
        )
    )


def _exportable_rights():
    rc = RightsClassificationORM
    return select(rc.document_id, rc.jurisdiction).where(
        rc.may_process.is_(True),
        rc.may_export_free.is_(True),
        rc.revoked_at.is_(None),
        rc.delivery_id.in_(_eligible_deliveries()),
    )


def _eligible_documents():
    return select(DocumentORM.id).where(
        DocumentORM.id.in_(select(_exportable_rights().subquery().c.document_id)),
        DocumentORM.created_via_delivery_id.in_(_eligible_deliveries()),
    )


def _eligible_works():
    reached = (
        select(DocumentORM.work_id.label("id"))
        .where(DocumentORM.id.in_(_eligible_documents()))
        .cte("exportable_work", recursive=True)
    )
    parent = select(WorkORM.merged_into_work_id).join(reached, WorkORM.id == reached.c.id).where(
        WorkORM.merged_into_work_id.is_not(None)
    )
    reached = reached.union(parent)
    return select(reached.c.id)


def _statement(table_name: str):
    table = Base.metadata.tables[table_name]
    delivery_ok = table.c.delivery_id.in_(_eligible_deliveries()) if "delivery_id" in table.c else None

    def with_delivery(*conditions):
        parts = list(conditions)
        if delivery_ok is not None:
            parts.append(delivery_ok)
        return select(table).where(*parts)

    if table_name == "source":
        return select(table).where(
            table.c.id.in_(
                select(DeliveryORM.source_id).where(DeliveryORM.id.in_(_eligible_deliveries()))
            )
        )
    if table_name == "delivery":
        return select(table).where(table.c.id.in_(_eligible_deliveries()))
    if table_name == "work":
        return select(table).where(table.c.id.in_(_eligible_works()))
    if table_name == "document":
        return select(table).where(table.c.id.in_(_eligible_documents()))
    if table_name in ("document_designation", "document_title", "document_embedding", "segment"):
        return with_delivery(table.c.document_id.in_(_eligible_documents()))
    if table_name == "rights_classification":
        rc = RightsClassificationORM
        return select(table).where(
            rc.may_process.is_(True),
            rc.may_export_free.is_(True),
            rc.revoked_at.is_(None),
            rc.delivery_id.in_(_eligible_deliveries()),
            rc.document_id.in_(_eligible_documents()),
        )
    if table_name == "edge":
        left = aliased(RightsClassificationORM, name="left_rights")
        right = aliased(RightsClassificationORM, name="right_rights")
        shared = (
            select(sa.literal(1))
            .select_from(left)
            .join(right, right.jurisdiction == left.jurisdiction)
            .where(
                left.document_id == EdgeORM.from_document_id,
                right.document_id == EdgeORM.to_document_id,
                left.may_process.is_(True), left.may_export_free.is_(True),
                left.revoked_at.is_(None),
                right.may_process.is_(True), right.may_export_free.is_(True),
                right.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == left.jurisdiction),
            )
            .exists()
        )
        return select(table).where(
            EdgeORM.layer == "free",
            EdgeORM.revoked_at.is_(None),
            EdgeORM.delivery_id.in_(_eligible_deliveries()),
            EdgeORM.from_document_id.in_(_eligible_documents()),
            EdgeORM.to_document_id.in_(_eligible_documents()),
            shared,
        )
    if table_name == "embedding":
        exported_segments = select(SegmentORM.id).where(
            SegmentORM.document_id.in_(_eligible_documents()),
            SegmentORM.delivery_id.in_(_eligible_deliveries()),
        )
        return with_delivery(table.c.segment_id.in_(exported_segments))
    raise ValueError(f"not a knowledge-base table: {table_name!r}")


def _kind(column: sa.Column) -> str:
    column_type = column.type
    if isinstance(column_type, Vector):
        return "vector"
    if isinstance(column_type, sa.Boolean):
        return "bool"
    if isinstance(column_type, sa.Integer):
        return "int"
    if isinstance(column_type, sa.Float):
        return "float"
    if isinstance(column_type, sa.DateTime):
        return "timestamp"
    if isinstance(column_type, sa.Date):
        return "date"
    return "string"  # String, Text, Uuid, Enum


def _to_exchange(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if hasattr(value, "tolist"):  # numpy vector from pgvector
        return [float(x) for x in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    return value


def _from_exchange(column: sa.Column, value: Any) -> Any:
    if value is None:
        return None
    column_type = column.type
    if isinstance(column_type, (postgresql.UUID, sa.Uuid)):
        return uuid.UUID(value)
    if isinstance(column_type, sa.Enum) and column_type.enum_class is not None:
        return column_type.enum_class(value)
    return value


def _primary_key(table: sa.Table) -> list[sa.Column]:
    return list(table.primary_key.columns)


class PostgresKnowledgeExchangeRepository:
    def __init__(self, session: Session):
        self._session = session

    def exchange_columns(self, table: str) -> list[ExchangeColumn]:
        return [ExchangeColumn(c.name, _kind(c)) for c in Base.metadata.tables[table].columns]

    def iter_exportable_rows(
        self, table: str, *, batch_size: int = 5000
    ) -> Iterator[list[dict[str, Any]]]:
        sa_table = Base.metadata.tables[table]
        statement = _statement(table).order_by(*_primary_key(sa_table))
        result = self._session.connection().execution_options(
            yield_per=batch_size, stream_results=True
        ).execute(statement)
        for partition in result.partitions():
            yield [
                {name: _to_exchange(value) for name, value in row._mapping.items()}
                for row in partition
            ]

    def exportable_deliveries(self) -> list[tuple[str, str, str]]:
        rows = self._session.execute(
            select(DeliveryORM.id, SourceORM.publisher, SourceORM.legal_basis_category)
            .join(SourceORM, SourceORM.id == DeliveryORM.source_id)
            .where(DeliveryORM.id.in_(_eligible_deliveries()))
            .order_by(DeliveryORM.id)
        )
        return [(str(i), publisher, category.value) for i, publisher, category in rows]

    def imported_version(self) -> ImportRecord | None:
        row = self._session.execute(select(KnowledgeBaseImportORM)).scalar_one_or_none()
        if row is None:
            return None
        return ImportRecord(
            row.dump_version, row.exchange_schema_version,
            row.embedding_model_revision, row.imported_at,
        )

    def replace_knowledge_base(
        self, tables: Mapping[str, RowBatches], *, record: ImportRecord
    ) -> None:
        connection = self._session.connection()
        keep_tables = self._load_keys(connection, tables)
        try:
            for name in reversed(KNOWLEDGE_TABLES):
                self._delete_missing(connection, name, keep_tables[name])
        except IntegrityError as exc:
            raise ImportBlockedError(name, str(exc.orig).splitlines()[0]) from exc
        for name in KNOWLEDGE_TABLES:
            self._upsert(connection, name, tables[name])
        self._write_record(record)

    def _load_keys(self, connection, tables: Mapping[str, RowBatches]) -> dict[str, sa.Table]:
        keep_tables: dict[str, sa.Table] = {}
        for name in KNOWLEDGE_TABLES:
            sa_table = Base.metadata.tables[name]
            key_columns = _primary_key(sa_table)
            keep = sa.Table(
                f"_kb_keep_{name}", sa.MetaData(),
                *[sa.Column(c.name, c.type) for c in key_columns],
                prefixes=["TEMPORARY"], postgresql_on_commit="DROP",
            )
            keep.create(connection)
            for batch in tables[name]():
                rows = [
                    {c.name: _from_exchange(c, row[c.name]) for c in key_columns}
                    for row in batch
                ]
                for start in range(0, len(rows), _WRITE_BATCH):
                    connection.execute(sa.insert(keep), rows[start:start + _WRITE_BATCH])
            keep_tables[name] = keep
        return keep_tables

    def _delete_missing(self, connection, name: str, keep: sa.Table) -> None:
        sa_table = Base.metadata.tables[name]
        match = sa.and_(*[keep.c[c.name] == c for c in _primary_key(sa_table)])
        connection.execute(sa.delete(sa_table).where(~sa.exists().where(match)))

    def _upsert(self, connection, name: str, batches: RowBatches) -> None:
        sa_table = Base.metadata.tables[name]
        key_names = [c.name for c in _primary_key(sa_table)]
        value_columns = [c for c in sa_table.columns if c.name not in key_names]
        self_reference = "merged_into_work_id" if name == "work" else None
        deferred: list[dict[str, Any]] = []
        for batch in batches():
            rows = [
                {c.name: _from_exchange(c, row[c.name]) for c in sa_table.columns}
                for row in batch
            ]
            if self_reference:
                for row in rows:
                    if row[self_reference] is not None:
                        deferred.append(
                            {"id": row["id"], self_reference: row[self_reference]}
                        )
                        row[self_reference] = None
            for start in range(0, len(rows), _WRITE_BATCH):
                chunk = rows[start:start + _WRITE_BATCH]
                insert = pg_insert(sa_table)
                if value_columns:
                    insert = insert.on_conflict_do_update(
                        index_elements=key_names,
                        set_={c.name: insert.excluded[c.name] for c in value_columns},
                    )
                else:
                    insert = insert.on_conflict_do_nothing(index_elements=key_names)
                connection.execute(insert, chunk)
        for item in deferred:
            connection.execute(
                sa.update(sa_table).where(sa_table.c.id == item["id"]).values(
                    {self_reference: item[self_reference]}
                )
            )

    def _write_record(self, record: ImportRecord) -> None:
        insert = pg_insert(KnowledgeBaseImportORM.__table__).values(
            id=1, dump_version=record.dump_version,
            exchange_schema_version=record.exchange_schema_version,
            embedding_model_revision=record.embedding_model_revision,
            imported_at=record.imported_at or datetime.now(timezone.utc),
        )
        self._session.connection().execute(
            insert.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "dump_version": insert.excluded.dump_version,
                    "exchange_schema_version": insert.excluded.exchange_schema_version,
                    "embedding_model_revision": insert.excluded.embedding_model_revision,
                    "imported_at": insert.excluded.imported_at,
                },
            )
        )
```

Bekannte Stolperstellen, die beim Debuggen zuerst zu prüfen sind (nicht vorab „wegprogrammieren“): (1) `EdgeORM.layer == "free"` muss mit dem Enum-Typ vergleichen — ggf. `Layer.FREE` aus `normly_core.graph.domain` verwenden; (2) `delete` bei `embedding`/`document_embedding` greift über `ON DELETE CASCADE` ohnehin, ist aber idempotent; (3) ein `IntegrityError` verlässt die Transaktion im Fehlerzustand — das ist gewollt, der Aufrufer rollt zurück.

- [ ] **Step 6: Tests und Architektur-Guards laufen lassen**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_architecture.py tests/graph/test_orm_migration_consistency.py -v`
Expected: PASS. Schlägt ein Gate-Test fehl, ist die jeweilige Teilabfrage in `_statement` zu korrigieren, nicht der Test.

- [ ] **Step 7: Commit**

```bash
git add core/src core/migrations core/tests
git commit -s -m "feat(exchange): knowledge-exchange repository with export gate and atomic replace

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Parquet, Export und Import

**Files:**
- Create: `core/src/normly_core/exchange/parquet_io.py`, `exporter.py`, `importer.py`
- Test: `core/tests/exchange/test_parquet_io.py`, `core/tests/exchange/test_export_import.py`

**Interfaces:**
- Consumes: `KnowledgeExchangeRepository`, `Manifest`, `FileEntry`, `DeliveryEntry`, `sign`, `verify`, `sha256_file`, `KNOWLEDGE_TABLES`.
- Produces:
  - `write_parts(directory: Path, table: str, columns: list[ExchangeColumn], batches: Iterator[list[dict]], *, rows_per_part: int) -> list[FileEntry]` (Pfade relativ zum Dump-Verzeichnis, `tables/<table>/part-NNNN.parquet`) und `read_rows(path: Path, batch_size: int = 5000) -> Iterator[list[dict]]`.
  - `export_dump(repository, *, out_dir: Path, dump_version: str, private_key_pem: bytes, embedding_model_revision: str, rows_per_part: int = 100_000, now: datetime | None = None) -> Path` (liefert `<out_dir>/<dump_version>`; bricht ab, wenn das Verzeichnis existiert — Versionen sind unveränderlich).
  - `import_dump(repository, *, dump_dir: Path, public_key_pem: bytes, expected_model_name: str, expected_model_revision: str, now: datetime | None = None) -> ImportRecord`; Fehler: `ImportRefused(Exception)` mit klarer Meldung (Signatur, Schema-Version, Modellname/-revision, Prüfsumme, Dimension).

- [ ] **Step 1: Tests schreiben**

`test_parquet_io.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.exchange.parquet_io import read_rows, write_parts
from normly_core.graph.domain import ExchangeColumn

COLUMNS = [
    ExchangeColumn("id", "string"),
    ExchangeColumn("ok", "bool"),
    ExchangeColumn("n", "int"),
    ExchangeColumn("at", "timestamp"),
    ExchangeColumn("day", "date"),
    ExchangeColumn("vector", "vector"),
    ExchangeColumn("note", "string"),
]


def _row(i):
    return {
        "id": f"id-{i}", "ok": i % 2 == 0, "n": i,
        "at": datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc),
        "day": date(2026, 10, 9), "vector": [0.5, -1.0, float(i)],
        "note": None,
    }


def test_roundtrip_across_parts(tmp_path):
    rows = [_row(i) for i in range(5)]
    entries = write_parts(tmp_path, "t", COLUMNS, iter([rows[:3], rows[3:]]), rows_per_part=2)

    assert [e.rows for e in entries] == [2, 2, 1]
    assert entries[0].path == "tables/t/part-0000.parquet"
    read = [r for e in entries for b in read_rows(tmp_path / e.path) for r in b]
    assert read == rows


def test_empty_table_still_writes_one_part(tmp_path):
    entries = write_parts(tmp_path, "t", COLUMNS, iter([]), rows_per_part=10)
    assert [e.rows for e in entries] == [0]
    assert list(read_rows(tmp_path / entries[0].path)) == []
```

`test_export_import.py` (Roundtrip gegen Postgres; hilfsfunktionen aus `test_exchange_repository.py` durch Import wiederverwenden: `from tests.exchange.test_exchange_repository import _source, _delivery, _document` — falls `tests` kein importierbares Paket ist, die Helfer in `core/tests/exchange/helpers.py` auslagern und in beiden Dateien importieren):

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import pytest

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.importer import ImportRefused, import_dump
from normly_core.exchange.signing import generate_keypair
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from tests.exchange.helpers import make_delivery, make_document, make_source

MODEL = "intfloat/multilingual-e5-large"
REVISION = "3d7cfbd"
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.fixture()
def exported(db_session, tmp_path):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "x")
    make_document(db_session, delivery, "TRGS 900")
    private_pem, public_pem = generate_keypair()
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_dir = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.1",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    return repository, dump_dir, public_pem


def test_export_writes_manifest_signature_and_tables(exported):
    _, dump_dir, _ = exported
    assert (dump_dir / "manifest.json").is_file()
    assert len((dump_dir / "manifest.json.sig").read_bytes()) == 64
    assert (dump_dir / "tables" / "document" / "part-0000.parquet").is_file()


def test_export_refuses_to_overwrite_a_version(exported, tmp_path, db_session):
    repository, dump_dir, _ = exported
    with pytest.raises(FileExistsError):
        export_dump(
            repository, out_dir=dump_dir.parent, dump_version="2026.10.1",
            private_key_pem=generate_keypair()[0], embedding_model_revision=REVISION,
        )


def test_import_roundtrip_is_idempotent(exported):
    repository, dump_dir, public_pem = exported
    for _ in range(2):
        record = import_dump(
            repository, dump_dir=dump_dir, public_key_pem=public_pem,
            expected_model_name=MODEL, expected_model_revision=REVISION, now=NOW,
        )
    assert record.dump_version == "2026.10.1"
    assert repository.imported_version().dump_version == "2026.10.1"


def test_import_refuses_tampered_table_file(exported):
    repository, dump_dir, public_pem = exported
    part = dump_dir / "tables" / "document" / "part-0000.parquet"
    part.write_bytes(part.read_bytes() + b"x")
    with pytest.raises(ImportRefused, match="checksum"):
        import_dump(
            repository, dump_dir=dump_dir, public_key_pem=public_pem,
            expected_model_name=MODEL, expected_model_revision=REVISION,
        )


def test_import_refuses_bad_signature(exported):
    repository, dump_dir, _ = exported
    with pytest.raises(ImportRefused, match="signature"):
        import_dump(
            repository, dump_dir=dump_dir, public_key_pem=generate_keypair()[1],
            expected_model_name=MODEL, expected_model_revision=REVISION,
        )


def test_import_refuses_other_embedding_revision(exported):
    repository, dump_dir, public_pem = exported
    with pytest.raises(ImportRefused, match="embedding model revision"):
        import_dump(
            repository, dump_dir=dump_dir, public_key_pem=public_pem,
            expected_model_name=MODEL, expected_model_revision="other",
        )
```

Die Hilfsfunktionen stammen aus `core/tests/exchange/helpers.py` (Task 3). Ein Test für „falsche Austausch-Schema-Version“ wird ergänzt, indem das Manifest neu mit `exchange_schema_version=99` serialisiert und signiert wird (`sign(private_pem, …)`), erwartet `match="exchange schema version"`.

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange -v` — erwartet FAIL (fehlende Module).

- [ ] **Step 3: Implementierung**

`parquet_io.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from normly_core.exchange.manifest import EMBEDDING_DIMENSION, FileEntry, sha256_file
from normly_core.graph.domain import ExchangeColumn

_ARROW_TYPES = {
    "string": pa.string(),
    "bool": pa.bool_(),
    "int": pa.int64(),
    "float": pa.float64(),
    "timestamp": pa.timestamp("us", tz="UTC"),
    "date": pa.date32(),
    "vector": pa.list_(pa.float32()),
}


def schema_for(columns: list[ExchangeColumn]) -> pa.Schema:
    return pa.schema([pa.field(c.name, _ARROW_TYPES[c.kind]) for c in columns])


def write_parts(
    directory: Path,
    table: str,
    columns: list[ExchangeColumn],
    batches: Iterator[list[dict[str, Any]]],
    *,
    rows_per_part: int,
) -> list[FileEntry]:
    schema = schema_for(columns)
    table_dir = directory / "tables" / table
    table_dir.mkdir(parents=True, exist_ok=True)
    entries: list[FileEntry] = []
    writer: pq.ParquetWriter | None = None
    rows_in_part = 0
    part_path: Path | None = None

    def close_part() -> None:
        nonlocal writer, rows_in_part, part_path
        if writer is None:
            return
        writer.close()
        assert part_path is not None
        entries.append(
            FileEntry(
                path=part_path.relative_to(directory).as_posix(),
                sha256=sha256_file(part_path),
                rows=rows_in_part,
            )
        )
        writer, rows_in_part, part_path = None, 0, None

    def open_part() -> None:
        nonlocal writer, part_path
        part_path = table_dir / f"part-{len(entries):04d}.parquet"
        writer = pq.ParquetWriter(part_path, schema, compression="zstd")

    for batch in batches:
        for start in range(0, len(batch), rows_per_part):
            chunk = batch[start:start + rows_per_part]
            while chunk:
                if writer is None:
                    open_part()
                room = rows_per_part - rows_in_part
                head, chunk = chunk[:room], chunk[room:]
                writer.write_table(pa.Table.from_pylist(head, schema=schema))
                rows_in_part += len(head)
                if rows_in_part >= rows_per_part:
                    close_part()
    close_part()
    if not entries:  # keep the file list non-empty so a table is never "missing"
        open_part()
        close_part()
    return entries


def read_rows(path: Path, batch_size: int = 5000) -> Iterator[list[dict[str, Any]]]:
    for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_size):
        yield batch.to_pylist()


def vector_dimension_ok(path: Path) -> bool:
    """True when every vector in the file has EMBEDDING_DIMENSION entries."""
    for batch in read_rows(path):
        for row in batch:
            for value in row.values():
                if isinstance(value, list) and value and len(value) != EMBEDDING_DIMENSION:
                    return False
    return True
```

Hinweis: Im Test `test_roundtrip_across_parts` sind die Vektoren dreidimensional; `vector_dimension_ok` wird deshalb nur vom Importer aufgerufen und separat getestet (kleiner Test in `test_export_import.py`: Datei mit 3-dimensionalem Vektor → Importer lehnt ab mit `match="dimension"`).

`exporter.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone
from pathlib import Path

from normly_core.exchange.manifest import (
    EMBEDDING_DIMENSION,
    EXCHANGE_SCHEMA_VERSION,
    DeliveryEntry,
    Manifest,
)
from normly_core.exchange.parquet_io import write_parts
from normly_core.exchange.signing import sign
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import KnowledgeExchangeRepository


def export_dump(
    repository: KnowledgeExchangeRepository,
    *,
    out_dir: Path,
    dump_version: str,
    private_key_pem: bytes,
    embedding_model_revision: str,
    rows_per_part: int = 100_000,
    now: datetime | None = None,
) -> Path:
    dump_dir = out_dir / dump_version
    dump_dir.mkdir(parents=True, exist_ok=False)  # versions are immutable

    tables = {}
    models: set[str] = set()
    for name in KNOWLEDGE_TABLES:
        columns = repository.exchange_columns(name)

        def batches(name=name):
            for batch in repository.iter_exportable_rows(name):
                if name in ("embedding", "document_embedding"):
                    models.update(row["model_name"] for row in batch)
                yield batch

        tables[name] = write_parts(
            dump_dir, name, columns, batches(), rows_per_part=rows_per_part
        )

    manifest = Manifest(
        exchange_schema_version=EXCHANGE_SCHEMA_VERSION,
        dump_version=dump_version,
        created_at=(now or datetime.now(timezone.utc)).isoformat(),
        embedding_models=sorted(models),
        embedding_model_revision=embedding_model_revision,
        embedding_dimension=EMBEDDING_DIMENSION,
        deliveries=[DeliveryEntry(*d) for d in repository.exportable_deliveries()],
        tables=tables,
    )
    data = manifest.to_bytes()
    (dump_dir / "manifest.json").write_bytes(data)
    (dump_dir / "manifest.json.sig").write_bytes(sign(private_key_pem, data))
    return dump_dir
```

`importer.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone
from pathlib import Path

from normly_core.exchange.manifest import (
    EMBEDDING_DIMENSION,
    EXCHANGE_SCHEMA_VERSION,
    Manifest,
    sha256_file,
)
from normly_core.exchange.parquet_io import read_rows, vector_dimension_ok
from normly_core.exchange.signing import SignatureError, verify
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import ImportRecord, KnowledgeExchangeRepository


class ImportRefused(Exception):
    """The dump cannot be imported; nothing was changed."""


def import_dump(
    repository: KnowledgeExchangeRepository,
    *,
    dump_dir: Path,
    public_key_pem: bytes,
    expected_model_name: str,
    expected_model_revision: str,
    now: datetime | None = None,
) -> ImportRecord:
    manifest_bytes = (dump_dir / "manifest.json").read_bytes()
    try:
        verify(public_key_pem, manifest_bytes, (dump_dir / "manifest.json.sig").read_bytes())
    except SignatureError as exc:
        raise ImportRefused(f"signature check failed: {exc}") from exc

    manifest = Manifest.from_bytes(manifest_bytes)
    if manifest.exchange_schema_version != EXCHANGE_SCHEMA_VERSION:
        raise ImportRefused(
            f"exchange schema version {manifest.exchange_schema_version} is not supported "
            f"(this build reads {EXCHANGE_SCHEMA_VERSION}); use a matching application version"
        )
    if manifest.embedding_dimension != EMBEDDING_DIMENSION:
        raise ImportRefused(f"embedding dimension {manifest.embedding_dimension} unsupported")
    if set(manifest.embedding_models) - {expected_model_name}:
        raise ImportRefused(
            f"dump embeddings use {manifest.embedding_models}, this instance runs "
            f"{expected_model_name}"
        )
    if manifest.embedding_model_revision != expected_model_revision:
        raise ImportRefused(
            f"embedding model revision {manifest.embedding_model_revision} in the dump "
            f"differs from {expected_model_revision} on this instance"
        )
    missing = [name for name in KNOWLEDGE_TABLES if name not in manifest.tables]
    if missing:
        raise ImportRefused(f"dump lacks tables: {missing}")

    for name in KNOWLEDGE_TABLES:
        for entry in manifest.tables[name]:
            path = dump_dir / entry.path
            if not path.is_file() or sha256_file(path) != entry.sha256:
                raise ImportRefused(f"checksum mismatch for {entry.path}")
            if name in ("embedding", "document_embedding") and not vector_dimension_ok(path):
                raise ImportRefused(f"vector dimension mismatch in {entry.path}")

    def batches(name: str):
        def produce():
            for entry in manifest.tables[name]:
                yield from read_rows(dump_dir / entry.path)
        return produce

    record = ImportRecord(
        dump_version=manifest.dump_version,
        exchange_schema_version=manifest.exchange_schema_version,
        embedding_model_revision=manifest.embedding_model_revision,
        imported_at=now or datetime.now(timezone.utc),
    )
    repository.replace_knowledge_base(
        {name: batches(name) for name in KNOWLEDGE_TABLES}, record=record
    )
    return record
```

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — erwartet PASS. Nach jedem rot gewordenen Test zuerst die tatsächliche Fehlermeldung lesen (Typ-Mismatch Arrow↔Python, Enum-Konvertierung) statt zu raten.

- [ ] **Step 5: Commit**

```bash
git add core/src core/tests
git commit -s -m "feat(exchange): Parquet export and verified, idempotent import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: CLI, Abruf per HTTPS, Image und Compose-Profil

**Files:**
- Create: `core/src/normly_core/exchange/fetch.py`, `core/src/normly_core/exchange/__main__.py`
- Create: `core/src/normly_core/exchange/keys/kb-signing.pub.pem` (Platzhalter bis Task 11; **kein** gültiger Schlüssel committen — die Datei wird in Task 11 mit dem echten öffentlichen Schlüssel angelegt; bis dahin verlangt der Import `--public-key`)
- Modify: `docker/python.Dockerfile` (pipeline-Stage), `compose.yaml`, `.env.example`, `docs/guide/self-hosting.md`
- Test: `core/tests/exchange/test_fetch.py`, `core/tests/exchange/test_cli.py`

**Interfaces:**
- Produces: `fetch_dump(base_url: str, version: str, destination: Path, *, opener=urllib.request.urlopen) -> Path` (löst `latest` über `<base>/latest` auf, lädt `manifest.json`, `manifest.json.sig` und alle Dateien aus dem Manifest nach `destination/<version>/`; verifiziert nichts — das macht `import_dump`).
- CLI (`python -m normly_core.exchange`):
  - `keygen --private PATH --public PATH` (verweigert Überschreiben; Dateimodus 0600 für privat)
  - `export --version V --out DIR --private-key PATH` (liest `NORMLY_DATABASE_URL`, `NORMLY_EMBEDDING_MODEL_REVISION`)
  - `import (--from DIR | --fetch VERSION|latest) [--public-key PATH]` (liest `NORMLY_DATABASE_URL`, `NORMLY_KB_BASE_URL`, `NORMLY_EMBEDDING_MODEL_REVISION`; Modellname aus `normly_core.pipeline.embeddings.MODEL_NAME`, lazy importiert)
  - `info` (druckt die importierte Dump-Version oder `none`)
  - `tables GROUP` (druckt Tabellennamen, eine je Zeile)

- [ ] **Step 1: Tests schreiben**

`test_fetch.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io
import json

from normly_core.exchange.fetch import fetch_dump

FILES = {
    "https://kb.example/latest": b"2026.10.1\n",
    "https://kb.example/2026.10.1/manifest.json": json.dumps({
        "exchange_schema_version": 1, "dump_version": "2026.10.1",
        "created_at": "x", "embedding_models": [], "embedding_model_revision": "r",
        "embedding_dimension": 1024, "deliveries": [],
        "tables": {"source": [{"path": "tables/source/part-0000.parquet", "sha256": "s", "rows": 0}]},
    }).encode(),
    "https://kb.example/2026.10.1/manifest.json.sig": b"S" * 64,
    "https://kb.example/2026.10.1/tables/source/part-0000.parquet": b"PAR1",
}


def _opener(url, timeout=None):
    return io.BytesIO(FILES[url])


def test_fetch_latest_downloads_manifest_and_all_listed_files(tmp_path):
    dump_dir = fetch_dump("https://kb.example", "latest", tmp_path, opener=_opener)

    assert dump_dir == tmp_path / "2026.10.1"
    assert (dump_dir / "manifest.json.sig").read_bytes() == b"S" * 64
    assert (dump_dir / "tables/source/part-0000.parquet").read_bytes() == b"PAR1"
```

`test_cli.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.exchange.__main__ import main
from normly_core.exchange.tables import KNOWLEDGE_TABLES


def test_tables_command_prints_group(capsys):
    assert main(["tables", "knowledge"]) == 0
    assert capsys.readouterr().out.split() == list(KNOWLEDGE_TABLES)


def test_keygen_writes_both_keys_and_refuses_overwrite(tmp_path, capsys):
    private, public = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == 0
    assert oct(private.stat().st_mode & 0o777) == "0o600"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == 1
    assert "exists" in capsys.readouterr().err


def test_import_without_database_url_fails(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    assert main(["info"]) == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err
```

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_fetch.py tests/exchange/test_cli.py -v` — erwartet FAIL.

- [ ] **Step 3: Implementierung**

`fetch.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import shutil
import urllib.request
from pathlib import Path

from normly_core.exchange.manifest import Manifest

_TIMEOUT_SECONDS = 60


def _get(url: str, opener) -> bytes:
    with opener(url, timeout=_TIMEOUT_SECONDS) as response:
        return response.read()


def _download(url: str, destination: Path, opener) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with opener(url, timeout=_TIMEOUT_SECONDS) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def fetch_dump(
    base_url: str, version: str, destination: Path, *, opener=urllib.request.urlopen
) -> Path:
    base = base_url.rstrip("/")
    if version == "latest":
        version = _get(f"{base}/latest", opener).decode("utf-8").strip()
    dump_dir = destination / version
    for name in ("manifest.json", "manifest.json.sig"):
        _download(f"{base}/{version}/{name}", dump_dir / name, opener)
    manifest = Manifest.from_bytes((dump_dir / "manifest.json").read_bytes())
    for entries in manifest.tables.values():
        for entry in entries:
            _download(f"{base}/{version}/{entry.path}", dump_dir / entry.path, opener)
    return dump_dir
```

`__main__.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
python -m normly_core.exchange {keygen|export|import|info|tables}

The knowledge-base dump tooling (ADR-025). Commits happen here, never in the
repository.
"""

import argparse
import os
import sys
import tempfile
from importlib import resources
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.fetch import fetch_dump
from normly_core.exchange.importer import ImportRefused, import_dump
from normly_core.exchange.signing import generate_keypair
from normly_core.exchange.tables import group_tables
from normly_core.graph.domain import ImportBlockedError
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository

_MODEL_REVISION_ENV = "NORMLY_EMBEDDING_MODEL_REVISION"


def _packaged_public_key() -> bytes:
    return (resources.files("normly_core.exchange") / "keys" / "kb-signing.pub.pem").read_bytes()


def _require_env(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        print(f"{name} environment variable is required", file=sys.stderr)
    return value


def _keygen(args) -> int:
    private, public = Path(args.private), Path(args.public)
    for path in (private, public):
        if path.exists():
            print(f"{path} exists; refusing to overwrite", file=sys.stderr)
            return 1
    private_pem, public_pem = generate_keypair()
    private.write_bytes(private_pem)
    private.chmod(0o600)
    public.write_bytes(public_pem)
    print(f"wrote {private} (keep offline) and {public} (commit to the repository)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.exchange")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen")
    keygen.add_argument("--private", required=True)
    keygen.add_argument("--public", required=True)

    export = sub.add_parser("export")
    export.add_argument("--version", required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--private-key", type=Path, required=True)

    imp = sub.add_parser("import")
    source = imp.add_mutually_exclusive_group(required=True)
    source.add_argument("--from", dest="from_dir", type=Path)
    source.add_argument("--fetch", metavar="VERSION")
    imp.add_argument("--public-key", type=Path)

    sub.add_parser("info")

    tables = sub.add_parser("tables")
    tables.add_argument("group", choices=["knowledge", "user", "pipeline", "all"])

    args = parser.parse_args(argv)

    if args.command == "keygen":
        return _keygen(args)
    if args.command == "tables":
        print("\n".join(group_tables(args.group)))
        return 0

    database_url = _require_env("NORMLY_DATABASE_URL")
    if not database_url:
        return 1
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            repository = PostgresKnowledgeExchangeRepository(session)
            if args.command == "info":
                record = repository.imported_version()
                print(record.dump_version if record else "none")
                return 0
            revision = _require_env(_MODEL_REVISION_ENV)
            if not revision:
                return 1
            if args.command == "export":
                dump_dir = export_dump(
                    repository, out_dir=args.out, dump_version=args.version,
                    private_key_pem=args.private_key.read_bytes(),
                    embedding_model_revision=revision,
                )
                print(f"exported {dump_dir}")
                return 0
            # import
            from normly_core.pipeline.embeddings import MODEL_NAME  # heavy import, import only here

            public_pem = (
                args.public_key.read_bytes() if args.public_key else _packaged_public_key()
            )
            with tempfile.TemporaryDirectory() as scratch:
                if args.fetch:
                    base_url = _require_env("NORMLY_KB_BASE_URL")
                    if not base_url:
                        return 1
                    dump_dir = fetch_dump(base_url, args.fetch, Path(scratch))
                else:
                    dump_dir = args.from_dir
                try:
                    record = import_dump(
                        repository, dump_dir=dump_dir, public_key_pem=public_pem,
                        expected_model_name=MODEL_NAME, expected_model_revision=revision,
                    )
                except (ImportRefused, ImportBlockedError) as exc:
                    session.rollback()
                    print(f"import refused: {exc}", file=sys.stderr)
                    return 1
            session.commit()
            print(f"imported knowledge base {record.dump_version}")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
```

Der Ordner `keys/` braucht eine `.gitkeep`; `pyproject.toml` (hatch) nimmt Nicht-Python-Dateien im Paket ohnehin mit, solange sie unter `src/normly_core` liegen.

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — erwartet PASS.

- [ ] **Step 5: Image, Compose, Env, Guide**

`docker/python.Dockerfile`, `pipeline`-Stage ersetzen durch:

```dockerfile
FROM base AS pipeline
# The revision is recorded in every dump manifest and checked on import:
# embeddings from another e5 revision live in a different vector space.
ARG E5_REVISION
ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
    NORMLY_CORE_DIR=/app/core \
    NORMLY_EMBEDDING_MODEL_REVISION=${E5_REVISION}
# Deploy assets travel inside this signed image: `normly-deploy` extracts them
# after `cosign verify`, so compose.yaml and the Caddyfile are as trustworthy
# as the images they start.
COPY --chown=normly:normly compose.yaml /app/deploy/compose.yaml
COPY --chown=normly:normly docker/caddy/Caddyfile /app/deploy/docker/caddy/Caddyfile
COPY --chown=normly:normly scripts/normly-deploy scripts/normly-backup scripts/normly-backup-retention.py /app/deploy/scripts/
USER normly
ENTRYPOINT ["python", "-m", "normly_core.pipeline"]
```

`ARG E5_REVISION` steht oben im Dockerfile vor der `weights`-Stage (Zeile ~75); weil `ARG`s stage-lokal sind, muss die Zeile `ARG E5_REVISION=3d7cfb…` wie dort definiert **in der `pipeline`-Stage ohne Default** wiederholt werden (Wert kommt dann aus dem globalen Default nur, wenn vor dem ersten `FROM` deklariert). Prüfen: `grep -n "ARG E5_REVISION" docker/python.Dockerfile`; liegt die Deklaration nicht vor dem ersten `FROM`, in der `pipeline`-Stage `ARG E5_REVISION=<derselbe Hash>` mit Kommentar „muss mit der weights-Stage übereinstimmen“ setzen **oder** (bevorzugt) die bestehende Deklaration oberhalb des ersten `FROM` verschieben, damit es genau eine Definition gibt. Danach `.dockerignore` auf Ausschluss von `scripts/` und `compose.yaml` prüfen und anpassen.

`compose.yaml`, neuen Dienst neben `pipeline` einfügen:

```yaml
  kb-import:
    build:
      <<: *python-build
      target: pipeline
    image: ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}
    profiles: ["tools"]
    entrypoint: ["python", "-m", "normly_core.exchange", "import", "--fetch"]
    command: ["latest"]
    env_file: .env
    depends_on:
      migrate:
        condition: service_completed_successfully
    restart: "no"
```

`.env.example`, im Abschnitt Database/Images ergänzen:

```
# --- Knowledge base -------------------------------------------------------
# Public location of the versioned knowledge-base dumps (ADR-025).
# `docker compose run --rm kb-import` imports the newest one.
# NORMLY_KB_BASE_URL=
```

`docs/guide/self-hosting.md` (Englisch): den Punkt „No versioned knowledge-base dump yet …“ unter „Known gaps“ streichen und vor „Ingesting documents“ einen Abschnitt „Importing the knowledge base“ einfügen: Befehl `docker compose run --rm kb-import` (`docker compose run --rm kb-import 2026.10.1` für eine feste Version), Hinweis auf `NORMLY_KB_BASE_URL`, Prüfungen (Signatur, Modell-Revision, Prüfsummen), dass der Import idempotent ist, und dass ein Import abbricht, wenn Nutzerdaten noch auf entfernte Zeilen verweisen.

- [ ] **Step 6: Verifikation (lokal, kein Push)**

Run: `docker compose config -q` (Expected: kein Fehler), `cd core && ../.venv/bin/pytest tests/exchange -q` (Expected: PASS). Ein lokaler Image-Build ist **nicht** Teil dieses Tasks (5 GB, Zeit); er läuft in Task 11 auf der VM.

- [ ] **Step 7: Commit**

```bash
git add core docker compose.yaml .env.example docs/guide/self-hosting.md
git commit -s -m "feat(exchange): CLI, HTTPS fetch, image revision env and kb-import service

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Teil B — Sicherung

### Task 6: `normly-backup`, Aufbewahrung und Timer

**Files:**
- Create: `scripts/normly-backup`, `scripts/normly-backup-retention.py`
- Create: `deploy/systemd/normly-backup.service`, `deploy/systemd/normly-backup.timer`
- Create: `scripts/tests/conftest.py`, `scripts/tests/test_retention.py`, `scripts/tests/test_backup.py`

**Interfaces:**
- Produces:
  - `scripts/normly-backup-retention.py`: liest Objektnamen (eine je Zeile, nur `*.dump.age`) von stdin und gibt die **zu löschenden Basisnamen** aus (`<ts>-<kind>`); Funktion `select_deletions(names: list[str]) -> list[str]`.
  - `scripts/normly-backup run [--kind daily|pre-<tag>]`: legt die Sicherung an und gibt als **letzte Zeile** den Basisnamen aus; `scripts/normly-backup prune`.
- Umgebung (aus `/opt/normly/.env`, geladen vom Skript): `NORMLY_DATABASE_URL`, `NORMLY_BACKUP_AGE_RECIPIENT`, `NORMLY_BACKUP_REMOTE` (rclone-Ziel, z. B. `stackit:normly-backups`), rclone-Zugangsdaten über `RCLONE_*`-Variablen (`.env` der VM). `NORMLY_COMPOSE` (Standard `docker compose -f /opt/normly/current/compose.yaml --project-directory /opt/normly/current`).

- [ ] **Step 1: Tests für die Aufbewahrung schreiben**

`scripts/tests/test_retention.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "retention", Path(__file__).parents[1] / "normly-backup-retention.py"
)
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


def daily(day, hour="033000"):
    return f"2026{day}T{hour}Z-daily.dump.age"


def test_keeps_seven_dailies_one_per_day():
    names = [daily(f"10{d:02d}") for d in range(1, 11)]  # 10 days in October
    deleted = retention.select_deletions(names)
    # days 4..10 are the seven newest; October's monthly anchor is day 10,
    # which is already kept
    assert sorted(deleted) == [
        "20261001T033000Z-daily", "20261002T033000Z-daily", "20261003T033000Z-daily",
    ]


def test_second_daily_on_same_day_is_dropped_first():
    names = [daily("1010", "033000"), daily("1010", "153000")]
    assert retention.select_deletions(names) == ["20261010T033000Z-daily"]


def test_keeps_newest_daily_of_two_most_recent_months():
    recent = [daily(f"10{d:02d}") for d in range(1, 11)]  # fills the 7 daily slots
    names = [daily("0815"), daily("0831"), daily("0930"), *recent]
    deleted = set(retention.select_deletions(names))
    # September's newest (0930) stays as the second monthly anchor; August goes,
    # as do the three oldest October dailies outside the 7 daily slots
    assert deleted == {
        "20260815T033000Z-daily", "20260831T033000Z-daily",
        "20261001T033000Z-daily", "20261002T033000Z-daily", "20261003T033000Z-daily",
    }


def test_keeps_three_newest_pre_rollout_dumps():
    names = [f"2026100{d}T100000Z-pre-0.1.{d}.dump.age" for d in range(1, 6)]
    deleted = set(retention.select_deletions(names))
    assert deleted == {"20261001T100000Z-pre-0.1.1", "20261002T100000Z-pre-0.1.2"}


def test_ignores_unrelated_names():
    assert retention.select_deletions(["notes.txt", "x.dump.age"]) == []
```


- [ ] **Step 2:** `cd scripts && python3 -m pytest tests/test_retention.py -v` — erwartet FAIL (Datei fehlt).

- [ ] **Step 3: `scripts/normly-backup-retention.py`**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Decide which backups to delete. Reads object names (one per line) from stdin,
prints the base names (<timestamp>-<kind>) to delete. Standard library only:
it runs on the VM next to the shell script.

Keep: 7 daily (newest per calendar day), the newest daily of each of the 2 most
recent calendar months, and the 3 newest pre-rollout dumps.
"""

import re
import sys

DAILY_KEEP = 7
MONTHLY_KEEP = 2
PRE_KEEP = 3

_NAME = re.compile(r"^(\d{8})T(\d{6})Z-(daily|pre-[0-9A-Za-z.\-]+)\.dump\.age$")


def select_deletions(names: list[str]) -> list[str]:
    daily, pre = [], []
    for name in names:
        match = _NAME.match(name)
        if not match:
            continue
        date, time, kind = match.groups()
        base = f"{date}T{time}Z-{kind}"
        (daily if kind == "daily" else pre).append((date + time, date, base))

    keep: set[str] = set()

    newest_first = sorted(daily, reverse=True)
    days_seen: list[str] = []
    for _stamp, date, base in newest_first:
        if date in days_seen:
            continue
        days_seen.append(date)
        if len(days_seen) <= DAILY_KEEP:
            keep.add(base)

    months_seen: list[str] = []
    for _stamp, date, base in newest_first:
        month = date[:6]
        if month in months_seen:
            continue
        months_seen.append(month)
        if len(months_seen) <= MONTHLY_KEEP:
            keep.add(base)

    for _stamp, _date, base in sorted(pre, reverse=True)[:PRE_KEEP]:
        keep.add(base)

    return sorted(base for _s, _d, base in daily + pre if base not in keep)


if __name__ == "__main__":
    for base in select_deletions([line.strip() for line in sys.stdin if line.strip()]):
        print(base)
```

`chmod +x scripts/normly-backup-retention.py`.

- [ ] **Step 4:** `cd scripts && python3 -m pytest tests/test_retention.py -v` — erwartet PASS.

- [ ] **Step 5: Test-Harness mit Fake-Binaries**

`scripts/tests/conftest.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Harness: run the real shell scripts with fake binaries first on PATH. Each fake
appends its argv to $CALLS and may be scripted through env vars, so tests can
assert order and arguments of every external command.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]

FAKE = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$CALLS"
override="FAKE_$(basename "$0" | tr 'a-z-' 'A-Z_')_EXIT"
if [ "${!override:-0}" != "0" ]; then exit "${!override}"; fi
out="FAKE_$(basename "$0" | tr 'a-z-' 'A-Z_')_OUT"
if [ -n "${!out:-}" ]; then printf '%s\\n' "${!out}"; fi
if [ -n "${FAKE_DOCKER_EXIT_ON:-}" ] && [ "$(basename "$0")" = docker ]; then
  case " $* " in *" $FAKE_DOCKER_EXIT_ON "*) exit 1 ;; esac
fi
# fake tools that write a file named after -o / --file
case "$(basename "$0")" in
  pg_dump) for a in "$@"; do case "$a" in --file=*) : > "${a#--file=}";; esac; done ;;
  age) prev=""; for a in "$@"; do [ "$prev" = "-o" ] && echo cipher > "$a"; prev="$a"; done ;;
esac
exit 0
"""


@pytest.fixture()
def harness(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("docker", "cosign", "rclone", "age", "pg_dump", "pg_restore", "psql", "sha256sum"):
        path = bin_dir / name
        path.write_text(FAKE)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    calls = tmp_path / "calls.log"
    calls.write_text("")
    fake_backup = bin_dir / "fake-normly-backup"
    fake_backup.write_text("#!/usr/bin/env bash\necho 20261009T100000Z-pre-0.1.2\n")
    fake_backup.chmod(fake_backup.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CALLS": str(calls),
        "NORMLY_DIR": str(tmp_path / "normly"),
        "NORMLY_DATABASE_URL": "postgresql+psycopg://u:p@db:5432/normly",
        "NORMLY_BACKUP_AGE_RECIPIENT": "age1recipient",
        "NORMLY_BACKUP_REMOTE": "stackit:bucket",
        "NORMLY_COMPOSE": "docker compose",
        "NORMLY_BACKUP_BIN": str(fake_backup),
    }
    (tmp_path / "normly").mkdir()

    class Harness:
        def run(self, script, *args, extra_env=None, input_text=None):
            return subprocess.run(
                [str(SCRIPTS / script), *args], env={**env, **(extra_env or {})},
                capture_output=True, text=True, input=input_text,
            )

        def calls(self):
            return calls.read_text().splitlines()

        dir = tmp_path / "normly"

    return Harness()
```

- [ ] **Step 6: Tests für `normly-backup`**

`scripts/tests/test_backup.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

def test_run_dumps_only_user_tables_encrypts_and_uploads(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account\nwatchlist"},
    )

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    dump = next(c for c in calls if c.startswith("pg_dump"))
    assert "--data-only" in dump and "--format=custom" in dump
    assert "--table=public.account" in dump and "--table=public.watchlist" in dump
    assert "postgresql://u:p@db:5432/normly" in dump  # +psycopg driver suffix removed
    assert any(c.startswith("age ") and "-r age1recipient" in c for c in calls)
    assert any(c.startswith("rclone copyto") and "stackit:bucket/backups/" in c for c in calls)
    name = result.stdout.strip().splitlines()[-1]
    assert name.endswith("-daily")


def test_run_fails_and_prints_nothing_when_upload_fails(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_EXIT": "1"},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_run_never_leaves_plaintext_dump_behind(harness, tmp_path):
    harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "TMPDIR": str(tmp_path)},
    )
    assert not list(tmp_path.glob("normly-backup.*"))


def test_run_rejects_unknown_kind(harness):
    result = harness.run("normly-backup", "run", "--kind", "weekly")
    assert result.returncode == 2
```

- [ ] **Step 7:** `cd scripts && python3 -m pytest tests -v` — erwartet FAIL für `test_backup.py` (Skript fehlt).

- [ ] **Step 8: `scripts/normly-backup`**

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Encrypted backup of the user-data tables (TP4 spec, Teil 2).
#
#   normly-backup run [--kind daily|pre-<tag>]   dump, encrypt, upload; the
#                                                last stdout line is the base name
#   normly-backup prune                          apply the retention policy
#
# The VM only knows the age PUBLIC key (NORMLY_BACKUP_AGE_RECIPIENT): it can
# write backups but not read them. The private key lives in the Secrets Manager
# and offline with the operator. Only the user-data group is dumped; the
# knowledge base is reproducible from its dump version (ADR-025).
set -euo pipefail

NORMLY_DIR="${NORMLY_DIR:-/opt/normly}"
if [ -f "$NORMLY_DIR/.env" ]; then
  set -a; . "$NORMLY_DIR/.env"; set +a
fi
: "${NORMLY_DATABASE_URL:?}" "${NORMLY_BACKUP_AGE_RECIPIENT:?}" "${NORMLY_BACKUP_REMOTE:?}"
COMPOSE="${NORMLY_COMPOSE:-docker compose -f $NORMLY_DIR/current/compose.yaml --project-directory $NORMLY_DIR/current}"
DATABASE_URL="${NORMLY_DATABASE_URL/+psycopg/}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

user_tables() {
  $COMPOSE run --rm --no-deps -T --entrypoint python pipeline \
    -m normly_core.exchange tables user
}

run_backup() {
  local kind="$1"
  case "$kind" in
    daily|pre-*) ;;
    *) echo "unknown --kind: $kind" >&2; exit 2 ;;
  esac

  local stamp base work
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  base="${stamp}-${kind}"
  work="$(mktemp -d -t normly-backup.XXXXXX)"
  chmod 700 "$work"
  trap 'rm -rf "$work"' EXIT

  local table_args=()
  while IFS= read -r table; do
    [ -n "$table" ] && table_args+=("--table=public.$table")
  done < <(user_tables)
  [ "${#table_args[@]}" -gt 0 ] || { echo "no user tables resolved" >&2; exit 1; }

  pg_dump --dbname="$DATABASE_URL" --format=custom --data-only \
    --file="$work/$base.dump" "${table_args[@]}"
  age -r "$NORMLY_BACKUP_AGE_RECIPIENT" -o "$work/$base.dump.age" "$work/$base.dump"
  rm -f "$work/$base.dump"   # no plaintext beyond this point

  local revision image_tag kb_version
  revision="$(psql "$DATABASE_URL" -Atc 'SELECT version_num FROM alembic_version' || true)"
  image_tag="$(cat "$NORMLY_DIR/state/current_tag" 2>/dev/null || echo unknown)"
  kb_version="$($COMPOSE run --rm --no-deps -T --entrypoint python pipeline \
    -m normly_core.exchange info 2>/dev/null || echo none)"
  printf '{"alembic_revision":"%s","image_tag":"%s","kb_version":"%s"}\n' \
    "$revision" "$image_tag" "$kb_version" > "$work/$base.meta.json"
  (cd "$work" && sha256sum "$base.dump.age" > "$base.sha256")

  for suffix in dump.age meta.json sha256; do
    rclone copyto "$work/$base.$suffix" "$NORMLY_BACKUP_REMOTE/backups/$base.$suffix"
  done
  echo "$base"
}

prune() {
  local names
  names="$(rclone lsf "$NORMLY_BACKUP_REMOTE/backups" | grep '\.dump\.age$' || true)"
  printf '%s\n' "$names" | python3 "$HERE/normly-backup-retention.py" | while IFS= read -r base; do
    for suffix in dump.age meta.json sha256; do
      rclone deletefile "$NORMLY_BACKUP_REMOTE/backups/$base.$suffix" || true
    done
    echo "pruned $base" >&2
  done
}

case "${1:-}" in
  run)
    shift
    kind=daily
    while [ $# -gt 0 ]; do
      case "$1" in
        --kind) kind="${2:?}"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
      esac
    done
    run_backup "$kind"
    ;;
  prune) prune ;;
  *) echo "usage: normly-backup {run [--kind daily|pre-<tag>]|prune}" >&2; exit 2 ;;
esac
```

`chmod +x scripts/normly-backup`. Hinweis: Die Fake-`docker` liefert über `FAKE_DOCKER_OUT` die Tabellenliste; im Test `test_run_rejects_unknown_kind` greift die Prüfung vor jedem externen Aufruf. Die Funktion `run_backup` ruft `exit 2` aus einer Funktion — das beendet das Skript, wie gewünscht.

- [ ] **Step 9:** `cd scripts && python3 -m pytest tests -v` und `shellcheck scripts/normly-backup` — erwartet PASS bzw. keine Befunde (Befunde beheben, nicht unterdrücken, außer mit begründetem `# shellcheck disable=`).

- [ ] **Step 10: systemd-Units**

`deploy/systemd/normly-backup.service`:

```ini
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
[Unit]
Description=normly daily user-data backup
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/normly/bin/normly-backup run --kind daily
ExecStartPost=/opt/normly/bin/normly-backup prune
```

`deploy/systemd/normly-backup.timer`:

```ini
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
[Unit]
Description=normly daily user-data backup

[Timer]
OnCalendar=*-*-* 03:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 11: Commit**

```bash
git add scripts deploy
git commit -s -m "feat(backup): encrypted user-data backup with retention and daily timer

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Teil C — Rollout und Rollback

### Task 7: `normly-deploy`

**Files:**
- Create: `scripts/normly-deploy`
- Test: `scripts/tests/test_deploy.py`

**Interfaces:**
- Consumes: `normly-backup run --kind pre-<tag>` (letzte Stdout-Zeile = Basisname), Harness aus Task 6.
- Produces: `normly-deploy deploy <tag>`, `normly-deploy rollback --age-identity FILE [--yes]`, `normly-deploy status`.
- Zustandsdateien unter `$NORMLY_DIR/state/`: `current_tag`, `previous_tag`, `pre_rollout_backup`, `pre_rollout_kb_version`, `deploy.lock` (Verzeichnis-Lock via `mkdir`). Release-Dateien unter `$NORMLY_DIR/releases/<tag>/` (Compose, Caddyfile, Skripte); `$NORMLY_DIR/current` ist ein Symlink auf das aktive Release; `.env` in jedem Release-Ordner ist ein Symlink auf `$NORMLY_DIR/.env`.

**Verhalten (Spec Teil 1):** Tag ohne `v` normalisieren; nur `X.Y.Z` akzeptieren. Reihenfolge von `deploy`: Lock → `cosign verify` aller fünf Images (Identität `^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/tags/v<tag>$`, Issuer `https://token.actions.githubusercontent.com`) → Assets aus dem `pipeline`-Image nach `releases/<tag>/` extrahieren → Pre-Rollout-Sicherung (Abbruch ohne bestätigten Upload) → `pull` → `up -d --wait` → Zustand schreiben. Bei Fehlschlag: klare Meldung, **kein** automatischer Rückweg, `current_tag` unverändert.

- [ ] **Step 1: Tests schreiben**

`scripts/tests/test_deploy.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest


def _index(calls, prefix):
    return next(i for i, c in enumerate(calls) if c.startswith(prefix))


def test_deploy_runs_in_the_specified_order(harness):
    result = harness.run("normly-deploy", "deploy", "v0.1.2")

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    verify = _index(calls, "cosign verify")
    pull = next(i for i, c in enumerate(calls) if c.startswith("docker") and " pull" in c)
    assert verify < pull
    assert sum(c.startswith("cosign verify") for c in calls) == 5
    assert (harness.dir / "state" / "current_tag").read_text().strip() == "0.1.2"


def test_deploy_aborts_before_any_change_when_signature_fails(harness):
    result = harness.run("normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_COSIGN_EXIT": "1"})

    assert result.returncode != 0
    assert not any("pull" in c or "up -d" in c for c in harness.calls())
    assert not (harness.dir / "state" / "current_tag").exists()


def test_deploy_rejects_non_release_tags(harness):
    for tag in ("edge", "latest", "0.1", "main"):
        assert harness.run("normly-deploy", "deploy", tag).returncode == 2
    assert harness.calls() == []


def test_deploy_aborts_when_pre_rollout_backup_fails(harness):
    (harness.dir / "state").mkdir()
    (harness.dir / "state" / "current_tag").write_text("0.1.1\n")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"NORMLY_BACKUP_BIN": "/bin/false"},
    )
    assert result.returncode != 0
    assert not any("pull" in c for c in harness.calls())
    assert (harness.dir / "state" / "current_tag").read_text().strip() == "0.1.1"


def test_deploy_moves_current_to_previous(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")

    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0

    assert (state / "previous_tag").read_text().strip() == "0.1.1"
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_failed_health_wait_keeps_current_tag_and_says_how_to_roll_back(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"FAKE_DOCKER_EXIT_ON": "up"},
    )
    assert result.returncode != 0
    assert "rollback" in result.stderr
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_second_run_is_refused_while_locked(harness):
    (harness.dir / "state" / "deploy.lock").mkdir(parents=True)
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode == 3
    assert "already running" in result.stderr


def test_rollback_requires_confirmation(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")

    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), input_text="no\n"
    )

    assert result.returncode == 1
    assert not any(c.startswith("pg_restore") for c in harness.calls())


def test_rollback_rebuilds_schema_then_imports_kb_then_restores_users(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")

    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes",
        extra_env={"FAKE_DOCKER_OUT": "account"},
    )

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    drop = _index(calls, "psql")
    migrate = next(i for i, c in enumerate(calls) if "migrate" in c)
    kb_import = next(
        i for i, c in enumerate(calls) if "normly_core.exchange" in c and " import" in c
    )
    restore = _index(calls, "pg_restore")
    assert drop < migrate < kb_import < restore
    assert "--data-only" in calls[restore]
    assert (state / "current_tag").read_text().strip() == "0.1.1"
```

Der Harness aus Task 6 unterstützt dafür `FAKE_DOCKER_EXIT_ON=<wort>` (der Fake-`docker` endet mit 1, wenn das Wort in den Argumenten vorkommt) und setzt `NORMLY_BACKUP_BIN` standardmäßig auf ein Hilfsskript, das `20261009T100000Z-pre-0.1.2` ausgibt; `test_deploy_aborts_when_pre_rollout_backup_fails` überschreibt die Variable mit `/bin/false`.

- [ ] **Step 2:** `cd scripts && python3 -m pytest tests/test_deploy.py -v` — erwartet FAIL.

- [ ] **Step 3: `scripts/normly-deploy`**

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Pull-based rollout and rollback on the VM (TP4 spec, Teil 1; ADR-024).
#
#   normly-deploy deploy <vX.Y.Z>
#   normly-deploy rollback --age-identity FILE [--yes]
#   normly-deploy status
#
# No STACKIT credentials live on GitHub: the VM pulls signed images, verifies
# them with cosign, and starts them. A manual call (over SSH) is the trigger;
# the interface is timer-ready but no timer exists.
set -euo pipefail

NORMLY_DIR="${NORMLY_DIR:-/opt/normly}"
STATE="$NORMLY_DIR/state"
RELEASES="$NORMLY_DIR/releases"
REGISTRY="${NORMLY_REGISTRY:-ghcr.io/normly/web-app}"
IMAGES=(api chat accounts pipeline frontend)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_BIN="${NORMLY_BACKUP_BIN:-$HERE/normly-backup}"
OIDC_ISSUER="https://token.actions.githubusercontent.com"
HEALTH_TIMEOUT="${NORMLY_HEALTH_TIMEOUT:-600}"

die() { echo "normly-deploy: $*" >&2; exit "${2:-1}"; }

normalise_tag() {
  local tag="${1#v}"
  [[ "$tag" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "not a release tag: $1 (expected vX.Y.Z)" 2
  echo "$tag"
}

read_state() { cat "$STATE/$1" 2>/dev/null || true; }

compose() {  # compose <tag> <args...>
  local tag="$1"; shift
  NORMLY_IMAGE_TAG="$tag" docker compose \
    -f "$RELEASES/$tag/compose.yaml" --project-directory "$RELEASES/$tag" "$@"
}

take_lock() {
  mkdir -p "$STATE"
  mkdir "$STATE/deploy.lock" 2>/dev/null || die "another run is already running (remove $STATE/deploy.lock if stale)" 3
  trap 'rmdir "$STATE/deploy.lock" 2>/dev/null || true' EXIT
}

verify_images() {
  local tag="$1" image
  for image in "${IMAGES[@]}"; do
    cosign verify \
      --certificate-identity-regexp "^https://github\\.com/normly/web-app/\\.github/workflows/images\\.yml@refs/tags/v${tag//./\\.}\$" \
      --certificate-oidc-issuer "$OIDC_ISSUER" \
      "$REGISTRY/$image:$tag" > /dev/null \
      || die "signature verification failed for $image:$tag; nothing was changed"
  done
}

extract_assets() {
  local tag="$1" target="$RELEASES/$tag" container
  mkdir -p "$target"
  container="$(docker create "$REGISTRY/pipeline:$tag")"
  docker cp "$container:/app/deploy/." "$target/"
  docker rm "$container" > /dev/null
  ln -sfn "$NORMLY_DIR/.env" "$target/.env"
}

deploy() {
  local tag; tag="$(normalise_tag "${1:?usage: normly-deploy deploy <vX.Y.Z>}")"
  take_lock

  verify_images "$tag"
  extract_assets "$tag"

  local current kb_version backup_base
  current="$(read_state current_tag)"
  if [ -n "$current" ]; then
    kb_version="$(compose "$current" run --rm --no-deps -T --entrypoint python pipeline \
      -m normly_core.exchange info 2>/dev/null || echo none)"
    backup_base="$("$BACKUP_BIN" run --kind "pre-$tag" | tail -n 1)" \
      || die "pre-rollout backup failed; nothing was changed"
    [ -n "$backup_base" ] || die "pre-rollout backup returned no name; nothing was changed"
    printf '%s\n' "$backup_base" > "$STATE/pre_rollout_backup.new"
    printf '%s\n' "$kb_version" > "$STATE/pre_rollout_kb_version.new"
  fi

  compose "$tag" pull || die "pull failed for $tag; nothing was changed"
  if ! compose "$tag" up -d --wait --wait-timeout "$HEALTH_TIMEOUT"; then
    [ -n "$current" ] && { mv "$STATE/pre_rollout_backup.new" "$STATE/pre_rollout_backup"
                           mv "$STATE/pre_rollout_kb_version.new" "$STATE/pre_rollout_kb_version"; }
    die "rollout of $tag did not become healthy. Inspect: docker compose logs. To go back: normly-deploy rollback --age-identity <file> (current_tag is still $current)"
  fi

  if [ -n "$current" ]; then
    mv "$STATE/pre_rollout_backup.new" "$STATE/pre_rollout_backup"
    mv "$STATE/pre_rollout_kb_version.new" "$STATE/pre_rollout_kb_version"
    printf '%s\n' "$current" > "$STATE/previous_tag"
  fi
  printf '%s\n' "$tag" > "$STATE/current_tag"
  ln -sfn "$RELEASES/$tag" "$NORMLY_DIR/current"
  echo "deployed $tag"
}

rollback() {
  local identity="" assume_yes=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --age-identity) identity="${2:?}"; shift 2 ;;
      --yes) assume_yes=1; shift ;;
      *) die "unknown argument: $1" 2 ;;
    esac
  done
  [ -f "$identity" ] || die "--age-identity FILE is required (the private backup key, supplied only for this run)" 2

  local current previous backup kb_version
  current="$(read_state current_tag)"; previous="$(read_state previous_tag)"
  backup="$(read_state pre_rollout_backup)"; kb_version="$(read_state pre_rollout_kb_version)"
  [ -n "$previous" ] && [ -n "$backup" ] || die "no previous release recorded; nothing to roll back to"
  [ -d "$RELEASES/$previous" ] || die "release files for $previous are missing in $RELEASES"
  take_lock

  cat >&2 <<EOF
Rollback $current -> $previous
  Database state after backup '$backup' is DISCARDED (accounts, chats, watchlists
  created or changed since the rollout are lost).
  Steps: stop services, drop all tables, migrate with $previous, import the
  knowledge base ($kb_version), restore user data.
EOF
  if [ "$assume_yes" -ne 1 ]; then
    printf 'Type the target tag (%s) to continue: ' "$previous" >&2
    read -r answer
    [ "$answer" = "$previous" ] || die "aborted"
  fi

  local work database_url drop_sql
  work="$(mktemp -d -t normly-rollback.XXXXXX)"; chmod 700 "$work"
  trap 'rm -rf "$work"; rmdir "$STATE/deploy.lock" 2>/dev/null || true' EXIT
  if [ -f "$NORMLY_DIR/.env" ]; then set -a; . "$NORMLY_DIR/.env"; set +a; fi
  database_url="${NORMLY_DATABASE_URL:?}"; database_url="${database_url/+psycopg/}"

  rclone copyto "${NORMLY_BACKUP_REMOTE:?}/backups/$backup.dump.age" "$work/dump.age"
  age -d -i "$identity" -o "$work/dump" "$work/dump.age"

  compose "$current" down
  drop_sql="$(compose "$previous" run --rm --no-deps -T --entrypoint python pipeline \
    -m normly_core.exchange tables all | sed 's/.*/DROP TABLE IF EXISTS "&" CASCADE;/')"
  psql "$database_url" -v ON_ERROR_STOP=1 -c "$drop_sql"
  compose "$previous" run --rm migrate
  if [ "$kb_version" != "none" ] && [ -n "$kb_version" ]; then
    compose "$previous" run --rm --no-deps --entrypoint python pipeline \
      -m normly_core.exchange import --fetch "$kb_version"
  fi
  pg_restore --dbname="$database_url" --data-only --exit-on-error "$work/dump"
  compose "$previous" up -d --wait --wait-timeout "$HEALTH_TIMEOUT"

  printf '%s\n' "$previous" > "$STATE/current_tag"
  : > "$STATE/previous_tag"
  ln -sfn "$RELEASES/$previous" "$NORMLY_DIR/current"
  echo "rolled back to $previous"
}

status() {
  echo "current:  $(read_state current_tag)"
  echo "previous: $(read_state previous_tag)"
  echo "last pre-rollout backup: $(read_state pre_rollout_backup)"
}

case "${1:-}" in
  deploy) shift; deploy "$@" ;;
  rollback) shift; rollback "$@" ;;
  status) status ;;
  *) echo "usage: normly-deploy {deploy <vX.Y.Z>|rollback --age-identity FILE [--yes]|status}" >&2; exit 2 ;;
esac
```

`chmod +x scripts/normly-deploy`. Offene Stolperstellen, die beim Grünmachen der Tests auffallen und dort zu lösen sind: (a) Die erste Bereitstellung hat keinen `current_tag` und damit keine Pre-Rollout-Sicherung (gewollt: es gibt noch keine Nutzerdaten, die zu sichern wären); (b) im Test stirbt `read_state` bei fehlenden Dateien nicht, weil es `|| true` nutzt; (c) `drop_sql` ist eine Zeile je Tabelle und wird mit `psql -c` als ein Befehlsstring gesendet — mehrere Anweisungen in einem `-c` laufen in einer Transaktion, das ist gewollt.

- [ ] **Step 4:** `cd scripts && python3 -m pytest tests -v` und `shellcheck scripts/normly-deploy` — erwartet PASS.

- [ ] **Step 5: CI-Job ergänzen**

In `.github/workflows/ci.yml` einen Job `test-scripts` anfügen, nach dem Muster der vorhandenen Jobs (Runner und Checkout-Version von `test-docs` übernehmen, nicht neu erfinden):

```yaml
  test-scripts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends shellcheck
      - run: shellcheck scripts/normly-backup scripts/normly-deploy
      - run: pip install pytest && python -m pytest scripts/tests -q
```

Vor dem Einfügen `sed -n 60,80p .github/workflows/ci.yml` lesen und `runs-on`/`container`/Action-Versionen an die dort verwendeten angleichen.

- [ ] **Step 6: Commit**

```bash
git add scripts .github/workflows/ci.yml
git commit -s -m "feat(deploy): pull-based rollout and rollback with cosign verification

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Dokumentation

### Task 8: ADR-024, ADR-025, ADR-021-Nachtrag, CLAUDE.md, SRS, Betriebsguide

**Files:**
- Modify: `docs/adr/README.md` (ADR-024, ADR-025 anfügen; ADR-021-Nachtrag bei Zeile ~700; Register „Offene Punkte“ prüfen)
- Modify: `CLAUDE.md` (Ausnahmeregel zu ADR-021: Satz zu STACKIT Git und Wissensbasis)
- Modify: `docs/srs/03-anforderungen.md` (REQ-GIT-005 Satz zu STACKIT Git; Verweise bei REQ-INST-002, REQ-INST-004, REQ-DIST-004)
- Create: `docs/guide/operations.md` (Englisch)
- Modify: `docs/guide/releasing.md` (Verweis auf `normly-deploy deploy vX.Y.Z` als nächster Schritt nach einem Release)

- [ ] **Step 1: ADR-024 anfügen** (Format der Nachbar-ADRs übernehmen: Überschrift `## ADR-024 — …`, Status, Datum, Kontext, Entscheidung, Begründung, Verworfen, Folgen). Inhalt:

  - **Titel:** „Rollout, Rollback und Sicherung auf der Einzel-VM“; Status: angenommen 2026-10-09 (Nachtrag-Hinweis: baut auf ADR-010, ADR-014, ADR-023).
  - **Kontext:** Die VM baut heute aus dem Quellcode; es gibt keinen Rollback; Nutzerdaten sind nur durch die Flex-Sicherung (30 Tage, Anbieter-intern) gesichert; STACKIT-Zugangsdaten dürfen nicht auf GitHub liegen (ADR-021).
  - **Entscheidungen:** (1) Manueller Auslöser per SSH (`normly-deploy deploy vX.Y.Z`), Skript timerfähig; (2) vor dem Start `cosign verify` aller fünf Images gegen die Release-Workflow-Identität des Tags, Compose-Datei und Skripte reisen im signierten `pipeline`-Image; (3) Rollback stellt Images **und** Daten auf den Stand vor dem Rollout zurück — Schema wird neu aufgebaut (Tabellen verwerfen, `migrate` des vorherigen Images, Wissensbestand-Import, Nutzerdaten-Restore); (4) Sicherung nur der Nutzerdaten-Gruppe, `age`-verschlüsselt auf der VM mit dem öffentlichen Schlüssel, privater Schlüssel nie auf der VM, Upload per `rclone` in einen privaten Object-Storage-Bucket; (5) Aufbewahrung 7 täglich / 2 monatlich / 3 Pre-Rollout, zusätzlich die 30-Tage-Flex-Sicherung der Gesamtdatenbank; (6) manueller Restore-Test.
  - **Begründung:** je Entscheidung aus Spec Abschnitte „Entscheidungen“ und „Teil 1/2“ (Kern: ein Mensch entscheidet über Migrationsfenster; Migrationen sind nur vorwärts, daher Rollback = Neuaufbau; Wissensbestand reproduzierbar, daher kein täglicher Gesamtdump bei zweistelligen GB; Schlüsseltrennung schützt auch bei kompromittierter VM).
  - **Verworfen:** Timer-Auto-Rollout; reiner Image-Rollback mit Expand/Contract-Disziplin; nur serverseitige Verschlüsselung; täglicher Gesamtdump; nur Pre-Rollout-Dumps.
  - **Folgen/Offen:** Datenverlust seit dem Rollout beim Rollback (Warnung + Bestätigung); Rollback-Dauer wächst mit dem Wissensbestand; Kryptographisches Löschen bei lizenzierten Beständen (ADR-014) ist für die kommerzielle Schicht offen; Secrets-Fluss per AppRole (TP3) bleibt außerhalb.

- [ ] **Step 2: ADR-025 anfügen:** Titel „Wissensbestand-Dump als Austauschformat“; Entscheidungen: Parquet je Tabelle plus signiertes Manifest, Import/Export über die Repository-Schicht (`KnowledgeExchangeRepository`), Austauschschema-Version unabhängig von Alembic, Ed25519-Signatur im Kern (Begründung: kein zusätzliches Binary im Image), Verteilung über öffentlich lesbaren STACKIT-Object-Storage-Bucket mit Kalenderversion `kb/<version>/` und `kb/latest`, Import atomar und idempotent, Abbruch bei blockierenden Nutzerdaten-Verweisen, Modellname und -revision werden geprüft; Export-Gate = Rechteklassifikation (einziges Tor) mit Kategorien A/B/D. Begründung D4 aus der Spec übernehmen (ADR-006, öffentliches Produkt, Abstammung, Preis). Verworfen: `pg_dump` des Wissensbestands, Delta-Dumps (später möglich), STACKIT-Git als Ablage, zusätzliches Git-Manifest.

- [ ] **Step 3: ADR-021-Nachtrag:** Unter dem bestehenden Nachtragsmuster (siehe ADR-020) einen datierten Absatz „Nachtrag 2026-10-09“ ergänzen: Die Aussage, STACKIT Git sei für das künftige Hosting der Normen-Wissensbasis vorgesehen, ist durch ADR-025 überholt; die Wissensbasis wird als signierter Dump im STACKIT Object Storage verteilt. Das Repository `normly-webapp` bleibt ohne Aufgabe; ob es archiviert oder gelöscht wird, ist offen. Gleichen Satz in `CLAUDE.md` (Ausnahme-Absatz) und REQ-GIT-005 anpassen: „…ist für die Wissensbasis nicht mehr vorgesehen (ADR-025); die Wissensbasis liegt als Dump im STACKIT Object Storage.“

- [ ] **Step 4: SRS-Verweise:** Je ein Satz „Umsetzung: ADR-024 (`normly-deploy`)“ bei REQ-INST-002 und REQ-INST-004, „Umsetzung: ADR-025“ bei REQ-DIST-004. Anker im `docs/srs/README.md` prüfen (der `test-docs`-Job hat eine Baseline „3 issues found“; Anzahl darf nicht steigen).

- [ ] **Step 5: `docs/guide/operations.md` (Englisch)** mit den Abschnitten: Prerequisites on the VM (`docker`, `cosign`, `age`, `rclone`, `postgresql-client`, `python3`; Installationsbefehle für Ubuntu), Directory layout (`/opt/normly/{.env,bin,releases,state,current}`), Installing the scripts (aus dem verifizierten Image: `docker run --rm --entrypoint cat ghcr.io/normly/web-app/pipeline:<tag> /app/deploy/scripts/normly-deploy > /opt/normly/bin/normly-deploy` nach `cosign verify`), Deploying a release, Rolling back (inkl. Datenverlust-Warnung, Schlüsselbereitstellung), Backups (Timer aktivieren, `.env`-Variablen, Schlüsselverwaltung, Aufbewahrung), Restore test (manuelle Schritte: Backup herunterladen, `age -d`, in eine Wegwerf-Datenbank `migrate` + `pg_restore --data-only`, `SELECT count(*)` je Tabelle), Knowledge-base dumps (Export, Signieren, Hochladen mit `rclone`, `kb/latest` setzen). Alle Befehle müssen mit den implementierten Skripten übereinstimmen.

- [ ] **Step 6: Verifikation und Commit**

Run: die Docs-Prüfung wie in CI (`docker run python:3.12` mit zensical, siehe Memory-Hinweis zum `test-docs`-Job), Expected: weiterhin „3 issues found“.

```bash
git add docs CLAUDE.md
git commit -s -m "docs: ADR-024/025, ADR-021 addendum, operations guide

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Live-Verifikation (mit dem Nutzer)

### Task 9: Einrichtung und Abnahme auf STACKIT

Nach Merge der Teile A–C und Release eines Tags (`v0.1.2`, Ablauf laut `docs/guide/releasing.md`). **Jeder Schritt mit Wirkung nach außen (Push, PR, Bucket anlegen, Schlüssel erzeugen, Rollout) wird vorher mit dem Nutzer abgestimmt.**

- [ ] **Step 1: Nutzer legt an:** privaten Bucket `normly-backups` und öffentlich lesbaren Bucket `normly-kb` in STACKIT Object Storage (Zugangsdaten nur in `/opt/normly/.env`, nie im Chat); prüft, ob der Backup-Bucket eine Objektsperre bietet und ob Flex Punkt-in-Zeit-Wiederherstellung und Verschlüsselung der Sicherungen bietet — Ergebnisse tragen wir in die Spec („Befund Flex-Sicherung“, „Offene Punkte“) ein und passen die Aufbewahrung an, falls nötig.
- [ ] **Step 2: Schlüssel-Zeremonie (Nutzer, offline):** `age-keygen -o age.key` (privat offline und im Secrets Manager, öffentlicher Schlüssel in `NORMLY_BACKUP_AGE_RECIPIENT`); `python -m normly_core.exchange keygen --private kb-signing.key --public kb-signing.pub.pem` auf einer vertrauenswürdigen Maschine; der öffentliche Schlüssel wird nach `core/src/normly_core/exchange/keys/kb-signing.pub.pem` committet (eigener kleiner PR), der private bleibt offline.
- [ ] **Step 3: VM vorbereiten:** Pakete installieren, `/opt/normly/{bin,releases,state}` anlegen, Skripte aus dem verifizierten Image nach `/opt/normly/bin`, systemd-Units nach `/etc/systemd/system`, `.env` um `NORMLY_BACKUP_*`, `RCLONE_*`, `NORMLY_KB_BASE_URL` ergänzen. Den bestehenden Quellcode-Stack (`/opt/normly/src`) erst abschalten, wenn der erste `normly-deploy deploy` grün ist; Volumes und `.env` bleiben.
- [ ] **Step 4: Erste Bereitstellung:** `normly-deploy deploy v0.1.2` (ohne `current_tag` entfällt die Pre-Rollout-Sicherung; das ist beabsichtigt). Erwartet: fünf `cosign verify` grün, `app.normly.ai` antwortet 200, `normly-deploy status` zeigt `current: 0.1.2`.
- [ ] **Step 5: Sicherung prüfen:** `normly-backup run --kind daily`, Objekte im Bucket sichten (`.dump.age`, `.meta.json`, `.sha256`), `systemctl enable --now normly-backup.timer`, `systemctl list-timers`. **Restore-Test** laut Guide gegen eine Wegwerf-Datenbank mit dem privaten Schlüssel des Nutzers; Ergebnis (Tabellen, Zeilenzahlen) in die Spec eintragen.
- [ ] **Step 6: Dump Ende-zu-Ende:** lokal mit der Ingestion (z. B. BAuA-Testbestand) `export` mit dem privaten Signaturschlüssel, Upload nach `normly-kb/kb/<version>/` und `kb/latest`, auf der VM `docker compose run --rm kb-import`; Erwartung: „imported knowledge base <version>“, Suche in der App liefert Treffer, zweiter Import ohne Änderung. Negativproben: manipulierte Parquet-Datei und fremde Signatur werden abgelehnt.
- [ ] **Step 7: Rollback-Probe:** `normly-deploy deploy` auf einen zweiten Test-Tag (z. B. `v0.1.3`, nur nach Absprache), danach `normly-deploy rollback --age-identity …`; Erwartung: vorheriger Tag läuft, Wissensbestand in der gemerkten Dump-Version, Nutzerdaten wie vor dem Rollout. Dauer und Befund in die Spec eintragen.
- [ ] **Step 8:** Ergebnisse als Abschnitt „Verifikation 2026-10-…“ in die TP4-Spec schreiben (Muster: TP2-Spec), `docs/guide/self-hosting.md` um die reale `NORMLY_KB_BASE_URL` ergänzen, Memory aktualisieren.

---

## Selbstprüfung gegen die Spec

| Spec-Abschnitt | Abgedeckt durch |
|---|---|
| D1 manueller Auslöser, timerfähig | Task 7 (`deploy`, keine Timer-Logik), Task 8 (ADR-024) |
| D2 Rollback mit Daten | Task 7 (`rollback`, Schema-Neuaufbau), Tests für Reihenfolge und Bestätigung |
| D3 verschlüsselte Sicherung, Schlüsseltrennung | Task 6 (`age` mit öffentlichem Schlüssel, `rclone`), Task 9 Schritte 2 und 5 |
| D4 Parquet + Manifest, Repository-Schicht | Tasks 1–4 |
| D5 Object Storage, Kalenderversion, signiert | Tasks 2, 5, 9 (Bucket, Schlüssel, Upload) |
| D6 Sicherung nach Datenart | Task 1 (Gruppen + Test), Task 6 (nur Nutzerdaten) |
| `cosign verify` vor dem Start | Task 7 (`verify_images`) |
| Restore-Test manuell | Task 8 (Guide), Task 9 Schritt 5 |
| Aufbewahrung 7/2/3 | Task 6 (`select_deletions` + Tests) |
| Idempotenter, atomarer Import; Abbruch bei blockierenden Verweisen | Task 3 (`replace_knowledge_base`, Tests), Task 4 |
| Modellname/-revision/Dimension geprüft | Task 4 (`import_dump`), Task 5 (Image-ENV) |
| Erster Start von Selbsthostern | Task 5 (`kb-import`, Guide) |
| ADR-024/025, ADR-021-Nachtrag, CLAUDE.md, SRS, Guides | Task 8 |
| Offene Punkte (PITR, Objektsperre, ADR-014) | Task 9 Schritt 1, ADR-024 „Folgen/Offen“ |

**Bekannte Lücken, bewusst nicht in diesem Plan:** Delta-Dumps, Timer-Auto-Rollout, automatischer Restore-Test, Secrets per AppRole (TP3), Entscheidung über das Repository `normly-webapp`. **Risiken, die beim Bau zu prüfen sind** (nicht vorab entschieden): Verhalten von `docker compose up --wait` mit dem One-Shot-Dienst `migrate` auf der VM-Compose-Version; Fremdschlüssel-Reihenfolge bei `pg_restore --data-only` ohne Superuser-Rechte auf Postgres Flex; Laufzeit und Speicherbedarf von Export/Import bei realem Bestand.
