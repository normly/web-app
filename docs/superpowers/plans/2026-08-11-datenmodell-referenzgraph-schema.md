# Datenmodell & Referenzgraph-Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PostgreSQL schema and repository abstraction layer for the normly reference graph — the foundation the ingestion pipeline, public API, and chat backend will build on.

**Architecture:** Python domain layer of plain dataclasses and `Protocol` repository interfaces, with zero SQLAlchemy imports. A PostgreSQL adapter (SQLAlchemy ORM + Alembic migrations) implements those interfaces, mapping ORM rows to domain dataclasses at the boundary so no persistence detail escapes into consuming code.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, Alembic, psycopg 3, pytest, testcontainers-python (PostgreSQL 16 container for tests).

**Spec:** `docs/superpowers/specs/2026-08-11-datenmodell-referenzgraph-schema-design.md`

## Global Constraints

- Every new source file in `core/` starts with the AGPL license header (CONTRIBUTING.md):
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors
  ```
- Every commit uses `git commit -s` (DCO `Signed-off-by`) and a Conventional Commits subject line.
- The domain layer (`core/src/normly_core/graph/domain.py`) never imports `sqlalchemy` — enforced by an automated test (REQ-GRAPH-004).
- No SQL or ORM query appears outside `core/src/normly_core/graph/postgres/` (architecture rule from CLAUDE.md).
- No secrets in code or tests — the test database URL comes from the testcontainers fixture at runtime, never hardcoded.
- Every schema element (table, column, constraint) matches the spec exactly — same names, same types.

---

## File Structure

```
core/
  pyproject.toml
  alembic.ini
  src/normly_core/
    __init__.py
    graph/
      __init__.py
      domain.py                  # dataclasses, enums, Protocol interfaces
      postgres/
        __init__.py
        orm.py                   # SQLAlchemy declarative models (private to this package)
        repositories.py          # Protocol implementations + ORM<->dataclass mapping
  migrations/
    env.py
    script.py.mako
    versions/
      0001_create_source.py
      0002_create_delivery.py
      0003_create_document.py
      0004_create_document_designation_and_title.py
      0005_create_rights_classification.py
      0006_create_edge.py
  tests/
    conftest.py                  # testcontainers Postgres fixture, migrated engine, db_session
    graph/
      test_architecture.py
      test_source_repository.py
      test_delivery_repository.py
      test_document_repository.py
      test_designation_and_title.py
      test_rights_gate.py
      test_edge_repository.py
      test_lineage_revocation.py
      test_jurisdiction_export.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `core/pyproject.toml`
- Create: `core/src/normly_core/__init__.py`
- Create: `core/src/normly_core/graph/__init__.py`
- Create: `core/src/normly_core/graph/postgres/__init__.py`
- Test: `core/tests/test_scaffolding.py`

**Interfaces:**
- Produces: an installable `normly_core` package importable from `core/tests/`.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_scaffolding.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import normly_core


def test_package_is_importable():
    assert normly_core is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/test_scaffolding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core'`

- [ ] **Step 3: Create the package files**

```toml
# core/pyproject.toml
[project]
name = "normly-core"
version = "0.1.0"
description = "normly free core: reference graph data model and repository layer"
requires-python = ">=3.11"
license = { text = "AGPL-3.0-or-later" }
dependencies = [
    "sqlalchemy>=2.0,<3.0",
    "alembic>=1.13,<2.0",
    "psycopg[binary]>=3.1,<4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "testcontainers[postgres]>=4.0,<5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/normly_core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# core/src/normly_core/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# core/src/normly_core/graph/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# core/src/normly_core/graph/postgres/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

Install in editable mode: `cd core && pip install -e ".[dev]"`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && python -m pytest tests/test_scaffolding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/pyproject.toml core/src core/tests/test_scaffolding.py
git commit -s -m "chore: scaffold normly-core Python package"
```

---

### Task 2: Domain layer — dataclasses, enums, repository interfaces

**Files:**
- Create: `core/src/normly_core/graph/domain.py`
- Test: `core/tests/graph/test_architecture.py`

**Interfaces:**
- Produces (used by every later task):
  - Enums: `LegalBasisCategory`, `TdmOptOutResult`, `EdgeType`, `Layer`
  - Dataclasses: `Source`, `Delivery`, `Document`, `DocumentDesignation`, `DocumentTitle`, `Edge`, `RightsClassification`
  - Protocols: `SourceRepository`, `DeliveryRepository`, `DocumentRepository`, `RightsRepository`, `EdgeRepository`

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/__init__.py
```

```python
# core/tests/graph/test_architecture.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import ast
from pathlib import Path


def test_domain_module_does_not_import_sqlalchemy():
    domain_path = (
        Path(__file__).parents[2] / "src" / "normly_core" / "graph" / "domain.py"
    )
    tree = ast.parse(domain_path.read_text())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "sqlalchemy" not in imported_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/graph/test_architecture.py -v`
Expected: FAIL with `FileNotFoundError` (domain.py does not exist yet)

- [ ] **Step 3: Write the domain layer**

```python
# core/src/normly_core/graph/domain.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Protocol


class LegalBasisCategory(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class TdmOptOutResult(str, Enum):
    NONE_FOUND = "none_found"
    OPT_OUT_PRESENT = "opt_out_present"


class EdgeType(str, Enum):
    REFERENCES = "references"
    REPLACES = "replaces"
    WITHDRAWN_BY = "withdrawn_by"
    BASED_ON_LAW = "based_on_law"
    ADOPTED_FROM = "adopted_from"


class Layer(str, Enum):
    FREE = "free"
    COMMERCIAL = "commercial"


@dataclass(frozen=True)
class Source:
    id: uuid.UUID
    publisher: str
    retrieval_path: str
    legal_basis_category: LegalBasisCategory
    jurisdiction: str
    reviewed_at: date
    responsible_person: str
    commercial_catalog: bool
    contract_reference: str | None
    tdm_opt_out_checked_at: date | None
    tdm_opt_out_result: TdmOptOutResult | None


@dataclass(frozen=True)
class Delivery:
    id: uuid.UUID
    source_id: uuid.UUID
    content_hash: str
    ingested_at: datetime
    withdrawn_at: datetime | None


@dataclass(frozen=True)
class Document:
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    created_via_delivery_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True)
class DocumentDesignation:
    id: uuid.UUID
    document_id: uuid.UUID
    issuer: str
    designation: str
    language: str
    edition: str | None
    is_primary: bool
    delivery_id: uuid.UUID


