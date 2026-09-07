# Normtracker Semantic Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ILIKE-only document search with a hybrid (exact-then-semantic) search whose results are grouped by `Work`, per `docs/superpowers/specs/2026-09-07-normtracker-semantic-search-design.md`.

**Architecture:** A new `DocumentEmbedding` (one pgvector embedding per `Document`, built from its primary designation + first title) is created/kept fresh during ingestion and backfilled for existing documents via a new CLI command. A new repository method merges exact ILIKE matches (Tier 1) with pgvector nearest-neighbor matches (Tier 2), deduplicates to one hit per `Work`, and the API exposes it as a new response shape.

**Tech Stack:** Python, SQLAlchemy ORM, Alembic, pgvector, `sentence-transformers` (existing `EmbeddingModel`), FastAPI, pytest + testcontainers — spans `core/` and `api/`.

## Global Constraints

- Every commit: `git commit -s` (DCO) plus a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer. Never a second `Signed-off-by` from the AI.
- SPDX header on every new file, exactly:
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors
  ```
- No direct push to `main`. This plan's work happens on its own branch off the current `main` (already includes merged PR #11). Push/PR/merge only after the user explicitly confirms — STACKIT CI runners are billed per run and there is no working cancel API on this instance.
- Database access only through the repository layer. The embedding **model call** is business logic, not database access: no repository method ever calls `EmbeddingModel`. Repository methods that need a vector take one as an already-computed `query_vector: list[float]` parameter.
- Every migration must be idempotent and its `downgrade()` must actually work (`core/tests/graph/test_migration_determinism.py` round-trips the whole chain).
- No ML model loading inside an Alembic migration, ever — that is what the new `backfill-document-embeddings` CLI command is for.
- `DocumentTitle` has **no** `is_primary` field (unlike `DocumentDesignation`, which does) — do not assume one exists anywhere in this plan.
- `TestClient(app)` runs the real FastAPI `lifespan()` on every test using `api/tests/conftest.py`'s `client` fixture. If `api/`'s lifespan loads the real embedding model unconditionally, every api/ test pays that cost, not just search tests — Task 5 below fixes this with a fake, cheap, deterministic embedding-model dependency override as the `client` fixture's default, mirroring the existing `enforce_rate_limit` override-by-default pattern already in that file.
- Task order matters: Tasks 1-4 (`core/`) must land before Tasks 5-6 (`api/`), since the API layer depends on the repository method and domain types Tasks 1-4 introduce.

---

### Task 1: `DocumentEmbedding` — domain type, ORM model, repository, migration

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (insert after `EmbeddingRepository` ends, i.e. after line 490, before `class WorkStatus(str, Enum):` at line 492); also modify `DocumentRepository` Protocol — no changes needed there yet (Task 4 adds `search_works_for_jurisdiction` to it)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (insert after `EmbeddingORM` ends, i.e. after line 337, before `class IdentityResolutionCaseORM(Base):`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (insert after `PostgresEmbeddingRepository` ends — find it by searching for `class PostgresEmbeddingRepository`, insert the new helper + class immediately after its last method, before `class PostgresIdentityResolutionRepository:`)
- Create: `core/migrations/versions/0025_create_document_embedding.py`
- Create: `core/tests/graph/test_document_embedding_repository.py`

**Interfaces:**
- Produces: `DocumentEmbedding` (frozen dataclass: `id: uuid.UUID`, `document_id: uuid.UUID`, `model_name: str`, `vector: list[float]`, `delivery_id: uuid.UUID`, `created_at: datetime`), `DocumentEmbeddingRepository` Protocol with `upsert_document_embedding(self, *, document_id: uuid.UUID, delivery_id: uuid.UUID, model_name: str, vector: list[float]) -> DocumentEmbedding` and `list_documents_without_embedding(self, model_name: str) -> list[Document]`, `PostgresDocumentEmbeddingRepository` implementing both.
- Consumes: `Document`, `_document_to_domain`, `DocumentORM`, `_require_active_delivery`, `pg_insert` (all already imported/defined in `repositories.py` — `pg_insert` is `from sqlalchemy.dialects.postgresql import insert as pg_insert`, already at the top of the file).

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_document_embedding_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:document-embedding-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_document(db_session, delivery_id):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery_id,
    )


def test_upsert_document_embedding_creates_a_new_row(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)

    embedding = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    assert embedding.document_id == document.id
    assert embedding.model_name == "test-model"
    assert embedding.vector == [0.1] * 1024


def test_upsert_document_embedding_overwrites_the_existing_vector(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)
    first = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    second = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.9] * 1024,
    )

    assert second.id == first.id
    assert second.vector == [0.9] * 1024


def test_list_documents_without_embedding_excludes_documents_with_one(db_session):
    delivery = _make_delivery(db_session)
    with_embedding = _make_document(db_session, delivery.id)
    without_embedding = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 45001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresDocumentEmbeddingRepository(db_session)
    repo.upsert_document_embedding(
        document_id=with_embedding.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    missing = repo.list_documents_without_embedding("test-model")

    missing_ids = {document.id for document in missing}
    assert without_embedding.id in missing_ids
    assert with_embedding.id not in missing_ids


def test_list_documents_without_embedding_is_scoped_to_the_model_name(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)
    repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="old-model",
        vector=[0.1] * 1024,
    )

    missing = repo.list_documents_without_embedding("new-model")

    assert document.id in {d.id for d in missing}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_embedding_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PostgresDocumentEmbeddingRepository'`.

- [ ] **Step 3: Add the domain type**

