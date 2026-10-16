# TP4 deployment automation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New versions are rolled out pull-based to the VM and can be rolled back, user data is backed up encrypted, and the free knowledge base is distributed and imported as a signed, schema-independent Parquet dump in Object Storage.

**Architecture:** Three separately acceptable parts. (A) Exchange format in the core: `normly_core.exchange` (table groups, manifest, Ed25519 signature, Parquet export/import) via a new repository interface `KnowledgeExchangeRepository`. (B) `normly-backup` (Bash + stdlib Python for the retention). (C) `normly-deploy` (Bash) with `cosign verify`, pre-rollout backup, rollback by rebuilding the schema. Deploy files (Compose, Caddyfile, scripts) travel in the signed `pipeline` image.

**Tech Stack:** Python 3.11+, SQLAlchemy 2 Core, Alembic, pyarrow (Parquet), cryptography (Ed25519), pytest + testcontainers; Bash, age, rclone, cosign, pg_dump/psql/pg_restore, systemd.

Spec: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md` (decisions D1–D6 apply unchanged).

## Global Constraints

- Source files carry a license header: `SPDX-License-Identifier: AGPL-3.0-or-later` and `Copyright (C) 2026 normly contributors` (core, scripts, deploy files).
- Commits: English, Conventional Commits, `-s` (DCO, the human's Signed-off-by), trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **never** run `git config`; no push and no PR without asking first (CI is billed).
- Database access only via the repository layer (ADR-006): no SQL in `normly_core/exchange/`. `test_architecture.py` requires a `jurisdiction` parameter for every Protocol method with the prefix `get_`/`list_` — the new interface therefore uses **no** methods with these prefixes.
- Rights classification is the only gate: missing classification means do not export; only sources of categories A, B, D, never `commercial_catalog`.
- Processing steps idempotent; every derived artifact carries `delivery_id` (lineage is preserved in every export row).
- Everything persisted encrypted; the private `age` key and the private signing key are **never** on the VM and never in the repository.
- No secrets in code, not even in tests (tests generate keys at runtime).
- Documentation (`docs/guide/`) in English; ADRs, spec, plan in German (ADR-020).
- Python tests run with `cd core && ../.venv/bin/pytest <path>`; Docker must be running (testcontainers).
- Dump layout: `<version>/manifest.json`, `<version>/manifest.json.sig` (64 raw bytes Ed25519), `<version>/tables/<table>/part-NNNN.parquet`.
- Table order in the knowledge base is FK-safe (parents first): `source, delivery, work, document, document_designation, document_title, rights_classification, edge, segment, embedding, document_embedding`.
- Object layout in the backup bucket: `backups/<YYYYMMDDTHHMMSSZ>-<kind>.dump.age` (+ `.meta.json`, `.sha256`), `kind` = `daily` or `pre-<tag>`.
- Retention: 7 daily (one per calendar day), 2 monthly (in each case the newest daily backup of the 2 most recent calendar months), 3 pre-rollout backups.
- Image tags carry no `v` prefix (`0.1.2`); the scripts accept `v0.1.2` and `0.1.2`.

## File overview

| File | Responsibility |
|---|---|
| `core/src/normly_core/exchange/tables.py` | Table groups (knowledge base / user data / pipeline state), FK order |
| `core/src/normly_core/exchange/manifest.py` | Manifest data model, checksums, (de)serialization |
| `core/src/normly_core/exchange/signing.py` | Ed25519 key generation, signing, verification |
| `core/src/normly_core/exchange/parquet_io.py` | Parquet writing/reading with a fixed schema per column kind |
| `core/src/normly_core/exchange/exporter.py` | Export orchestration via the repository interface |
| `core/src/normly_core/exchange/importer.py` | Import orchestration (signature, model, checksums, exchange) |
| `core/src/normly_core/exchange/fetch.py` | Load the dump over HTTPS |
| `core/src/normly_core/exchange/__main__.py` | CLI: `keygen`, `export`, `import`, `info`, `tables` |
| `core/src/normly_core/graph/domain.py` | + `ExchangeColumn`, `ImportRecord`, `ImportBlockedError`, `KnowledgeExchangeRepository` |
| `core/src/normly_core/graph/postgres/exchange.py` | `PostgresKnowledgeExchangeRepository` (gate queries, atomic exchange) |
| `core/src/normly_core/graph/postgres/orm.py` + `core/migrations/versions/0032_create_knowledge_base_import.py` | Table `knowledge_base_import` (imported version) |
| `docker/python.Dockerfile` | `pipeline` stage: `NORMLY_EMBEDDING_MODEL_REVISION`, deploy files to `/app/deploy` |
| `compose.yaml`, `.env.example` | Profile `kb-import` or service, `NORMLY_KB_BASE_URL` |
| `scripts/normly-backup`, `scripts/normly-backup-retention.py` | Backup, encryption, upload, retention |
| `scripts/normly-deploy` | `deploy`, `rollback`, `status` |
| `scripts/tests/` | pytest harness with fake binaries for both scripts |
| `deploy/systemd/normly-backup.{service,timer}` | daily timer |
| `docs/guide/operations.md`, `docs/guide/self-hosting.md` | Operations and dump import (English) |
| `docs/adr/README.md`, `CLAUDE.md`, `docs/srs/…` | ADR-024, ADR-025, ADR-021 addendum, references |

---

## Part A — Exchange format in the core

### Task 1: Table groups and completeness test

**Files:**
- Create: `core/src/normly_core/exchange/__init__.py`
- Create: `core/src/normly_core/exchange/tables.py`
- Test: `core/tests/exchange/__init__.py`, `core/tests/exchange/test_tables.py`

**Interfaces:**
- Produces: `KNOWLEDGE_TABLES: tuple[str, ...]`, `USER_TABLES: tuple[str, ...]`, `PIPELINE_STATE_TABLES: tuple[str, ...]`, `SYSTEM_TABLES: tuple[str, ...]` (`knowledge_base_import`; `alembic_version` is not in the ORM and is listed in `UNMANAGED_TABLES`), `group_tables(name: str) -> tuple[str, ...]` for `knowledge|user|pipeline|all`.

- [ ] **Step 1: Write the failing test**

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

The test presupposes `knowledge_base_import` from Task 3; until then the first test fails at exactly this point. Therefore Step 3 in this task already lists the table in `SYSTEM_TABLES`, and Task 3 creates the ORM/migration; **Task 1 is only fully green after Task 3** — the test for "every ORM table exactly once" is marked in Task 1 with `pytest.mark.xfail(strict=True, reason="knowledge_base_import arrives in Task 3")` and unmarked in Task 3 Step 6.

- [ ] **Step 2: Run the test, it must fail**

Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.exchange'`