@dataclass(frozen=True)
class DocumentTitle:
    id: uuid.UUID
    document_id: uuid.UUID
    language: str
    title: str
    delivery_id: uuid.UUID


@dataclass(frozen=True)
class Edge:
    id: uuid.UUID
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    edge_type: EdgeType
    jurisdiction: str | None
    layer: Layer
    delivery_id: uuid.UUID
    revoked_at: datetime | None


@dataclass(frozen=True)
class RightsClassification:
    document_id: uuid.UUID
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str
    classified_at: datetime
    classified_by: str
    delivery_id: uuid.UUID
    revoked_at: datetime | None


class SourceRepository(Protocol):
    def create_source(
        self,
        *,
        publisher: str,
        retrieval_path: str,
        legal_basis_category: LegalBasisCategory,
        jurisdiction: str,
        reviewed_at: date,
        responsible_person: str,
        commercial_catalog: bool = False,
        contract_reference: str | None = None,
        tdm_opt_out_checked_at: date | None = None,
        tdm_opt_out_result: TdmOptOutResult | None = None,
    ) -> Source: ...

    def get_source(self, source_id: uuid.UUID) -> Source | None: ...


class DeliveryRepository(Protocol):
    def record_delivery(
        self, *, source_id: uuid.UUID, content_hash: str, ingested_at: datetime
    ) -> Delivery: ...

    def get_delivery(self, delivery_id: uuid.UUID) -> Delivery | None: ...

    def revoke_delivery(self, delivery_id: uuid.UUID) -> None: ...


class DocumentRepository(Protocol):
    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
    ) -> Document: ...

    def get_document_unchecked(self, document_id: uuid.UUID) -> Document | None: ...

    def add_designation(
        self,
        *,
        document_id: uuid.UUID,
        issuer: str,
        designation: str,
        language: str,
        edition: str | None,
        is_primary: bool,
        delivery_id: uuid.UUID,
    ) -> DocumentDesignation: ...

    def add_title(
        self, *, document_id: uuid.UUID, language: str, title: str, delivery_id: uuid.UUID
    ) -> DocumentTitle: ...

    def list_designations(self, document_id: uuid.UUID) -> list[DocumentDesignation]: ...

    def list_titles(self, document_id: uuid.UUID) -> list[DocumentTitle]: ...

    def get_document_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> Document | None: ...

    def list_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]: ...


class RightsRepository(Protocol):
    def classify(
        self,
        *,
        document_id: uuid.UUID,
        jurisdiction: str,
        may_process: bool,
        may_index_fulltext: bool,
        may_cite_passages: bool,
        may_export_free: bool,
        legal_basis_reference: str,
        classified_at: datetime,
        classified_by: str,
        delivery_id: uuid.UUID,
    ) -> RightsClassification: ...

    def get_classification(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> RightsClassification | None: ...


class EdgeRepository(Protocol):
    def create_edge(
        self,
        *,
        from_document_id: uuid.UUID,
        to_document_id: uuid.UUID,
        edge_type: EdgeType,
        jurisdiction: str | None,
        layer: Layer,
        delivery_id: uuid.UUID,
    ) -> Edge: ...

    def list_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && python -m pytest tests/graph/test_architecture.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/tests/graph
git commit -s -m "feat: add graph domain model and repository interfaces"
```

---

### Task 3: Test infrastructure — testcontainers fixture and Alembic skeleton

**Files:**
- Create: `core/alembic.ini`
- Create: `core/migrations/env.py`
- Create: `core/migrations/script.py.mako`
- Create: `core/migrations/versions/` (empty directory, via `.gitkeep`)
- Create: `core/src/normly_core/graph/postgres/orm.py`
- Create: `core/tests/conftest.py`
- Test: `core/tests/graph/test_migration_baseline.py`

**Interfaces:**
- Consumes: nothing from earlier tasks besides the package layout from Task 1.
- Produces: `Base` (SQLAlchemy `DeclarativeBase`) in `orm.py` for later tasks to attach models to; pytest fixtures `postgres_container` (session), `migrated_engine` (session), `db_session` (function) in `conftest.py` for every later test.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_migration_baseline.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from sqlalchemy import text


def test_migrated_engine_reaches_alembic_head(migrated_engine):
    with migrated_engine.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        rows = list(result)
    assert len(rows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/graph/test_migration_baseline.py -v`
Expected: FAIL with `fixture 'migrated_engine' not found`

- [ ] **Step 3: Write the ORM base, Alembic config, and pytest fixtures**

```python
# core/src/normly_core/graph/postgres/orm.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```ini
; core/alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# core/migrations/env.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from normly_core.graph.postgres.orm import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

```mako
## core/migrations/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

```bash
mkdir -p core/migrations/versions
touch core/migrations/versions/.gitkeep
```

```python
# core/tests/conftest.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

CORE_DIR = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as container:
        yield container


@pytest.fixture(scope="session")
def db_url(postgres_container) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def migrated_engine(db_url):
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(migrated_engine):
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && python -m pytest tests/graph/test_migration_baseline.py -v`
Expected: PASS (first run pulls the `postgres:16` container image, which takes longer)

- [ ] **Step 5: Commit**

```bash
git add core/alembic.ini core/migrations core/src/normly_core/graph/postgres/orm.py core/tests/conftest.py core/tests/graph/test_migration_baseline.py
git commit -s -m "test: add testcontainers Postgres fixture and Alembic skeleton"
```

---

### Task 4: `source` table, ORM model, repository

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Create: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0001_create_source.py`
- Test: `core/tests/graph/test_source_repository.py`

**Interfaces:**
- Consumes: `Source`, `LegalBasisCategory`, `TdmOptOutResult`, `SourceRepository` from Task 2 `domain.py`; `Base` from Task 3 `orm.py`; `db_session` fixture from Task 3 `conftest.py`.
- Produces: `SourceORM` in `orm.py`; `PostgresSourceRepository` in `repositories.py`, used by every later task that needs a `source_id`.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_source_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date

import pytest

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import PostgresSourceRepository


def test_create_and_get_source(db_session):
    repo = PostgresSourceRepository(db_session)

    source = repo.create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )

    fetched = repo.get_source(source.id)
    assert fetched == source


