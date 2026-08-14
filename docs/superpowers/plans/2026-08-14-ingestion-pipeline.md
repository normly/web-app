# Ingestion-Pipeline (EUR-Lex, DGUV) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the reference graph built in the previous sub-project with real data from two free sources (EUR-Lex harmonised-standards lists, DGUV regulations), including full-text segments and embeddings for DGUV's freely usable content.

**Architecture:** A `SourceAdapter` Protocol (directory-based `fetch()`, source-specific `extract_structure()`/`classify_rights()`) feeds a source-agnostic orchestration `runner` that writes through the existing repository layer. Two new derived-artifact tables (`segment`, `embedding`) and a review queue (`identity_resolution_case`) extend the schema; `pgvector` provides the vector column.

**Tech Stack:** Python 3.11+ (continuing `core/` package), SQLAlchemy 2.0, Alembic, `pgvector` (Python client + Postgres extension), `pdfplumber` (PDF text/table extraction), `sentence-transformers` (`intfloat/multilingual-e5-large`).

**Spec:** `docs/superpowers/specs/2026-08-14-ingestion-pipeline-design.md`

## Global Constraints

- Every new source file in `core/` starts with the AGPL license header:
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors
  ```
- Every commit uses `git commit -s` (DCO `Signed-off-by`) and a Conventional Commits subject line.
- `pipeline.domain` and `graph.domain` never import `sqlalchemy` — enforced by an automated test, same pattern as the previous sub-project.
- Every write method taking a `delivery_id` calls the existing `_require_active_delivery` guard first — no exceptions.
- Every new idempotent write follows the established select-then-`begin_nested()`-insert-with-`IntegrityError`-recovery pattern (see `record_delivery` in `core/src/normly_core/graph/postgres/repositories.py`).
- Test output must be pristine (zero warnings) — every task runs the full suite with `-W error` before committing.
- No live network calls in the default test suite except the one, explicit, one-time fixture-download step in Task 13 — everything else runs against checked-in fixtures.
- No secrets in code or tests.

---

## File Structure

```
core/
  pyproject.toml                              # Modify: add pgvector, pdfplumber, sentence-transformers
  migrations/versions/
    0008_enable_pgvector.py
    0009_create_segment.py
    0010_create_embedding.py
    0011_create_identity_resolution_case.py
  src/normly_core/graph/
    domain.py                                 # Modify: Segment, Embedding, IdentityResolutionCase dataclasses + Protocol extensions
    postgres/
      orm.py                                  # Modify: SegmentORM, EmbeddingORM, IdentityResolutionCaseORM
      repositories.py                         # Modify: new repository classes/methods, extended revoke_delivery
  src/normly_core/pipeline/
    __init__.py
    domain.py                                 # RawRecord, RawSection, RawReference, RightsRule, IdentityResolution, SourceAdapter
    identity.py                               # parse_designation, resolve
    references.py                             # extract_references
    embeddings.py                             # EmbeddingModel wrapper
    runner.py                                 # run_adapter orchestration
    cli.py                                    # `python -m normly_core.pipeline`
    adapters/
      __init__.py
      eur_lex.py                              # EurLexAdapter
      dguv.py                                 # DguvAdapter
  tests/
    conftest.py                               # Modify: pgvector-enabled container image
    fixtures/
      eur_lex_machinery_summary.pdf           # trimmed real Commission PDF
      dguv_sample_vorschrift.pdf               # synthetic, realistically structured
    graph/
      test_segment_repository.py
      test_embedding_repository.py
      test_identity_resolution_case_repository.py
      test_delivery_find_and_document_find.py
      test_lineage_revocation_pipeline_tables.py
    pipeline/
      __init__.py
      test_architecture.py
      test_identity.py
      test_references.py
      test_embeddings.py
      test_runner.py
      test_eur_lex_adapter.py
      test_dguv_adapter.py
      test_cli.py
      test_end_to_end.py
```

---

### Task 1: pgvector-enabled test infrastructure and extension migration

**Files:**
- Modify: `core/tests/conftest.py`
- Create: `core/migrations/versions/0008_enable_pgvector.py`
- Test: `core/tests/graph/test_pgvector_extension.py`

**Interfaces:**
- Consumes: `migrated_engine`/`db_session` fixtures from the previous sub-project's `conftest.py`.
- Produces: the `vector` Postgres extension enabled on every test database; nothing else changes for later tasks.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_pgvector_extension.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from sqlalchemy import text


def test_vector_extension_is_enabled(migrated_engine):
    with migrated_engine.connect() as connection:
        result = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        rows = list(result)
    assert len(rows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_pgvector_extension.py -v`
Expected: FAIL — the `postgres:16` image has no `vector` extension available, `CREATE EXTENSION` would error if attempted, and no migration attempts it yet, so the query returns zero rows.

- [ ] **Step 3: Switch the container image**

In `core/tests/conftest.py`, change the `PostgresContainer` construction from `postgres:16` to `pgvector/pgvector:pg16` (keep the existing `driver="psycopg"` argument and the `testcontainers.community.postgres` import — only the image tag changes):

```python
with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as container:
```

- [ ] **Step 4: Add the migration**

```python
# core/migrations/versions/0008_enable_pgvector.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""enable pgvector extension

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-14
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
```

Before writing this file, run `ls core/migrations/versions/` yourself to confirm `0007` is genuinely still the chain head — if a later fix on `main` shifted it, adjust `down_revision` and this file's own number accordingly, the same way earlier tasks in the previous sub-project had to.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_pgvector_extension.py -v`
Expected: PASS (first run pulls the `pgvector/pgvector:pg16` image, allow extra time)

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pre-existing tests still pass, pristine output

- [ ] **Step 7: Commit**

```bash
git add core/tests/conftest.py core/migrations/versions/0008_enable_pgvector.py core/tests/graph/test_pgvector_extension.py
git commit -s -m "feat: switch test infrastructure to pgvector-enabled Postgres"
```

---

### Task 2: `segment` table, domain type, idempotent repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0009_create_segment.py`
- Test: `core/tests/graph/test_segment_repository.py`

**Interfaces:**
- Consumes: `Document`, `DocumentRepository` from `domain.py`; `DocumentORM` from `orm.py`; `_require_active_delivery` from `repositories.py`.
- Produces: `Segment` dataclass and `SegmentRepository` Protocol in `domain.py`; `SegmentORM` in `orm.py`; `PostgresSegmentRepository.add_segment` in `repositories.py` (`list_segments_for_jurisdiction` is added in Task 3, on the same class).

- [ ] **Step 1: Add the domain type and Protocol**

Append to `core/src/normly_core/graph/domain.py`:

```python
@dataclass(frozen=True)
class Segment:
    id: uuid.UUID
    document_id: uuid.UUID
    delivery_id: uuid.UUID
    sequence_number: int
    heading: str | None
    text: str
    language: str
    created_at: datetime


class SegmentRepository(Protocol):
    def add_segment(
        self,
        *,
        document_id: uuid.UUID,
        delivery_id: uuid.UUID,
        sequence_number: int,
        heading: str | None,
        text: str,
        language: str,
    ) -> Segment: ...

    def list_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]: ...
```

- [ ] **Step 2: Write the failing test**

```python
# core/tests/graph/test_segment_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _make_document(db_session, content_hash="sha256:segment-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_add_segment_and_read_back(db_session):
    document, delivery = _make_document(db_session)
    repo = PostgresSegmentRepository(db_session)

    segment = repo.add_segment(
        document_id=document.id,
        delivery_id=delivery.id,
        sequence_number=1,
        heading="§ 3 Grundpflichten",
        text="Der Unternehmer hat dafür zu sorgen, dass...",
        language="de",
    )

    assert segment.document_id == document.id
    assert segment.sequence_number == 1


def test_add_segment_is_idempotent_by_document_and_sequence(db_session):
    document, delivery = _make_document(db_session)
    repo = PostgresSegmentRepository(db_session)

    first = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    second = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )

    assert first.id == second.id
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_segment_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresSegmentRepository'`

- [ ] **Step 4: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
class SegmentORM(Base):
    __tablename__ = "segment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    sequence_number: Mapped[int]
    heading: Mapped[str | None]
    text: Mapped[str]
    language: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "document_id", "sequence_number", name="uq_segment_document_sequence"
        ),
    )
```

- [ ] **Step 5: Add the migration**

Run `ls core/migrations/versions/` first to confirm the actual chain head (should be `0008` after Task 1; adjust `down_revision`/this file's number if a later task shifted it):

```python
# core/migrations/versions/0009_create_segment.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create segment table

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "segment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("heading", sa.String, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("language", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id", "sequence_number", name="uq_segment_document_sequence"
        ),
    )


def downgrade() -> None:
    op.drop_table("segment")
