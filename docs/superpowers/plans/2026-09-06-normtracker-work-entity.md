# Normtracker Work-Entität Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a `Work` entity in `core/` that gives every Regelwerk one logical identity across its editions and national adoptions, fulfilling REQ-GRAPH-005's acceptance criterion, per `docs/superpowers/specs/2026-09-06-normtracker-work-entity-design.md`.

**Architecture:** A new `work` table holds only identity/lifecycle state (`id`, `status`, `merged_into_work_id`, `created_via`, `created_at`) — no titles or content. `document.work_id` becomes a required foreign key. The ingestion pipeline assigns `work_id` automatically from explicit `REPLACES`/`WITHDRAWN_BY`/`ADOPTED_FROM` signals already present in `RawRecord.raw_references`; anything else gets its own new Work. `IdentityResolutionCase` gains a `work_merge` case type for a curator to later merge two Works a matching signal missed.

**Tech Stack:** Python, SQLAlchemy ORM, Alembic migrations, pytest + testcontainers (`pgvector/pgvector:pg16`), all inside `core/`.

## Global Constraints

- Every commit: `git commit -s` (DCO) plus a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer. Never a second `Signed-off-by` from the AI.
- SPDX header on every new file, exactly:
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors
  ```
- No direct push to `main`. Work happens on its own branch off the current `main` (already includes merged PR #10). Push/PR/merge only after the user explicitly confirms — STACKIT CI runners are billed per run and there is no working cancel API on this instance.
- Database access only through the repository layer (`core/src/normly_core/graph/postgres/repositories.py`) — no raw SQL or graph-specific queries in pipeline/application code. Migrations are the one place raw/Core SQL against table names is expected.
- `Work` carries no delivery lineage of its own (it has no content) — only `Document` rows keep `created_via_delivery_id`. No task adds a `delivery_id` column to `work`.
- Every migration must be safe to run twice with no different outcome (idempotent), and every migration's `downgrade()` must actually work — `core/tests/graph/test_migration_determinism.py` round-trips the entire chain from `head` to `base` and back on the shared test database.
- `case_type=work_merge` on `IdentityResolutionCase` is orthogonal to `case_type=new_document`; no task changes the meaning or call sites of the existing `enqueue_case`/`resolve_case`/`reject_case` behavior for `new_document` cases beyond adding the new `case_type` column (default `new_document`).
- Only `REPLACES`, `WITHDRAWN_BY`, `ADOPTED_FROM` edges ever imply shared Work membership. `REFERENCES` and `BASED_ON_LAW` never do, in any task.
- No task touches `api/`, `accounts/`, or `chat/`. Exposing `work_id` over the HTTP API is deliberately out of scope here (no consumer needs it yet — Teilprojekt 2, semantic search, is where grouping-by-Work first has an API-facing use). Nothing in this plan blocks that later work.

---

### Task 1: Work entity — domain type, ORM model, Postgres repository, migration

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add near the `IdentityResolutionCase` section, before line 482)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (add after `DocumentTitleORM`, before line 165)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add near `PostgresDocumentRepository`, e.g. after line 316, before the `_rights_to_domain` helper)
- Create: `core/migrations/versions/0020_create_work.py`
- Create: `core/tests/graph/test_work_repository.py`

**Interfaces:**
- Produces: `WorkStatus` (`str, Enum`: `ACTIVE = "active"`, `MERGED = "merged"`), `WorkCreatedVia` (`str, Enum`: `AUTO_MATCHED = "auto_matched"`, `MANUAL = "manual"`), `Work` (frozen dataclass: `id: uuid.UUID`, `status: WorkStatus`, `merged_into_work_id: uuid.UUID | None`, `created_via: WorkCreatedVia`, `created_at: datetime`), `WorkRepository` Protocol with `create_work(self, *, created_via: WorkCreatedVia) -> Work` and `get_work(self, work_id: uuid.UUID) -> Work | None`, `PostgresWorkRepository` implementing it. `get_work` transparently follows a single `merged_into_work_id` redirect when the looked-up Work has `status=MERGED` (Task 4 guarantees a merge target is always `ACTIVE`, so one hop always suffices).
- Consumes: nothing from other tasks (this is the foundation).

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_work_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import WorkCreatedVia, WorkStatus
from normly_core.graph.postgres.orm import WorkORM
from normly_core.graph.postgres.repositories import PostgresWorkRepository


def test_create_work_defaults_to_active(db_session):
    repo = PostgresWorkRepository(db_session)

    work = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)

    assert work.status == WorkStatus.ACTIVE
    assert work.merged_into_work_id is None
    assert work.created_via == WorkCreatedVia.AUTO_MATCHED


def test_get_work_returns_none_for_unknown_id(db_session):
    repo = PostgresWorkRepository(db_session)

    assert repo.get_work(uuid.uuid4()) is None


def test_get_work_returns_the_active_work(db_session):
    repo = PostgresWorkRepository(db_session)
    work = repo.create_work(created_via=WorkCreatedVia.MANUAL)

    found = repo.get_work(work.id)

    assert found == work


def test_get_work_redirects_through_a_merged_work(db_session):
    repo = PostgresWorkRepository(db_session)
    target = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    source = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)

    # Task 4 adds the real merge operation (resolve_work_merge_case). Here we
    # only need a merged Work to exist to prove get_work()'s read-side
    # redirect works -- so the merge is set up directly via the ORM.
    orm = db_session.get(WorkORM, source.id)
    orm.status = WorkStatus.MERGED
    orm.merged_into_work_id = target.id
    db_session.flush()

    found = repo.get_work(source.id)

    assert found.id == target.id
    assert found.status == WorkStatus.ACTIVE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'WorkCreatedVia'` (nothing exists yet).

- [ ] **Step 3: Add the domain types**

In `core/src/normly_core/graph/domain.py`, insert immediately before line 482 (`class IdentityResolutionStatus(str, Enum):`):