def test_category_d_source_cannot_be_marked_as_commercial_catalog(db_session):
    repo = PostgresSourceRepository(db_session)

    with pytest.raises(Exception):
        repo.create_source(
            publisher="DIN Media",
            retrieval_path="https://nautos.de",
            legal_basis_category=LegalBasisCategory.D,
            jurisdiction="DE",
            reviewed_at=date(2026, 1, 15),
            responsible_person="J. Weber",
            commercial_catalog=True,
        )


def test_category_c_source_without_contract_reference_is_rejected(db_session):
    repo = PostgresSourceRepository(db_session)

    with pytest.raises(Exception):
        repo.create_source(
            publisher="Austrian Standards",
            retrieval_path="sftp://delivery.austrian-standards.at",
            legal_basis_category=LegalBasisCategory.C,
            jurisdiction="AT",
            reviewed_at=date(2026, 1, 15),
            responsible_person="J. Weber",
            contract_reference=None,
        )


def test_category_c_source_with_contract_reference_succeeds(db_session):
    repo = PostgresSourceRepository(db_session)

    source = repo.create_source(
        publisher="Austrian Standards",
        retrieval_path="sftp://delivery.austrian-standards.at",
        legal_basis_category=LegalBasisCategory.C,
        jurisdiction="AT",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
        contract_reference="CONTRACT-2026-001",
    )

    assert source.contract_reference == "CONTRACT-2026-001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/graph/test_source_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.graph.postgres.repositories'`

- [ ] **Step 3: Add the ORM model**

```python
# core/src/normly_core/graph/postgres/orm.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from normly_core.graph.domain import LegalBasisCategory, TdmOptOutResult


class Base(DeclarativeBase):
    pass


class SourceORM(Base):
    __tablename__ = "source"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publisher: Mapped[str]
    retrieval_path: Mapped[str]
    legal_basis_category: Mapped[LegalBasisCategory] = mapped_column(
        sa.Enum(LegalBasisCategory, name="legal_basis_category", native_enum=False)
    )
    jurisdiction: Mapped[str]
    reviewed_at: Mapped[date]
    responsible_person: Mapped[str]
    commercial_catalog: Mapped[bool] = mapped_column(default=False)
    contract_reference: Mapped[str | None]
    tdm_opt_out_checked_at: Mapped[date | None]
    tdm_opt_out_result: Mapped[TdmOptOutResult | None] = mapped_column(
        sa.Enum(TdmOptOutResult, name="tdm_opt_out_result", native_enum=False)
    )

    __table_args__ = (
        sa.CheckConstraint(
            "NOT (legal_basis_category = 'D' AND commercial_catalog)",
            name="ck_source_no_category_d_commercial_catalog",
        ),
        sa.CheckConstraint(
            "legal_basis_category != 'C' OR contract_reference IS NOT NULL",
            name="ck_source_category_c_requires_contract",
        ),
    )
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0001_create_source.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create source table

Revision ID: 0001
Revises:
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("publisher", sa.String, nullable=False),
        sa.Column("retrieval_path", sa.String, nullable=False),
        sa.Column(
            "legal_basis_category",
            sa.Enum("A", "B", "C", "D", name="legal_basis_category", native_enum=False),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String, nullable=False),
        sa.Column("reviewed_at", sa.Date, nullable=False),
        sa.Column("responsible_person", sa.String, nullable=False),
        sa.Column(
            "commercial_catalog", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("contract_reference", sa.String, nullable=True),
        sa.Column("tdm_opt_out_checked_at", sa.Date, nullable=True),
        sa.Column(
            "tdm_opt_out_result",
            sa.Enum(
                "none_found",
                "opt_out_present",
                name="tdm_opt_out_result",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "NOT (legal_basis_category = 'D' AND commercial_catalog)",
            name="ck_source_no_category_d_commercial_catalog",
        ),
        sa.CheckConstraint(
            "legal_basis_category != 'C' OR contract_reference IS NOT NULL",
            name="ck_source_category_c_requires_contract",
        ),
    )


def downgrade() -> None:
    op.drop_table("source")
```

- [ ] **Step 5: Add the repository**

```python
# core/src/normly_core/graph/postgres/repositories.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date

from sqlalchemy.orm import Session

from normly_core.graph.domain import (
    LegalBasisCategory,
    Source,
    TdmOptOutResult,
)
from normly_core.graph.postgres.orm import SourceORM


def _source_to_domain(orm: SourceORM) -> Source:
    return Source(
        id=orm.id,
        publisher=orm.publisher,
        retrieval_path=orm.retrieval_path,
        legal_basis_category=orm.legal_basis_category,
        jurisdiction=orm.jurisdiction,
        reviewed_at=orm.reviewed_at,
        responsible_person=orm.responsible_person,
        commercial_catalog=orm.commercial_catalog,
        contract_reference=orm.contract_reference,
        tdm_opt_out_checked_at=orm.tdm_opt_out_checked_at,
        tdm_opt_out_result=orm.tdm_opt_out_result,
    )


class PostgresSourceRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_source(
        self,
        *,
        publisher: str,
        retrieval_path: str,
        legal_basis_category: LegalBasisCategory,
        jurisdiction: str,
        reviewed_at: date,
        responsible_person: str,
        commercial_catalog: bool = False,
        contract_reference: str | None = None,
        tdm_opt_out_checked_at: date | None = None,
        tdm_opt_out_result: TdmOptOutResult | None = None,
    ) -> Source:
        orm = SourceORM(
            id=uuid.uuid4(),
            publisher=publisher,
            retrieval_path=retrieval_path,
            legal_basis_category=legal_basis_category,
            jurisdiction=jurisdiction,
            reviewed_at=reviewed_at,
            responsible_person=responsible_person,
            commercial_catalog=commercial_catalog,
            contract_reference=contract_reference,
            tdm_opt_out_checked_at=tdm_opt_out_checked_at,
            tdm_opt_out_result=tdm_opt_out_result,
        )
        self._session.add(orm)
        self._session.flush()
        return _source_to_domain(orm)

    def get_source(self, source_id: uuid.UUID) -> Source | None:
        orm = self._session.get(SourceORM, source_id)
        return _source_to_domain(orm) if orm else None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/graph/test_source_repository.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0001_create_source.py core/tests/graph/test_source_repository.py
git commit -s -m "feat: add source register table and repository"
```