- [ ] **Step 3: Implementation**

`core/src/normly_core/exchange/__init__.py`: license header only.

`core/src/normly_core/exchange/tables.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Which table belongs to which backup/exchange group.

Three groups (TP4 spec, Part 2):

* knowledge -- the free knowledge base. Reproducible from source deliveries,
  distributed as a versioned dump (Part 3), never part of the daily backup.
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

Note on `all`: the order is "children first" and is used for `DROP TABLE … CASCADE` in the rollback; CASCADE makes it non-critical.

- [ ] **Step 4: Run the test**

Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py -v`
Expected: PASS for the order tests; the marked completeness test XFAIL.

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/exchange core/tests/exchange
git commit -s -m "feat(exchange): table groups for backup and knowledge-base dump

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Manifest and Ed25519 signature

**Files:**
- Create: `core/src/normly_core/exchange/manifest.py`, `core/src/normly_core/exchange/signing.py`
- Modify: `core/pyproject.toml` (dependencies `pyarrow>=17,<20`, `cryptography>=43,<46`), then `uv lock`
- Test: `core/tests/exchange/test_manifest.py`, `core/tests/exchange/test_signing.py`

**Interfaces:**
- Produces:
  - `EXCHANGE_SCHEMA_VERSION = 1`, `EMBEDDING_DIMENSION = 1024`
  - `FileEntry(path: str, sha256: str, rows: int)`; `DeliveryEntry(delivery_id: str, publisher: str, legal_basis_category: str)`
  - `Manifest(exchange_schema_version: int, dump_version: str, created_at: str, embedding_models: list[str], embedding_model_revision: str, embedding_dimension: int, deliveries: list[DeliveryEntry], tables: dict[str, list[FileEntry]])` with `to_bytes() -> bytes` (canonical JSON, `sort_keys=True`, UTF-8) and `Manifest.from_bytes(data: bytes) -> Manifest`
  - `sha256_file(path: Path) -> str`
  - `generate_keypair() -> tuple[bytes, bytes]` (PEM private, PEM public), `sign(private_pem: bytes, data: bytes) -> bytes`, `verify(public_pem: bytes, data: bytes, signature: bytes) -> None` (raises `SignatureError`)