In `core/src/normly_core/graph/domain.py`, insert immediately after line 490 (the `...` ending `EmbeddingRepository.add_embedding`'s docstring/body), before line 492 (`class WorkStatus(str, Enum):`):

```python
@dataclass(frozen=True)
class DocumentEmbedding:
    id: uuid.UUID
    document_id: uuid.UUID
    model_name: str
    vector: list[float]
    delivery_id: uuid.UUID
    created_at: datetime


class DocumentEmbeddingRepository(Protocol):
    """
    The write surface for per-Document search embeddings.

    Unlike `EmbeddingRepository.add_embedding` (segment-scoped, create-if-
    absent -- segment text never changes, so no update is ever needed),
    `upsert_document_embedding` always (re)writes the vector: a Document's
    primary designation/title can change across re-ingestion, so the
    embedding must track it rather than freeze on the first value ever seen.
    """

    def upsert_document_embedding(
        self,
        *,
        document_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> DocumentEmbedding: ...

    def list_documents_without_embedding(self, model_name: str) -> list[Document]:
        """
        Every Document with no DocumentEmbedding row for `model_name` yet.
        Pipeline/administrative method (used by the `backfill-document-
        embeddings` CLI command) -- nothing here is served to a public
        caller, it only decides what the backfill still has to do.
        """
        ...
```

- [ ] **Step 4: Add the ORM model**

In `core/src/normly_core/graph/postgres/orm.py`, insert immediately after `EmbeddingORM` ends (after its `__table_args__` tuple, before `class IdentityResolutionCaseORM(Base):`):

```python
class DocumentEmbeddingORM(Base):
    __tablename__ = "document_embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str]
    vector: Mapped[list[float]] = mapped_column(Vector(1024))
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "document_id", "model_name", name="uq_document_embedding_document_model"
        ),
    )
```

(`Vector` is already imported at the top of this file — `from pgvector.sqlalchemy import Vector` — reused from `EmbeddingORM`, not a new import.)

- [ ] **Step 5: Add the Postgres repository**

In `core/src/normly_core/graph/postgres/repositories.py`, add `DocumentEmbedding` to the domain import block and `DocumentEmbeddingORM` to the ORM import block (both already contain `Embedding`/`EmbeddingORM` — add the new names alongside them, alphabetically). Then find `class PostgresEmbeddingRepository:` and insert this immediately after its last method (`add_embedding`), before whatever class comes next:

```python
def _document_embedding_to_domain(orm: DocumentEmbeddingORM) -> DocumentEmbedding:
    return DocumentEmbedding(
        id=orm.id,
        document_id=orm.document_id,
        model_name=orm.model_name,
        vector=list(orm.vector),
        delivery_id=orm.delivery_id,
        created_at=orm.created_at,
    )


class PostgresDocumentEmbeddingRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_document_embedding(
        self, *, document_id: uuid.UUID, delivery_id: uuid.UUID, model_name: str,
        vector: list[float],
    ) -> DocumentEmbedding:
        _require_active_delivery(self._session, delivery_id)
        stmt = (
            pg_insert(DocumentEmbeddingORM)
            .values(
                id=uuid.uuid4(), document_id=document_id, delivery_id=delivery_id,
                model_name=model_name, vector=vector,
            )
            .on_conflict_do_update(
                index_elements=[DocumentEmbeddingORM.document_id, DocumentEmbeddingORM.model_name],
                set_={"vector": vector, "delivery_id": delivery_id},
            )
            .returning(DocumentEmbeddingORM)
        )
        orm = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return _document_embedding_to_domain(orm)

    def list_documents_without_embedding(self, model_name: str) -> list[Document]:
        rows = self._session.execute(
            select(DocumentORM)
            .where(
                ~sa.exists(
                    select(DocumentEmbeddingORM.id).where(
                        DocumentEmbeddingORM.document_id == DocumentORM.id,
                        DocumentEmbeddingORM.model_name == model_name,
                    )
                )
            )
            .order_by(DocumentORM.id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]
```

- [ ] **Step 6: Write the migration**

Create `core/migrations/versions/0025_create_document_embedding.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document_embedding table

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_embedding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True),
            sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("vector", Vector(1024), nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id", "model_name", name="uq_document_embedding_document_model"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_embedding")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_embedding_repository.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0025_create_document_embedding.py core/tests/graph/test_document_embedding_repository.py
git commit -s -m "feat(core): add DocumentEmbedding for per-Document search vectors

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Build the embedding text + wire it into ingestion

**Files:**
- Create: `core/src/normly_core/pipeline/document_embedding.py`
- Modify: `core/src/normly_core/pipeline/runner.py` (imports at top; the `run_adapter` repo-instantiation block; inside `process()`, right after the `add_designation`/`add_title` block ends, before `rights_repo.classify(...)`)
- Create: `core/tests/pipeline/test_document_embedding.py`
- Create: `core/tests/pipeline/test_runner_document_embedding.py`

**Interfaces:**
- Consumes: `DocumentDesignation`, `DocumentTitle` (`core/src/normly_core/graph/domain.py`, unchanged), `PostgresDocumentEmbeddingRepository.upsert_document_embedding` (Task 1), `EmbeddingModel.embed` / `MODEL_NAME` (`core/src/normly_core/pipeline/embeddings.py`, unchanged).
- Produces: `build_document_embedding_text(designations: list[DocumentDesignation], titles: list[DocumentTitle]) -> str | None` in `core/src/normly_core/pipeline/document_embedding.py`. Task 3 adds a second function to this same file.

- [ ] **Step 1: Write the failing unit tests for `build_document_embedding_text`**

Create `core/tests/pipeline/test_document_embedding.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import DocumentDesignation, DocumentTitle
from normly_core.pipeline.document_embedding import build_document_embedding_text


def _designation(designation: str, *, is_primary: bool) -> DocumentDesignation:
    return DocumentDesignation(
        id=uuid.uuid4(), document_id=uuid.uuid4(), issuer="CEN", designation=designation,
        language="de", edition=None, is_primary=is_primary, delivery_id=uuid.uuid4(),
    )


def _title(title: str) -> DocumentTitle:
    return DocumentTitle(
        id=uuid.uuid4(), document_id=uuid.uuid4(), language="de", title=title,
        delivery_id=uuid.uuid4(),
    )


def test_combines_primary_designation_and_first_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]
    titles = [_title("Qualitätsmanagementsysteme")]

    text = build_document_embedding_text(designations, titles)

    assert text == "EN ISO 9001:2018 — Qualitätsmanagementsysteme"