```

- [ ] **Step 6: Add the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import Segment
from normly_core.graph.postgres.orm import SegmentORM


def _segment_to_domain(orm: SegmentORM) -> Segment:
    return Segment(
        id=orm.id,
        document_id=orm.document_id,
        delivery_id=orm.delivery_id,
        sequence_number=orm.sequence_number,
        heading=orm.heading,
        text=orm.text,
        language=orm.language,
        created_at=orm.created_at,
    )


class PostgresSegmentRepository:
    def __init__(self, session: Session):
        self._session = session

    def add_segment(
        self,
        *,
        document_id: uuid.UUID,
        delivery_id: uuid.UUID,
        sequence_number: int,
        heading: str | None,
        text: str,
        language: str,
    ) -> Segment:
        _require_active_delivery(self._session, delivery_id)

        existing = self._session.execute(
            select(SegmentORM).where(
                SegmentORM.document_id == document_id,
                SegmentORM.sequence_number == sequence_number,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _segment_to_domain(existing)

        orm = SegmentORM(
            id=uuid.uuid4(),
            document_id=document_id,
            delivery_id=delivery_id,
            sequence_number=sequence_number,
            heading=heading,
            text=text,
            language=language,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(SegmentORM).where(
                    SegmentORM.document_id == document_id,
                    SegmentORM.sequence_number == sequence_number,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _segment_to_domain(existing)
        return _segment_to_domain(orm)
```

`_require_active_delivery`, `IntegrityError`, and `select` are already imported/defined earlier in this file — do not duplicate.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_segment_repository.py -v`
Expected: PASS

- [ ] **Step 8: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0009_create_segment.py core/tests/graph/test_segment_repository.py
git commit -s -m "feat: add segment table with idempotent recording"
```

---

### Task 3: Rights-gated segment reads

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Test: `core/tests/graph/test_segment_repository.py`

**Interfaces:**
- Consumes: `SegmentRepository.list_segments_for_jurisdiction` signature from Task 2; `RightsClassificationORM` and its established join pattern from `get_document_for_jurisdiction`.
- Produces: `PostgresSegmentRepository.list_segments_for_jurisdiction`, completing `SegmentRepository`.

- [ ] **Step 1: Append the failing tests**

Append to `core/tests/graph/test_segment_repository.py`:

```python
from normly_core.graph.postgres.repositories import PostgresRightsRepository


def test_segments_are_gated_by_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    segment_repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )

    assert segment_repo.list_segments_for_jurisdiction(document.id, "DE") == []

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        classified_by="J. Weber", delivery_id=delivery.id,
    )

    segments = segment_repo.list_segments_for_jurisdiction(document.id, "DE")
    assert len(segments) == 1
    assert segments[0].text == "Text A"
```

Replace the inline `__import__` calls with a proper `from datetime import datetime, timezone` import at the top of the file alongside the existing `date` import — write it as a clean import, the inline form above is only to show the exact values needed; use:

```python
from datetime import date, datetime, timezone
```