```python
class WorkStatus(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"


class WorkCreatedVia(str, Enum):
    AUTO_MATCHED = "auto_matched"
    MANUAL = "manual"


@dataclass(frozen=True)
class Work:
    id: uuid.UUID
    status: WorkStatus
    merged_into_work_id: uuid.UUID | None
    created_via: WorkCreatedVia
    created_at: datetime


class WorkRepository(Protocol):
    def create_work(self, *, created_via: WorkCreatedVia) -> Work: ...

    def get_work(self, work_id: uuid.UUID) -> Work | None:
        """
        Look up a Work by id. If it has been merged into another Work
        (`status == MERGED`), returns the target Work it was merged into
        instead -- callers never see a retired Work as if it were current.
        """
        ...


class ContradictoryWorkMergeError(Exception):
    def __init__(self, source_work_id: uuid.UUID, target_work_id: uuid.UUID):
        self.source_work_id = source_work_id
        self.target_work_id = target_work_id
        super().__init__(
            f"cannot merge work {source_work_id} into {target_work_id}: "
            "same work, or target is not active"
        )
```

(`ContradictoryWorkMergeError` is not used until Task 4, but lives here alongside `Work` since it is a Work-lifecycle error, matching how `WithdrawnDeliveryError` sits next to `Delivery` rather than next to whatever repository happens to raise it.)

- [ ] **Step 4: Add the ORM model**

In `core/src/normly_core/graph/postgres/orm.py`, add `WorkCreatedVia` and `WorkStatus` to the import block at the top (lines 13-22), so it reads:

```python
from normly_core.graph.domain import (
    AccountTokenPurpose,
    ChatAnswerType,
    ChatMessageRole,
    EdgeType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    Layer,
    TdmOptOutResult,
    WorkCreatedVia,
    WorkStatus,
)
```

Then insert this new class after `DocumentTitleORM` ends (after line 163, before `class RightsClassificationORM(Base):` at line 165):

```python
class WorkORM(Base):
    __tablename__ = "work"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[WorkStatus] = mapped_column(
        sa.Enum(
            WorkStatus,
            name="work_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        default=WorkStatus.ACTIVE,
    )
    merged_into_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
    )
    created_via: Mapped[WorkCreatedVia] = mapped_column(
        sa.Enum(
            WorkCreatedVia,
            name="work_created_via",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

- [ ] **Step 5: Add the Postgres repository**

In `core/src/normly_core/graph/postgres/repositories.py`, add `Work`, `WorkCreatedVia`, `WorkStatus` to the domain import block (lines 13-41) and `WorkORM` to the ORM import block (lines 43-60). Then insert after `PostgresDocumentRepository` ends (after line 316, before `def _rights_to_domain`):

```python
def _work_to_domain(orm: WorkORM) -> Work:
    return Work(
        id=orm.id,
        status=orm.status,
        merged_into_work_id=orm.merged_into_work_id,
        created_via=orm.created_via,
        created_at=orm.created_at,
    )


class PostgresWorkRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_work(self, *, created_via: WorkCreatedVia) -> Work:
        orm = WorkORM(id=uuid.uuid4(), status=WorkStatus.ACTIVE, created_via=created_via)
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _work_to_domain(orm)

    def get_work(self, work_id: uuid.UUID) -> Work | None:
        orm = self._session.get(WorkORM, work_id)
        if orm is None:
            return None
        if orm.status == WorkStatus.MERGED and orm.merged_into_work_id is not None:
            orm = self._session.get(WorkORM, orm.merged_into_work_id)
        return _work_to_domain(orm)
```

- [ ] **Step 6: Write the migration**

Create `core/migrations/versions/0020_create_work.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create work table

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            sa.Enum(
                "active", "merged",
                name="work_status", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "merged_into_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True,
        ),
        sa.Column(
            "created_via",
            sa.Enum(
                "auto_matched", "manual",
                name="work_created_via", native_enum=False, create_constraint=True,
            ),
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
    op.drop_table("work")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_repository.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v`
Expected: PASS. (The migration-consistency and determinism tests are the existing whole-schema guards described in Global Constraints — run them from Task 1 onward, every task, since they run against the shared `migrated_engine` fixture and will immediately show if a new migration or ORM model drifted.)

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0020_create_work.py core/tests/graph/test_work_repository.py
git commit -s -m "feat(core): add Work entity for the Normtracker reference graph

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `document.work_id` — required foreign key with an implicit default

**Files:**
- Modify: `core/src/normly_core/graph/domain.py:85-93` (`Document` dataclass), `core/src/normly_core/graph/domain.py:204-212` (`DocumentRepository.create_document` Protocol)
- Modify: `core/src/normly_core/graph/postgres/orm.py:104-119` (`DocumentORM`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py:283-291` (`_document_to_domain`), `core/src/normly_core/graph/postgres/repositories.py:322-343` (`PostgresDocumentRepository.create_document`)
- Create: `core/migrations/versions/0021_add_document_work_id.py`
- Create: `core/tests/graph/test_document_work_id.py`

**Interfaces:**
- Consumes: `Work`, `WorkCreatedVia`, `WorkStatus`, `PostgresWorkRepository` from Task 1.
- Produces: `Document.work_id: uuid.UUID` (always set, never `None` once this task lands). `create_document(..., work_id: uuid.UUID | None = None)`: when `work_id` is omitted, the repository creates a fresh `Work` (`created_via=WorkCreatedVia.AUTO_MATCHED`) and uses its id — this is the "no signal → new 1:1 Work" default rule from the spec, implemented once here so every other existing call site (pipeline, ~30 pre-existing tests) keeps working unchanged. When `work_id` is given explicitly, it is stored as-is (Task 5 is the only caller that ever passes it).

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_document_work_id.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash="sha256:work-id-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_create_document_without_work_id_gets_its_own_new_work(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    assert document.work_id is not None
    work = PostgresWorkRepository(db_session).get_work(document.work_id)
    assert work.created_via == WorkCreatedVia.AUTO_MATCHED


def test_create_document_without_work_id_gets_distinct_works(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    first = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )

    assert first.work_id != second.work_id


def test_create_document_honours_an_explicit_work_id(db_session):
    delivery = _make_delivery(db_session)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_repo = PostgresDocumentRepository(db_session)

    first = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=work.id,
    )
    second = doc_repo.create_document(
        origin_issuer="BS", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=work.id,
    )

    assert first.work_id == work.id
    assert second.work_id == work.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_work_id.py -v`
Expected: FAIL — `TypeError: create_document() got an unexpected keyword argument 'work_id'` does not yet apply; instead the first assertion fails with `AttributeError: 'Document' object has no attribute 'work_id'`.

- [ ] **Step 3: Add `work_id` to the `Document` dataclass and Protocol**

In `core/src/normly_core/graph/domain.py`, replace lines 85-93:

```python
@dataclass(frozen=True)
class Document:
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    work_id: uuid.UUID
    created_via_delivery_id: uuid.UUID
    created_at: datetime