def test_ignores_a_non_primary_designation_when_a_primary_one_exists():
    designations = [
        _designation("wrong-secondary", is_primary=False),
        _designation("EN ISO 9001:2018", is_primary=True),
    ]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_falls_back_to_designation_alone_when_there_is_no_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_returns_none_when_there_is_no_primary_designation():
    text = build_document_embedding_text([], [_title("Qualitätsmanagementsysteme")])

    assert text is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_document_embedding.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_core.pipeline.document_embedding'`.

- [ ] **Step 3: Write `document_embedding.py`**

Create `core/src/normly_core/pipeline/document_embedding.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from normly_core.graph.domain import DocumentDesignation, DocumentTitle


def build_document_embedding_text(
    designations: list[DocumentDesignation], titles: list[DocumentTitle]
) -> str | None:
    """
    "<primary designation> — <first title>" for the search embedding, or just
    the designation if no title exists yet, or None if there is no primary
    designation to embed at all (nothing indexed until one exists).

    DocumentTitle has no `is_primary` flag (unlike DocumentDesignation) --
    the first title in insertion order wins. Deliberate simplification:
    multi-title documents are rare today, and a real "best title" concept is
    not something this sub-project introduces.
    """
    primary_designation = next((d for d in designations if d.is_primary), None)
    if primary_designation is None:
        return None
    if not titles:
        return primary_designation.designation
    return f"{primary_designation.designation} — {titles[0].title}"
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_document_embedding.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing runner integration tests**

Create `core/tests/pipeline/test_runner_document_embedding.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import DocumentEmbeddingORM, DocumentORM
from normly_core.graph.postgres.repositories import PostgresSourceRepository
from normly_core.pipeline.domain import RawRecord, RightsRule
from normly_core.pipeline.embeddings import MODEL_NAME
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