and then `classified_at=datetime.now(timezone.utc)` directly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_segment_repository.py::test_segments_are_gated_by_jurisdiction -v`
Expected: FAIL with `AttributeError: 'PostgresSegmentRepository' object has no attribute 'list_segments_for_jurisdiction'`

- [ ] **Step 3: Implement the gated read**

Add to `PostgresSegmentRepository` in `core/src/normly_core/graph/postgres/repositories.py`:

```python
    def list_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]:
        rows = self._session.execute(
            select(SegmentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == SegmentORM.document_id,
            )
            .where(
                SegmentORM.document_id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(SegmentORM.sequence_number)
        ).scalars()
        return [_segment_to_domain(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_segment_repository.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_segment_repository.py
git commit -s -m "feat: gate segment reads by jurisdiction"
```

---

### Task 4: `embedding` table with cascading FK, idempotent repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Modify: `core/pyproject.toml`
- Create: `core/migrations/versions/0010_create_embedding.py`
- Test: `core/tests/graph/test_embedding_repository.py`

**Interfaces:**
- Consumes: `Segment`, `SegmentRepository` from Tasks 2–3; `SegmentORM` from `orm.py`.
- Produces: `Embedding` dataclass and `EmbeddingRepository` Protocol in `domain.py`; `EmbeddingORM` in `orm.py`; `PostgresEmbeddingRepository` in `repositories.py`.

- [ ] **Step 1: Add the `pgvector` dependency**

In `core/pyproject.toml`, add to the `dependencies` list:

```toml
    "pgvector>=0.3,<0.4",
```

Install it: `cd core && .venv/bin/pip install -e ".[dev]"`

- [ ] **Step 2: Add the domain type and Protocol**

Append to `core/src/normly_core/graph/domain.py`:

```python
@dataclass(frozen=True)
class Embedding:
    id: uuid.UUID
    segment_id: uuid.UUID
    delivery_id: uuid.UUID
    model_name: str
    vector: list[float]
    created_at: datetime


class EmbeddingRepository(Protocol):
    def add_embedding(
        self,
        *,
        segment_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> Embedding: ...

    def get_embedding(
        self, segment_id: uuid.UUID, model_name: str
    ) -> Embedding | None: ...
```

- [ ] **Step 3: Write the failing tests**

```python
# core/tests/graph/test_embedding_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _make_segment(db_session, content_hash="sha256:embedding-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    segment = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    return segment, delivery


def test_add_embedding_and_read_back(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    vector = [0.1] * 1024

    embedding = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id,
        model_name="intfloat/multilingual-e5-large", vector=vector,
    )

    fetched = repo.get_embedding(segment.id, "intfloat/multilingual-e5-large")
    assert fetched is not None
    assert fetched.id == embedding.id
    assert len(fetched.vector) == 1024


def test_add_embedding_is_idempotent_by_segment_and_model(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    vector = [0.2] * 1024

    first = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=vector,
    )
    second = repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=vector,
    )

    assert first.id == second.id


def test_embedding_is_removed_when_its_segment_is_deleted(db_session):
    segment, delivery = _make_segment(db_session)
    repo = PostgresEmbeddingRepository(db_session)
    repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=[0.3] * 1024,
    )

    from normly_core.graph.postgres.orm import SegmentORM
    db_session.execute(
        __import__("sqlalchemy").delete(SegmentORM).where(SegmentORM.id == segment.id)
    )
    db_session.flush()

    assert repo.get_embedding(segment.id, "model-a") is None
```

Replace the `__import__("sqlalchemy")` call in the last test with a proper `import sqlalchemy as sa` at the top of the file, then use `sa.delete(SegmentORM)` — the inline form above only exists to show the exact statement; write it cleanly.

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_embedding_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresEmbeddingRepository'`

- [ ] **Step 5: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
from pgvector.sqlalchemy import Vector


class EmbeddingORM(Base):
    __tablename__ = "embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("segment.id", ondelete="CASCADE"), nullable=False
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    model_name: Mapped[str]
    vector: Mapped[list[float]] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("segment_id", "model_name", name="uq_embedding_segment_model"),
    )
```

- [ ] **Step 6: Add the migration**

Confirm the actual chain head first (`ls core/migrations/versions/`, expect `0009`), then:

```python
# core/migrations/versions/0010_create_embedding.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create embedding table

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "segment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("segment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("vector", Vector(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("segment_id", "model_name", name="uq_embedding_segment_model"),
    )


def downgrade() -> None:
    op.drop_table("embedding")
```

- [ ] **Step 7: Add the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import Embedding
from normly_core.graph.postgres.orm import EmbeddingORM


def _embedding_to_domain(orm: EmbeddingORM) -> Embedding:
    return Embedding(
        id=orm.id,
        segment_id=orm.segment_id,
        delivery_id=orm.delivery_id,
        model_name=orm.model_name,
        vector=list(orm.vector),
        created_at=orm.created_at,
    )


class PostgresEmbeddingRepository:
    def __init__(self, session: Session):
        self._session = session

    def add_embedding(
        self,
        *,
        segment_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> Embedding:
        _require_active_delivery(self._session, delivery_id)

        existing = self._session.execute(
            select(EmbeddingORM).where(
                EmbeddingORM.segment_id == segment_id,
                EmbeddingORM.model_name == model_name,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _embedding_to_domain(existing)

        orm = EmbeddingORM(
            id=uuid.uuid4(),
            segment_id=segment_id,
            delivery_id=delivery_id,
            model_name=model_name,
            vector=vector,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(EmbeddingORM).where(
                    EmbeddingORM.segment_id == segment_id,
                    EmbeddingORM.model_name == model_name,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _embedding_to_domain(existing)
        return _embedding_to_domain(orm)

    def get_embedding(self, segment_id: uuid.UUID, model_name: str) -> Embedding | None:
        orm = self._session.execute(
            select(EmbeddingORM).where(
                EmbeddingORM.segment_id == segment_id,
                EmbeddingORM.model_name == model_name,
            )
        ).scalar_one_or_none()
        return _embedding_to_domain(orm) if orm else None
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_embedding_repository.py -v`
Expected: PASS — including the `ondelete="CASCADE"` test, which proves the FK-level cascade works against the real database, not just application code.

- [ ] **Step 9: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 10: Commit**

```bash
git add core/pyproject.toml core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0010_create_embedding.py core/tests/graph/test_embedding_repository.py
git commit -s -m "feat: add embedding table with cascading FK and idempotent recording"
```

---

### Task 5: `identity_resolution_case` table and repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Create: `core/migrations/versions/0011_create_identity_resolution_case.py`
- Test: `core/tests/graph/test_identity_resolution_case_repository.py`

**Interfaces:**
- Consumes: `Document`, `DeliveryORM` conventions established in earlier tasks.
- Produces: `IdentityResolutionStatus` enum, `IdentityResolutionCase` dataclass, `IdentityResolutionRepository` Protocol in `domain.py`; `IdentityResolutionCaseORM` in `orm.py`; `PostgresIdentityResolutionRepository` in `repositories.py`.

- [ ] **Step 1: Add the domain types and Protocol**

Append to `core/src/normly_core/graph/domain.py`:

```python
class IdentityResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IdentityResolutionCase:
    id: uuid.UUID
    delivery_id: uuid.UUID
    raw_designation: str
    raw_issuer: str | None
    reason: str
    status: IdentityResolutionStatus
    resolved_document_id: uuid.UUID | None
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

    def list_pending_cases(self) -> list[IdentityResolutionCase]: ...

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase: ...

    def reject_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase: ...
```

- [ ] **Step 2: Write the failing tests**

```python
# core/tests/graph/test_identity_resolution_case_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import IdentityResolutionStatus, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:identity-case-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_enqueue_and_list_pending_cases(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)

    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="EN ???", raw_issuer="CEN",
        reason="unparseable_designation",
    )

    pending = repo.list_pending_cases()
    assert case.id in {c.id for c in pending}
    assert case.status == IdentityResolutionStatus.PENDING


def test_resolve_case(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="EN 9001:2015", raw_issuer="CEN",
        reason="ambiguous_match",
    )

    resolved = repo.resolve_case(case.id, resolved_document_id=document.id, resolved_by="J. Weber")

    assert resolved.status == IdentityResolutionStatus.RESOLVED
    assert resolved.resolved_document_id == document.id
    assert case.id not in {c.id for c in repo.list_pending_cases()}


def test_reject_case(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="???", raw_issuer=None,
        reason="unparseable_designation",
    )

    rejected = repo.reject_case(case.id, resolved_by="J. Weber")

    assert rejected.status == IdentityResolutionStatus.REJECTED
    assert case.id not in {c.id for c in repo.list_pending_cases()}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_identity_resolution_case_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresIdentityResolutionRepository'`

- [ ] **Step 4: Add the ORM model**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
from normly_core.graph.domain import IdentityResolutionStatus


class IdentityResolutionCaseORM(Base):
    __tablename__ = "identity_resolution_case"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    raw_designation: Mapped[str]
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
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolved_by: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

`_enum_values` is the helper already defined near the top of `orm.py` (used by `legal_basis_category`/`tdm_opt_out_result`/`edge_type`/`layer`) — reuse it, do not redefine it.

- [ ] **Step 5: Add the migration**

Confirm the actual chain head first (expect `0010`), then:

```python
# core/migrations/versions/0011_create_identity_resolution_case.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create identity_resolution_case table

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_resolution_case",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("raw_designation", sa.String, nullable=False),
        sa.Column("raw_issuer", sa.String, nullable=True),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "resolved", "rejected",
                name="identity_resolution_status", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "resolved_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("identity_resolution_case")
```

- [ ] **Step 6: Add the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py`:

```python
from normly_core.graph.domain import IdentityResolutionCase, IdentityResolutionStatus
from normly_core.graph.postgres.orm import IdentityResolutionCaseORM


def _identity_case_to_domain(orm: IdentityResolutionCaseORM) -> IdentityResolutionCase:
    return IdentityResolutionCase(
        id=orm.id,
        delivery_id=orm.delivery_id,
        raw_designation=orm.raw_designation,
        raw_issuer=orm.raw_issuer,
        reason=orm.reason,
        status=orm.status,
        resolved_document_id=orm.resolved_document_id,
        resolved_at=orm.resolved_at,
        resolved_by=orm.resolved_by,
        created_at=orm.created_at,
    )


class PostgresIdentityResolutionRepository:
    def __init__(self, session: Session):
        self._session = session

    def enqueue_case(
        self,
        *,
        delivery_id: uuid.UUID,
        raw_designation: str,
        raw_issuer: str | None,
        reason: str,
    ) -> IdentityResolutionCase:
        _require_active_delivery(self._session, delivery_id)
        orm = IdentityResolutionCaseORM(
            id=uuid.uuid4(),
            delivery_id=delivery_id,
            raw_designation=raw_designation,
            raw_issuer=raw_issuer,
            reason=reason,
            status=IdentityResolutionStatus.PENDING,
        )
        self._session.add(orm)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def list_pending_cases(self) -> list[IdentityResolutionCase]:
        rows = self._session.execute(
            select(IdentityResolutionCaseORM)
            .where(IdentityResolutionCaseORM.status == IdentityResolutionStatus.PENDING)
            .order_by(IdentityResolutionCaseORM.created_at)
        ).scalars()
        return [_identity_case_to_domain(row) for row in rows]

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        orm.status = IdentityResolutionStatus.RESOLVED
        orm.resolved_document_id = resolved_document_id
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def reject_case(self, case_id: uuid.UUID, *, resolved_by: str) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        orm.status = IdentityResolutionStatus.REJECTED
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_identity_resolution_case_repository.py -v`
Expected: PASS

- [ ] **Step 8: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0011_create_identity_resolution_case.py core/tests/graph/test_identity_resolution_case_repository.py
git commit -s -m "feat: add identity resolution review queue"
```

---

### Task 6: `find_delivery` and `find_by_designation` — non-breaking repository extensions

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Test: `core/tests/graph/test_delivery_find_and_document_find.py`

**Interfaces:**
- Consumes: `DeliveryRepository`, `DocumentRepository` Protocols; `DeliveryORM`, `DocumentORM`, `DocumentDesignationORM`.
- Produces: `DeliveryRepository.find_delivery(source_id, content_hash) -> Delivery | None`; `DocumentRepository.find_by_designation(issuer, designation) -> Document | None`. Both are pure additions — no existing method signature changes.

- [ ] **Step 1: Add both methods to their Protocols**

In `core/src/normly_core/graph/domain.py`, add to `DeliveryRepository`:

```python
    def find_delivery(self, source_id: uuid.UUID, content_hash: str) -> Delivery | None: ...
```

Add to `DocumentRepository`:

```python
    def find_by_designation(self, issuer: str, designation: str) -> Document | None: ...
```

- [ ] **Step 2: Write the failing tests**

```python
# core/tests/graph/test_delivery_find_and_document_find.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def test_find_delivery_returns_none_when_absent(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)

    assert delivery_repo.find_delivery(source.id, "sha256:never-seen") is None


def test_find_delivery_returns_existing_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    created = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:find-me", ingested_at=datetime.now(timezone.utc)
    )

    found = delivery_repo.find_delivery(source.id, "sha256:find-me")

    assert found is not None
    assert found.id == created.id


def test_find_by_designation_returns_none_when_absent(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    assert doc_repo.find_by_designation("CEN", "EN 0000:0000") is None


def test_find_by_designation_returns_matching_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:designation-find", ingested_at=datetime.now(timezone.utc)
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")

    assert found is not None
    assert found.id == document.id
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_delivery_find_and_document_find.py -v`
Expected: FAIL with `AttributeError` for both missing methods

- [ ] **Step 4: Implement `find_delivery`**

Add to `PostgresDeliveryRepository` in `core/src/normly_core/graph/postgres/repositories.py`:

```python
    def find_delivery(self, source_id: uuid.UUID, content_hash: str) -> Delivery | None:
        orm = self._session.execute(
            select(DeliveryORM).where(
                DeliveryORM.source_id == source_id,
                DeliveryORM.content_hash == content_hash,
            )
        ).scalar_one_or_none()
        return _delivery_to_domain(orm) if orm else None
```

- [ ] **Step 5: Implement `find_by_designation`**

Add to `PostgresDocumentRepository`:

```python
    def find_by_designation(self, issuer: str, designation: str) -> Document | None:
        orm = self._session.execute(
            select(DocumentORM)
            .join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
            )
        ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_delivery_find_and_document_find.py -v`
Expected: PASS

- [ ] **Step 7: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_delivery_find_and_document_find.py
git commit -s -m "feat: add find_delivery and find_by_designation lookups"
```

---

### Task 7: Extend cascading revocation and the drift guard to `segment`/`embedding`/`identity_resolution_case`

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Modify: `core/tests/graph/test_lineage_revocation.py` (the drift-guard test)
- Test: `core/tests/graph/test_lineage_revocation_pipeline_tables.py`

**Interfaces:**
- Consumes: `PostgresDeliveryRepository.revoke_delivery` from the previous sub-project; `SegmentORM`, `EmbeddingORM`, `IdentityResolutionCaseORM`.
- Produces: `revoke_delivery` extended to sweep the three new tables; the drift guard extended to expect them.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/graph/test_lineage_revocation_pipeline_tables.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import EmbeddingORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresIdentityResolutionRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:pipeline-revocation",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_revoking_a_delivery_removes_its_segments_and_embeddings(db_session):
    document, delivery = _setup(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    embedding_repo = PostgresEmbeddingRepository(db_session)

    segment = segment_repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 3", text="Text A", language="de",
    )
    embedding_repo.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name="model-a", vector=[0.1] * 1024,
    )

    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_repo.revoke_delivery(delivery.id)

    remaining_segment = db_session.get(
        __import__("normly_core.graph.postgres.orm", fromlist=["SegmentORM"]).SegmentORM,
        segment.id,
    )
    assert remaining_segment is None
    assert embedding_repo.get_embedding(segment.id, "model-a") is None


def test_revoking_a_delivery_rejects_its_pending_identity_case(db_session):
    document, delivery = _setup(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    case = identity_repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="???", raw_issuer=None,
        reason="unparseable_designation",
    )

    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_repo.revoke_delivery(delivery.id)

    assert case.id not in {c.id for c in identity_repo.list_pending_cases()}
```

Replace the `__import__(...)` line in the first test with a proper top-of-file import
(`from normly_core.graph.postgres.orm import SegmentORM` alongside the existing `EmbeddingORM`
import) and then `db_session.get(SegmentORM, segment.id)` directly — the inline form only shows
what to check.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_lineage_revocation_pipeline_tables.py -v`
Expected: FAIL — `remaining_segment` is not `None` (the segment was never removed), and the identity case is still pending

- [ ] **Step 3: Extend `revoke_delivery`**

In `core/src/normly_core/graph/postgres/repositories.py`, find the existing `revoke_delivery` method on `PostgresDeliveryRepository` (it currently ends with the `document_title` delete followed by `self._session.flush()`) and insert three more statements before the final `flush()`:

```python
        self._session.execute(
            sa.delete(SegmentORM).where(SegmentORM.delivery_id == delivery_id)
        )
        self._session.execute(
            sa.delete(EmbeddingORM).where(EmbeddingORM.delivery_id == delivery_id)
        )
        self._session.execute(
            sa.update(IdentityResolutionCaseORM)
            .where(
                IdentityResolutionCaseORM.delivery_id == delivery_id,
                IdentityResolutionCaseORM.status == IdentityResolutionStatus.PENDING,
            )
            .values(
                status=IdentityResolutionStatus.REJECTED,
                resolved_by="system:delivery_revoked",
                resolved_at=now,
            )
        )
```

Deleting `SegmentORM` rows first lets the `embedding.segment_id` `ON DELETE CASCADE` remove any
embedding attached to a deleted segment regardless of which delivery created that embedding
(the same cross-artifact case documented in the design spec); the explicit `EmbeddingORM` delete
afterwards catches embeddings whose own `delivery_id` is the revoked one but whose segment
belongs to a still-active delivery. Pending identity cases are rejected, not deleted — deleting
them would erase the fact that this delivery ever produced an ambiguous record, and REQ-PIPE-005
asks for a traceable, not silently vanishing, revocation. `now` is the same variable already
computed earlier in the method (`datetime.now(orm.ingested_at.tzinfo)`) — reuse it, do not
recompute it.

- [ ] **Step 4: Extend the drift guard**

In `core/tests/graph/test_lineage_revocation.py`, find
`test_revoke_delivery_covers_every_delivery_scoped_table` and update its `expected_cascaded` set:

```python
    expected_cascaded = {
        "edge", "rights_classification", "document_designation", "document_title",
        "segment", "embedding",
    }
```

`identity_resolution_case` is deliberately NOT in `expected_cascaded` (it is rejected in place,
not deleted or locked) — add it to a third set and adjust the final assertion:

```python
    expected_rejected_in_place = {"identity_resolution_case"}
    expected_exempt = {"document"}
    assert delivery_scoped_tables == (
        expected_cascaded | expected_rejected_in_place | expected_exempt
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_lineage_revocation_pipeline_tables.py tests/graph/test_lineage_revocation.py -v`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_lineage_revocation.py core/tests/graph/test_lineage_revocation_pipeline_tables.py
git commit -s -m "feat: cascade delivery revocation to segments, embeddings, and identity cases"
```

---

### Task 8: `pipeline.domain` — RawRecord, SourceAdapter, and friends

**Files:**
- Create: `core/src/normly_core/pipeline/__init__.py`
- Create: `core/src/normly_core/pipeline/domain.py`
- Create: `core/tests/pipeline/__init__.py`
- Test: `core/tests/pipeline/test_architecture.py`

**Interfaces:**
- Consumes: `EdgeType` from `normly_core.graph.domain`.
- Produces: `RawReference`, `RawSection`, `RawRecord`, `RightsRule`, `IdentityResolution`, `SourceAdapter` — used by every later pipeline task.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/pipeline/__init__.py
```

```python
# core/tests/pipeline/test_architecture.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import ast
from pathlib import Path


def test_pipeline_domain_does_not_import_sqlalchemy():
    domain_path = (
        Path(__file__).parents[2] / "src" / "normly_core" / "pipeline" / "domain.py"
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

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_architecture.py -v`
Expected: FAIL with `FileNotFoundError` (domain.py does not exist yet)

- [ ] **Step 3: Write the package files**

```python
# core/src/normly_core/pipeline/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# core/src/normly_core/pipeline/domain.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Protocol

from normly_core.graph.domain import EdgeType


@dataclass(frozen=True)
class RawReference:
    target_issuer: str
    target_designation: str
    edge_type: EdgeType


@dataclass(frozen=True)
class RawSection:
    sequence_number: int
    heading: str | None
    text: str


@dataclass(frozen=True)
class RawRecord:
    source_id: uuid.UUID
    content_hash: str
    raw_designation: str
    raw_issuer: str | None
    raw_title: str | None
    full_text: str | None
    raw_references: list[RawReference] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: __import__("datetime").datetime.now())
```

Replace the `fetched_at` default with a clean import instead of the inline `__import__` call —
add `from datetime import datetime` is already present via the `datetime` import above, so write:

```python
    fetched_at: datetime = field(default_factory=datetime.utcnow)
```

Continue the file:

```python
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
    document_id: uuid.UUID | None
    is_new: bool
    is_ambiguous: bool
    reason: str | None


class SourceAdapter(Protocol):
    source_id: uuid.UUID

    def fetch(self) -> Iterable[RawRecord]: ...
    def extract_structure(self, record: RawRecord) -> list[RawSection]: ...
    def classify_rights(self, record: RawRecord) -> RightsRule: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_architecture.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/__init__.py core/src/normly_core/pipeline/domain.py core/tests/pipeline/__init__.py core/tests/pipeline/test_architecture.py
git commit -s -m "feat: add pipeline domain layer (RawRecord, SourceAdapter)"
```

---

### Task 9: Identity resolution — designation parsing and matching

**Files:**
- Create: `core/src/normly_core/pipeline/identity.py`
- Test: `core/tests/pipeline/test_identity.py`

**Interfaces:**
- Consumes: `RawRecord`, `IdentityResolution` from Task 8; `DocumentRepository.find_by_designation` from Task 6.
- Produces: `parse_designation(raw: str) -> ParsedDesignation`, `UnparseableDesignationError`, `resolve(raw_record, document_repo) -> IdentityResolution` — used by the runner in Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/pipeline/test_identity.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord
from normly_core.pipeline.identity import (
    ParsedDesignation,
    UnparseableDesignationError,
    parse_designation,
    resolve,
)


def test_parse_designation_splits_number_and_edition():
    parsed = parse_designation("EN ISO 12100:2010")
    assert parsed == ParsedDesignation(number="EN ISO 12100", edition="2010")


def test_parse_designation_without_edition():
    parsed = parse_designation("DGUV Vorschrift 1")
    assert parsed == ParsedDesignation(number="DGUV Vorschrift 1", edition=None)


def test_parse_designation_rejects_empty_string():
    with pytest.raises(UnparseableDesignationError):
        parse_designation("   ")


def _make_record(raw_designation, raw_issuer):
    return RawRecord(
        source_id=uuid.uuid4(),
        content_hash="sha256:identity-test",
        raw_designation=raw_designation,
        raw_issuer=raw_issuer,
        raw_title=None,
        full_text=None,
    )


def test_resolve_finds_existing_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-existing",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("EN ISO 12100:2010", "CEN")
    result = resolve(record, doc_repo)

    assert result.document_id == document.id
    assert result.is_new is False
    assert result.is_ambiguous is False


def test_resolve_reports_new_document(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("EN ISO 99999:2030", "CEN")

    result = resolve(record, doc_repo)

    assert result.document_id is None
    assert result.is_new is True
    assert result.is_ambiguous is False


def test_resolve_reports_ambiguous_for_unparseable_designation(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("   ", "CEN")

    result = resolve(record, doc_repo)

    assert result.is_ambiguous is True
    assert result.reason == "unparseable_designation"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_identity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.identity'`

- [ ] **Step 3: Write the implementation**

```python
# core/src/normly_core/pipeline/identity.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass

from normly_core.graph.domain import DocumentRepository
from normly_core.pipeline.domain import IdentityResolution, RawRecord


class UnparseableDesignationError(Exception):
    def __init__(self, raw: str):
        self.raw = raw
        super().__init__(f"cannot parse designation: {raw!r}")


@dataclass(frozen=True)
class ParsedDesignation:
    number: str
    edition: str | None


def parse_designation(raw: str) -> ParsedDesignation:
    stripped = raw.strip()
    if not stripped:
        raise UnparseableDesignationError(raw)
    if ":" in stripped:
        number_part, edition = stripped.rsplit(":", 1)
        number_part = number_part.strip()
        edition = edition.strip()
        if not number_part:
            raise UnparseableDesignationError(raw)
        return ParsedDesignation(number=number_part, edition=edition or None)
    return ParsedDesignation(number=stripped, edition=None)


def resolve(record: RawRecord, document_repo: DocumentRepository) -> IdentityResolution:
    try:
        parse_designation(record.raw_designation)
    except UnparseableDesignationError:
        return IdentityResolution(
            document_id=None, is_new=False, is_ambiguous=True,
            reason="unparseable_designation",
        )

    if record.raw_issuer is not None:
        existing = document_repo.find_by_designation(record.raw_issuer, record.raw_designation)
        if existing is not None:
            return IdentityResolution(
                document_id=existing.id, is_new=False, is_ambiguous=False, reason=None
            )

    return IdentityResolution(document_id=None, is_new=True, is_ambiguous=False, reason=None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_identity.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/identity.py core/tests/pipeline/test_identity.py
git commit -s -m "feat: add identity resolution (designation parsing and matching)"
```

---

### Task 10: Reference extraction

**Files:**
- Create: `core/src/normly_core/pipeline/references.py`
- Test: `core/tests/pipeline/test_references.py`

**Interfaces:**
- Consumes: `RawReference`, `RawRecord` from Task 8; `DocumentRepository.find_by_designation` from Task 6; `EdgeRepository.create_edge` from the previous sub-project.
- Produces: `extract_references(record, document_id, delivery_id, document_repo, edge_repo, identity_repo) -> None` — used by the runner in Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/pipeline/test_references.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference
from normly_core.pipeline.references import extract_references


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:references-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    return doc_repo, delivery, standard


def test_extract_references_creates_edge_when_target_exists(db_session):
    doc_repo, delivery, standard = _setup(db_session)
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=legal_act.id, issuer="EU", designation="2006/42/EC", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=uuid.uuid4() if False else __import__("uuid").uuid4(),
        content_hash="sha256:ref-record", raw_designation="EN ISO 12100:2010",
        raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )

    extract_references(record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo)

    edges = edge_repo.list_edges_for_jurisdiction(standard.id, "EU")
    # No rights classification exists yet in this test, so the gated list is empty by
    # design (REQ-PIPE-004) — assert directly against the ORM instead to prove the edge
    # was actually created, independent of the rights gate.
    from normly_core.graph.postgres.orm import EdgeORM
    from sqlalchemy import select

    created = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == legal_act.id
        )
    ).scalar_one_or_none()
    assert created is not None
    assert created.edge_type == EdgeType.BASED_ON_LAW