- [ ] **Step 1: Write the tests**

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

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange -v` — expected FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementation**

`core/pyproject.toml`, add to `dependencies`: `"pyarrow>=17,<20",` and `"cryptography>=43,<46",`. Then run `uv lock` in the repo root and check `git diff uv.lock` for only expected additions.

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

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — expected PASS.

- [ ] **Step 5: Commit**

```bash
git add core/pyproject.toml uv.lock core/src/normly_core/exchange core/tests/exchange
git commit -s -m "feat(exchange): dump manifest and Ed25519 signing

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Repository interface, migration and Postgres implementation

The largest task. It delivers: table `knowledge_base_import`, Protocol, gate queries and the atomic exchange — all tested with real data against Postgres.

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (dataclasses + Protocol at the end of the file)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`KnowledgeBaseImportORM`)
- Create: `core/migrations/versions/0032_create_knowledge_base_import.py`
- Create: `core/src/normly_core/graph/postgres/exchange.py`
- Modify: `core/tests/exchange/test_tables.py` (remove xfail)
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

  Rows are `dict[str, Any]` with exchange types: UUID → `str`, Enum → `str` (`.value`), vector → `list[float]`, otherwise native Python types (`datetime` with time zone, `date`, `bool`, `int`, `str`).
- Produces (in `normly_core.graph.postgres.exchange`): `PostgresKnowledgeExchangeRepository(session: Session)`.
- The methods never commit; the caller commits.

- [ ] **Step 1: ORM, migration, unmarking**

Append at the end of `orm.py`:

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

`0032_create_knowledge_base_import.py` (take the revision IDs from the neighboring migration; `down_revision` is the ID of the migration `0031_add_hnsw_indexes` — look it up with `grep -n "^revision" core/migrations/versions/0031_add_hnsw_indexes.py`):

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

In `core/tests/exchange/test_tables.py`, remove the `xfail` marker (Step 1 from Task 1). Run: `cd core && ../.venv/bin/pytest tests/exchange/test_tables.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v` — Expected: PASS.

- [ ] **Step 2: Domain types and Protocol**

Append to `core/src/normly_core/graph/domain.py` (add the imports `Any, Callable, Iterator, Mapping` from `typing`/`collections.abc` if missing; **no** SQLAlchemy import):

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

- [ ] **Step 3: Failing tests for the repository**

First `core/tests/exchange/helpers.py` (fixture pattern from `tests/graph/test_jurisdiction_export.py`; also used by Task 4):

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
        responsible_person="Test Reviewer", commercial_catalog=commercial,
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
        legal_basis_reference="§ 5 UrhG", classified_at=NOW, classified_by="Test Reviewer",
        delivery_id=delivery.id,
    )
    return document
```

Then `core/tests/exchange/test_exchange_repository.py`:

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

Note: the signature of `PostgresAccountRepository.create_account` and `PostgresSegmentRepository.add_segment` is to be checked before writing with `grep -n "def create_account\|def add_segment" core/src/normly_core/graph/postgres/repositories.py`, and the test adapted to the actual parameters (parameter names, not what the tests assert).

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange/test_exchange_repository.py -v` — expected FAIL (`ModuleNotFoundError: normly_core.graph.postgres.exchange`).

- [ ] **Step 5: Implementation**

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

Known pitfalls to check first when debugging (do not "program them away" in advance): (1) `EdgeORM.layer == "free"` must compare against the enum type — use `Layer.FREE` from `normly_core.graph.domain` if needed; (2) `delete` on `embedding`/`document_embedding` takes effect via `ON DELETE CASCADE` anyway, but is idempotent; (3) an `IntegrityError` leaves the transaction in an error state — that is intended, the caller rolls back.

- [ ] **Step 6: Run the tests and architecture guards**

Run: `cd core && ../.venv/bin/pytest tests/exchange tests/graph/test_architecture.py tests/graph/test_orm_migration_consistency.py -v`
Expected: PASS. If a gate test fails, the respective subquery in `_statement` is to be corrected, not the test.

- [ ] **Step 7: Commit**