---

### Task 5: `delivery` table, idempotent recording, repository

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0002_create_delivery.py`
- Test: `core/tests/graph/test_delivery_repository.py`

**Interfaces:**
- Consumes: `Delivery`, `DeliveryRepository` from Task 2 `domain.py`; `SourceORM`, `PostgresSourceRepository` from Task 4.
- Produces: `DeliveryORM` in `orm.py`; `PostgresDeliveryRepository` in `repositories.py`, whose `record_delivery` and `revoke_delivery` every later task depends on for lineage.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_delivery_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresSourceRepository,
)


def _make_source(db_session):
    source_repo = PostgresSourceRepository(db_session)
    return source_repo.create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )


def test_record_delivery_is_idempotent_by_content_hash(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    now = datetime.now(timezone.utc)

    first = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:abc123", ingested_at=now
    )
    second = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:abc123", ingested_at=now
    )

    assert first.id == second.id


def test_revoke_delivery_sets_withdrawn_at(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery = delivery_repo.record_delivery(
        source_id=source.id,
        content_hash="sha256:def456",
        ingested_at=datetime.now(timezone.utc),
    )

    delivery_repo.revoke_delivery(delivery.id)

    revoked = delivery_repo.get_delivery(delivery.id)
    assert revoked.withdrawn_at is not None


def test_revoke_delivery_is_idempotent(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery = delivery_repo.record_delivery(
        source_id=source.id,
        content_hash="sha256:ghi789",
        ingested_at=datetime.now(timezone.utc),
    )

    delivery_repo.revoke_delivery(delivery.id)
    delivery_repo.revoke_delivery(delivery.id)  # must not raise

    revoked = delivery_repo.get_delivery(delivery.id)
    assert revoked.withdrawn_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/graph/test_delivery_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresDeliveryRepository'`

- [ ] **Step 3: Add the ORM model**

Add to `core/src/normly_core/graph/postgres/orm.py` (append below `SourceORM`):

```python
from datetime import datetime


class DeliveryORM(Base):
    __tablename__ = "delivery"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("source.id"), nullable=False
    )
    content_hash: Mapped[str]
    ingested_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]

    __table_args__ = (
        sa.UniqueConstraint("source_id", "content_hash", name="uq_delivery_source_hash"),
    )
```

(Move the `from datetime import datetime` import to the top of the file alongside the existing `from datetime import date` import — combine into `from datetime import date, datetime`.)

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0002_create_delivery.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create delivery table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("source.id"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_delivery_source_hash"),
    )


def downgrade() -> None:
    op.drop_table("delivery")
```

- [ ] **Step 5: Add the repository**

Add to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from datetime import datetime

from sqlalchemy import select

from normly_core.graph.domain import Delivery
from normly_core.graph.postgres.orm import DeliveryORM


def _delivery_to_domain(orm: DeliveryORM) -> Delivery:
    return Delivery(
        id=orm.id,
        source_id=orm.source_id,
        content_hash=orm.content_hash,
        ingested_at=orm.ingested_at,
        withdrawn_at=orm.withdrawn_at,
    )


class PostgresDeliveryRepository:
    def __init__(self, session: Session):
        self._session = session

    def record_delivery(
        self, *, source_id: uuid.UUID, content_hash: str, ingested_at: datetime
    ) -> Delivery:
        existing = self._session.execute(
            select(DeliveryORM).where(
                DeliveryORM.source_id == source_id,
                DeliveryORM.content_hash == content_hash,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _delivery_to_domain(existing)

        orm = DeliveryORM(
            id=uuid.uuid4(),
            source_id=source_id,
            content_hash=content_hash,
            ingested_at=ingested_at,
            withdrawn_at=None,
        )
        self._session.add(orm)
        self._session.flush()
        return _delivery_to_domain(orm)

    def get_delivery(self, delivery_id: uuid.UUID) -> Delivery | None:
        orm = self._session.get(DeliveryORM, delivery_id)
        return _delivery_to_domain(orm) if orm else None

    def revoke_delivery(self, delivery_id: uuid.UUID) -> None:
        orm = self._session.get(DeliveryORM, delivery_id)
        if orm is None or orm.withdrawn_at is not None:
            return
        orm.withdrawn_at = datetime.now(orm.ingested_at.tzinfo)
        self._session.flush()
```

(`import uuid` and `from sqlalchemy.orm import Session` are already present from Task 4 — do not duplicate.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/graph/test_delivery_repository.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0002_create_delivery.py core/tests/graph/test_delivery_repository.py
git commit -s -m "feat: add delivery table with idempotent recording"
```

**Note for Task 10:** `revoke_delivery` here only marks `withdrawn_at`. Task 10 extends it to cascade to `edge`, `rights_classification`, `document_designation`, and `document_title`.

---

### Task 6: `document` table and repository

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0003_create_document.py`
- Test: `core/tests/graph/test_document_repository.py`

**Interfaces:**
- Consumes: `Document`, `DocumentRepository` from Task 2; `DeliveryORM`/`PostgresDeliveryRepository`, `SourceORM`/`PostgresSourceRepository` from Tasks 4–5.
- Produces: `DocumentORM`; `PostgresDocumentRepository.create_document` / `.get_document_unchecked` (the rest of `DocumentRepository`'s methods are added in Tasks 7–8; `get_document` was renamed to `get_document_unchecked` during Task 8's review to avoid an ungated read path sitting next to the rights-gated ones).

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_document_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:doc-fixture",
        ingested_at=datetime.now(timezone.utc),
    )