```

And replace the `create_document` method in the `DocumentRepository` Protocol (lines 204-212):

```python
    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
        work_id: uuid.UUID | None = None,
    ) -> Document:
        """
        `work_id` is the pipeline's explicit assignment when an ingestion
        signal (REPLACES/WITHDRAWN_BY/ADOPTED_FROM to a known document)
        resolved one -- see `normly_core.pipeline.work_assignment`. Omitted,
        the repository creates a fresh 1:1 Work for this document, which is
        the correct default whenever nothing links it to an existing one.
        """
        ...
```

- [ ] **Step 4: Add the `work_id` column to `DocumentORM`**

In `core/src/normly_core/graph/postgres/orm.py`, replace lines 104-119 (`DocumentORM`):

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
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
    created_via_delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

- [ ] **Step 5: Update `_document_to_domain` and `create_document`**

In `core/src/normly_core/graph/postgres/repositories.py`, add `WorkCreatedVia`, `WorkStatus` and `WorkORM` to the existing import blocks if not already present from Task 1 (they are — Task 1 added them). Replace `_document_to_domain` (lines 283-291):

```python
def _document_to_domain(orm: DocumentORM) -> Document:
    return Document(
        id=orm.id,
        origin_issuer=orm.origin_issuer,
        origin_number=orm.origin_number,
        edition=orm.edition,
        part=orm.part,
        work_id=orm.work_id,
        created_via_delivery_id=orm.created_via_delivery_id,
        created_at=orm.created_at,
    )