def test_extract_references_enqueues_case_when_target_missing(db_session):
    doc_repo, delivery, standard = _setup(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=__import__("uuid").uuid4(), content_hash="sha256:ref-missing-target",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="9999/99/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )

    extract_references(record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo)

    pending = identity_repo.list_pending_cases()
    assert any(c.reason == "reference_target_not_found" for c in pending)
```

Replace both `__import__("uuid").uuid4()` calls with a proper `import uuid` at the top of the
file and `uuid.uuid4()` — the inline form only shows what value is needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_references.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.references'`

- [ ] **Step 3: Write the implementation**

```python
# core/src/normly_core/pipeline/references.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from normly_core.graph.domain import DocumentRepository, EdgeRepository, IdentityResolutionRepository
from normly_core.pipeline.domain import RawRecord


def extract_references(
    record: RawRecord,
    document_id: uuid.UUID,
    delivery_id: uuid.UUID,
    document_repo: DocumentRepository,
    edge_repo: EdgeRepository,
    identity_repo: IdentityResolutionRepository,
) -> None:
    for reference in record.raw_references:
        target = document_repo.find_by_designation(
            reference.target_issuer, reference.target_designation
        )
        if target is None:
            identity_repo.enqueue_case(
                delivery_id=delivery_id,
                raw_designation=reference.target_designation,
                raw_issuer=reference.target_issuer,
                reason="reference_target_not_found",
            )
            continue
        edge_repo.create_edge(
            from_document_id=document_id,
            to_document_id=target.id,
            edge_type=reference.edge_type,
            jurisdiction=None,
            layer=__import__("normly_core.graph.domain", fromlist=["Layer"]).Layer.FREE,
            delivery_id=delivery_id,
        )
```

Replace the `__import__(...)` call for `Layer` with a proper `from normly_core.graph.domain
import DocumentRepository, EdgeRepository, IdentityResolutionRepository, Layer` on the existing
import line, then use `Layer.FREE` directly — the inline form only shows what value is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_references.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/references.py core/tests/pipeline/test_references.py
git commit -s -m "feat: add reference extraction with issue-queue fallback"
```

---

### Task 11: Embedding model wrapper

**Files:**
- Modify: `core/pyproject.toml`
- Create: `core/src/normly_core/pipeline/embeddings.py`
- Test: `core/tests/pipeline/test_embeddings.py`

**Interfaces:**
- Consumes: nothing from earlier pipeline tasks.
- Produces: `EmbeddingModel` class with `.embed(text: str) -> list[float]` and a `MODEL_NAME` constant — used by the runner in Task 12.

- [ ] **Step 1: Add the dependency**

In `core/pyproject.toml`, add to `dependencies`:

```toml
    "sentence-transformers>=3.0,<4.0",
```

Install: `cd core && .venv/bin/pip install -e ".[dev]"` — this pulls in `torch` and will take
noticeably longer than previous installs; that is expected.

- [ ] **Step 2: Write the failing test**

```python
# core/tests/pipeline/test_embeddings.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel


def test_embed_returns_1024_dimensional_vector():
    model = EmbeddingModel()

    vector = model.embed("Der Unternehmer hat dafür zu sorgen, dass Gefährdungen vermieden werden.")

    assert len(vector) == 1024
    assert all(isinstance(component, float) for component in vector)


def test_embed_is_deterministic_for_the_same_text():
    model = EmbeddingModel()
    text = "Sicherheit am Arbeitsplatz"

    first = model.embed(text)
    second = model.embed(text)

    assert first == second


def test_model_name_matches_the_loaded_model():
    assert MODEL_NAME == "intfloat/multilingual-e5-large"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_embeddings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.embeddings'`

- [ ] **Step 4: Write the implementation**

```python
# core/src/normly_core/pipeline/embeddings.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-large"


class EmbeddingModel:
    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        # e5 models are trained with an instruction prefix; "passage: " is the
        # documented convention for indexing content (as opposed to "query: " for
        # search queries issued against the index).
        prefixed = f"passage: {text}"
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return vector.tolist()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_embeddings.py -v`
Expected: PASS (first run downloads the model from Hugging Face, several hundred MB — allow
significant extra time; the model is cached locally afterwards)

- [ ] **Step 6: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 7: Commit**

```bash
git add core/pyproject.toml core/src/normly_core/pipeline/embeddings.py core/tests/pipeline/test_embeddings.py
git commit -s -m "feat: add multilingual-e5-large embedding wrapper"
```

---

### Task 12: Pipeline orchestration (`runner`)

**Files:**
- Create: `core/src/normly_core/pipeline/runner.py`
- Test: `core/tests/pipeline/test_runner.py`

**Interfaces:**
- Consumes: `SourceAdapter`, `RawRecord` from Task 8; `identity.resolve` from Task 9; `references.extract_references` from Task 10; `EmbeddingModel` from Task 11; every repository from Tasks 2–6 and the previous sub-project.
- Produces: `run_adapter(adapter, session) -> RunSummary` — the entry point Task 15's CLI calls.

This task uses a minimal in-memory fake `SourceAdapter` (not a real PDF adapter — those come in
Tasks 13–14) so the orchestration logic is tested in isolation from PDF parsing.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/pipeline/test_runner.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import PostgresSourceRepository
from normly_core.pipeline.domain import RawRecord, RawReference, RawSection, RightsRule
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records, sections_by_designation=None):
        self.source_id = source_id
        self._records = records
        self._sections = sections_by_designation or {}

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return self._sections.get(record.raw_designation, [])

    def classify_rights(self, record):
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=record.full_text is not None,
            may_cite_passages=record.full_text is not None, may_export_free=True,
            legal_basis_reference="§ 5 UrhG",
        )


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )


def test_run_adapter_creates_a_document_for_a_new_record(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-new-doc", raw_designation="DGUV Vorschrift 1",
        raw_issuer="DGUV", raw_title="Grundsätze der Prävention", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    summary = run_adapter(adapter, db_session)

    assert summary.documents_created == 1
    assert summary.records_processed == 1
    assert summary.records_skipped == 0


def test_run_adapter_skips_unchanged_delivery_on_second_run(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-skip", raw_designation="DGUV Vorschrift 2",
        raw_issuer="DGUV", raw_title="Titel", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)
    second_summary = run_adapter(adapter, db_session)

    assert second_summary.records_skipped == 1
    assert second_summary.documents_created == 0


def test_run_adapter_segments_and_embeds_full_text_records(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-fulltext", raw_designation="DGUV Vorschrift 3",
        raw_issuer="DGUV", raw_title="Titel", full_text="§ 1 Text. § 2 Mehr Text.",
    )
    sections = {
        "DGUV Vorschrift 3": [
            RawSection(sequence_number=1, heading="§ 1", text="Text."),
            RawSection(sequence_number=2, heading="§ 2", text="Mehr Text."),
        ]
    }
    adapter = _FakeAdapter(source.id, [record], sections)

    summary = run_adapter(adapter, db_session)

    assert summary.segments_created == 2
    assert summary.embeddings_created == 2


def test_run_adapter_enqueues_unparseable_designations(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:runner-ambiguous", raw_designation="   ",
        raw_issuer="DGUV", raw_title=None, full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    summary = run_adapter(adapter, db_session)

    assert summary.records_enqueued_for_review == 1
    assert summary.documents_created == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.runner'`

- [ ] **Step 3: Write the implementation**

```python
# core/src/normly_core/pipeline/runner.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresEmbeddingRepository,
    PostgresIdentityResolutionRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
)
from normly_core.pipeline import identity, references
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.embeddings import EmbeddingModel


@dataclass
class RunSummary:
    records_processed: int = 0
    records_skipped: int = 0
    records_enqueued_for_review: int = 0
    documents_created: int = 0
    segments_created: int = 0
    embeddings_created: int = 0


def run_adapter(adapter: SourceAdapter, session: Session) -> RunSummary:
    delivery_repo = PostgresDeliveryRepository(session)
    document_repo = PostgresDocumentRepository(session)
    rights_repo = PostgresRightsRepository(session)
    edge_repo = PostgresEdgeRepository(session)
    segment_repo = PostgresSegmentRepository(session)
    embedding_repo = PostgresEmbeddingRepository(session)
    identity_repo = PostgresIdentityResolutionRepository(session)
    embedding_model: EmbeddingModel | None = None

    summary = RunSummary()

    for record in adapter.fetch():
        if delivery_repo.find_delivery(record.source_id, record.content_hash) is not None:
            summary.records_skipped += 1
            continue

        delivery = delivery_repo.record_delivery(
            source_id=record.source_id,
            content_hash=record.content_hash,
            ingested_at=datetime.now(timezone.utc),
        )
        summary.records_processed += 1

        result = identity.resolve(record, document_repo)
        if result.is_ambiguous:
            identity_repo.enqueue_case(
                delivery_id=delivery.id,
                raw_designation=record.raw_designation,
                raw_issuer=record.raw_issuer,
                reason=result.reason or "unknown",
            )
            summary.records_enqueued_for_review += 1
            continue

        if result.is_new:
            parsed = identity.parse_designation(record.raw_designation)
            document = document_repo.create_document(
                origin_issuer=record.raw_issuer or "unknown",
                origin_number=parsed.number,
                edition=parsed.edition or "",
                part=None,
                delivery_id=delivery.id,
            )
            summary.documents_created += 1
        else:
            document = document_repo.get_document_unchecked(result.document_id)

        if record.raw_issuer is not None:
            document_repo.add_designation(
                document_id=document.id,
                issuer=record.raw_issuer,
                designation=record.raw_designation,
                language="en",
                edition=None,
                is_primary=True,
                delivery_id=delivery.id,
            )
        if record.raw_title is not None:
            document_repo.add_title(
                document_id=document.id,
                language="en",
                title=record.raw_title,
                delivery_id=delivery.id,
            )

        rule = adapter.classify_rights(record)
        rights_repo.classify(
            document_id=document.id,
            jurisdiction=rule.jurisdiction,
            may_process=rule.may_process,
            may_index_fulltext=rule.may_index_fulltext,
            may_cite_passages=rule.may_cite_passages,
            may_export_free=rule.may_export_free,
            legal_basis_reference=rule.legal_basis_reference,
            classified_at=datetime.now(timezone.utc),
            classified_by="pipeline:automatic",
            delivery_id=delivery.id,
        )

        references.extract_references(
            record, document.id, delivery.id, document_repo, edge_repo, identity_repo
        )

        if record.full_text is not None:
            for section in adapter.extract_structure(record):
                segment = segment_repo.add_segment(
                    document_id=document.id,
                    delivery_id=delivery.id,
                    sequence_number=section.sequence_number,
                    heading=section.heading,
                    text=section.text,
                    language="de",
                )
                summary.segments_created += 1

                if embedding_model is None:
                    embedding_model = EmbeddingModel()
                vector = embedding_model.embed(segment.text)
                embedding_repo.add_embedding(
                    segment_id=segment.id,
                    delivery_id=delivery.id,
                    model_name=embedding_model.MODEL_NAME
                    if hasattr(embedding_model, "MODEL_NAME")
                    else __import__("normly_core.pipeline.embeddings", fromlist=["MODEL_NAME"]).MODEL_NAME,
                    vector=vector,
                )
                summary.embeddings_created += 1

    return summary
```

Replace the awkward `embedding_model.MODEL_NAME if hasattr(...) else __import__(...)` expression
with a clean top-level import instead: add `from normly_core.pipeline.embeddings import
EmbeddingModel, MODEL_NAME` to the existing import line, delete the `EmbeddingModel` import that
duplicates it, and simply write `model_name=MODEL_NAME` — the inline form above only exists to
show which constant is needed; write the clean version.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_runner.py -v`
Expected: PASS — this test run genuinely loads and runs the real embedding model (Task 12's
fake adapter still produces real segment text that gets really embedded), so expect it to take
longer than a typical repository test.

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/runner.py core/tests/pipeline/test_runner.py
git commit -s -m "feat: add pipeline orchestration runner"
```

---

### Task 13: EUR-Lex adapter — real „Summary list" PDF fixture and table parser

**Files:**
- Create: `core/tests/fixtures/eur_lex_machinery_summary.pdf`
- Create: `core/src/normly_core/pipeline/adapters/__init__.py`
- Create: `core/src/normly_core/pipeline/adapters/eur_lex.py`
- Test: `core/tests/pipeline/test_eur_lex_adapter.py`
- Modify: `core/pyproject.toml`

**Interfaces:**
- Consumes: `RawRecord`, `RawReference`, `RightsRule`, `SourceAdapter` from Task 8.
- Produces: `EurLexAdapter(directory: Path, source_id: uuid.UUID, legislation_reference: str)` implementing `SourceAdapter` — used by the CLI in Task 15.

- [ ] **Step 1: Add the `pdfplumber` dependency**

In `core/pyproject.toml`, add to `dependencies`:

```toml
    "pdfplumber>=0.11,<0.12",
```

Install: `cd core && .venv/bin/pip install -e ".[dev]"`

- [ ] **Step 2: Create the real fixture PDF**

Download the real, publicly available European Commission summary list and trim it to its
first two pages (the header plus seven real standard rows) so the fixture stays small:

```bash
mkdir -p core/tests/fixtures
curl -sL -o /tmp/eur_lex_full.pdf \
  "https://single-market-economy.ec.europa.eu/system/files/2021-10/2006_42%20Machinery%20-%20Summary%20list%20of%20harmonised%20standards%20-%20Generated%20on%2015.10.2021.pdf"
cd core && .venv/bin/python -c "
from pypdf import PdfReader, PdfWriter
reader = PdfReader('/tmp/eur_lex_full.pdf')
writer = PdfWriter()
for page in reader.pages[:2]:
    writer.add_page(page)
with open('tests/fixtures/eur_lex_machinery_summary.pdf', 'wb') as f:
    writer.write(f)
"
```

`pypdf` is already an installed dependency (SentenceTransformers pulls transitive PDF tooling in
some environments, but do not rely on that — if `pypdf` is not importable, add
`"pypdf>=4.0,<5.0"` to `core/pyproject.toml`'s `dependencies` and reinstall first). Verify the
trimmed file: `cd core && .venv/bin/python -c "import pdfplumber; print(pdfplumber.open('tests/fixtures/eur_lex_machinery_summary.pdf').pages[0].extract_text()[:200])"` — expect it to
print text starting with "EUROPEAN COMMISSION".

If the download fails (no network access in this environment), report BLOCKED with the exact
error — do not fabricate a substitute PDF purporting to be the real Commission document; ask for
guidance instead, since the whole point of this fixture is that it is genuine.

- [ ] **Step 3: Write the failing tests**

```python
# core/tests/pipeline/test_eur_lex_adapter.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_fetch_yields_the_legal_act_record_first():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())

    assert records[0].raw_designation == "2006/42/EC"
    assert records[0].raw_issuer == "EU"
    assert records[0].full_text is None


def test_fetch_yields_standard_records_with_based_on_law_reference():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())
    standard_records = [r for r in records if r.raw_designation != "2006/42/EC"]

    assert len(standard_records) >= 1
    first = standard_records[0]
    assert first.raw_issuer == "CEN"
    assert "EN ISO 12100" in first.raw_designation
    assert first.full_text is None
    assert first.raw_references == [
        RawReferenceMatch := first.raw_references[0]
    ]
    assert RawReferenceMatch.target_issuer == "EU"
    assert RawReferenceMatch.target_designation == "2006/42/EC"
    assert RawReferenceMatch.edge_type == EdgeType.BASED_ON_LAW


def test_extract_structure_is_always_empty():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )
    records = list(adapter.fetch())

    assert adapter.extract_structure(records[1]) == []


def test_classify_rights_denies_fulltext_but_allows_export():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )
    records = list(adapter.fetch())

    rule = adapter.classify_rights(records[1])

    assert rule.may_process is True
    assert rule.may_index_fulltext is False
    assert rule.may_cite_passages is False
    assert rule.may_export_free is True
```

Fix the slightly awkward walrus expression in the second test — replace the
`assert first.raw_references == [RawReferenceMatch := first.raw_references[0]]` line with two
plain statements instead:

```python
    assert len(first.raw_references) == 1
    reference = first.raw_references[0]
```

and then use `reference.target_issuer` etc. below — the walrus form above was only there to show
the intent; write the clean two-statement version.

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_eur_lex_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.adapters'`

- [ ] **Step 5: Write the implementation**

```python
# core/src/normly_core/pipeline/adapters/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# core/src/normly_core/pipeline/adapters/eur_lex.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pdfplumber

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.domain import (
    RawRecord,
    RawReference,
    RawSection,
    RightsRule,
)

# Column indices in the Commission's "Summary list of harmonised standards" table,
# 0-based, matching the real, verified layout: Legislation reference, ESO, Reference
# number of the standard, Title of the standard, Type, ... (remaining columns unused
# for now, see design spec's Offene Punkte).
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3


class EurLexAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID, legislation_reference: str):
        self.directory = directory
        self.source_id = source_id
        self.legislation_reference = legislation_reference

    def fetch(self) -> Iterable[RawRecord]:
        pdf_path = self.directory / "eur_lex_machinery_summary.pdf"
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        now = datetime.now(timezone.utc)

        yield RawRecord(
            source_id=self.source_id,
            content_hash=f"{content_hash}:legal-act",
            raw_designation=self.legislation_reference,
            raw_issuer="EU",
            raw_title=None,
            full_text=None,
            fetched_at=now,
        )

        with pdfplumber.open(pdf_path) as pdf:
            seen_designations: set[str] = set()
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        if row is None or len(row) <= _COLUMN_TITLE:
                            continue
                        eso = (row[_COLUMN_ESO] or "").strip()
                        designation = (row[_COLUMN_STANDARD_REFERENCE] or "").strip()
                        title = (row[_COLUMN_TITLE] or "").strip()
                        if not eso or not designation or eso == "ESO":
                            continue
                        if designation in seen_designations:
                            continue
                        seen_designations.add(designation)
                        yield RawRecord(
                            source_id=self.source_id,
                            content_hash=f"{content_hash}:{designation}",
                            raw_designation=designation,
                            raw_issuer=eso,
                            raw_title=title or None,
                            full_text=None,
                            raw_references=[
                                RawReference(
                                    target_issuer="EU",
                                    target_designation=self.legislation_reference,
                                    edge_type=EdgeType.BASED_ON_LAW,
                                )
                            ],
                            fetched_at=now,
                        )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        return []

    def classify_rights(self, record: RawRecord) -> RightsRule:
        if record.raw_designation == self.legislation_reference:
            return RightsRule(
                jurisdiction="EU", may_process=True, may_index_fulltext=False,
                may_cite_passages=False, may_export_free=True,
                legal_basis_reference="§ 5 UrhG / amtliches Werk (Rechtsakt)",
            )
        return RightsRule(
            jurisdiction="EU", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True,
            legal_basis_reference="Kategorie A — Kommissions-Zusammenfassung, kein Normvolltext",
        )
```

If `page.extract_tables()` does not cleanly detect the table structure of the real fixture PDF
(table extraction quality varies with the exact PDF's internal layout), read the actual output of
`pdfplumber.open(pdf_path).pages[0].extract_tables()` yourself first — print it and inspect it —
before assuming the column indices above are correct; adjust `_COLUMN_ESO` /
`_COLUMN_STANDARD_REFERENCE` / `_COLUMN_TITLE` to match what `pdfplumber` actually extracts from
this specific file, and update the column-index comment to match reality. Do not guess — verify
against the real fixture.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_eur_lex_adapter.py -v`
Expected: PASS. If a test fails because the extracted designation/title text has different
whitespace or line-break characters than expected (common with PDF table extraction), inspect
the actual extracted value and adjust the test's assertions to match reality rather than forcing
the parser to produce an artificial value — the real PDF's exact text is the source of truth.

- [ ] **Step 7: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 8: Commit**

```bash
git add core/pyproject.toml core/tests/fixtures/eur_lex_machinery_summary.pdf core/src/normly_core/pipeline/adapters/__init__.py core/src/normly_core/pipeline/adapters/eur_lex.py core/tests/pipeline/test_eur_lex_adapter.py
git commit -s -m "feat: add EUR-Lex adapter for the Summary List PDF format"
```

---

### Task 14: DGUV adapter — synthetic fixture PDF and structure extraction

**Files:**
- Create: `core/tests/fixtures/dguv_sample_vorschrift.pdf`
- Create: `core/src/normly_core/pipeline/adapters/dguv.py`
- Test: `core/tests/pipeline/test_dguv_adapter.py`

**Interfaces:**
- Consumes: `RawRecord`, `RawSection`, `RightsRule`, `SourceAdapter` from Task 8.
- Produces: `DguvAdapter(directory: Path, source_id: uuid.UUID)` implementing `SourceAdapter` — used by the CLI in Task 15.

The fixture PDF here is **not** a real, downloaded DGUV publication — it is a synthetic file
constructed to have the realistic §-paragraph structure DGUV Vorschriften typically use, built
directly by this task's own code so the exact expected text is known. This is an honest,
generic extraction technique (PDF text extraction + a regex heuristic for German legal-style
headings), not a claim to understand any specific DGUV-internal format.

- [ ] **Step 1: Create the synthetic fixture PDF**

```bash
cd core && .venv/bin/python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/dguv_sample_vorschrift.pdf')
lines = [
    'DGUV Vorschrift 1',
    'Grundsätze der Prävention',
    '',
    '§ 1 Geltungsbereich',
    'Diese Vorschrift gilt für alle Unternehmen und Versicherte.',
    '',
    '§ 2 Pflichten des Unternehmers',
    'Der Unternehmer hat die erforderlichen Maßnahmen zur Verhütung von',
    'Arbeitsunfällen zu treffen.',
    '',
    '§ 3 Pflichten der Versicherten',
    'Die Versicherten haben die Anweisungen des Unternehmers zu befolgen.',
]
y = 800
for line in lines:
    c.drawString(72, y, line)
    y -= 20
c.save()
"
```

If `reportlab` is not installed, add `"reportlab>=4.0,<5.0"` to `core/pyproject.toml`'s
`[project.optional-dependencies].dev` list (it is only ever needed to construct this test
fixture, never at runtime, so it belongs in `dev`, not `dependencies`) and reinstall:
`cd core && .venv/bin/pip install -e ".[dev]"`.

Verify: `cd core && .venv/bin/python -c "import pdfplumber; print(pdfplumber.open('tests/fixtures/dguv_sample_vorschrift.pdf').pages[0].extract_text())"` — expect it to print the lines above.

- [ ] **Step 2: Write the failing tests**

```python
# core/tests/pipeline/test_dguv_adapter.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

from normly_core.pipeline.adapters.dguv import DguvAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_fetch_yields_one_record_per_pdf_with_full_text():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())

    records = list(adapter.fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == "DGUV Vorschrift 1"
    assert record.raw_issuer == "DGUV"
    assert record.raw_title == "Grundsätze der Prävention"
    assert record.full_text is not None
    assert "§ 1 Geltungsbereich" in record.full_text


def test_extract_structure_splits_on_paragraph_headings():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    sections = adapter.extract_structure(record)

    assert len(sections) == 3
    assert sections[0].heading == "§ 1 Geltungsbereich"
    assert "Diese Vorschrift gilt" in sections[0].text
    assert sections[1].heading == "§ 2 Pflichten des Unternehmers"
    assert sections[2].heading == "§ 3 Pflichten der Versicherten"
    assert [s.sequence_number for s in sections] == [1, 2, 3]


def test_classify_rights_allows_full_processing():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    rule = adapter.classify_rights(record)

    assert rule.may_process is True
    assert rule.may_index_fulltext is True
    assert rule.may_cite_passages is True
    assert rule.may_export_free is True
    assert rule.jurisdiction == "DE"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_dguv_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.adapters.dguv'`

- [ ] **Step 4: Write the implementation**

```python
# core/src/normly_core/pipeline/adapters/dguv.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pdfplumber

from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

_HEADING_PATTERN = re.compile(r"^§\s*\d+\s+.+")


class DguvAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        pdf_path = self.directory / "dguv_sample_vorschrift.pdf"
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

        with pdfplumber.open(pdf_path) as pdf:
            lines: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())

        designation = lines[0].strip()
        title = lines[1].strip() if len(lines) > 1 else None
        full_text = "\n".join(lines)

        yield RawRecord(
            source_id=self.source_id,
            content_hash=content_hash,
            raw_designation=designation,
            raw_issuer="DGUV",
            raw_title=title,
            full_text=full_text,
            fetched_at=datetime.now(timezone.utc),
        )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        assert record.full_text is not None
        lines = record.full_text.splitlines()

        sections: list[RawSection] = []
        current_heading: str | None = None
        current_body: list[str] = []
        sequence_number = 0

        def _flush() -> None:
            nonlocal sequence_number
            if current_heading is None:
                return
            sequence_number += 1
            sections.append(
                RawSection(
                    sequence_number=sequence_number,
                    heading=current_heading,
                    text=" ".join(line.strip() for line in current_body if line.strip()),
                )
            )

        for line in lines:
            if _HEADING_PATTERN.match(line.strip()):
                _flush()
                current_heading = line.strip()
                current_body = []
            elif current_heading is not None:
                current_body.append(line)
        _flush()

        return sections

    def classify_rights(self, record: RawRecord) -> RightsRule:
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG — amtliches Werk (DGUV-Vorschrift)",
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_dguv_adapter.py -v`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 7: Commit**

```bash
git add core/pyproject.toml core/tests/fixtures/dguv_sample_vorschrift.pdf core/src/normly_core/pipeline/adapters/dguv.py core/tests/pipeline/test_dguv_adapter.py
git commit -s -m "feat: add DGUV adapter with regex-based structure extraction"
```

---

### Task 15: CLI entry point

**Files:**
- Create: `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/pipeline/test_cli.py`

**Interfaces:**
- Consumes: `run_adapter` from Task 12; `EurLexAdapter` from Task 13; `DguvAdapter` from Task 14; a database session factory.
- Produces: `python -m normly_core.pipeline ingest <source>` runnable from the shell.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/pipeline/test_cli.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

from sqlalchemy.orm import sessionmaker

from normly_core.pipeline.cli import build_adapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_build_adapter_returns_eur_lex_adapter_for_eur_lex_source():
    adapter = build_adapter("eur-lex", directory=FIXTURE_DIR)
    assert type(adapter).__name__ == "EurLexAdapter"


def test_build_adapter_returns_dguv_adapter_for_dguv_source():
    adapter = build_adapter("dguv", directory=FIXTURE_DIR)
    assert type(adapter).__name__ == "DguvAdapter"


def test_build_adapter_rejects_unknown_source():
    import pytest

    with pytest.raises(ValueError, match="unknown source"):
        build_adapter("not-a-real-source", directory=FIXTURE_DIR)
```

Move the `import pytest` to the top of the file with the other imports rather than inline inside
the test function — the inline form above only shows what is needed.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.cli'`

- [ ] **Step 3: Write the implementation**

```python
# core/src/normly_core/pipeline/cli.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.runner import run_adapter

_EUR_LEX_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DGUV_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def build_adapter(source: str, *, directory: Path) -> SourceAdapter:
    if source == "eur-lex":
        return EurLexAdapter(
            directory=directory, source_id=_EUR_LEX_SOURCE_ID,
            legislation_reference="2006/42/EC",
        )
    if source == "dguv":
        return DguvAdapter(directory=directory, source_id=_DGUV_SOURCE_ID)
    raise ValueError(f"unknown source: {source!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("source", choices=["eur-lex", "dguv"])
    ingest_parser.add_argument(
        "--directory", type=Path, required=True,
        help="local directory containing the source's raw files",
    )

    args = parser.parse_args(argv)

    database_url = os.environ.get("NORMLY_DATABASE_URL")
    if not database_url:
        print("NORMLY_DATABASE_URL environment variable is required", file=sys.stderr)
        return 1

    adapter = build_adapter(args.source, directory=args.directory)
    engine = create_engine(database_url)
    with Session(engine) as session:
        summary = run_adapter(adapter, session)
        session.commit()

    print(
        f"processed={summary.records_processed} skipped={summary.records_skipped} "
        f"documents_created={summary.documents_created} "
        f"segments_created={summary.segments_created} "
        f"embeddings_created={summary.embeddings_created} "
        f"enqueued_for_review={summary.records_enqueued_for_review}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/cli.py core/tests/pipeline/test_cli.py
git commit -s -m "feat: add pipeline CLI entry point"
```

---

### Task 16: Capstone — end-to-end pipeline test

**Files:**
- Test: `core/tests/pipeline/test_end_to_end.py`

**Interfaces:**
- Consumes: everything from Tasks 1–15. No new production code expected unless this test reveals
  a real integration gap — if so, fix it in the task that owns the affected file.

- [ ] **Step 1: Write the test**

```python
# core/tests/pipeline/test_end_to_end.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresSegmentRepository,
)
from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.runner import run_adapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_eur_lex_and_dguv_runs_populate_a_queryable_graph_with_correct_rights_asymmetry(
    db_session,
):
    eur_lex_adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )
    dguv_adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())

    eur_lex_summary = run_adapter(eur_lex_adapter, db_session)
    dguv_summary = run_adapter(dguv_adapter, db_session)

    assert eur_lex_summary.documents_created >= 2  # legal act + at least one standard
    assert dguv_summary.documents_created == 1
    assert dguv_summary.segments_created == 3
    assert dguv_summary.embeddings_created == 3

    doc_repo = PostgresDocumentRepository(db_session)
    segment_repo = PostgresSegmentRepository(db_session)

    eur_lex_standard = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")
    assert eur_lex_standard is not None
    assert segment_repo.list_segments_for_jurisdiction(eur_lex_standard.id, "EU") == []

    dguv_document = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1")
    assert dguv_document is not None
    dguv_segments = segment_repo.list_segments_for_jurisdiction(dguv_document.id, "DE")
    assert len(dguv_segments) == 3
    assert dguv_segments[0].heading == "§ 1 Geltungsbereich"


def test_running_the_same_adapter_twice_skips_unchanged_records(db_session):
    dguv_adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())

    first_summary = run_adapter(dguv_adapter, db_session)
    second_summary = run_adapter(dguv_adapter, db_session)

    assert first_summary.records_processed == 1
    assert second_summary.records_skipped == 1
    assert second_summary.documents_created == 0
    assert second_summary.embeddings_created == 0
```

Adjust the exact EUR-Lex designation string in
`doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")` to match whatever the real fixture
PDF's table extraction actually produced in Task 13 — if `pdfplumber` extracted the designation
with different whitespace or formatting, use that exact string here (the same adjustment
principle as Task 13's own tests: the real PDF's extracted text is the source of truth, not an
assumption).

- [ ] **Step 2: Run the test**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_end_to_end.py -v`
Expected: PASS. If it fails on a specific assertion, trace whether the gap is in this test's
expectations (fix the test) or in the production code from an earlier task (fix that task's
file, not this test).

- [ ] **Step 3: Run the entire test suite one final time**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: every test from Tasks 1–16 passes, pristine output, no warnings.

- [ ] **Step 4: Commit**

```bash
git add core/tests/pipeline/test_end_to_end.py
git commit -s -m "test: verify end-to-end pipeline run and idempotent re-run"
```

---

## Self-Review

**Spec coverage:**

| Spec-Abschnitt | Task |
|---|---|
| Adapter-Abstraktion (`SourceAdapter`, `RawRecord`) | Task 8 |
| EUR-Lex-Quellformat („Summary list") | Task 13 |
| Modullayout | Tasks 8–15 (files land exactly where the spec's tree shows) |
| `segment` | Tasks 2–3 |
| `embedding` (inkl. `ON DELETE CASCADE`) | Task 4 |
| `find_delivery` / nicht-brechende Erweiterung | Task 6 |
| `identity_resolution_case` | Task 5 |
| Identitätsauflösung | Task 9 |
| Rechteklassifikation (quellenspezifisch) | Tasks 13–14 (`classify_rights`) |
| Strukturextraktion (nur DGUV) | Task 14 |
| Verweisextraktion | Task 10 |
| Segmentierung und Einbettung (nur DGUV) | Tasks 11–12 |
| Datenfluss (volle Orchestrierung) | Task 12 |
| Fehlerbehandlung (alle sechs Fälle) | Tasks 6 (Skip), 9–10 (Warteschlange), 4 (Embedding-Fehlschlag idempotent nachholbar), 7 (`WithdrawnDeliveryError` bereits vorhanden) |
| Testkonzept (pgvector, echte Fixtures, echtes Modell, E2E, Rücknahme) | Task 1 (pgvector), 13–14 (echte Fixtures), 11 (echtes Modell), 16 (E2E), 7 (Rücknahme) |

Keine Lücke gefunden.

**Placeholder-Scan:** Mehrere Codeblöcke enthalten absichtlich einen inline `__import__(...)`-
oder Walrus-Platzhalter mit der expliziten Anweisung, ihn durch einen sauberen Import/eine saubere
Zuweisung zu ersetzen, bevor der Schritt abgeschlossen wird — das ist eine bewusste
Übergangsdarstellung, keine unvollständige Spezifikation; jede betroffene Stelle nennt exakt den
Zielwert und die zu schreibende saubere Form. Ansonsten kein „TBD"/„TODO"/„similar to Task N"
gefunden.

**Typkonsistenz:** Repository-/Domänen-Namen aus Task 2–6 (`Segment`, `Embedding`,
`IdentityResolutionCase`, `find_delivery`, `find_by_designation`) stimmen mit ihrer Verwendung in
Tasks 9–16 überein — geprüft gegen jede Verwendungsstelle. `RawReference.target_issuer` (Task 8)
wird in Task 10 (`extract_references`) und Task 13 (`EurLexAdapter`) konsistent verwendet.
`EmbeddingModel.embed`/`MODEL_NAME` (Task 11) stimmt mit der Verwendung in Task 12 überein.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-14-ingestion-pipeline.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