def test_ingesting_a_new_document_creates_its_embedding(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-new-doc", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title="Qualitätsmanagementsysteme", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)

    document = db_session.execute(select(DocumentORM)).scalar_one()
    embedding = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalar_one()
    assert embedding.model_name == MODEL_NAME
    assert len(embedding.vector) == 1024


def test_reprocessing_the_same_document_overwrites_its_embedding(db_session):
    source = _make_source(db_session)
    first_record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-repeat-1", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title="Qualitätsmanagementsysteme", full_text=None,
    )
    second_record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-repeat-2", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title="Andere Bezeichnung", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [first_record])
    run_adapter(adapter, db_session)
    document = db_session.execute(select(DocumentORM)).scalar_one()
    first_vector = db_session.execute(
        select(DocumentEmbeddingORM.vector).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalar_one()

    second_adapter = _FakeAdapter(source.id, [second_record])
    run_adapter(second_adapter, db_session)

    rows = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalars().all()
    assert len(rows) == 1  # overwritten in place, not a second row
    assert list(rows[0].vector) != list(first_vector)


def test_a_document_with_no_issuer_and_no_prior_designation_gets_no_embedding(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-no-issuer", raw_designation="untitled",
        raw_issuer=None, raw_title="Ein Titel ohne Herausgeber", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)

    document = db_session.execute(select(DocumentORM)).scalar_one()
    embeddings = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalars().all()
    assert embeddings == []
```

- [ ] **Step 6: Run the integration tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_runner_document_embedding.py -v`
Expected: FAIL — no `DocumentEmbeddingORM` row is created yet (`scalar_one()` raises `NoResultFound` on the first test).

- [ ] **Step 7: Wire the embedding step into `runner.py`**

In `core/src/normly_core/pipeline/runner.py`, add to the imports (the `from normly_core.graph.postgres.repositories import (...)` block, alongside the existing names): `PostgresDocumentEmbeddingRepository`. Add to the `from normly_core.pipeline import identity, references, work_assignment` line: `document_embedding` (so it reads `from normly_core.pipeline import document_embedding, identity, references, work_assignment`).

In `run_adapter`, add to the repository-instantiation block (alongside the other `*_repo = Postgres*Repository(session)` lines):

```python
    document_embedding_repo = PostgresDocumentEmbeddingRepository(session)
```

Inside `process()`, immediately after the existing block that ends:

```python
        if record.raw_title is not None:
            document_repo.add_title(
                document_id=document.id,
                language=language,
                title=record.raw_title,
                delivery_id=delivery.id,
            )
```

and before `rights_repo.classify(`, insert:

```python
        embedding_text = document_embedding.build_document_embedding_text(
            document_repo.list_designations(document.id), document_repo.list_titles(document.id)
        )
        if embedding_text is not None:
            if embedding_model is None:
                embedding_model = EmbeddingModel()
            document_embedding_repo.upsert_document_embedding(
                document_id=document.id,
                delivery_id=delivery.id,
                model_name=MODEL_NAME,
                vector=embedding_model.embed(embedding_text),
            )
```

(`embedding_model` is the same `nonlocal embedding_model` variable the segment-embedding code further down already lazily initializes — reused here, not a second model instance. `MODEL_NAME` and `EmbeddingModel` are already imported at the top of this file.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_runner_document_embedding.py tests/pipeline/test_document_embedding.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS — in particular `tests/pipeline/test_runner.py` (pre-existing, untouched) must still pass unchanged.

- [ ] **Step 10: Commit**

```bash
git add core/src/normly_core/pipeline/document_embedding.py core/src/normly_core/pipeline/runner.py core/tests/pipeline/test_document_embedding.py core/tests/pipeline/test_runner_document_embedding.py
git commit -s -m "feat(core): create/refresh a document's search embedding during ingestion

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Backfill CLI command for existing documents

**Files:**
- Modify: `core/src/normly_core/pipeline/document_embedding.py` (add `backfill_document_embeddings`)
- Modify: `core/src/normly_core/pipeline/cli.py` (new subcommand + branch in `main()`)
- Modify: `core/tests/pipeline/test_document_embedding.py` (add backfill tests)
- Modify: `core/tests/pipeline/test_cli.py` (add one CLI-level test using the existing `committed_db` fixture)

**Interfaces:**
- Consumes: `PostgresDocumentRepository`, `PostgresDocumentEmbeddingRepository.list_documents_without_embedding`/`upsert_document_embedding` (Task 1), `build_document_embedding_text` (this file, Task 2), `EmbeddingModel`/`MODEL_NAME`.
- Produces: `backfill_document_embeddings(session: Session) -> int` in `core/src/normly_core/pipeline/document_embedding.py`, returning the count of embeddings it created. Wired into `cli.py`'s `main()` as the `backfill-document-embeddings` subcommand.

- [ ] **Step 1: Write the failing tests for `backfill_document_embeddings`**

Append to `core/tests/pipeline/test_document_embedding.py`:

```python
from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.document_embedding import backfill_document_embeddings


def _make_delivery_for_backfill(db_session, content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_backfill_creates_embeddings_for_documents_missing_one(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-1")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 9001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )

    created = backfill_document_embeddings(db_session)

    assert created == 1
    embedding_repo = PostgresDocumentEmbeddingRepository(db_session)
    assert document.id not in {
        d.id for d in embedding_repo.list_documents_without_embedding("intfloat/multilingual-e5-large")
    }


def test_backfill_is_idempotent(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-2")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 45001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 45001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    backfill_document_embeddings(db_session)

    second_run_created = backfill_document_embeddings(db_session)

    assert second_run_created == 0


def test_backfill_skips_a_document_with_no_primary_designation(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-3")
    # A document created directly via create_document with no add_designation
    # call has no primary designation -- build_document_embedding_text
    # returns None for it, and the backfill must not choke on that.
    PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 14001", edition="2018", part=None,
        delivery_id=delivery.id,
    )

    created = backfill_document_embeddings(db_session)

    assert created == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_document_embedding.py -v -k backfill`
Expected: FAIL — `ImportError: cannot import name 'backfill_document_embeddings'`.

- [ ] **Step 3: Add `backfill_document_embeddings`**

In `core/src/normly_core/pipeline/document_embedding.py`, add these imports at the top (after the existing `from normly_core.graph.domain import DocumentDesignation, DocumentTitle` line):

```python
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
)
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel
```

Then append this function at the end of the file:

```python
def backfill_document_embeddings(session: Session) -> int:
    """
    Create a DocumentEmbedding for every Document that doesn't have one yet
    for the current model. Idempotent: a document that already has one is
    left untouched here -- re-embedding an existing document only happens
    through re-ingestion (runner.py), which is the only place a document's
    designation/title can actually change.
    """
    document_repo = PostgresDocumentRepository(session)
    embedding_repo = PostgresDocumentEmbeddingRepository(session)
    embedding_model: EmbeddingModel | None = None
    created = 0

    for document in embedding_repo.list_documents_without_embedding(MODEL_NAME):
        text = build_document_embedding_text(
            document_repo.list_designations(document.id), document_repo.list_titles(document.id)
        )
        if text is None:
            continue

        if embedding_model is None:
            embedding_model = EmbeddingModel()
        embedding_repo.upsert_document_embedding(
            document_id=document.id,
            delivery_id=document.created_via_delivery_id,
            model_name=MODEL_NAME,
            vector=embedding_model.embed(text),
        )
        created += 1

    return created
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_document_embedding.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI test**

In `core/tests/pipeline/test_cli.py`, this new test writes a `document_embedding` row through `committed_db` (real commit, no rollback) — but that fixture's `_WRITTEN_TABLES` tuple (top of the file) does not list `document_embedding` yet (it predates this table). Add `"document_embedding",` to `_WRITTEN_TABLES`, ordered before `"document"` (it has a foreign key to `document.id`, so it must be truncated first or `CASCADE`, matching how `"embedding"` is already listed before `"segment"` for the same reason).

Note for whoever runs this plan's final whole-branch review, not something to fix in this task: `_WRITTEN_TABLES` also does not list `"work"`, even though `document`'s implicit-default-Work behavior (sub-project 1) means every `committed_db`-based CLI test already leaks `work` rows into the shared test database today. No existing or new test in this plan asserts a global `work` count, so this is currently invisible — same class of issue as sub-project 1's own Finding 1, just not triggered yet. Worth a one-line fix (`"work",` added to the tuple) but it's pre-existing, out of scope for this task specifically.

Then add this test (uses the existing `committed_db` fixture already defined at the top of that file):

Add these imports to the top of `core/tests/pipeline/test_cli.py`, alongside its existing ones: `from datetime import date, datetime, timezone` and `from normly_core.graph.domain import LegalBasisCategory` and, to its existing `from normly_core.graph.postgres.repositories import (...)`-style imports or a new one, `PostgresDeliveryRepository`, `PostgresDocumentRepository`, `PostgresSourceRepository` (check first whether the file already imports any of these — it already uses `PostgresSourceRepository`-adjacent helpers elsewhere in this session's Task 2/3 work, so only add names not already present).

```python
def test_backfill_document_embeddings_command_creates_embeddings(committed_db, capsys):
    from sqlalchemy.orm import Session

    with Session(committed_db) as session:
        source = PostgresSourceRepository(session).create_source(
            publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
            legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
            reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
        )
        delivery = PostgresDeliveryRepository(session).record_delivery(
            source_id=source.id, content_hash="sha256:cli-backfill",
            ingested_at=datetime.now(timezone.utc),
        )
        doc_repo = PostgresDocumentRepository(session)
        document = doc_repo.create_document(
            origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
            delivery_id=delivery.id,
        )
        doc_repo.add_designation(
            document_id=document.id, issuer="CEN", designation="EN ISO 9001:2018", language="de",
            edition=None, is_primary=True, delivery_id=delivery.id,
        )
        session.commit()

    exit_code = main(["backfill-document-embeddings"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "document_embeddings_created=1" in output
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_cli.py -v -k backfill_document_embeddings`
Expected: FAIL — `argparse` rejects `backfill-document-embeddings` as an invalid choice (subcommand doesn't exist yet).

- [ ] **Step 7: Wire the subcommand into `cli.py`**

In `core/src/normly_core/pipeline/cli.py`, add the import: `from normly_core.pipeline.document_embedding import backfill_document_embeddings`.

Replace `main()` entirely with:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("source", choices=["eur-lex", "dguv", "baua"])
    ingest_parser.add_argument(
        "--directory", type=Path, required=True,
        help="local directory containing the source's raw files",
    )

    subparsers.add_parser("backfill-document-embeddings")

    args = parser.parse_args(argv)

    database_url = os.environ.get("NORMLY_DATABASE_URL")
    if not database_url:
        print("NORMLY_DATABASE_URL environment variable is required", file=sys.stderr)
        return 1

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            if args.command == "ingest":
                adapter = build_adapter(args.source, directory=args.directory, session=session)
                summary = run_adapter(adapter, session)
                session.commit()
                print(
                    f"processed={summary.records_processed} skipped={summary.records_skipped} "
                    f"failed={summary.records_failed} "
                    f"documents_created={summary.documents_created} "
                    f"segments_created={summary.segments_created} "
                    f"embeddings_created={summary.embeddings_created} "
                    f"enqueued_for_review={summary.records_enqueued_for_review}"
                )
            elif args.command == "backfill-document-embeddings":
                created = backfill_document_embeddings(session)
                session.commit()
                print(f"document_embeddings_created={created}")
    finally:
        engine.dispose()

    return 0
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_cli.py -v`
Expected: PASS — including every pre-existing test in this file (`ingest` behavior is unchanged, just moved under an `if` branch).

- [ ] **Step 9: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add core/src/normly_core/pipeline/document_embedding.py core/src/normly_core/pipeline/cli.py core/tests/pipeline/test_document_embedding.py core/tests/pipeline/test_cli.py
git commit -s -m "feat(core): add a CLI command to backfill document search embeddings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Hybrid, Work-grouped search — `search_works_for_jurisdiction`

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `WorkSearchHit` near `DocumentEmbeddingRepository`; add `search_works_for_jurisdiction` to the `DocumentRepository` Protocol, right after `search_documents_for_jurisdiction`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add `search_works_for_jurisdiction` to `PostgresDocumentRepository`, right after `search_documents_for_jurisdiction`)
- Create: `core/tests/graph/test_work_search.py`

**Interfaces:**
- Consumes: `Document`, `DocumentORM`, `RightsClassificationORM`, `DocumentEmbeddingORM` (Task 1), `_document_to_domain`, the existing `search_documents_for_jurisdiction` (unchanged, reused as Tier 1's implementation).
- Produces: `WorkSearchHit` (frozen dataclass: `work_id: uuid.UUID`, `best_match: Document`, `other_editions_count: int`) in `domain.py`. `DocumentRepository.search_works_for_jurisdiction(self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None, query_vector: list[float] | None = None, embedding_model_name: str | None = None, limit: int = 20, offset: int = 0) -> tuple[list[WorkSearchHit], int]`.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_work_search.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_visible_document(
    db_session, delivery, *, issuer, designation, jurisdiction="DE", work_id=None,
):
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=designation, edition="2018", part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=designation, language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_exact_match_is_returned_with_no_query_vector(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-exact")
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 1",
    )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction("DE", q="Vorschrift 1")

    assert total == 1
    assert hits[0].work_id == document.work_id
    assert hits[0].best_match.id == document.id
    assert hits[0].other_editions_count == 0


def test_two_documents_in_the_same_work_produce_one_hit(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-grouping")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_document = _make_visible_document(
        db_session, delivery, issuer="DIN", designation="EN ISO 9001:2018", work_id=work.id,
    )
    _make_visible_document(
        db_session, delivery, issuer="BS", designation="EN ISO 9001:2018 UK", work_id=work.id,
    )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction("DE", q="ISO 9001")

    assert total == 1
    assert hits[0].work_id == work.id
    assert hits[0].other_editions_count == 1


def test_semantic_tier_finds_a_document_with_no_exact_text_match(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-semantic")
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 38",
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.9] + [0.0] * 1023,
    )

    hits, total = PostgresDocumentRepository(db_session).search_works_for_jurisdiction(
        "DE", q="Absturzsicherung auf Baustellen",
        query_vector=[0.9] + [0.0] * 1023, embedding_model_name="test-model",
    )

    assert total == 1
    assert hits[0].best_match.id == document.id


def test_exact_tier_ranks_before_the_semantic_tier(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-tier-order")
    exact_match = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 38",
    )
    semantic_match = _make_visible_document(
        db_session, delivery, issuer="DIN", designation="DIN 4420",
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=exact_match.id, delivery_id=delivery.id, model_name="test-model",
        vector=[1.0] + [0.0] * 1023,
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=semantic_match.id, delivery_id=delivery.id, model_name="test-model",
        vector=[1.0] + [0.0] * 1023,
    )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction(
        "DE", q="Vorschrift 38", query_vector=[1.0] + [0.0] * 1023,
        embedding_model_name="test-model",
    )

    assert total == 2
    assert hits[0].best_match.id == exact_match.id  # exact tier first
    assert hits[1].best_match.id == semantic_match.id  # semantic tier second


def test_no_query_returns_the_whole_jurisdiction_grouped_by_work(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-no-query")
    _make_visible_document(db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 1")
    _make_visible_document(db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 2")

    hits, total = PostgresDocumentRepository(db_session).search_works_for_jurisdiction("DE")

    assert total == 2


def test_pagination_respects_limit_and_offset(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-pagination")
    for n in range(3):
        _make_visible_document(
            db_session, delivery, issuer="DGUV", designation=f"DGUV Vorschrift {n}",
        )
    doc_repo = PostgresDocumentRepository(db_session)

    first_page, total = doc_repo.search_works_for_jurisdiction("DE", limit=2, offset=0)
    second_page, _ = doc_repo.search_works_for_jurisdiction("DE", limit=2, offset=2)

    assert total == 3
    assert len(first_page) == 2
    assert len(second_page) == 1
    first_ids = {hit.work_id for hit in first_page}
    second_ids = {hit.work_id for hit in second_page}
    assert first_ids.isdisjoint(second_ids)


def test_a_document_not_classified_for_the_jurisdiction_is_excluded(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-jurisdiction-gate")
    _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 1", jurisdiction="FR",
    )

    hits, total = PostgresDocumentRepository(db_session).search_works_for_jurisdiction("DE")

    assert total == 0
    assert hits == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_search.py -v`
Expected: FAIL — `AttributeError: 'PostgresDocumentRepository' object has no attribute 'search_works_for_jurisdiction'`.

- [ ] **Step 3: Add `WorkSearchHit` to the domain layer**

In `core/src/normly_core/graph/domain.py`, insert immediately after the `DocumentEmbeddingRepository` Protocol block added in Task 1 (before `class WorkStatus(str, Enum):`):

```python
@dataclass(frozen=True)
class WorkSearchHit:
    work_id: uuid.UUID
    best_match: Document
    other_editions_count: int
```

Then, inside the `DocumentRepository` Protocol, add this method right after `search_documents_for_jurisdiction` ends (after its closing `...`, before `list_exportable_documents_for_jurisdiction`):

```python
    def search_works_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        query_vector: list[float] | None = None, embedding_model_name: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[WorkSearchHit], int]:
        """
        Hybrid, Work-grouped search: exact ILIKE matches on designation/title
        (Tier 1, via search_documents_for_jurisdiction) rank first, then
        documents ranked by cosine distance to `query_vector` (Tier 2) fill
        the rest. Both tiers are deduplicated by work_id -- exactly one hit
        per Work, led by its best-ranked Document. `total` counts distinct
        Works matched, not raw document rows.

        `query_vector` must already be computed (via
        `EmbeddingModel.embed_query`) by the caller -- this repository never
        calls the embedding model itself. `embedding_model_name` is required
        whenever `query_vector` is given (mixing vectors from different
        models in one ORDER BY compares distances from unrelated vector
        spaces); if either is omitted, Tier 2 is skipped and this behaves as
        Tier-1-only, Work-grouped search.
        """
        ...
```

- [ ] **Step 4: Implement `search_works_for_jurisdiction`**

In `core/src/normly_core/graph/postgres/repositories.py`, add `WorkSearchHit` to the domain import block. Add this module-level constant near the top of the file, alongside the other module-level helpers (e.g. right before `def _escape_like(term: str) -> str:`):

```python
# How many nearest-neighbour candidates Tier 2 (semantic) pulls per search --
# not a page size. search_works_for_jurisdiction groups these (plus Tier 1's
# exact matches) down to one hit per Work before paginating, so this bounds
# the expensive ANN query rather than the number of Works actually returned.
_SEMANTIC_CANDIDATE_POOL = 200
```

Inside `PostgresDocumentRepository`, add this method right after `search_documents_for_jurisdiction` ends:

```python
    def search_works_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        query_vector: list[float] | None = None, embedding_model_name: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[WorkSearchHit], int]:
        tier1_documents, _ = self.search_documents_for_jurisdiction(
            jurisdiction, q=q, issuer=issuer, limit=_SEMANTIC_CANDIDATE_POOL, offset=0,
        )
        ordered_documents = list(tier1_documents)
        seen_document_ids = {document.id for document in ordered_documents}

        if query_vector is not None and embedding_model_name is not None:
            rows = self._session.execute(
                select(DocumentORM)
                .join(
                    RightsClassificationORM,
                    RightsClassificationORM.document_id == DocumentORM.id,
                )
                .join(
                    DocumentEmbeddingORM,
                    DocumentEmbeddingORM.document_id == DocumentORM.id,
                )
                .where(
                    RightsClassificationORM.jurisdiction == jurisdiction,
                    RightsClassificationORM.may_process.is_(True),
                    RightsClassificationORM.revoked_at.is_(None),
                    DocumentEmbeddingORM.model_name == embedding_model_name,
                )
                .order_by(DocumentEmbeddingORM.vector.cosine_distance(query_vector))
                .limit(_SEMANTIC_CANDIDATE_POOL)
            ).scalars()
            for row in rows:
                if row.id in seen_document_ids:
                    continue
                seen_document_ids.add(row.id)
                ordered_documents.append(_document_to_domain(row))

        seen_work_ids: set[uuid.UUID] = set()
        grouped: list[Document] = []
        for document in ordered_documents:
            if document.work_id in seen_work_ids:
                continue
            seen_work_ids.add(document.work_id)
            grouped.append(document)

        total = len(grouped)
        page = grouped[offset:offset + limit]
        if not page:
            return [], total

        edition_counts = dict(
            self._session.execute(
                select(DocumentORM.work_id, sa.func.count())
                .where(DocumentORM.work_id.in_([document.work_id for document in page]))
                .group_by(DocumentORM.work_id)
            ).all()
        )
        return [
            WorkSearchHit(
                work_id=document.work_id, best_match=document,
                other_editions_count=edition_counts[document.work_id] - 1,
            )
            for document in page
        ], total
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_search.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS — `tests/graph/test_document_search.py` (the existing `search_documents_for_jurisdiction` tests) must still pass completely unmodified, since Tier 1 reuses that method as-is.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_work_search.py
git commit -s -m "feat(core): add hybrid, Work-grouped document search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Wire the embedding model into `api/`, with a fast test double

**Files:**
- Modify: `api/src/normly_api/main.py` (`lifespan`)
- Modify: `api/src/normly_api/dependencies.py` (new `get_embedding_model`)
- Modify: `api/tests/conftest.py` (`client` fixture default override)
- Modify: `api/tests/test_main.py` (one new assertion)

**Interfaces:**
- Consumes: `EmbeddingModel` (`core/src/normly_core/pipeline/embeddings.py`, unchanged).
- Produces: `app.state.embedding_model: EmbeddingModel` set at API startup. `get_embedding_model(request: Request) -> EmbeddingModel` in `api/src/normly_api/dependencies.py`. A test-only fake embedding model class in `api/tests/conftest.py`, wired as the `client` fixture's default `get_embedding_model` override — Task 6's tests either use this default (fast, deterministic) or pop it to exercise the real model.

- [ ] **Step 1: Write the failing test**

In `api/tests/test_main.py`, add:

```python
def test_embedding_model_is_loaded_once_at_startup(client):
    assert client.app.state.embedding_model is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd api && .venv/bin/pytest tests/test_main.py -v -k embedding_model`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'embedding_model'`.

- [ ] **Step 3: Load the embedding model at startup**

In `api/src/normly_api/main.py`, add the import: `from normly_core.pipeline.embeddings import EmbeddingModel`. In `lifespan`, add — mirroring `chat/src/normly_chat/main.py`'s identical existing line and comment — right after `app.state.engine = engine`:

```python
    # Loaded once at startup, not per-request: the same real,
    # multi-hundred-MB model the ingestion pipeline and chat/ use -- reusing
    # the single already-established EmbeddingModel class, not a second one.
    app.state.embedding_model = EmbeddingModel()
```

- [ ] **Step 4: Add the dependency**

In `api/src/normly_api/dependencies.py`, add the import: `from normly_core.pipeline.embeddings import EmbeddingModel`. Add this function after `get_session`:

```python
def get_embedding_model(request: Request) -> EmbeddingModel:
    return request.app.state.embedding_model
```

- [ ] **Step 5: Run the test — it will now fail differently (slowly)**

Run: `cd api && .venv/bin/pytest tests/test_main.py -v -k embedding_model`
Expected: PASS, but slowly (the real model now loads on every `client` fixture use across the whole suite) — this is the exact problem Step 6 fixes. Do not stop here; continue immediately.

- [ ] **Step 6: Add a fast fake and override it by default in `client`**

In `api/tests/conftest.py`, add near the top (after the existing imports):

```python
class _FakeEmbeddingModel:
    """
    A cheap, deterministic stand-in for the real (multi-hundred-MB)
    EmbeddingModel, used as the `client` fixture's default so ordinary API
    tests don't pay the real model's load cost -- mirrors how
    `enforce_rate_limit` is overridden to a no-op by default in this same
    fixture, for the same reason (tests that aren't ABOUT the real thing
    shouldn't pay for it). Tests that need to embed a query the same way the
    app will (e.g. to pre-compute a matching DocumentEmbedding) request the
    `fake_embedding_model` fixture below directly instead of the real model.
    """

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * 1024
        vector[hash(text) % 1024] = 1.0
        return vector


@pytest.fixture()
def fake_embedding_model() -> _FakeEmbeddingModel:
    return _FakeEmbeddingModel()
```

Then, in the `client` fixture, add the imports `from normly_api.dependencies import get_embedding_model` (alongside the existing `get_session` import) and add `fake_embedding_model` to its parameter list (pytest injects it), and this line alongside the existing `app.dependency_overrides[enforce_rate_limit] = lambda: None`:

```python
    app.dependency_overrides[get_embedding_model] = lambda: fake_embedding_model
```

(`client`'s signature becomes `def client(db_url, monkeypatch, db_session, fake_embedding_model):` — the same fixture instance both backs the override and is available for tests to request directly, so a test that pre-computes a vector with `fake_embedding_model.embed_query(...)` is guaranteed to get the exact same vector the running app will compute for the same text.)

- [ ] **Step 7: Run tests to verify they pass and the suite is fast again**

Run: `cd api && .venv/bin/pytest -v`
Expected: PASS, at roughly the same wall-clock time as before this task (confirming the fake, not the real model, is what most tests now pay for).

- [ ] **Step 8: Commit**

```bash
git add api/src/normly_api/main.py api/src/normly_api/dependencies.py api/tests/conftest.py api/tests/test_main.py
git commit -s -m "feat(api): load the embedding model at startup, with a fast test double

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: `/v1/documents/search` returns Work-grouped hybrid results

**Files:**
- Modify: `api/src/normly_api/schemas.py` (new `WorkSearchResultResponse`, `WorkSearchResponse`; `DocumentSearchResponse` may stay or be removed — see Step 3)
- Modify: `api/src/normly_api/routers/search.py` (rewrite the endpoint)
- Modify: `api/tests/test_documents_search_endpoint.py` (fix the now-outdated assertions; add new tests)

**Interfaces:**
- Consumes: `search_works_for_jurisdiction`, `WorkSearchHit` (Task 4), `get_embedding_model` (Task 5), `document_to_response` (`api/src/normly_api/routers/documents.py`, unchanged), `EmbeddingModel.embed_query`.
- Produces: `GET /v1/documents/search` now returns `WorkSearchResponse`.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `api/tests/test_documents_search_endpoint.py` with:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _seed_document(
    db_session, *, issuer, designation, jurisdiction="DE", content_hash, work_id=None,
):
    source = PostgresSourceRepository(db_session).create_source(
        publisher=issuer, retrieval_path="https://example.de", legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE", reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=designation, edition="2013", part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=designation, language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_endpoint_returns_a_work_grouped_result(client, db_session):
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-1",
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Vorschrift 1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["work_id"] == str(document.work_id)
    assert body["results"][0]["best_match"]["id"] == str(document.id)
    assert body["results"][0]["other_editions_count"] == 0


def test_search_endpoint_groups_two_documents_in_the_same_work(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    _seed_document(
        db_session, issuer="DIN", designation="EN ISO 9001:2018", content_hash="sha256:endpoint-work-1",
        work_id=work.id,
    )
    _seed_document(
        db_session, issuer="BS", designation="EN ISO 9001:2018 UK",
        content_hash="sha256:endpoint-work-2", work_id=work.id,
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "ISO 9001"},
    )

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["other_editions_count"] == 1


def test_search_endpoint_finds_a_semantic_match_via_the_query_embedding(
    client, db_session, fake_embedding_model,
):
    # fake_embedding_model (api/tests/conftest.py) maps text to a one-hot
    # vector keyed by hash(text) % 1024 -- it's the SAME fixture instance the
    # `client` fixture wired up as the app's get_embedding_model override, so
    # embedding "Absturzsicherung" here produces exactly the vector the
    # running app will compute for that same query text. Pre-loading a
    # DocumentEmbedding with that vector and then searching for that exact
    # text proves the query embedding is actually computed and passed
    # through to Tier 2 end-to-end, without needing the real model.
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:endpoint-semantic",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 38", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 38", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="test", delivery_id=delivery.id,
    )
    vector = fake_embedding_model.embed_query("Absturzsicherung")
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id,
        model_name="intfloat/multilingual-e5-large", vector=vector,
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Absturzsicherung"},
    )

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["best_match"]["id"] == str(document.id)


def test_search_endpoint_returns_400_when_jurisdiction_is_missing(client, db_session):
    response = client.get("/v1/documents/search", params={"q": "Vorschrift"})

    assert response.status_code == 400


def test_search_endpoint_with_no_query_returns_everything_in_the_jurisdiction(client, db_session):
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-2",
    )

    response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_endpoint_respects_limit(client, db_session):
    for n in range(3):
        _seed_document(
            db_session, issuer="DGUV", designation=f"DGUV Vorschrift {n}",
            content_hash=f"sha256:endpoint-limit-{n}",
        )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": 2},
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["results"]) == 2


def test_search_endpoint_rejects_a_negative_limit_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": -1},
    )

    assert response.status_code == 400


def test_search_endpoint_rejects_a_negative_offset_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "offset": -1},
    )

    assert response.status_code == 400


def test_search_endpoint_rejects_a_limit_above_the_maximum_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": 101},
    )

    assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && .venv/bin/pytest tests/test_documents_search_endpoint.py -v`
Expected: FAIL — `response.json()["results"][0]` has no `"work_id"` key yet (old flat `DocumentResponse` shape).

- [ ] **Step 3: Add the new response schemas**

In `api/src/normly_api/schemas.py`, add after `DocumentSearchResponse` (leave `DocumentSearchResponse` itself in place — it stays unused by `search.py` after this task but nothing requires deleting it, and removing it is out of scope for this plan):

```python
class WorkSearchResultResponse(BaseModel):
    work_id: uuid.UUID
    best_match: DocumentResponse
    other_editions_count: int


class WorkSearchResponse(BaseModel):
    results: list[WorkSearchResultResponse]
    total: int
```

- [ ] **Step 4: Rewrite the search endpoint**

Replace the entire contents of `api/src/normly_api/routers/search.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresDocumentRepository
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel

from normly_api.dependencies import get_embedding_model, get_session
from normly_api.routers.documents import document_to_response
from normly_api.schemas import WorkSearchResponse, WorkSearchResultResponse

search_router = APIRouter(prefix="/v1/documents", tags=["search"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@search_router.get("/search", response_model=WorkSearchResponse)
def search_documents_endpoint(
    jurisdiction: str, q: str | None = None, issuer: str | None = None,
    # Declarative bounds rather than a manual min() clamp: the clamp only
    # capped the upper end, so a negative value reached SQL and came back as a
    # 503 -- an unauthenticated caller could raise the exact signal that means
    # "the database is down" at will, and the caller was told to retry a
    # request that can never succeed. These also document themselves in the
    # OpenAPI schema.
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    embedding_model: EmbeddingModel = Depends(get_embedding_model),
) -> WorkSearchResponse:
    query_vector = embedding_model.embed_query(q) if q is not None else None
    doc_repo = PostgresDocumentRepository(session)
    hits, total = doc_repo.search_works_for_jurisdiction(
        jurisdiction, q=q, issuer=issuer, query_vector=query_vector,
        embedding_model_name=MODEL_NAME if query_vector is not None else None,
        limit=limit, offset=offset,
    )
    return WorkSearchResponse(
        results=[
            WorkSearchResultResponse(
                work_id=hit.work_id,
                best_match=document_to_response(hit.best_match, session),
                other_editions_count=hit.other_editions_count,
            )
            for hit in hits
        ],
        total=total,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && .venv/bin/pytest tests/test_documents_search_endpoint.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full api test suite**

Run: `cd api && .venv/bin/pytest -v`
Expected: PASS — including `tests/test_documents_search.py` (the `/v1/documents` find-by-designation endpoint, a different endpoint entirely, untouched by this task) and `tests/test_openapi_and_end_to_end.py` (which may assert on the OpenAPI schema shape — if it references `DocumentSearchResponse` by name, that assertion will need the same rename `WorkSearchResponse` applied; read that file if this run fails here and fix accordingly, matching the same shape change).

- [ ] **Step 7: Run the full core test suite too, to confirm nothing there regressed**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/src/normly_api/schemas.py api/src/normly_api/routers/search.py api/tests/test_documents_search_endpoint.py
git commit -s -m "feat(api): return Work-grouped hybrid search results

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** Hybrid Tier-1/Tier-2 search (Task 4), Work-grouping (Task 4), `DocumentEmbedding` schema + upsert semantics (Task 1), ingestion-time embedding refresh (Task 2), CLI backfill instead of a migration (Task 3), `WorkSearchResultResponse`/`WorkSearchResponse` API shape with `other_editions_count` only — no full edition list (Task 6), `embed_query` vs `embed` prefix distinction exercised explicitly (Task 2 uses `embed`, Task 6 uses `embed_query`). The spec's "Bezug zu Requirements und ADRs" REQ-SEARCH-001 documentation follow-up is a docs-only task, not required for this plan's code to be complete — do it as a small separate commit once this branch is reviewed, same as sub-project 1's ADR-011 follow-up.
- **Placeholder scan:** none — every step carries complete code and exact run commands.
- **Carried-forward item for the final whole-branch review:** `core/tests/pipeline/test_cli.py`'s `_WRITTEN_TABLES` still omits `"work"` (pre-existing gap from sub-project 1, not introduced here — see Task 3 Step 5's note). No test in this plan is affected, but it's the same class of issue as sub-project 1's final-review Finding 1 and worth a one-line fix while a reviewer is already looking at that file.
- **Type consistency:** `DocumentEmbedding`/`WorkSearchHit` field names match exactly between `domain.py`, `orm.py`, `repositories.py`, and their consuming call sites in `document_embedding.py`/`search.py`/`schemas.py`. `query_vector`/`embedding_model_name` parameter names match between the `DocumentRepository` Protocol, `PostgresDocumentRepository`'s implementation, and `search.py`'s call site.