```bash
git add core/src core/migrations core/tests
git commit -s -m "feat(exchange): knowledge-exchange repository with export gate and atomic replace

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Parquet, export and import

**Files:**
- Create: `core/src/normly_core/exchange/parquet_io.py`, `exporter.py`, `importer.py`
- Test: `core/tests/exchange/test_parquet_io.py`, `core/tests/exchange/test_export_import.py`

**Interfaces:**
- Consumes: `KnowledgeExchangeRepository`, `Manifest`, `FileEntry`, `DeliveryEntry`, `sign`, `verify`, `sha256_file`, `KNOWLEDGE_TABLES`.
- Produces:
  - `write_parts(directory: Path, table: str, columns: list[ExchangeColumn], batches: Iterator[list[dict]], *, rows_per_part: int) -> list[FileEntry]` (paths relative to the dump directory, `tables/<table>/part-NNNN.parquet`) and `read_rows(path: Path, batch_size: int = 5000) -> Iterator[list[dict]]`.
  - `export_dump(repository, *, out_dir: Path, dump_version: str, private_key_pem: bytes, embedding_model_revision: str, rows_per_part: int = 100_000, now: datetime | None = None) -> Path` (returns `<out_dir>/<dump_version>`; aborts if the directory exists — versions are immutable).
  - `import_dump(repository, *, dump_dir: Path, public_key_pem: bytes, expected_model_name: str, expected_model_revision: str, now: datetime | None = None) -> ImportRecord`; errors: `ImportRefused(Exception)` with a clear message (signature, schema version, model name/revision, checksum, dimension).

- [ ] **Step 1: Write the tests**

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

`test_export_import.py` (roundtrip against Postgres; reuse helper functions from `test_exchange_repository.py` by import: `from tests.exchange.test_exchange_repository import _source, _delivery, _document` — if `tests` is not an importable package, move the helpers out into `core/tests/exchange/helpers.py` and import them in both files):

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

The helper functions come from `core/tests/exchange/helpers.py` (Task 3). A test for "wrong exchange schema version" is added by re-serializing and signing the manifest with `exchange_schema_version=99` (`sign(private_pem, …)`), expected `match="exchange schema version"`.

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange -v` — expected FAIL (missing modules).

- [ ] **Step 3: Implementation**

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

Note: in the test `test_roundtrip_across_parts` the vectors are three-dimensional; `vector_dimension_ok` is therefore only called by the importer and tested separately (small test in `test_export_import.py`: file with a 3-dimensional vector → importer refuses with `match="dimension"`).

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

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — expected PASS. After every test that turns red, first read the actual error message (type mismatch Arrow↔Python, enum conversion) instead of guessing.

- [ ] **Step 5: Commit**

```bash
git add core/src core/tests
git commit -s -m "feat(exchange): Parquet export and verified, idempotent import

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: CLI, fetching over HTTPS, image and Compose profile

**Files:**
- Create: `core/src/normly_core/exchange/fetch.py`, `core/src/normly_core/exchange/__main__.py`
- Create: `core/src/normly_core/exchange/keys/kb-signing.pub.pem` (placeholder until Task 11; commit **no** valid key — the file is created in Task 11 with the real public key; until then the import requires `--public-key`)
- Modify: `docker/python.Dockerfile` (pipeline stage), `compose.yaml`, `.env.example`, `docs/guide/self-hosting.md`
- Test: `core/tests/exchange/test_fetch.py`, `core/tests/exchange/test_cli.py`

**Interfaces:**
- Produces: `fetch_dump(base_url: str, version: str, destination: Path, *, opener=urllib.request.urlopen) -> Path` (resolves `latest` via `<base>/latest`, loads `manifest.json`, `manifest.json.sig` and all files from the manifest into `destination/<version>/`; verifies nothing — `import_dump` does that).
- CLI (`python -m normly_core.exchange`):
  - `keygen --private PATH --public PATH` (refuses to overwrite; file mode 0600 for private)
  - `export --version V --out DIR --private-key PATH` (reads `NORMLY_DATABASE_URL`, `NORMLY_EMBEDDING_MODEL_REVISION`)
  - `import (--from DIR | --fetch VERSION|latest) [--public-key PATH]` (reads `NORMLY_DATABASE_URL`, `NORMLY_KB_BASE_URL`, `NORMLY_EMBEDDING_MODEL_REVISION`; model name from `normly_core.pipeline.embeddings.MODEL_NAME`, imported lazily)
  - `info` (prints the imported dump version or `none`)
  - `tables GROUP` (prints table names, one per line)

- [ ] **Step 1: Write the tests**

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

- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_fetch.py tests/exchange/test_cli.py -v` — expected FAIL.

- [ ] **Step 3: Implementation**

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

The folder `keys/` needs a `.gitkeep`; `pyproject.toml` (hatch) includes non-Python files in the package anyway, as long as they are under `src/normly_core`.

- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange -v` — expected PASS.

- [ ] **Step 5: Image, Compose, env, guide**

`docker/python.Dockerfile`, replace the `pipeline` stage with:

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

`ARG E5_REVISION` is at the top of the Dockerfile before the `weights` stage (line ~75); because `ARG`s are stage-local, the line `ARG E5_REVISION=3d7cfb…` as defined there must be repeated **in the `pipeline` stage without a default** (the value then comes from the global default only if declared before the first `FROM`). Check: `grep -n "ARG E5_REVISION" docker/python.Dockerfile`; if the declaration is not before the first `FROM`, set `ARG E5_REVISION=<the same hash>` in the `pipeline` stage with the comment "must match the weights stage" **or** (preferred) move the existing declaration above the first `FROM`, so that there is exactly one definition. Then check `.dockerignore` for the exclusion of `scripts/` and `compose.yaml` and adjust it.

`compose.yaml`, insert a new service next to `pipeline`:

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

`.env.example`, add in the Database/Images section:

```
# --- Knowledge base -------------------------------------------------------
# Public location of the versioned knowledge-base dumps (ADR-025).
# `docker compose run --rm kb-import` imports the newest one.
# NORMLY_KB_BASE_URL=
```

`docs/guide/self-hosting.md` (English): delete the item "No versioned knowledge-base dump yet …" under "Known gaps" and insert a section "Importing the knowledge base" before "Ingesting documents": command `docker compose run --rm kb-import` (`docker compose run --rm kb-import 2026.10.1` for a fixed version), note on `NORMLY_KB_BASE_URL`, checks (signature, model revision, checksums), that the import is idempotent, and that an import aborts if user data still points to removed rows.

- [ ] **Step 6: Verification (local, no push)**

Run: `docker compose config -q` (Expected: no error), `cd core && ../.venv/bin/pytest tests/exchange -q` (Expected: PASS). A local image build is **not** part of this task (5 GB, time); it runs in Task 11 on the VM.

- [ ] **Step 7: Commit**

```bash
git add core docker compose.yaml .env.example docs/guide/self-hosting.md
git commit -s -m "feat(exchange): CLI, HTTPS fetch, image revision env and kb-import service

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Part B — Backup

### Task 6: `normly-backup`, retention and timer

**Files:**
- Create: `scripts/normly-backup`, `scripts/normly-backup-retention.py`
- Create: `deploy/systemd/normly-backup.service`, `deploy/systemd/normly-backup.timer`
- Create: `scripts/tests/conftest.py`, `scripts/tests/test_retention.py`, `scripts/tests/test_backup.py`

**Interfaces:**
- Produces:
  - `scripts/normly-backup-retention.py`: reads object names (one per line, only `*.dump.age`) from stdin and outputs the **base names to delete** (`<ts>-<kind>`); function `select_deletions(names: list[str]) -> list[str]`.
  - `scripts/normly-backup run [--kind daily|pre-<tag>]`: creates the backup and outputs the base name as the **last line**; `scripts/normly-backup prune`.