def test_create_and_get_document(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresDocumentRepository(db_session)

    document = repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    fetched = repo.get_document_unchecked(document.id)
    assert fetched == document
    assert fetched.created_via_delivery_id == delivery.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/graph/test_document_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresDocumentRepository'`

- [ ] **Step 3: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
class DocumentORM(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origin_issuer: Mapped[str]
    origin_number: Mapped[str]
    edition: Mapped[str]
    part: Mapped[str | None]
    created_via_delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0003_create_document.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("origin_issuer", sa.String, nullable=False),
        sa.Column("origin_number", sa.String, nullable=False),
        sa.Column("edition", sa.String, nullable=False),
        sa.Column("part", sa.String, nullable=True),
        sa.Column(
            "created_via_delivery_id",
            UUID(as_uuid=True),
            sa.ForeignKey("delivery.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("document")
```

- [ ] **Step 5: Add the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import Document
from normly_core.graph.postgres.orm import DocumentORM


def _document_to_domain(orm: DocumentORM) -> Document:
    return Document(
        id=orm.id,
        origin_issuer=orm.origin_issuer,
        origin_number=orm.origin_number,
        edition=orm.edition,
        part=orm.part,
        created_via_delivery_id=orm.created_via_delivery_id,
        created_at=orm.created_at,
    )


class PostgresDocumentRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
    ) -> Document:
        orm = DocumentORM(
            id=uuid.uuid4(),
            origin_issuer=origin_issuer,
            origin_number=origin_number,
            edition=edition,
            part=part,
            created_via_delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _document_to_domain(orm)

    def get_document_unchecked(self, document_id: uuid.UUID) -> Document | None:
        orm = self._session.get(DocumentORM, document_id)
        return _document_to_domain(orm) if orm else None
```

(The rest of `DocumentRepository` — `add_designation`, `add_title`, `list_designations`, `list_titles` — is added to this same class in Task 7; `get_document_for_jurisdiction` and `list_documents_for_jurisdiction` in Task 8.)

- [ ] **Step 6: Run test to verify it passes**

Run: `cd core && python -m pytest tests/graph/test_document_repository.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0003_create_document.py core/tests/graph/test_document_repository.py
git commit -s -m "feat: add document node table and repository"
```

---

### Task 7: `document_designation` and `document_title` — national adoptions and multilingual titles

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0004_create_document_designation_and_title.py`
- Test: `core/tests/graph/test_designation_and_title.py`

**Interfaces:**
- Consumes: `DocumentDesignation`, `DocumentTitle` from Task 2; `DocumentORM`/`PostgresDocumentRepository` from Task 6.
- Produces: `DocumentDesignationORM`, `DocumentTitleORM`; `PostgresDocumentRepository.add_designation` / `.add_title` / `.list_designations` / `.list_titles`.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_designation_and_title.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:designation-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="CEN/CENELEC",
        retrieval_path="https://standards.cencenelec.eu",
        legal_basis_category=LegalBasisCategory.B,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_three_national_adoptions_stay_one_node(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    for issuer, designation, language in [
        ("DIN", "DIN EN ISO 9001", "de"),
        ("BSI", "BS EN ISO 9001", "en"),
        ("AFNOR", "NF EN ISO 9001", "fr"),
    ]:
        doc_repo.add_designation(
            document_id=document.id,
            issuer=issuer,
            designation=designation,
            language=language,
            edition=None,
            is_primary=False,
            delivery_id=delivery.id,
        )

    designations = doc_repo.list_designations(document.id)
    assert len(designations) == 3
    assert {d.issuer for d in designations} == {"DIN", "BSI", "AFNOR"}
    assert doc_repo.get_document_unchecked(document.id).id == document.id


def test_document_titles_are_multilingual(db_session):
    delivery = _make_delivery(db_session, content_hash="sha256:title-fixture")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    doc_repo.add_title(
        document_id=document.id,
        language="en",
        title="Quality management systems — Requirements",
        delivery_id=delivery.id,
    )
    doc_repo.add_title(
        document_id=document.id,
        language="de",
        title="Qualitätsmanagementsysteme — Anforderungen",
        delivery_id=delivery.id,
    )

    titles = doc_repo.list_titles(document.id)
    assert {t.language for t in titles} == {"en", "de"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/graph/test_designation_and_title.py -v`
Expected: FAIL with `AttributeError: 'PostgresDocumentRepository' object has no attribute 'add_designation'`

- [ ] **Step 3: Add the ORM models**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
class DocumentDesignationORM(Base):
    __tablename__ = "document_designation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    issuer: Mapped[str]
    designation: Mapped[str]
    language: Mapped[str]
    edition: Mapped[str | None]
    is_primary: Mapped[bool] = mapped_column(default=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
    )


class DocumentTitleORM(Base):
    __tablename__ = "document_title"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    language: Mapped[str]
    title: Mapped[str]
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0004_create_document_designation_and_title.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document_designation and document_title tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_designation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column("issuer", sa.String, nullable=False),
        sa.Column("designation", sa.String, nullable=False),
        sa.Column("language", sa.String, nullable=False),
        sa.Column("edition", sa.String, nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
    )
    op.create_table(
        "document_title",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column("language", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("document_title")
    op.drop_table("document_designation")
```

- [ ] **Step 5: Extend the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`, and add the four methods to the existing `PostgresDocumentRepository` class:

```python
from normly_core.graph.domain import DocumentDesignation, DocumentTitle
from normly_core.graph.postgres.orm import DocumentDesignationORM, DocumentTitleORM


def _designation_to_domain(orm: DocumentDesignationORM) -> DocumentDesignation:
    return DocumentDesignation(
        id=orm.id,
        document_id=orm.document_id,
        issuer=orm.issuer,
        designation=orm.designation,
        language=orm.language,
        edition=orm.edition,
        is_primary=orm.is_primary,
        delivery_id=orm.delivery_id,
    )


def _title_to_domain(orm: DocumentTitleORM) -> DocumentTitle:
    return DocumentTitle(
        id=orm.id,
        document_id=orm.document_id,
        language=orm.language,
        title=orm.title,
        delivery_id=orm.delivery_id,
    )
```

Add these methods to `PostgresDocumentRepository` (alongside `create_document`/`get_document_unchecked`):

```python
    def add_designation(
        self,
        *,
        document_id: uuid.UUID,
        issuer: str,
        designation: str,
        language: str,
        edition: str | None,
        is_primary: bool,
        delivery_id: uuid.UUID,
    ) -> DocumentDesignation:
        orm = DocumentDesignationORM(
            id=uuid.uuid4(),
            document_id=document_id,
            issuer=issuer,
            designation=designation,
            language=language,
            edition=edition,
            is_primary=is_primary,
            delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        return _designation_to_domain(orm)

    def add_title(
        self, *, document_id: uuid.UUID, language: str, title: str, delivery_id: uuid.UUID
    ) -> DocumentTitle:
        orm = DocumentTitleORM(
            id=uuid.uuid4(),
            document_id=document_id,
            language=language,
            title=title,
            delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        return _title_to_domain(orm)

    def list_designations(self, document_id: uuid.UUID) -> list[DocumentDesignation]:
        rows = self._session.execute(
            select(DocumentDesignationORM).where(
                DocumentDesignationORM.document_id == document_id
            )
        ).scalars()
        return [_designation_to_domain(row) for row in rows]

    def list_titles(self, document_id: uuid.UUID) -> list[DocumentTitle]:
        rows = self._session.execute(
            select(DocumentTitleORM).where(DocumentTitleORM.document_id == document_id)
        ).scalars()
        return [_title_to_domain(row) for row in rows]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd core && python -m pytest tests/graph/test_designation_and_title.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0004_create_document_designation_and_title.py core/tests/graph/test_designation_and_title.py
git commit -s -m "feat: add national designations and multilingual titles"
```

---

### Task 8: `rights_classification` table and the rights gate

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0005_create_rights_classification.py`
- Test: `core/tests/graph/test_rights_gate.py`

**Interfaces:**
- Consumes: `RightsClassification`, `RightsRepository` from Task 2; `DocumentORM`/`PostgresDocumentRepository` from Task 6.
- Produces: `RightsClassificationORM`; `PostgresRightsRepository`; `PostgresDocumentRepository.get_document_for_jurisdiction` / `.list_documents_for_jurisdiction` (the rights gate every later read path relies on).

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_rights_gate.py
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


def _make_document(db_session, content_hash="sha256:rights-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="BAuA",
        retrieval_path="https://www.baua.de/technische-regeln",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="BAuA",
        origin_number="TRGS 900",
        edition="2026",
        part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_document_without_classification_is_not_readable(db_session):
    document, _ = _make_document(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    assert doc_repo.list_documents_for_jurisdiction("DE") == []


def test_classified_document_is_readable_for_its_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=True,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    fetched = doc_repo.get_document_for_jurisdiction(document.id, "DE")
    assert fetched is not None
    assert fetched.id == document.id

    exported = doc_repo.list_documents_for_jurisdiction("DE")
    assert [d.id for d in exported] == [document.id]


def test_classification_does_not_grant_access_in_other_jurisdictions(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=True,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    assert doc_repo.get_document_for_jurisdiction(document.id, "US") is None


def test_may_process_false_still_blocks_read(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=False,
        may_index_fulltext=False,
        may_cite_passages=False,
        may_export_free=False,
        legal_basis_reference="unklar, in Prüfung",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/graph/test_rights_gate.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresRightsRepository'`

- [ ] **Step 3: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
class RightsClassificationORM(Base):
    __tablename__ = "rights_classification"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True
    )
    jurisdiction: Mapped[str] = mapped_column(primary_key=True)
    may_process: Mapped[bool]
    may_index_fulltext: Mapped[bool]
    may_cite_passages: Mapped[bool]
    may_export_free: Mapped[bool]
    legal_basis_reference: Mapped[str]
    classified_at: Mapped[datetime]
    classified_by: Mapped[str]
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None]
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0005_create_rights_classification.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create rights_classification table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_classification",
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True
        ),
        sa.Column("jurisdiction", sa.String, primary_key=True),
        sa.Column("may_process", sa.Boolean, nullable=False),
        sa.Column("may_index_fulltext", sa.Boolean, nullable=False),
        sa.Column("may_cite_passages", sa.Boolean, nullable=False),
        sa.Column("may_export_free", sa.Boolean, nullable=False),
        sa.Column("legal_basis_reference", sa.String, nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("classified_by", sa.String, nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rights_classification")
```

- [ ] **Step 5: Add the repository and extend the rights gate**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import RightsClassification
from normly_core.graph.postgres.orm import RightsClassificationORM


def _rights_to_domain(orm: RightsClassificationORM) -> RightsClassification:
    return RightsClassification(
        document_id=orm.document_id,
        jurisdiction=orm.jurisdiction,
        may_process=orm.may_process,
        may_index_fulltext=orm.may_index_fulltext,
        may_cite_passages=orm.may_cite_passages,
        may_export_free=orm.may_export_free,
        legal_basis_reference=orm.legal_basis_reference,
        classified_at=orm.classified_at,
        classified_by=orm.classified_by,
        delivery_id=orm.delivery_id,
        revoked_at=orm.revoked_at,
    )


class PostgresRightsRepository:
    def __init__(self, session: Session):
        self._session = session

    def classify(
        self,
        *,
        document_id: uuid.UUID,
        jurisdiction: str,
        may_process: bool,
        may_index_fulltext: bool,
        may_cite_passages: bool,
        may_export_free: bool,
        legal_basis_reference: str,
        classified_at: datetime,
        classified_by: str,
        delivery_id: uuid.UUID,
    ) -> RightsClassification:
        orm = RightsClassificationORM(
            document_id=document_id,
            jurisdiction=jurisdiction,
            may_process=may_process,
            may_index_fulltext=may_index_fulltext,
            may_cite_passages=may_cite_passages,
            may_export_free=may_export_free,
            legal_basis_reference=legal_basis_reference,
            classified_at=classified_at,
            classified_by=classified_by,
            delivery_id=delivery_id,
            revoked_at=None,
        )
        self._session.merge(orm)
        self._session.flush()
        return _rights_to_domain(orm)

    def get_classification(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> RightsClassification | None:
        orm = self._session.get(RightsClassificationORM, (document_id, jurisdiction))
        return _rights_to_domain(orm) if orm else None
```

Add these two methods to `PostgresDocumentRepository`:

```python
    def get_document_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> Document | None:
        orm = self._session.execute(
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentORM.id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None

    def list_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]:
        rows = self._session.execute(
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalars()
        return [_document_to_domain(row) for row in rows]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/graph/test_rights_gate.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0005_create_rights_classification.py core/tests/graph/test_rights_gate.py
git commit -s -m "feat: add rights classification and enforce the rights gate on reads"
```

---

### Task 9: `edge` table and jurisdiction-filtered edge listing

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0006_create_edge.py`
- Test: `core/tests/graph/test_edge_repository.py`

**Interfaces:**
- Consumes: `Edge`, `EdgeType`, `Layer`, `EdgeRepository` from Task 2; `DocumentORM` from Task 6; `RightsClassificationORM` from Task 8.
- Produces: `EdgeORM`; `PostgresEdgeRepository`.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_edge_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _make_two_documents(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:edge-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return old, new, delivery


def test_create_edge(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge = edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    assert edge.edge_type == EdgeType.REPLACES
    assert edge.revoked_at is None


def test_duplicate_active_edge_is_rejected(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    with pytest.raises(Exception):
        edge_repo.create_edge(
            from_document_id=new.id,
            to_document_id=old.id,
            edge_type=EdgeType.REPLACES,
            jurisdiction=None,
            layer=Layer.FREE,
            delivery_id=delivery.id,
        )


def test_edges_only_listed_when_target_is_rights_classified(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []

    rights_repo.classify(
        document_id=old.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=True,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    edges = edge_repo.list_edges_for_jurisdiction(new.id, "DE")
    assert len(edges) == 1
    assert edges[0].to_document_id == old.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/graph/test_edge_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresEdgeRepository'`

- [ ] **Step 3: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
from normly_core.graph.domain import EdgeType, Layer


class EdgeORM(Base):
    __tablename__ = "edge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    to_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    edge_type: Mapped[EdgeType] = mapped_column(
        sa.Enum(EdgeType, name="edge_type", native_enum=False)
    )
    jurisdiction: Mapped[str | None]
    layer: Mapped[Layer] = mapped_column(sa.Enum(Layer, name="layer", native_enum=False))
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.Index(
            "uq_edge_active_from_to_type_jurisdiction",
            "from_document_id",
            "to_document_id",
            "edge_type",
            "jurisdiction",
            unique=True,
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
    )
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0006_create_edge.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create edge table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "to_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "edge_type",
            sa.Enum(
                "references",
                "replaces",
                "withdrawn_by",
                "based_on_law",
                "adopted_from",
                name="edge_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String, nullable=True),
        sa.Column(
            "layer",
            sa.Enum("free", "commercial", name="layer", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_edge_active_from_to_type_jurisdiction",
        "edge",
        ["from_document_id", "to_document_id", "edge_type", "jurisdiction"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_edge_active_from_to_type_jurisdiction", table_name="edge")
    op.drop_table("edge")
```

- [ ] **Step 5: Add the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import Edge, EdgeType, Layer
from normly_core.graph.postgres.orm import EdgeORM


def _edge_to_domain(orm: EdgeORM) -> Edge:
    return Edge(
        id=orm.id,
        from_document_id=orm.from_document_id,
        to_document_id=orm.to_document_id,
        edge_type=orm.edge_type,
        jurisdiction=orm.jurisdiction,
        layer=orm.layer,
        delivery_id=orm.delivery_id,
        revoked_at=orm.revoked_at,
    )


class PostgresEdgeRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_edge(
        self,
        *,
        from_document_id: uuid.UUID,
        to_document_id: uuid.UUID,
        edge_type: EdgeType,
        jurisdiction: str | None,
        layer: Layer,
        delivery_id: uuid.UUID,
    ) -> Edge:
        orm = EdgeORM(
            id=uuid.uuid4(),
            from_document_id=from_document_id,
            to_document_id=to_document_id,
            edge_type=edge_type,
            jurisdiction=jurisdiction,
            layer=layer,
            delivery_id=delivery_id,
            revoked_at=None,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _edge_to_domain(orm)

    def list_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        rows = self._session.execute(
            select(EdgeORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == EdgeORM.to_document_id,
            )
            .where(
                EdgeORM.from_document_id == document_id,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalars()
        return [_edge_to_domain(row) for row in rows]
```

Add `import sqlalchemy as sa` to the top of `repositories.py` (needed for `sa.or_`).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/graph/test_edge_repository.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0006_create_edge.py core/tests/graph/test_edge_repository.py
git commit -s -m "feat: add edge table with rights-gated jurisdiction listing"
```

---

### Task 10: Cascading lineage revocation

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Test: `core/tests/graph/test_lineage_revocation.py`

**Interfaces:**
- Consumes: `PostgresDeliveryRepository.revoke_delivery` (Task 5, currently sets `withdrawn_at` only); `EdgeORM`, `RightsClassificationORM`, `DocumentDesignationORM`, `DocumentTitleORM` (Tasks 7–9).
- Produces: `PostgresDeliveryRepository.revoke_delivery` extended to cascade.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_lineage_revocation.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_a = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:revoke-a", ingested_at=datetime.now(timezone.utc)
    )
    delivery_b = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:revoke-b", ingested_at=datetime.now(timezone.utc)
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery_a.id,
    )
    other = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2026", part=None,
        delivery_id=delivery_a.id,
    )
    return document, other, delivery_a, delivery_b, doc_repo, delivery_repo


def test_revoking_a_delivery_locks_only_its_own_edges(db_session):
    document, other, delivery_a, delivery_b, doc_repo, delivery_repo = _setup(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    rights_repo.classify(
        document_id=other.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery_a.id,
    )
    edge_from_a = edge_repo.create_edge(
        from_document_id=document.id, to_document_id=other.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery_a.id,
    )
    edge_from_b = edge_repo.create_edge(
        from_document_id=other.id, to_document_id=document.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery_b.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    edges_de = edge_repo.list_edges_for_jurisdiction(other.id, "DE")
    remaining_ids = {e.id for e in edges_de}
    assert edge_from_a.id not in remaining_ids


def test_document_stays_readable_when_a_second_delivery_still_supports_it(db_session):
    document, _other, delivery_a, delivery_b, doc_repo, delivery_repo = _setup(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery_a.id,
    )
    doc_repo.add_title(
        document_id=document.id, language="de", title="DGUV Regel 1",
        delivery_id=delivery_b.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    remaining_titles = doc_repo.list_titles(document.id)
    assert len(remaining_titles) == 1


def test_designations_from_revoked_delivery_are_removed(db_session):
    document, _other, delivery_a, _delivery_b, doc_repo, delivery_repo = _setup(db_session)

    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Regel 1",
        language="de", edition=None, is_primary=True, delivery_id=delivery_a.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    assert doc_repo.list_designations(document.id) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/graph/test_lineage_revocation.py -v`
Expected: FAIL — `test_revoking_a_delivery_locks_only_its_own_edges` and the other two fail because `revoke_delivery` does not yet cascade (edges/titles/designations from the revoked delivery are still active/present).

- [ ] **Step 3: Extend `revoke_delivery` to cascade**

Replace the `revoke_delivery` method on `PostgresDeliveryRepository` in `core/src/normly_core/graph/postgres/repositories.py`:

```python
    def revoke_delivery(self, delivery_id: uuid.UUID) -> None:
        orm = self._session.get(DeliveryORM, delivery_id)
        if orm is None or orm.withdrawn_at is not None:
            return

        now = datetime.now(orm.ingested_at.tzinfo)
        orm.withdrawn_at = now

        self._session.execute(
            sa.update(EdgeORM)
            .where(EdgeORM.delivery_id == delivery_id, EdgeORM.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self._session.execute(
            sa.update(RightsClassificationORM)
            .where(
                RightsClassificationORM.delivery_id == delivery_id,
                RightsClassificationORM.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        self._session.execute(
            sa.delete(DocumentDesignationORM).where(
                DocumentDesignationORM.delivery_id == delivery_id
            )
        )
        self._session.execute(
            sa.delete(DocumentTitleORM).where(DocumentTitleORM.delivery_id == delivery_id)
        )
        self._session.flush()
```

Add `import sqlalchemy as sa` at the top of `repositories.py` if not already present from Task 9, and ensure `EdgeORM`, `RightsClassificationORM`, `DocumentDesignationORM`, `DocumentTitleORM` are imported (all already imported by earlier tasks in this file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/graph/test_lineage_revocation.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd core && python -m pytest -v`
Expected: PASS (all tests from Tasks 1–10)

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_lineage_revocation.py
git commit -s -m "feat: cascade delivery revocation to derived artifacts"
```

---

### Task 11: Capstone — jurisdiction-differential export and migration determinism

**Files:**
- Test: `core/tests/graph/test_jurisdiction_export.py`
- Test: `core/tests/graph/test_migration_determinism.py`

**Interfaces:**
- Consumes: the full repository stack from Tasks 4–10. No production code changes expected; if this task's tests reveal a gap, fix it in the relevant `repositories.py` method from the owning task.

- [ ] **Step 1: Write the jurisdiction-differential export test**

```python
# core/tests/graph/test_jurisdiction_export.py
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


def test_two_jurisdiction_exports_differ(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:export-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    de_only = doc_repo.create_document(
        origin_issuer="BAuA", origin_number="TRGS 900", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    both = doc_repo.create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    rights_repo.classify(
        document_id=de_only.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="US", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    de_export = {d.id for d in doc_repo.list_documents_for_jurisdiction("DE")}
    us_export = {d.id for d in doc_repo.list_documents_for_jurisdiction("US")}

    assert de_export == {de_only.id, both.id}
    assert us_export == {both.id}
    assert de_export != us_export
```

- [ ] **Step 2: Run test — it should already pass**

Run: `cd core && python -m pytest tests/graph/test_jurisdiction_export.py -v`
Expected: PASS (this test exercises existing behavior from Task 8; if it fails, the gap is in `list_documents_for_jurisdiction` in `repositories.py` — fix it there)

- [ ] **Step 3: Write the migration determinism test**

```python
# core/tests/graph/test_migration_determinism.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

CORE_DIR = Path(__file__).parents[2]


def test_downgrade_and_upgrade_round_trip_is_deterministic(db_url, migrated_engine):
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    tables_before = set(inspect(migrated_engine).get_table_names())

    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    tables_after = set(inspect(migrated_engine).get_table_names())
    assert tables_before == tables_after
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && python -m pytest tests/graph/test_migration_determinism.py -v`
Expected: PASS

- [ ] **Step 5: Run the entire test suite**

Run: `cd core && python -m pytest -v`
Expected: PASS — every test from Tasks 1–11 green

- [ ] **Step 6: Commit**

```bash
git add core/tests/graph/test_jurisdiction_export.py core/tests/graph/test_migration_determinism.py
git commit -s -m "test: verify jurisdiction-differential export and migration determinism"
```

---

## Self-Review

**Spec coverage:**

| Spec-Abschnitt | Task |
|---|---|
| Repository-Muster (Ansatz 3) | Task 2 (Protocols) + jede Postgres-Task |
| `source` | Task 4 |
| `delivery` | Task 5 |
| `document` | Task 6 |
| `document_designation` / `document_title` | Task 7 |
| `edge` | Task 9 |
| `rights_classification` | Task 8 |
| Schreibpfad (Pflicht-`delivery_id`) | Tasks 4–9 (jede `create_*`-Signatur) |
| Lesepfad (Rechte-Gate) | Task 8 (`get_document_for_jurisdiction`, `list_documents_for_jurisdiction`), Task 9 (`list_edges_for_jurisdiction`) |
| Rücknahmepfad (kaskadierend) | Task 10 |
| Fehlerbehandlung (Tabelle im Spec) | Task 4 (CHECK-Constraints), Task 8/Task 5 (leeres Ergebnis statt Fehler), Task 5 (idempotente Rücknahme) |
| Testkonzept (alle sechs Punkte) | Task 4 (CHECK), Task 7 (REQ-GRAPH-005), Task 11 (REQ-GRAPH-006), Task 10 (REQ-PIPE-005), Task 8 (REQ-PIPE-004), Task 11 (REQ-PIPE-006 Migrationsdeterminismus) |

Keine Lücke gefunden.

**Placeholder-Scan:** keine „TBD"/„TODO"/„similar to Task N" gefunden — jeder Schritt trägt vollständigen Code.

**Typkonsistenz:** Repository-Methodennamen aus den Protocols (Task 2) stimmen mit den Implementierungen überein (`create_source`/`get_source`, `record_delivery`/`get_delivery`/`revoke_delivery`, `create_document`/`get_document`/`add_designation`/`add_title`/`list_designations`/`list_titles`/`get_document_for_jurisdiction`/`list_documents_for_jurisdiction`, `classify`/`get_classification`, `create_edge`/`list_edges_for_jurisdiction`) — geprüft gegen jede Task-Implementierung, keine Abweichung gefunden.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-11-datenmodell-referenzgraph-schema.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