```

Replace `create_document` inside `PostgresDocumentRepository` (lines 322-343):

```python
    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
        work_id: uuid.UUID | None = None,
    ) -> Document:
        _require_active_delivery(self._session, delivery_id)
        if work_id is None:
            work = WorkORM(id=uuid.uuid4(), status=WorkStatus.ACTIVE, created_via=WorkCreatedVia.AUTO_MATCHED)
            self._session.add(work)
            self._session.flush()
            work_id = work.id
        orm = DocumentORM(
            id=uuid.uuid4(),
            origin_issuer=origin_issuer,
            origin_number=origin_number,
            edition=edition,
            part=part,
            work_id=work_id,
            created_via_delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _document_to_domain(orm)
```

- [ ] **Step 6: Write the migration (nullable column first)**

Create `core/migrations/versions/0021_add_document_work_id.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add nullable document.work_id column

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document",
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document", "work_id")
```

(It stays nullable here on purpose — Task 3's backfill migration needs to find pre-existing documents by `work_id IS NULL`, and Task 3 flips it to `NOT NULL` only once the backfill has run.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_work_id.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full existing core test suite to confirm no regressions**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS — every pre-existing `create_document(...)` call site (there are ~30 across `core/tests/`) omits `work_id` and keeps working via the new default; none of them need editing.

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0021_add_document_work_id.py core/tests/graph/test_document_work_id.py
git commit -s -m "feat(core): add document.work_id with an implicit default Work

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Backfill migration + `NOT NULL`

**Files:**
- Create: `core/migrations/versions/0022_backfill_document_work_id.py`
- Create: `core/migrations/versions/0023_document_work_id_not_null.py`
- Create: `core/tests/graph/test_work_backfill_migration.py`

**Interfaces:**
- Consumes: the `work` table and nullable `document.work_id` column from Tasks 1-2. This task's migrations use plain SQLAlchemy Core (`sa.table`/`sa.column` proxies), never the application's ORM classes — migrations must stand on their own even if the ORM shape changes later.
- Produces: every existing `document` row has a non-null `work_id`; `document.work_id` is `NOT NULL` from this point on.

- [ ] **Step 1: Write the failing test**

Create `core/tests/graph/test_work_backfill_migration.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

CORE_DIR = Path(__file__).parents[2]


def test_backfill_groups_documents_by_replaces_and_adopted_from_edges(db_url, migrated_engine):
    # Drives Alembic directly against the shared, session-scoped
    # `migrated_engine`, like test_migration_determinism.py -- mutates
    # schema state in place and relies on non-parallel test ordering to
    # leave the database at "head" again before any other test runs.
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.downgrade(alembic_cfg, "0021")

    source_id = uuid.uuid4()
    delivery_id = uuid.uuid4()
    doc_2015, doc_2018, doc_bs, doc_unrelated = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    )

    with migrated_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO source (id, publisher, retrieval_path, legal_basis_category, "
                "jurisdiction, reviewed_at, responsible_person, commercial_catalog) "
                "VALUES (:id, 'Test', 'file:///dev/null', 'A', 'DE', CURRENT_DATE, 'J. Weber', false)"
            ),
            {"id": source_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO delivery (id, source_id, content_hash, ingested_at) "
                "VALUES (:id, :source_id, 'sha256:backfill-fixture', now())"
            ),
            {"id": delivery_id, "source_id": source_id},
        )
        for doc_id, issuer, number, edition in [
            (doc_2015, "DIN", "EN ISO 9001", "2015"),
            (doc_2018, "DIN", "EN ISO 9001", "2018"),
            (doc_bs, "BS", "EN ISO 9001", "2018"),
            (doc_unrelated, "DGUV", "Vorschrift 1", "2020"),
        ]:
            connection.execute(
                sa.text(
                    "INSERT INTO document (id, origin_issuer, origin_number, edition, "
                    "created_via_delivery_id) VALUES (:id, :issuer, :number, :edition, :delivery_id)"
                ),
                {
                    "id": doc_id, "issuer": issuer, "number": number, "edition": edition,
                    "delivery_id": delivery_id,
                },
            )
        # doc_2018 REPLACES doc_2015; doc_bs is ADOPTED_FROM doc_2018 -- all
        # three must end up in one Work. doc_unrelated shares no edge with
        # them and must get its own.
        for from_id, to_id, edge_type in [
            (doc_2018, doc_2015, "replaces"),
            (doc_bs, doc_2018, "adopted_from"),
        ]:
            connection.execute(
                sa.text(
                    "INSERT INTO edge (id, from_document_id, to_document_id, edge_type, layer, "
                    "delivery_id) VALUES (:id, :from_id, :to_id, :edge_type, 'free', :delivery_id)"
                ),
                {
                    "id": uuid.uuid4(), "from_id": from_id, "to_id": to_id,
                    "edge_type": edge_type, "delivery_id": delivery_id,
                },
            )

    command.upgrade(alembic_cfg, "0022")

    with migrated_engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT id, work_id FROM document WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": [doc_2015, doc_2018, doc_bs, doc_unrelated]},
        ).all()

    work_id_by_doc = {row.id: row.work_id for row in rows}
    assert work_id_by_doc[doc_2015] == work_id_by_doc[doc_2018] == work_id_by_doc[doc_bs]
    assert work_id_by_doc[doc_unrelated] != work_id_by_doc[doc_2015]
    assert all(work_id is not None for work_id in work_id_by_doc.values())

    command.upgrade(alembic_cfg, "head")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_backfill_migration.py -v`
Expected: FAIL — `alembic.util.exc.CommandError` (revision "0022" does not exist yet), or the `command.upgrade(alembic_cfg, "0022")` call fails since work_id stays NULL (no backfill logic yet).

- [ ] **Step 3: Write the backfill migration**

Create `core/migrations/versions/0022_backfill_document_work_id.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""backfill document.work_id via union-find over replaces/withdrawn_by/adopted_from edges

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-06
"""

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_WORK_LINKING_EDGE_TYPES = ("replaces", "withdrawn_by", "adopted_from")

document_table = sa.table(
    "document", sa.column("id", UUID(as_uuid=True)), sa.column("work_id", UUID(as_uuid=True))
)
edge_table = sa.table(
    "edge",
    sa.column("from_document_id", UUID(as_uuid=True)),
    sa.column("to_document_id", UUID(as_uuid=True)),
    sa.column("edge_type", sa.String),
)
work_table = sa.table(
    "work",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("status", sa.String),
    sa.column("created_via", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    connection = op.get_bind()

    # Idempotency guard: only documents still missing a work_id are grouped.
    # A second run of this migration finds nothing left to do and changes
    # nothing.
    unassigned_ids = [
        row.id
        for row in connection.execute(
            sa.select(document_table.c.id).where(document_table.c.work_id.is_(None))
        )
    ]
    if not unassigned_ids:
        return

    parent: dict[uuid.UUID, uuid.UUID] = {doc_id: doc_id for doc_id in unassigned_ids}

    def find(x: uuid.UUID) -> uuid.UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: uuid.UUID, b: uuid.UUID) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # One-time whole-graph traversal for this backfill only -- not a
    # pattern for application code, which stays at 1-3 hops per ADR-006.
    edges = connection.execute(
        sa.select(edge_table.c.from_document_id, edge_table.c.to_document_id).where(
            edge_table.c.edge_type.in_(_WORK_LINKING_EDGE_TYPES),
            edge_table.c.from_document_id.in_(unassigned_ids),
            edge_table.c.to_document_id.in_(unassigned_ids),
        )
    )
    for from_id, to_id in edges:
        union(from_id, to_id)

    groups: dict[uuid.UUID, list[uuid.UUID]] = {}
    for doc_id in unassigned_ids:
        groups.setdefault(find(doc_id), []).append(doc_id)

    now = datetime.now(timezone.utc)
    for members in groups.values():
        work_id = uuid.uuid4()
        connection.execute(
            work_table.insert().values(
                id=work_id, status="active", created_via="auto_matched", created_at=now,
            )
        )
        connection.execute(
            document_table.update()
            .where(document_table.c.id.in_(members))
            .values(work_id=work_id)
        )


def downgrade() -> None:
    # No data to reverse here: 0021's downgrade drops the work_id column and
    # 0020's downgrade drops the work table, which together undo everything
    # this migration wrote. Splitting the undo across those two migrations
    # (rather than deleting rows here first) avoids foreign-key ordering
    # hazards between this migration and whatever downstream rows may by
    # then reference a Work this backfill created.
    pass
```

- [ ] **Step 4: Write the `NOT NULL` migration**

Create `core/migrations/versions/0023_document_work_id_not_null.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""make document.work_id not null

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-06
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document", "work_id", nullable=False)


def downgrade() -> None:
    op.alter_column("document", "work_id", nullable=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_backfill_migration.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/migrations/versions/0022_backfill_document_work_id.py core/migrations/versions/0023_document_work_id_not_null.py core/tests/graph/test_work_backfill_migration.py
git commit -s -m "feat(core): backfill document.work_id and enforce NOT NULL

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: `IdentityResolutionCase` work-merge extension

**Files:**
- Modify: `core/src/normly_core/graph/domain.py:482-520` (`IdentityResolutionStatus`, `IdentityResolutionCase`, `IdentityResolutionRepository`)
- Modify: `core/src/normly_core/graph/postgres/orm.py:300-329` (`IdentityResolutionCaseORM`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py:1089-1157` (`_identity_case_to_domain`, `PostgresIdentityResolutionRepository`)
- Create: `core/migrations/versions/0024_add_identity_resolution_case_work_fields.py`
- Create: `core/tests/graph/test_identity_resolution_work_merge.py`

**Interfaces:**
- Consumes: `Work`, `WorkStatus`, `WorkORM`, `PostgresWorkRepository.create_work` from Task 1; `PostgresDocumentRepository.create_document(..., work_id=...)` from Task 2; `ContradictoryWorkMergeError` from Task 1.
- Produces: `IdentityResolutionCaseType` (`str, Enum`: `NEW_DOCUMENT = "new_document"`, `WORK_MERGE = "work_merge"`). `IdentityResolutionCase` gains `case_type`, `source_work_id: uuid.UUID | None`, `target_work_id: uuid.UUID | None`; `raw_designation` becomes `str | None`. `IdentityResolutionRepository` gains `enqueue_work_merge_case(self, *, delivery_id: uuid.UUID, source_work_id: uuid.UUID, target_work_id: uuid.UUID, reason: str) -> IdentityResolutionCase` and `resolve_work_merge_case(self, case_id: uuid.UUID, *, resolved_by: str) -> IdentityResolutionCase`. `resolve_work_merge_case` reassigns every `Document.work_id` from `source_work_id` to `target_work_id`, sets the source Work to `status=MERGED` with `merged_into_work_id=target_work_id`, and raises `ContradictoryWorkMergeError` if `source_work_id == target_work_id` or the target Work is not `ACTIVE` — nothing is written in that case.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_identity_resolution_work_merge.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import (
    ContradictoryWorkMergeError,
    IdentityResolutionCaseType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    WorkCreatedVia,
    WorkStatus,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash="sha256:work-merge-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_enqueue_work_merge_case(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    source_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    target_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    repo = PostgresIdentityResolutionRepository(db_session)

    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=source_work.id, target_work_id=target_work.id,
        reason="curator_identified_duplicate",
    )

    assert case.case_type == IdentityResolutionCaseType.WORK_MERGE
    assert case.source_work_id == source_work.id
    assert case.target_work_id == target_work.id
    assert case.raw_designation is None
    assert case in repo.list_pending_cases()


def test_resolve_work_merge_case_reassigns_documents_and_retires_source(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    source_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    target_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_doc = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=source_work.id,
    )
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=source_work.id, target_work_id=target_work.id,
        reason="curator_identified_duplicate",
    )

    resolved = repo.resolve_work_merge_case(case.id, resolved_by="J. Weber")

    assert resolved.status == IdentityResolutionStatus.RESOLVED
    moved_doc = doc_repo.get_document_unchecked(din_doc.id)
    assert moved_doc.work_id == target_work.id
    merged_source = work_repo.get_work(source_work.id)
    assert merged_source.id == target_work.id  # get_work redirects transparently
    assert case not in repo.list_pending_cases()


def test_resolve_work_merge_case_rejects_self_merge(db_session):
    delivery = _make_delivery(db_session)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=work.id, target_work_id=work.id,
        reason="bad_case",
    )

    with pytest.raises(ContradictoryWorkMergeError):
        repo.resolve_work_merge_case(case.id, resolved_by="J. Weber")


def test_resolve_work_merge_case_rejects_an_already_merged_target(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)
    a = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    b = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    c = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    first_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=a.id, target_work_id=b.id, reason="merge-a-into-b",
    )
    repo.resolve_work_merge_case(first_merge.id, resolved_by="J. Weber")
    second_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=c.id, target_work_id=a.id, reason="merge-c-into-a",
    )

    with pytest.raises(ContradictoryWorkMergeError):
        repo.resolve_work_merge_case(second_merge.id, resolved_by="J. Weber")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_identity_resolution_work_merge.py -v`
Expected: FAIL — `ImportError: cannot import name 'IdentityResolutionCaseType'`.

- [ ] **Step 3: Extend the domain types**

In `core/src/normly_core/graph/domain.py`, replace lines 482-520 (`IdentityResolutionStatus` through the end of `IdentityResolutionRepository`):

```python
class IdentityResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class IdentityResolutionCaseType(str, Enum):
    NEW_DOCUMENT = "new_document"
    WORK_MERGE = "work_merge"


@dataclass(frozen=True)
class IdentityResolutionCase:
    id: uuid.UUID
    delivery_id: uuid.UUID
    case_type: IdentityResolutionCaseType
    raw_designation: str | None
    raw_issuer: str | None
    reason: str
    status: IdentityResolutionStatus
    resolved_document_id: uuid.UUID | None
    source_work_id: uuid.UUID | None
    target_work_id: uuid.UUID | None
    resolved_at: datetime | None
    resolved_by: str | None
    created_at: datetime


class IdentityResolutionRepository(Protocol):
    def enqueue_case(
        self,
        *,
        delivery_id: uuid.UUID,
        raw_designation: str,
        raw_issuer: str | None,
        reason: str,
    ) -> IdentityResolutionCase: ...

    def enqueue_work_merge_case(
        self,
        *,
        delivery_id: uuid.UUID,
        source_work_id: uuid.UUID,
        target_work_id: uuid.UUID,
        reason: str,
    ) -> IdentityResolutionCase: ...

    def list_pending_cases(self) -> list[IdentityResolutionCase]: ...

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase: ...

    def resolve_work_merge_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase:
        """
        Reassign every Document.work_id from the case's source_work_id to its
        target_work_id, mark the source Work MERGED, and mark the case
        RESOLVED. Raises ContradictoryWorkMergeError -- writing nothing -- if
        source_work_id == target_work_id or the target Work is not ACTIVE
        (already merged elsewhere).
        """
        ...

    def reject_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase: ...
```

- [ ] **Step 4: Extend the ORM model**

In `core/src/normly_core/graph/postgres/orm.py`, add `IdentityResolutionCaseType` to the domain import block, then replace `IdentityResolutionCaseORM` (lines 300-329):

```python
class IdentityResolutionCaseORM(Base):
    __tablename__ = "identity_resolution_case"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    case_type: Mapped[IdentityResolutionCaseType] = mapped_column(
        sa.Enum(
            IdentityResolutionCaseType,
            name="identity_resolution_case_type",
            native_enum=False,
            values_callable=_enum_values,
            create_constraint=True,
        ),
        default=IdentityResolutionCaseType.NEW_DOCUMENT,
    )
    raw_designation: Mapped[str | None]
    raw_issuer: Mapped[str | None]
    reason: Mapped[str]
    status: Mapped[IdentityResolutionStatus] = mapped_column(
        sa.Enum(
            IdentityResolutionStatus,
            name="identity_resolution_status",
            native_enum=False,
            values_callable=_enum_values,
            create_constraint=True,
        ),
        default=IdentityResolutionStatus.PENDING,
    )
    resolved_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id")
    )
    source_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
    )
    target_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolved_by: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

- [ ] **Step 5: Extend the Postgres repository**

In `core/src/normly_core/graph/postgres/repositories.py`, add `IdentityResolutionCaseType` and `ContradictoryWorkMergeError` to the domain import block. Replace `_identity_case_to_domain` (lines 1089-1101):

```python
def _identity_case_to_domain(orm: IdentityResolutionCaseORM) -> IdentityResolutionCase:
    return IdentityResolutionCase(
        id=orm.id,
        delivery_id=orm.delivery_id,
        case_type=orm.case_type,
        raw_designation=orm.raw_designation,
        raw_issuer=orm.raw_issuer,
        reason=orm.reason,
        status=orm.status,
        resolved_document_id=orm.resolved_document_id,
        source_work_id=orm.source_work_id,
        target_work_id=orm.target_work_id,
        resolved_at=orm.resolved_at,
        resolved_by=orm.resolved_by,
        created_at=orm.created_at,
    )
```

Then, inside `PostgresIdentityResolutionRepository` (starting at line 1104), add two new methods after `enqueue_case` (after line 1112, before `list_pending_cases`):

```python
    def enqueue_work_merge_case(
        self, *, delivery_id: uuid.UUID, source_work_id: uuid.UUID,
        target_work_id: uuid.UUID, reason: str,
    ) -> IdentityResolutionCase:
        _require_active_delivery(self._session, delivery_id)
        orm = IdentityResolutionCaseORM(
            id=uuid.uuid4(),
            delivery_id=delivery_id,
            case_type=IdentityResolutionCaseType.WORK_MERGE,
            raw_designation=None,
            raw_issuer=None,
            reason=reason,
            status=IdentityResolutionStatus.PENDING,
            source_work_id=source_work_id,
            target_work_id=target_work_id,
        )
        self._session.add(orm)
        self._session.flush()
        return _identity_case_to_domain(orm)
```

And add `resolve_work_merge_case` after `resolve_case` (after line 1146, before `reject_case`):

```python
    def resolve_work_merge_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        source_work = self._session.get(WorkORM, orm.source_work_id)
        target_work = self._session.get(WorkORM, orm.target_work_id)
        if orm.source_work_id == orm.target_work_id or target_work.status != WorkStatus.ACTIVE:
            raise ContradictoryWorkMergeError(orm.source_work_id, orm.target_work_id)

        self._session.execute(
            sa.update(DocumentORM)
            .where(DocumentORM.work_id == orm.source_work_id)
            .values(work_id=orm.target_work_id)
        )
        source_work.status = WorkStatus.MERGED
        source_work.merged_into_work_id = orm.target_work_id

        orm.status = IdentityResolutionStatus.RESOLVED
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)
```

- [ ] **Step 6: Write the migration**

Create `core/migrations/versions/0024_add_identity_resolution_case_work_fields.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add case_type and work-merge fields to identity_resolution_case

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "identity_resolution_case",
        sa.Column(
            "case_type",
            sa.Enum(
                "new_document", "work_merge",
                name="identity_resolution_case_type", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="new_document",
        ),
    )
    # raw_designation is meaningless for a work_merge case (there is no raw
    # ingested string to show) -- loosened rather than filled with a
    # placeholder string a reviewer might mistake for real ingestion data.
    op.alter_column("identity_resolution_case", "raw_designation", nullable=True)
    op.add_column(
        "identity_resolution_case",
        sa.Column("source_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )
    op.add_column(
        "identity_resolution_case",
        sa.Column("target_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("identity_resolution_case", "target_work_id")
    op.drop_column("identity_resolution_case", "source_work_id")
    op.execute(
        "UPDATE identity_resolution_case SET raw_designation = '' WHERE raw_designation IS NULL"
    )
    op.alter_column("identity_resolution_case", "raw_designation", nullable=False)
    op.drop_column("identity_resolution_case", "case_type")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_identity_resolution_work_merge.py tests/graph/test_identity_resolution_case_repository.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v`
Expected: PASS — including the pre-existing `test_identity_resolution_case_repository.py`, unmodified, since `enqueue_case`/`resolve_case`/`reject_case` keep their exact signatures and now just also populate `case_type=NEW_DOCUMENT` by default.

- [ ] **Step 8: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0024_add_identity_resolution_case_work_fields.py core/tests/graph/test_identity_resolution_work_merge.py
git commit -s -m "feat(core): add work_merge case type to IdentityResolutionCase

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Pipeline integration — automatic Work assignment during ingestion

**Files:**
- Create: `core/src/normly_core/pipeline/work_assignment.py`
- Modify: `core/src/normly_core/pipeline/runner.py:92-100` (the `is_new` branch of `process()`)
- Create: `core/tests/pipeline/test_work_assignment.py`
- Create: `core/tests/pipeline/test_runner_work_assignment.py`

**Interfaces:**
- Consumes: `RawRecord`, `RawReference` (`core/src/normly_core/pipeline/domain.py`, unchanged), `EdgeType` (`core/src/normly_core/graph/domain.py`, unchanged), `DocumentRepository.find_by_designation` (unchanged), `DocumentRepository.create_document(..., work_id=...)` from Task 2.
- Produces: `WorkAssignmentResult` (frozen dataclass: `work_id: uuid.UUID | None`, `is_ambiguous: bool`, `reason: str | None`) and `determine_work_assignment(record: RawRecord, document_repo: DocumentRepository) -> WorkAssignmentResult` in `core/src/normly_core/pipeline/work_assignment.py`. Modifies `runner.py`'s `process()` to call it in the `result.is_new` branch, mirroring how `identity.resolve()`'s ambiguous branch already works.

- [ ] **Step 1: Write the failing unit tests for `determine_work_assignment`**

Create `core/tests/pipeline/test_work_assignment.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference
from normly_core.pipeline.work_assignment import determine_work_assignment


def _make_delivery(db_session, content_hash="sha256:work-assignment-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_record(raw_references):
    return RawRecord(
        source_id=None, content_hash="sha256:record", raw_designation="BS EN ISO 9001:2018",
        raw_issuer="BS", raw_title=None, full_text=None, raw_references=raw_references,
    )


def test_no_references_means_no_signal(db_session):
    doc_repo = PostgresDocumentRepository(db_session)

    result = determine_work_assignment(_make_record([]), doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_a_references_only_edge_gives_no_signal(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    target = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=target.id, issuer="EU", designation="2006/42/EC", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.REFERENCES)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_an_adopted_from_signal_to_a_known_document_reuses_its_work(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    target = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=target.id, issuer="DIN", designation="EN ISO 9001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2018", edge_type=EdgeType.ADOPTED_FROM)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id == target.work_id
    assert result.is_ambiguous is False


def test_a_signal_to_an_unresolvable_target_is_treated_as_no_signal(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record(
        [RawReference(target_issuer="DIN", target_designation="EN ISO 99999:2030", edge_type=EdgeType.REPLACES)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_conflicting_work_linking_signals_are_ambiguous(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=first.id, issuer="DIN", designation="EN ISO 9001:2015", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=second.id, issuer="ISO", designation="9001:2015", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2015", edge_type=EdgeType.ADOPTED_FROM),
            RawReference(target_issuer="ISO", target_designation="9001:2015", edge_type=EdgeType.REPLACES),
        ]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.is_ambiguous is True
    assert result.reason == "conflicting_work_signal"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_work_assignment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_core.pipeline.work_assignment'`.

- [ ] **Step 3: Write `work_assignment.py`**

Create `core/src/normly_core/pipeline/work_assignment.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass

from normly_core.graph.domain import DocumentRepository, EdgeType
from normly_core.pipeline.domain import RawRecord

_WORK_LINKING_EDGE_TYPES = {EdgeType.REPLACES, EdgeType.WITHDRAWN_BY, EdgeType.ADOPTED_FROM}


@dataclass(frozen=True)
class WorkAssignmentResult:
    work_id: uuid.UUID | None
    is_ambiguous: bool
    reason: str | None


def determine_work_assignment(
    record: RawRecord, document_repo: DocumentRepository
) -> WorkAssignmentResult:
    """
    Only REPLACES/WITHDRAWN_BY/ADOPTED_FROM references count as a Work-linking
    signal -- REFERENCES and BASED_ON_LAW connect documents that are never the
    same Regelwerk. A reference whose target cannot be resolved yet is treated
    as no signal at all (not ambiguous): that document either does not exist
    yet, or the separate `reference_target_not_found` identity-resolution case
    that `references.extract_references` raises for it is the right place to
    flag the problem, not this one.
    """
    candidate_work_ids: set[uuid.UUID] = set()
    for reference in record.raw_references:
        if reference.edge_type not in _WORK_LINKING_EDGE_TYPES:
            continue
        target = document_repo.find_by_designation(
            reference.target_issuer, reference.target_designation
        )
        if target is None:
            continue
        candidate_work_ids.add(target.work_id)

    if len(candidate_work_ids) > 1:
        return WorkAssignmentResult(work_id=None, is_ambiguous=True, reason="conflicting_work_signal")
    if len(candidate_work_ids) == 1:
        return WorkAssignmentResult(work_id=next(iter(candidate_work_ids)), is_ambiguous=False, reason=None)
    return WorkAssignmentResult(work_id=None, is_ambiguous=False, reason=None)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_work_assignment.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing runner integration test**

Create `core/tests/pipeline/test_runner_work_assignment.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import EdgeType, IdentityResolutionStatus, LegalBasisCategory
from normly_core.graph.postgres.orm import DocumentDesignationORM, DocumentORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference, RightsRule
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records):
        self.source_id = source_id
        self._records = records

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return []

    def classify_rights(self, record):
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        )


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )


def test_a_national_adoption_signal_reuses_the_original_documents_work(db_session):
    source = _make_source(db_session)
    din_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-din", raw_designation="EN ISO 9001:2018",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    bs_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-bs", raw_designation="EN ISO 9001:2018",
        raw_issuer="BS", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2018", edge_type=EdgeType.ADOPTED_FROM)
        ],
    )
    adapter = _FakeAdapter(source.id, [din_record, bs_record])

    summary = run_adapter(adapter, db_session)

    assert summary.documents_created == 2
    din_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "DIN")
    ).scalar_one()
    bs_document = db_session.execute(
        select(DocumentORM)
        .join(DocumentDesignationORM, DocumentDesignationORM.document_id == DocumentORM.id)
        .where(DocumentDesignationORM.issuer == "BS")
    ).scalar_one()
    assert din_document.work_id == bs_document.work_id


def test_an_unrelated_record_gets_its_own_work(db_session):
    source = _make_source(db_session)
    record_a = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-a", raw_designation="EN ISO 9001:2018",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    record_b = RawRecord(
        source_id=source.id, content_hash="sha256:runner-work-b", raw_designation="Vorschrift 1",
        raw_issuer="DGUV", raw_title=None, full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record_a, record_b])

    run_adapter(adapter, db_session)

    documents = db_session.execute(select(DocumentORM)).scalars().all()
    work_ids = {document.work_id for document in documents}
    assert len(work_ids) == 2


def test_conflicting_work_signals_are_enqueued_for_review_not_written(db_session):
    source = _make_source(db_session)
    din_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-din", raw_designation="EN ISO 9001:2015",
        raw_issuer="DIN", raw_title=None, full_text=None,
    )
    iso_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-iso", raw_designation="9001:2015",
        raw_issuer="ISO", raw_title=None, full_text=None,
    )
    conflicted_record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-conflict-bs", raw_designation="EN ISO 9001:2015",
        raw_issuer="BS", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2015", edge_type=EdgeType.ADOPTED_FROM),
            RawReference(target_issuer="ISO", target_designation="9001:2015", edge_type=EdgeType.REPLACES),
        ],
    )
    adapter = _FakeAdapter(source.id, [din_record, iso_record, conflicted_record])

    summary = run_adapter(adapter, db_session)

    assert summary.documents_created == 2
    assert summary.records_enqueued_for_review == 1
    delivery = PostgresDeliveryRepository(db_session).find_delivery(source.id, "sha256:runner-conflict-bs")
    cases = PostgresIdentityResolutionRepository(db_session).list_pending_cases()
    conflict_case = next(case for case in cases if case.delivery_id == delivery.id)
    assert conflict_case.status == IdentityResolutionStatus.PENDING
    assert conflict_case.reason == "conflicting_work_signal"
```

- [ ] **Step 6: Run the integration tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_runner_work_assignment.py -v`
Expected: FAIL — `din_document.work_id != bs_document.work_id` (runner does not consult `work_assignment` yet, so every new document still gets its own independent default Work from Task 2).

- [ ] **Step 7: Wire `work_assignment` into `runner.py`**

In `core/src/normly_core/pipeline/runner.py`, add the import (after line 22):

```python
from normly_core.pipeline import identity, references, work_assignment
```

Then replace the `is_new` branch (lines 92-101):

```python
        if result.is_new:
            parsed = identity.parse_designation(record.raw_designation)
            assignment = work_assignment.determine_work_assignment(record, document_repo)
            if assignment.is_ambiguous:
                identity_repo.enqueue_case(
                    delivery_id=delivery.id,
                    raw_designation=record.raw_designation,
                    raw_issuer=record.raw_issuer,
                    reason=assignment.reason,
                )
                delta.records_enqueued_for_review += 1
                return delta
            document = document_repo.create_document(
                origin_issuer=record.raw_issuer or "unknown",
                origin_number=parsed.number,
                edition=parsed.edition or "",
                part=None,
                delivery_id=delivery.id,
                work_id=assignment.work_id,
            )
            delta.documents_created += 1
        else:
            document = document_repo.get_document_unchecked(result.document_id)
```

(`assignment.work_id` is `None` on the no-signal path, which `create_document` already treats as "give it a fresh Work" — the exact default rule from Task 2, so this line needs no branching between "reuse" and "create new".)

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_work_assignment.py tests/pipeline/test_runner_work_assignment.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS — in particular every pre-existing `tests/pipeline/test_runner.py` case, since a record with no `raw_references` (or only `REFERENCES`/`BASED_ON_LAW` ones) behaves exactly as before.

- [ ] **Step 10: Commit**

```bash
git add core/src/normly_core/pipeline/work_assignment.py core/src/normly_core/pipeline/runner.py core/tests/pipeline/test_work_assignment.py core/tests/pipeline/test_runner_work_assignment.py
git commit -s -m "feat(core): assign ingested documents to a shared Work automatically

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** Work table + lifecycle (Task 1), `document.work_id` default + backfill + `NOT NULL` (Tasks 2-3), `IdentityResolutionCase` work-merge extension with the exact rejection rule from the spec's Fehlerbehandlung section (Task 4), ingestion-time signal-based assignment restricted to `REPLACES`/`WITHDRAWN_BY`/`ADOPTED_FROM` (Task 5). REQ-GRAPH-005's acceptance criterion (three national adoptions as one node) is exercised end-to-end by Task 5's `test_a_national_adoption_signal_reuses_the_original_documents_work`, extendable to three real adoptions the same way. Updating ADR-011/REQ-GRAPH-005's text to reference `Work` (mentioned in the spec's "Bezug zu Requirements und ADRs") is a documentation follow-up, not a code task — do it as a small doc-only commit once this branch is reviewed, not blocking any task above.
- **Placeholder scan:** none — every step carries complete code and exact run commands.
- **Type consistency:** `work_id` is spelled identically everywhere (`Work.id`, `Document.work_id`, `WorkAssignmentResult.work_id`, `IdentityResolutionCase.source_work_id`/`target_work_id`); `WorkCreatedVia`/`WorkStatus`/`IdentityResolutionCaseType` values match between the domain enums, the ORM `sa.Enum(..., values_callable=_enum_values)` declarations, and the migrations' literal string lists.