- Environment (from `/opt/normly/.env`, loaded by the script): `NORMLY_DATABASE_URL`, `NORMLY_BACKUP_AGE_RECIPIENT`, `NORMLY_BACKUP_REMOTE` (rclone target, e.g. `stackit:normly-backups`), rclone credentials via `RCLONE_*` variables (the VM's `.env`). `NORMLY_COMPOSE` (default `docker compose -f /opt/normly/current/compose.yaml --project-directory /opt/normly/current`).

- [ ] **Step 1: Write the tests for the retention**

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


- [ ] **Step 2:** `cd scripts && python3 -m pytest tests/test_retention.py -v` — expected FAIL (file missing).

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

- [ ] **Step 4:** `cd scripts && python3 -m pytest tests/test_retention.py -v` — expected PASS.

- [ ] **Step 5: Test harness with fake binaries**

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

- [ ] **Step 6: Tests for `normly-backup`**

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

- [ ] **Step 7:** `cd scripts && python3 -m pytest tests -v` — expected FAIL for `test_backup.py` (script missing).

- [ ] **Step 8: `scripts/normly-backup`**

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Encrypted backup of the user-data tables (TP4 spec, Part 2).
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

`chmod +x scripts/normly-backup`. Note: the fake `docker` supplies the table list via `FAKE_DOCKER_OUT`; in the test `test_run_rejects_unknown_kind` the check takes effect before any external call. The function `run_backup` calls `exit 2` from within a function — that terminates the script, as intended.

- [ ] **Step 9:** `cd scripts && python3 -m pytest tests -v` and `shellcheck scripts/normly-backup` — expected PASS and no findings respectively (fix findings, do not suppress them, except with a justified `# shellcheck disable=`).

- [ ] **Step 10: systemd units**

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

## Part C — Rollout and rollback

### Task 7: `normly-deploy`

**Files:**
- Create: `scripts/normly-deploy`
- Test: `scripts/tests/test_deploy.py`

**Interfaces:**
- Consumes: `normly-backup run --kind pre-<tag>` (last stdout line = base name), harness from Task 6.
- Produces: `normly-deploy deploy <tag>`, `normly-deploy rollback --age-identity FILE [--yes]`, `normly-deploy status`.
- State files under `$NORMLY_DIR/state/`: `current_tag`, `previous_tag`, `pre_rollout_backup`, `pre_rollout_kb_version`, `deploy.lock` (directory lock via `mkdir`). Release files under `$NORMLY_DIR/releases/<tag>/` (Compose, Caddyfile, scripts); `$NORMLY_DIR/current` is a symlink to the active release; `.env` in every release folder is a symlink to `$NORMLY_DIR/.env`.

**Behavior (spec Part 1):** Normalize the tag to drop the `v`; accept only `X.Y.Z`. Order of `deploy`: lock → `cosign verify` of all five images (identity `^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/tags/v<tag>$`, issuer `https://token.actions.githubusercontent.com`) → extract the assets from the `pipeline` image to `releases/<tag>/` → pre-rollout backup (abort without a confirmed upload) → `pull` → `up -d --wait` → write state. On failure: clear message, **no** automatic way back, `current_tag` unchanged.

- [ ] **Step 1: Write the tests**

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

For this, the harness from Task 6 supports `FAKE_DOCKER_EXIT_ON=<word>` (the fake `docker` exits with 1 if the word occurs in the arguments) and by default sets `NORMLY_BACKUP_BIN` to a helper script that outputs `20261009T100000Z-pre-0.1.2`; `test_deploy_aborts_when_pre_rollout_backup_fails` overrides the variable with `/bin/false`.

- [ ] **Step 2:** `cd scripts && python3 -m pytest tests/test_deploy.py -v` — expected FAIL.

- [ ] **Step 3: `scripts/normly-deploy`**

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Pull-based rollout and rollback on the VM (TP4 spec, Part 1; ADR-024).
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

`chmod +x scripts/normly-deploy`. Open pitfalls that show up while making the tests green and are to be solved there: (a) the first deployment has no `current_tag` and therefore no pre-rollout backup (intended: there is no user data yet that would need backing up); (b) in the test, `read_state` does not die on missing files because it uses `|| true`; (c) `drop_sql` is one line per table and is sent with `psql -c` as one command string — multiple statements in one `-c` run in one transaction, that is intended.

- [ ] **Step 4:** `cd scripts && python3 -m pytest tests -v` and `shellcheck scripts/normly-deploy` — expected PASS.

- [ ] **Step 5: Add the CI job**

In `.github/workflows/ci.yml`, append a job `test-scripts`, following the pattern of the existing jobs (take the runner and checkout version from `test-docs`, do not reinvent them):

```yaml
  test-scripts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends shellcheck
      - run: shellcheck scripts/normly-backup scripts/normly-deploy
      - run: pip install pytest && python -m pytest scripts/tests -q
```

Before inserting, read `sed -n 60,80p .github/workflows/ci.yml` and align `runs-on`/`container`/action versions with the ones used there.

- [ ] **Step 6: Commit**

```bash
git add scripts .github/workflows/ci.yml
git commit -s -m "feat(deploy): pull-based rollout and rollback with cosign verification

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Documentation

### Task 8: ADR-024, ADR-025, ADR-021 addendum, CLAUDE.md, SRS, operations guide

**Files:**
- Modify: `docs/adr/README.md` (append ADR-024, ADR-025; ADR-021 addendum at line ~700; check the "Open items" register)
- Modify: `CLAUDE.md` (exception rule on ADR-021: sentence on STACKIT Git and the knowledge base)
- Modify: `docs/srs/03-requirements.md` (REQ-GIT-005 sentence on STACKIT Git; references at REQ-INST-002, REQ-INST-004, REQ-DIST-004)
- Create: `docs/guide/operations.md` (English)
- Modify: `docs/guide/releasing.md` (reference to `normly-deploy deploy vX.Y.Z` as the next step after a release)

- [ ] **Step 1: Append ADR-024** (adopt the format of the neighboring ADRs: heading `## ADR-024 — …`, status, date, context, decision, rationale, rejected, consequences). Content:

  - **Title:** "Rollout, rollback and backup on the single VM"; status: accepted 2026-10-09 (addendum note: builds on ADR-010, ADR-014, ADR-023).
  - **Context:** The VM currently builds from source code; there is no rollback; user data is backed up only by the Flex backup (30 days, provider-internal); STACKIT credentials must not be stored on GitHub (ADR-021).
  - **Decisions:** (1) Manual trigger via SSH (`normly-deploy deploy vX.Y.Z`), script timer-capable; (2) before the start, `cosign verify` of all five images against the tag's release workflow identity, Compose file and scripts travel in the signed `pipeline` image; (3) rollback restores images **and** data to the state before the rollout — the schema is rebuilt (drop tables, `migrate` of the previous image, knowledge base import, user data restore); (4) backup of the user data group only, `age`-encrypted on the VM with the public key, private key never on the VM, upload via `rclone` into a private Object Storage bucket; (5) retention 7 daily / 2 monthly / 3 pre-rollout, in addition the 30-day Flex backup of the whole database; (6) manual restore test.
  - **Rationale:** per decision, from the spec sections "Decisions" and "Part 1/2" (core: a human decides on migration windows; migrations are forward-only, hence rollback = rebuild; the knowledge base is reproducible, hence no daily full dump at double-digit GB; key separation protects even with a compromised VM).
  - **Rejected:** timer auto-rollout; pure image rollback with expand/contract discipline; server-side encryption only; daily full dump; pre-rollout dumps only.
  - **Consequences/open:** data loss since the rollout on rollback (warning + confirmation); rollback duration grows with the knowledge base; cryptographic erasure for licensed collections (ADR-014) is open for the commercial layer; secrets flow via AppRole (TP3) stays out of scope.

- [ ] **Step 2: Append ADR-025:** title "Knowledge base dump as exchange format"; decisions: Parquet per table plus signed manifest, import/export via the repository layer (`KnowledgeExchangeRepository`), exchange schema version independent of Alembic, Ed25519 signature in the core (rationale: no additional binary in the image), distribution via a publicly readable STACKIT Object Storage bucket with calendar version `kb/<version>/` and `kb/latest`, import atomic and idempotent, abort on blocking user-data references, model name and revision are checked; export gate = rights classification (the only gate) with categories A/B/D. Take over rationale D4 from the spec (ADR-006, public product, lineage, price). Rejected: `pg_dump` of the knowledge base, delta dumps (possible later), STACKIT Git as storage, additional Git manifest.

- [ ] **Step 3: ADR-021 addendum:** following the existing addendum pattern (see ADR-020), add a dated paragraph "Addendum 2026-10-09": the statement that STACKIT Git is intended for the future hosting of the norms knowledge base is superseded by ADR-025; the knowledge base is distributed as a signed dump in STACKIT Object Storage. The repository `normly-webapp` remains without a purpose; whether it is archived or deleted is open. Adjust the same sentence in `CLAUDE.md` (exception paragraph) and REQ-GIT-005: "…is no longer intended for the knowledge base (ADR-025); the knowledge base resides as a dump in STACKIT Object Storage."

- [ ] **Step 4: SRS references:** one sentence each, "Implementation: ADR-024 (`normly-deploy`)" at REQ-INST-002 and REQ-INST-004, "Implementation: ADR-025" at REQ-DIST-004. Check the anchors in `docs/srs/README.md` (the `test-docs` job has a baseline "3 issues found"; the count must not rise).

- [ ] **Step 5: `docs/guide/operations.md` (English)** with the sections: Prerequisites on the VM (`docker`, `cosign`, `age`, `rclone`, `postgresql-client`, `python3`; installation commands for Ubuntu), Directory layout (`/opt/normly/{.env,bin,releases,state,current}`), Installing the scripts (from the verified image: `docker run --rm --entrypoint cat ghcr.io/normly/web-app/pipeline:<tag> /app/deploy/scripts/normly-deploy > /opt/normly/bin/normly-deploy` after `cosign verify`), Deploying a release, Rolling back (incl. data-loss warning, key provisioning), Backups (enable the timer, `.env` variables, key management, retention), Restore test (manual steps: download the backup, `age -d`, into a throw-away database `migrate` + `pg_restore --data-only`, `SELECT count(*)` per table), Knowledge-base dumps (export, signing, uploading with `rclone`, setting `kb/latest`). All commands must match the implemented scripts.

- [ ] **Step 6: Verification and commit**

Run: the docs check as in CI (`docker run python:3.12` with zensical, see the memory note on the `test-docs` job), Expected: still "3 issues found".

```bash
git add docs CLAUDE.md
git commit -s -m "docs: ADR-024/025, ADR-021 addendum, operations guide

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Live verification (with the owner)

### Task 9: Setup and acceptance on STACKIT

After merging Parts A–C and releasing a tag (`v0.1.2`, procedure according to `docs/guide/releasing.md`). **Every step with an external effect (push, PR, creating a bucket, generating keys, rollout) is agreed with the owner beforehand.**

- [ ] **Step 1: The owner creates:** a private bucket `normly-backups` and a publicly readable bucket `normly-kb` in STACKIT Object Storage (credentials only in `/opt/normly/.env`, never in the chat); checks whether the backup bucket offers an object lock and whether Flex offers point-in-time recovery and encryption of the backups — we enter the results into the spec ("Finding: Flex backup", "Open items") and adjust the retention if necessary.
- [ ] **Step 2: Key ceremony (owner, offline):** `age-keygen -o age.key` (private offline and in the Secrets Manager, public key in `NORMLY_BACKUP_AGE_RECIPIENT`); `python -m normly_core.exchange keygen --private kb-signing.key --public kb-signing.pub.pem` on a trusted machine; the public key is committed to `core/src/normly_core/exchange/keys/kb-signing.pub.pem` (its own small PR), the private one stays offline.
- [ ] **Step 3: Prepare the VM:** install packages, create `/opt/normly/{bin,releases,state}`, scripts from the verified image to `/opt/normly/bin`, systemd units to `/etc/systemd/system`, extend `.env` with `NORMLY_BACKUP_*`, `RCLONE_*`, `NORMLY_KB_BASE_URL`. Switch off the existing source-code stack (`/opt/normly/src`) only once the first `normly-deploy deploy` is green; volumes and `.env` remain.
- [ ] **Step 4: First deployment:** `normly-deploy deploy v0.1.2` (without `current_tag` the pre-rollout backup is skipped; that is intended). Expected: five `cosign verify` green, `app.normly.ai` responds 200, `normly-deploy status` shows `current: 0.1.2`.
- [ ] **Step 5: Check the backup:** `normly-backup run --kind daily`, inspect the objects in the bucket (`.dump.age`, `.meta.json`, `.sha256`), `systemctl enable --now normly-backup.timer`, `systemctl list-timers`. **Restore test** according to the guide against a throw-away database with the owner's private key; enter the result (tables, row counts) into the spec.
- [ ] **Step 6: Dump end to end:** locally with the ingestion (e.g. BAuA test collection) `export` with the private signing key, upload to `normly-kb/kb/<version>/` and `kb/latest`, on the VM `docker compose run --rm kb-import`; expectation: "imported knowledge base <version>", search in the app returns hits, a second import changes nothing. Negative tests: a tampered Parquet file and a foreign signature are rejected.
- [ ] **Step 7: Rollback test:** `normly-deploy deploy` to a second test tag (e.g. `v0.1.3`, only after agreement), then `normly-deploy rollback --age-identity …`; expectation: the previous tag runs, the knowledge base at the recorded dump version, user data as before the rollout. Enter duration and finding into the spec.
- [ ] **Step 8:** Write the results as a section "Verification 2026-10-…" into the TP4 spec (pattern: TP2 spec), extend `docs/guide/self-hosting.md` with the real `NORMLY_KB_BASE_URL`, update memory.

---

## Self-review against the spec

| Spec section | Covered by |
|---|---|
| D1 manual trigger, timer-capable | Task 7 (`deploy`, no timer logic), Task 8 (ADR-024) |
| D2 rollback with data | Task 7 (`rollback`, schema rebuild), tests for order and confirmation |
| D3 encrypted backup, key separation | Task 6 (`age` with public key, `rclone`), Task 9 steps 2 and 5 |
| D4 Parquet + manifest, repository layer | Tasks 1–4 |
| D5 Object Storage, calendar version, signed | Tasks 2, 5, 9 (bucket, keys, upload) |
| D6 backup by data type | Task 1 (groups + test), Task 6 (user data only) |
| `cosign verify` before the start | Task 7 (`verify_images`) |
| Restore test manual | Task 8 (guide), Task 9 step 5 |
| Retention 7/2/3 | Task 6 (`select_deletions` + tests) |
| Idempotent, atomic import; abort on blocking references | Task 3 (`replace_knowledge_base`, tests), Task 4 |
| Model name/revision/dimension checked | Task 4 (`import_dump`), Task 5 (image ENV) |
| First start for self-hosters | Task 5 (`kb-import`, guide) |
| ADR-024/025, ADR-021 addendum, CLAUDE.md, SRS, guides | Task 8 |
| Open items (PITR, object lock, ADR-014) | Task 9 step 1, ADR-024 "Consequences/open" |

**Known gaps, deliberately not in this plan:** delta dumps, timer auto-rollout, automatic restore test, secrets via AppRole (TP3), decision about the repository `normly-webapp`. **Risks to be checked during the build** (not decided in advance): behavior of `docker compose up --wait` with the one-shot service `migrate` on the VM's Compose version; foreign-key order with `pg_restore --data-only` without superuser rights on Postgres Flex; runtime and memory requirement of export/import with a real collection.
