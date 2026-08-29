# Referenzgraph-Suche/-Browsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build free-text search, browse-by-issuer, and a clickable document detail
page over the reference graph (`api/`), plus a minimal anonymous-usage rate limiter,
on top of the already-shipped `frontend/` app shell and BFF architecture.

**Architecture:** A new `GET /v1/documents/search` endpoint in `api/` (backed by a
repository extension in `core/`) fronted by a small Postgres-backed rate limiter
applied to every `api/` endpoint. Three new BFF Route Handlers in `frontend/` proxy
search/edges/validity. Two new pages (`/search`, `/documents/[id]`) consume them. A
new app-wide jurisdiction cookie/context (mirroring the existing locale one) replaces
the chat UI's hardcoded `"DE"`.

**Tech Stack:** Same as sub-project 1 — FastAPI/SQLAlchemy/Alembic (`core/`, `api/`),
Next.js 14 App Router/TypeScript/Vitest/Playwright (`frontend/`).

## Global Constraints

- Every new source file needs the two-line SPDX header (`AGPL-3.0-or-later` for
  `core/`/`frontend/`, `Apache-2.0` for `api/` per its existing `license_info`) —
  check each existing file in the package you're touching for the exact convention.
- DCO `Signed-off-by` on every commit (`git commit -s`).
- Database access only through the repository layer (ADR-006) — no SQL in routers.
- Every `api/` endpoint gets the shared rate-limit dependency, not just search
  (spec decision — REQ-ACC-003).
- The `normly_anon_id` cookie is httpOnly and used only for rate-limiting; never
  linked to chat history or account identity.
- No Redis — the rate limiter is Postgres-backed, matching the approved stack.
- Reuse the existing `DocumentResponse` schema for search results rather than
  inventing a lighter summary type (YAGNI, per the approved spec).

---

### Task 1: Rate-limiting infrastructure (`core/` + `api/`)

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `RateLimitRepository` Protocol)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (add `RateLimitBucketORM`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add
  `PostgresRateLimitRepository`)
- Create: `core/migrations/versions/0016_create_rate_limit_bucket.py`
- Test: `core/tests/graph/test_rate_limit_repository.py`
- Create: `api/src/normly_api/rate_limit.py`
- Modify: `api/src/normly_api/main.py` (apply the dependency to every router)
- Modify: `api/src/normly_api/errors.py` (add a 429 entry to `COMMON_ERROR_RESPONSES`)
- Test: `api/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PostgresRateLimitRepository.record_and_check(*, key: str, window_start:
  datetime, limit: int) -> bool`, `enforce_rate_limit` FastAPI dependency (importable
  from `normly_api.rate_limit`) — consumed by Task 2's new search router and by every
  existing router via `main.py`.

- [ ] **Step 1: Write the failing repository test**

```python
# core/tests/graph/test_rate_limit_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.postgres.repositories import PostgresRateLimitRepository


def test_record_and_check_allows_requests_within_the_limit(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        assert repo.record_and_check(key="1.2.3.4", window_start=window, limit=3) is True


def test_record_and_check_rejects_once_the_limit_is_exceeded(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="1.2.3.4", window_start=window, limit=3)

    assert repo.record_and_check(key="1.2.3.4", window_start=window, limit=3) is False


def test_record_and_check_counts_different_keys_independently(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="anon-a:1.2.3.4", window_start=window, limit=3)

    # A different key (e.g. a different anon_id from the same address) starts
    # its own count, unaffected by the first key's usage.
    assert repo.record_and_check(key="anon-b:1.2.3.4", window_start=window, limit=3) is True


def test_record_and_check_treats_different_windows_independently(db_session):
    repo = PostgresRateLimitRepository(db_session)
    first_window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    second_window = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="1.2.3.4", window_start=first_window, limit=3)

    assert repo.record_and_check(key="1.2.3.4", window_start=second_window, limit=3) is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_rate_limit_repository.py -v`
Expected: FAIL — `PostgresRateLimitRepository` doesn't exist yet.

- [ ] **Step 3: Add the migration**

```python
# core/migrations/versions/0016_create_rate_limit_bucket.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create rate_limit_bucket

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_bucket",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_bucket")
```

- [ ] **Step 4: Add the `RateLimitBucketORM` model**

In `core/src/normly_core/graph/postgres/orm.py`, add this class anywhere alongside
the other `*ORM` classes (its imports — `Mapped`, `mapped_column`, `sa`, `datetime`
— are already imported at the top of this file):

```python
class RateLimitBucketORM(Base):
    __tablename__ = "rate_limit_bucket"

    key: Mapped[str] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), primary_key=True
    )
    request_count: Mapped[int] = mapped_column(default=0)
```

- [ ] **Step 5: Add the `RateLimitRepository` Protocol**

In `core/src/normly_core/graph/domain.py`, add this Protocol near the other
repository Protocols (e.g. after `DocumentRepository`):

```python
class RateLimitRepository(Protocol):
    """
    A generic, jurisdiction-independent request counter used to enforce
    REQ-ACC-003's anonymous quota. Not part of the graph model, but kept in
    the same repository layer as everything else that touches the database,
    per CLAUDE.md's "Datenbankzugriff nur über die Repository-Schicht".
    """

    def record_and_check(
        self, *, key: str, window_start: datetime, limit: int
    ) -> bool:
        """
        Atomically increments the request counter for `key` within the
        window starting at `window_start`, and reports whether the caller
        is still within `limit`. Returns True when the request should be
        allowed (count <= limit after incrementing), False when it should
        be rejected.
        """
        ...
```

(This method starts with neither `list_` nor `get_`, so `test_every_protocol_read_
takes_a_jurisdiction` in `core/tests/graph/test_architecture.py` skips it
automatically — no entry needed in that test's `JURISDICTION_EXEMPT_READS`, since
rate limiting is correctly not jurisdiction-scoped at all.)

- [ ] **Step 6: Implement `PostgresRateLimitRepository`**

In `core/src/normly_core/graph/postgres/repositories.py`, add this import near the
top (alongside the existing `from sqlalchemy import select`):

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
```

Add `RateLimitBucketORM` to the existing `from normly_core.graph.postgres.orm import
(...)` block. Then add the class anywhere alongside the other `Postgres*Repository`
classes:

```python
class PostgresRateLimitRepository:
    def __init__(self, session: Session):
        self._session = session

    def record_and_check(self, *, key: str, window_start: datetime, limit: int) -> bool:
        # INSERT ... ON CONFLICT DO UPDATE is atomic under concurrent requests
        # for the same key -- two simultaneous requests in the same window
        # both reliably see their own increment, unlike a read-then-write
        # pattern from Python.
        stmt = (
            pg_insert(RateLimitBucketORM)
            .values(key=key, window_start=window_start, request_count=1)
            .on_conflict_do_update(
                index_elements=["key", "window_start"],
                set_={"request_count": RateLimitBucketORM.request_count + 1},
            )
            .returning(RateLimitBucketORM.request_count)
        )
        count = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return count <= limit
```

- [ ] **Step 7: Run the repository tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_rate_limit_repository.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Write the failing API test**

```python
# api/tests/test_rate_limit.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_requests_within_the_limit_succeed(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})
        assert response.status_code == 200


def test_exceeding_the_limit_returns_429(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 3)

    for _ in range(3):
        client.get("/v1/documents/search", params={"jurisdiction": "DE"})

    response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})
    assert response.status_code == 429


def test_different_anon_ids_are_counted_separately(client, monkeypatch):
    import normly_api.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_REQUESTS_PER_WINDOW", 1)

    client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": "anon-a"},
    )
    response = client.get(
        "/v1/documents/search",
        params={"jurisdiction": "DE"},
        headers={"X-Normly-Anon-Id": "anon-b"},
    )
    assert response.status_code == 200
```

(This test file depends on `GET /v1/documents/search` existing, which Task 2 adds.
Write this file now as specified — Task 2's implementer will find it already failing
for "endpoint doesn't exist" until their own work lands; that's expected and fine,
since Task 2 runs immediately after this one.)

- [ ] **Step 9: Run the test to verify it fails for the right reason**

Run: `cd api && .venv/bin/python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — `/v1/documents/search` returns 404 (route doesn't exist yet). This
confirms the test file itself is wired correctly; Task 2 is what makes it pass.

- [ ] **Step 10: Write the rate-limit dependency**

```python
# api/src/normly_api/rate_limit.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresRateLimitRepository

from normly_api.dependencies import get_session

# 60 anonymous requests/minute per key, applied to every api/ endpoint (not
# just search) -- see docs/superpowers/specs/2026-08-29-reference-graph-
# search-and-browse-design.md. Module-level so tests can monkeypatch it down
# to a small number instead of making 60 real requests. A fixed one-minute
# bucket (floored to the minute), not a sliding window: simple, and precise
# enough for the abuse pattern this guards against (systematic scraping),
# not split-second fairness.
_REQUESTS_PER_WINDOW = 60


def _client_origin_address(request: Request) -> str:
    # Trusts X-Forwarded-For from the immediate reverse proxy, per CLAUDE.md's
    # "hinter beliebigem Reverse Proxy" deployment assumption -- this is only
    # safe because the proxy is the sole path to this service; a caller
    # reaching api/ directly could otherwise spoof this header. Falls back to
    # the direct connection address when absent (e.g. local/test requests).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, session: Session = Depends(get_session)) -> None:
    # X-Normly-Anon-Id is set by the frontend BFF's middleware and forwarded
    # on every proxied api/ call -- see frontend/src/middleware.ts. Its
    # absence (a hypothetical direct caller bypassing the frontend) degrades
    # to origin-address-only limiting rather than rejecting the request.
    anon_id = request.headers.get("x-normly-anon-id")
    origin = _client_origin_address(request)
    key = f"{anon_id}:{origin}" if anon_id else origin

    window_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    allowed = PostgresRateLimitRepository(session).record_and_check(
        key=key, window_start=window_start, limit=_REQUESTS_PER_WINDOW,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
```

- [ ] **Step 11: Add a 429 entry to `COMMON_ERROR_RESPONSES`**

In `api/src/normly_api/errors.py`, add a `429` key to the existing
`COMMON_ERROR_RESPONSES` dict (between `400` and `503`):

```python
    429: {
        "model": ErrorResponse,
        "description": "Rate limit exceeded for this origin/session. Retry after the current window ends.",
    },
```

- [ ] **Step 12: Wire the dependency into every existing router**

In `api/src/normly_api/main.py`, add `from fastapi import Depends` to the existing
`from fastapi import FastAPI` import line (making it `from fastapi import Depends,
FastAPI`), add `from normly_api.rate_limit import enforce_rate_limit`, and add
`dependencies=[Depends(enforce_rate_limit)]` to each of the four existing
`include_router` calls:

```python
    app.include_router(
        documents_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
    app.include_router(
        edges_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
    app.include_router(
        export_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
    app.include_router(
        validity_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
```

(Task 2 adds a fifth `include_router` call, for the new search router, using the
same pattern.)

- [ ] **Step 13: Run the full `api/` suite**

Run: `cd api && .venv/bin/python -m pytest -v`
Expected: all pre-existing tests still PASS. Each test uses its own isolated,
rolled-back `db_session` transaction (see `api/tests/conftest.py`), so the rate
counter never accumulates across tests and no existing test comes close to
tripping the default 60/minute limit. `test_rate_limit.py`'s three new tests will
still show the Step 9 failure until Task 2 lands — that's expected.

- [ ] **Step 14: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/migrations/versions/0016_create_rate_limit_bucket.py \
  core/tests/graph/test_rate_limit_repository.py \
  api/src/normly_api/rate_limit.py api/src/normly_api/main.py api/src/normly_api/errors.py \
  api/tests/test_rate_limit.py
git commit -s -m "feat: add Postgres-backed rate limiting to every api/ endpoint"
```

---

### Task 2: Search/browse endpoint (`core/` + `api/`)

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `search_documents_for_
  jurisdiction` to `DocumentRepository`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (implement it)
- Test: `core/tests/graph/test_document_search.py`
- Modify: `api/src/normly_api/schemas.py` (add `DocumentSearchResponse`)
- Modify: `api/src/normly_api/routers/documents.py` (export `document_to_response`,
  drop its leading underscore — now used by two router modules)
- Create: `api/src/normly_api/routers/search.py`
- Modify: `api/src/normly_api/main.py` (register the new router)
- Test: `api/tests/test_documents_search_endpoint.py`

**Interfaces:**
- Consumes: `enforce_rate_limit` (Task 1).
- Produces: `GET /v1/documents/search` — consumed by Task 5 (frontend BFF proxy).

- [ ] **Step 1: Write the failing repository test**

```python
# core/tests/graph/test_document_search.py
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


def _seed_document(
    db_session, *, issuer, designation, title, jurisdiction="DE", content_hash,
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
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=designation, language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_title(
        document_id=document.id, language="de", title=title, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_finds_a_document_by_partial_designation(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-1",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", q="Vorschrift 1")

    assert total == 1
    assert [d.id for d in results] == [document.id]


def test_search_finds_a_document_by_partial_title(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-2",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", q="Prävention")

    assert total == 1
    assert [d.id for d in results] == [document.id]


def test_search_filters_by_issuer(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    dguv_doc = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        content_hash="sha256:search-3",
    )
    _seed_document(
        db_session, issuer="DIN", designation="DIN EN ISO 9001", title="B",
        content_hash="sha256:search-4",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", issuer="DGUV")

    assert total == 1
    assert [d.id for d in results] == [dguv_doc.id]


def test_search_hides_documents_not_classified_for_the_requested_jurisdiction(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        jurisdiction="DE", content_hash="sha256:search-5",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("FR", q="Vorschrift")

    assert total == 0
    assert results == []


def test_search_paginates_with_limit_and_offset(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    docs = [
        _seed_document(
            db_session, issuer="DGUV", designation=f"DGUV Vorschrift {n}", title=f"Titel {n}",
            content_hash=f"sha256:search-page-{n}",
        )
        for n in range(5)
    ]

    first_page, total = doc_repo.search_documents_for_jurisdiction(
        "DE", issuer="DGUV", limit=2, offset=0,
    )
    second_page, _ = doc_repo.search_documents_for_jurisdiction(
        "DE", issuer="DGUV", limit=2, offset=2,
    )

    assert total == 5
    assert len(first_page) == 2
    assert len(second_page) == 2
    assert {d.id for d in first_page}.isdisjoint({d.id for d in second_page})
    assert {d.id for d in docs} >= {d.id for d in first_page} | {d.id for d in second_page}


def test_search_with_no_filters_returns_everything_in_the_jurisdiction(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        content_hash="sha256:search-6",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE")

    assert total == 1
    assert [d.id for d in results] == [document.id]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_document_search.py -v`
Expected: FAIL — `search_documents_for_jurisdiction` doesn't exist yet.

- [ ] **Step 3: Add the Protocol method**

In `core/src/normly_core/graph/domain.py`, add this to `DocumentRepository` (after
`list_documents_for_jurisdiction`):

```python
    def search_documents_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Document], int]:
        """
        Free-text (designation/title, case-insensitive substring) and/or
        issuer-filtered listing, paginated. Returns (page, total_matching) --
        `total` reflects the full filtered set, not just this page's length.
        An empty q and issuer returns the whole jurisdiction, paginated --
        this is also how "browse by issuer" and "browse everything" work,
        without a separate method.
        """
        ...
```

- [ ] **Step 4: Implement it in `PostgresDocumentRepository`**

In `core/src/normly_core/graph/postgres/repositories.py`, add this method to
`PostgresDocumentRepository` (after `find_by_designation`):

```python
    def search_documents_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Document], int]:
        base = (
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
        )

        if q is not None or issuer is not None:
            # A document can have several designations, so this join can
            # multiply rows -- distinct() below dedupes by DocumentORM's
            # full column set (id is the primary key among them), which is
            # equivalent to per-document dedup here.
            base = base.join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            if q is not None:
                pattern = f"%{q}%"
                base = base.where(
                    sa.or_(
                        DocumentDesignationORM.designation.ilike(pattern),
                        DocumentORM.id.in_(
                            select(DocumentTitleORM.document_id).where(
                                DocumentTitleORM.title.ilike(pattern)
                            )
                        ),
                    )
                )
            if issuer is not None:
                base = base.where(DocumentDesignationORM.issuer == issuer)
            base = base.distinct()

        total = self._session.execute(
            select(sa.func.count()).select_from(base.subquery())
        ).scalar_one()

        rows = self._session.execute(
            base.order_by(DocumentORM.id).limit(limit).offset(offset)
        ).scalars()
        return [_document_to_domain(row) for row in rows], total
```

- [ ] **Step 5: Run the repository tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_document_search.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run the full `core/` suite to confirm nothing else broke**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, including `test_architecture.py` (the new Protocol method takes
`jurisdiction` as its first parameter, so `test_every_protocol_read_takes_a_
jurisdiction` passes without needing an exemption entry — it only checks methods
starting with `list_`/`get_`, and this one starts with `search_`, so it isn't even
inspected by that test; this is fine, the method still genuinely filters by
jurisdiction, the test just doesn't happen to cover `search_*` names).

- [ ] **Step 7: Rename `_document_to_response` so a second router can reuse it**

In `api/src/normly_api/routers/documents.py`, rename `_document_to_response` to
`document_to_response` (drop the leading underscore) at its definition (line 30) and
at its two call sites within this file (in `search_documents` and `get_document`).
No other change to the function body.

- [ ] **Step 8: Add the search response schema**

In `api/src/normly_api/schemas.py`, add this class (after `DocumentResponse`):

```python
class DocumentSearchResponse(BaseModel):
    results: list[DocumentResponse]
    total: int
```

- [ ] **Step 9: Write the failing API test**

```python
# api/tests/test_documents_search_endpoint.py
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


def _seed_document(db_session, *, issuer, designation, jurisdiction="DE", content_hash):
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
        delivery_id=delivery.id,
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


def test_search_endpoint_returns_matching_documents(client, db_session):
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-1",
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Vorschrift 1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == str(document.id)


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
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_search_endpoint.py -v`
Expected: FAIL — route doesn't exist yet.

- [ ] **Step 11: Write the search router**

```python
# api/src/normly_api/routers/search.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresDocumentRepository

from normly_api.dependencies import get_session
from normly_api.routers.documents import document_to_response
from normly_api.schemas import DocumentSearchResponse

search_router = APIRouter(prefix="/v1/documents", tags=["search"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@search_router.get("/search", response_model=DocumentSearchResponse)
def search_documents_endpoint(
    jurisdiction: str, q: str | None = None, issuer: str | None = None,
    limit: int = _DEFAULT_LIMIT, offset: int = 0,
    session: Session = Depends(get_session),
) -> DocumentSearchResponse:
    limit = min(limit, _MAX_LIMIT)
    doc_repo = PostgresDocumentRepository(session)
    documents, total = doc_repo.search_documents_for_jurisdiction(
        jurisdiction, q=q, issuer=issuer, limit=limit, offset=offset,
    )
    return DocumentSearchResponse(
        results=[document_to_response(d, session) for d in documents], total=total,
    )
```

- [ ] **Step 12: Register the router with the rate-limit dependency**

In `api/src/normly_api/main.py`, add `from normly_api.routers.search import
search_router` and add a fifth `include_router` call, same pattern as Task 1's
Step 12:

```python
    app.include_router(
        search_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
```

- [ ] **Step 13: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_search_endpoint.py tests/test_rate_limit.py -v`
Expected: PASS (4 + 3 = 7 tests — `test_rate_limit.py` from Task 1 now passes too,
since the route it targets exists).

- [ ] **Step 14: Run the full `api/` suite**

Run: `cd api && .venv/bin/python -m pytest -v`
Expected: all pass, including the pre-existing `test_documents_search.py` (the
exact-match `/v1/documents` endpoint, unaffected by this task's changes).

- [ ] **Step 15: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_document_search.py \
  api/src/normly_api/schemas.py api/src/normly_api/routers/documents.py \
  api/src/normly_api/routers/search.py api/src/normly_api/main.py \
  api/tests/test_documents_search_endpoint.py
git commit -s -m "feat: add GET /v1/documents/search (full-text + issuer + pagination)"
```

---

### Task 3: Anonymous identifier middleware (`frontend/`)

**Files:**
- Create: `frontend/src/middleware.ts`
- Test: `frontend/tests/unit/middleware.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces: the `normly_anon_id` cookie, read by Task 5's BFF routes via
  `request.cookies.get("normly_anon_id")`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/middleware.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

describe("middleware", () => {
  it("sets normly_anon_id when the cookie is missing", () => {
    const request = new NextRequest("http://localhost/");
    const response = middleware(request);
    const cookie = response.cookies.get("normly_anon_id");
    expect(cookie?.value).toBeTruthy();
    expect(cookie?.httpOnly).toBe(true);
  });

  it("leaves an existing normly_anon_id untouched", () => {
    const request = new NextRequest("http://localhost/", {
      headers: { cookie: "normly_anon_id=existing-value" },
    });
    const response = middleware(request);
    expect(response.cookies.get("normly_anon_id")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- middleware`
Expected: FAIL — `@/middleware` doesn't exist yet.

- [ ] **Step 3: Write the middleware**

```typescript
// frontend/src/middleware.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";

const ANON_ID_COOKIE = "normly_anon_id";
const ANON_ID_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

// Runs before every request. A Server Component cannot set a cookie during
// render (layout.tsx's normly_locale/normly_jurisdiction pattern only ever
// READS a cookie server-side, relying on client-side document.cookie writes
// for changes) -- but normly_anon_id must exist and be STABLE from the very
// first request, before any user interaction, so it can't wait for a
// client-side write. Middleware is the one place in the App Router that can
// inspect and set a cookie ahead of every request uniformly, regardless of
// which page is hit first.
export function middleware(request: NextRequest): NextResponse {
  const response = NextResponse.next();
  if (!request.cookies.get(ANON_ID_COOKIE)) {
    response.cookies.set(ANON_ID_COOKIE, randomUUID(), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: ANON_ID_MAX_AGE_SECONDS,
    });
  }
  return response;
}

export const config = {
  // Skip static assets and the service worker/manifest -- this cookie only
  // needs to exist before an actual page or API request, not before every
  // asset fetch.
  matcher: ["/((?!_next/static|_next/image|favicon|manifest|service-worker).*)"],
};
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- middleware`
Expected: PASS (2 tests).

- [ ] **Step 5: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS. Next.js picks up `src/middleware.ts` automatically (no registration
needed elsewhere) — confirm the build output does not warn about a missing or
misplaced middleware file.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/middleware.ts frontend/tests/unit/middleware.test.ts
git commit -s -m "feat: issue an anonymous rate-limiting identifier via middleware"
```

---

### Task 4: Jurisdiction context (`frontend/`)

**Files:**
- Create: `frontend/src/lib/jurisdiction/provider.tsx`
- Test: `frontend/tests/unit/jurisdiction.test.tsx`
- Create: `frontend/src/components/jurisdiction-switcher.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/app-header.tsx`
- Modify: `frontend/src/app/home-page-content.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: `JurisdictionProvider`, `useJurisdiction() -> { jurisdiction,
  setJurisdiction }`, `JURISDICTIONS` — consumed by Task 7 (`/search`) and Task 8
  (`/documents/[id]`).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/jurisdiction.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JurisdictionProvider, useJurisdiction } from "@/lib/jurisdiction/provider";

function Probe() {
  const { jurisdiction, setJurisdiction } = useJurisdiction();
  return <button onClick={() => setJurisdiction("EU")}>{jurisdiction}</button>;
}

describe("JurisdictionProvider", () => {
  it("exposes the initial jurisdiction", () => {
    render(
      <JurisdictionProvider initialJurisdiction="DE">
        <Probe />
      </JurisdictionProvider>,
    );
    expect(screen.getByRole("button", { name: "DE" })).toBeInTheDocument();
  });

  it("updates the jurisdiction and sets the cookie when changed", () => {
    render(
      <JurisdictionProvider initialJurisdiction="DE">
        <Probe />
      </JurisdictionProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "DE" }));
    expect(screen.getByRole("button", { name: "EU" })).toBeInTheDocument();
    expect(document.cookie).toContain("normly_jurisdiction=EU");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- jurisdiction`
Expected: FAIL — `@/lib/jurisdiction/provider` doesn't exist yet.

- [ ] **Step 3: Write the provider**

```tsx
// frontend/src/lib/jurisdiction/provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

// Mirrors lib/i18n/provider.tsx's LocaleProvider exactly: a small React
// Context so any client component (JurisdictionSwitcher, the chat send
// handler, the search/detail pages) can read and change the current
// jurisdiction without prop-drilling, persisted via a plain (non-httpOnly --
// this is UI state, not a security-relevant token) cookie the root layout
// reads server-side on the next request.
export const JURISDICTIONS = ["DE", "EU"] as const;
export type Jurisdiction = (typeof JURISDICTIONS)[number];

interface JurisdictionContextValue {
  jurisdiction: Jurisdiction;
  setJurisdiction: (jurisdiction: Jurisdiction) => void;
}

const JurisdictionContext = React.createContext<JurisdictionContextValue | null>(null);

export function JurisdictionProvider({
  children,
  initialJurisdiction,
}: {
  children: React.ReactNode;
  initialJurisdiction: Jurisdiction;
}) {
  const [jurisdiction, setJurisdictionState] = React.useState<Jurisdiction>(
    initialJurisdiction,
  );

  const setJurisdiction = React.useCallback((next: Jurisdiction) => {
    setJurisdictionState(next);
    document.cookie = `normly_jurisdiction=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
  }, []);

  const value = React.useMemo(
    () => ({ jurisdiction, setJurisdiction }),
    [jurisdiction, setJurisdiction],
  );

  return (
    <JurisdictionContext.Provider value={value}>{children}</JurisdictionContext.Provider>
  );
}

export function useJurisdiction(): JurisdictionContextValue {
  const context = React.useContext(JurisdictionContext);
  if (context === null) {
    throw new Error("useJurisdiction must be used within a JurisdictionProvider");
  }
  return context;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- jurisdiction`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire the provider into the root layout**

Update `frontend/src/app/layout.tsx`. Add this import alongside the existing
`LocaleProvider` import:

```tsx
import { JurisdictionProvider, JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/provider";
```

Add this function alongside `resolveInitialLocale`:

```tsx
function resolveInitialJurisdiction(): Jurisdiction {
  const cookieJurisdiction = cookies().get("normly_jurisdiction")?.value;
  if ((JURISDICTIONS as readonly string[]).includes(cookieJurisdiction ?? "")) {
    return cookieJurisdiction as Jurisdiction;
  }
  return "DE";
}
```

Update `RootLayout` to resolve and pass it, wrapping `JurisdictionProvider` inside
`LocaleProvider`:

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  const initialLocale = resolveInitialLocale();
  const initialJurisdiction = resolveInitialJurisdiction();
  return (
    <html
      lang={initialLocale}
      style={{ "--brand": config.brandColorHsl } as React.CSSProperties}
    >
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <JurisdictionProvider initialJurisdiction={initialJurisdiction}>
            <ServiceWorkerRegistration />
            {children}
          </JurisdictionProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Write the switcher component**

```tsx
// frontend/src/components/jurisdiction-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useJurisdiction, JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/provider";

export function JurisdictionSwitcher() {
  const { jurisdiction, setJurisdiction } = useJurisdiction();
  return (
    <select
      value={jurisdiction}
      onChange={(event) => setJurisdiction(event.target.value as Jurisdiction)}
      className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      aria-label="Jurisdiktion"
    >
      {JURISDICTIONS.map((value) => (
        <option key={value} value={value}>
          {value}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 7: Mount it in the shared header**

Update `frontend/src/components/app-header.tsx`: add the import
`import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";`, and add
`<JurisdictionSwitcher />` inside the `<div className="flex items-center gap-2">`
block, immediately after `<LocaleSwitcher />`.

- [ ] **Step 8: Make the chat call use the real jurisdiction**

Update `frontend/src/app/home-page-content.tsx`: add the import
`import { useJurisdiction } from "@/lib/jurisdiction/provider";`, add
`const { jurisdiction } = useJurisdiction();` inside `HomePageContent` (alongside
the existing `const { locale } = useTranslation();`), and change the two places that
currently hardcode `"DE"`:

- `body: JSON.stringify({ jurisdiction: "DE", language: locale, message })` becomes
  `body: JSON.stringify({ jurisdiction, language: locale, message })`
- `` `/api/documents/${citation.document_id}?jurisdiction=DE` `` becomes
  `` `/api/documents/${citation.document_id}?jurisdiction=${jurisdiction}` ``

- [ ] **Step 9: Run the full frontend unit suite**

Run: `cd frontend && npm test`
Expected: all pass. If `chat-input.test.tsx` or `smoke.test.tsx` render `HomePage`/
`HomePageContent` without wrapping in `JurisdictionProvider`, they will now fail
with "useJurisdiction must be used within a JurisdictionProvider" — if so, wrap the
render call in that test the same way it's already wrapped in `LocaleProvider`
(check the existing test file for the exact pattern before editing it).

- [ ] **Step 10: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS, all routes still `ƒ` (Dynamic) — `layout.tsx` already carries
`export const dynamic = "force-dynamic"` from a prior sub-project's fix and reads
`cookies()`, so this change doesn't reintroduce that regression, but confirm the
build output's route table regardless (this branch has a documented history of that
exact class of bug).

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/jurisdiction/ frontend/tests/unit/jurisdiction.test.tsx \
  frontend/src/components/jurisdiction-switcher.tsx frontend/src/app/layout.tsx \
  frontend/src/components/app-header.tsx frontend/src/app/home-page-content.tsx \
  frontend/tests/unit/smoke.test.tsx frontend/tests/unit/chat-input.test.tsx
git commit -s -m "feat: add an app-wide jurisdiction selector, replacing chat's hardcoded DE"
```

(Only add the two test files to this commit if Step 9 actually required editing
them — if the suite passed without changes, omit them from `git add`.)

---

### Task 5: Search/detail BFF Route Handlers (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/documents/search/route.ts`
- Create: `frontend/src/app/api/documents/[id]/edges/route.ts`
- Create: `frontend/src/app/api/documents/[id]/validity/route.ts`
- Test: `frontend/tests/unit/documents-search-route.test.ts`
- Test: `frontend/tests/unit/documents-edges-route.test.ts`
- Test: `frontend/tests/unit/documents-validity-route.test.ts`

**Interfaces:**
- Consumes: `getBackendUrls` (already exists, `lib/backend-urls.ts`), the
  `normly_anon_id` cookie (Task 3).
- Produces: `GET /api/documents/search`, `GET /api/documents/[id]/edges`,
  `GET /api/documents/[id]/validity` — consumed by Task 7 (`/search`) and Task 8
  (`/documents/[id]`).

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/documents-search-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/search/route";

const originalFetch = global.fetch;

describe("GET /api/documents/search", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards q/issuer/jurisdiction/limit/offset and returns the backend body", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/documents/search?q=Vorschrift&issuer=DGUV&jurisdiction=DE&limit=10&offset=5",
    );
    const response = await GET(request);
    const body = await response.json();

    expect(body).toEqual({ results: [], total: 0 });
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("http://api.internal/v1/documents/search?");
    expect(url).toContain("q=Vorschrift");
    expect(url).toContain("issuer=DGUV");
    expect(url).toContain("jurisdiction=DE");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("defaults jurisdiction to DE when absent", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    await GET(new NextRequest("http://localhost/api/documents/search"));

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("jurisdiction=DE");
  });

  it("forwards the normly_anon_id cookie as an X-Normly-Anon-Id header", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/documents/search", {
      headers: { cookie: "normly_anon_id=anon-123" },
    });
    await GET(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["X-Normly-Anon-Id"]).toBe("anon-123");
  });

  it("passes through a 429 from the backend", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "rate limit exceeded" }), { status: 429 }),
    );

    const response = await GET(new NextRequest("http://localhost/api/documents/search"));

    expect(response.status).toBe(429);
  });
});
```

```typescript
// frontend/tests/unit/documents-edges-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/edges/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/edges", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to the backend edges endpoint with encoded id/jurisdiction", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    const request = new NextRequest(
      "http://localhost/api/documents/abc/edges?jurisdiction=DE",
    );
    const response = await GET(request, { params: { id: "abc" } });

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/abc/edges?jurisdiction=DE");
  });

  it("percent-encodes a path-traversal id instead of forwarding it raw", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    const request = new NextRequest(
      "http://localhost/api/documents/..%2F..%2Fadmin/edges?jurisdiction=DE",
    );
    await GET(request, { params: { id: "../../admin" } });

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).not.toContain("/../../admin/");
    expect(url).toContain(encodeURIComponent("../../admin"));
  });
});
```

```typescript
// frontend/tests/unit/documents-validity-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/validity/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/validity", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to the backend validity endpoint", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "valid" }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/documents/abc/validity?jurisdiction=DE",
    );
    const response = await GET(request, { params: { id: "abc" } });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe("valid");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/abc/validity?jurisdiction=DE");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- documents-search-route documents-edges-route documents-validity-route`
Expected: FAIL — none of the three routes exist yet.

- [ ] **Step 3: Write the search proxy**

```typescript
// frontend/src/app/api/documents/search/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const incoming = request.nextUrl.searchParams;
  const forwarded = new URLSearchParams();
  forwarded.set("jurisdiction", incoming.get("jurisdiction") ?? "DE");
  const q = incoming.get("q");
  if (q) forwarded.set("q", q);
  const issuer = incoming.get("issuer");
  if (issuer) forwarded.set("issuer", issuer);
  const limit = incoming.get("limit");
  if (limit) forwarded.set("limit", limit);
  const offset = incoming.get("offset");
  if (offset) forwarded.set("offset", offset);

  const anonId = request.cookies.get("normly_anon_id")?.value;
  const forwardedFor = request.headers.get("x-forwarded-for");

  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/search?${forwarded.toString()}`,
    {
      headers: {
        ...(anonId ? { "X-Normly-Anon-Id": anonId } : {}),
        ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
      },
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Write the edges proxy**

```typescript
// frontend/src/app/api/documents/[id]/edges/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(params.id)}/edges` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 5: Write the validity proxy**

```typescript
// frontend/src/app/api/documents/[id]/validity/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(params.id)}/validity` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test -- documents-search-route documents-edges-route documents-validity-route`
Expected: PASS (4 + 2 + 1 = 7 tests).

- [ ] **Step 7: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS, all three new routes listed as `ƒ` (Dynamic) — each reads
`request.nextUrl`/`request.cookies`, which opts them out of static rendering the
same way the existing `documents/[id]/route.ts` already does.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/api/documents/search/ frontend/src/app/api/documents/\[id\]/edges/ \
  frontend/src/app/api/documents/\[id\]/validity/ \
  frontend/tests/unit/documents-search-route.test.ts \
  frontend/tests/unit/documents-edges-route.test.ts frontend/tests/unit/documents-validity-route.test.ts
git commit -s -m "feat: add BFF proxies for document search, edges, and validity"
```

---

### Task 6: New UI components and i18n (`frontend/`)

**Files:**
- Modify: `frontend/src/app/globals.css` (add `--foreground`/`--muted-foreground`)
- Modify: `frontend/tailwind.config.ts` (map them)
- Create: `frontend/src/components/ui/badge.tsx`
- Test: `frontend/tests/unit/badge.test.tsx`
- Create: `frontend/src/components/ui/pagination.tsx`
- Test: `frontend/tests/unit/pagination.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`

**Interfaces:**
- Consumes: `cn` (`lib/utils.ts`), `Button` (`components/ui/button.tsx`).
- Produces: `Badge`, `Pagination` — consumed by Task 7 (`/search`) and Task 8
  (`/documents/[id]`). New i18n keys under `search`/`edgeType`/`validity` —
  consumed by the same two tasks.

- [ ] **Step 1: Fix a pre-existing gap — `text-muted-foreground` has no definition**

`text-muted-foreground` is already used in `components/app-header.tsx` and
`components/chat/citation-chip.tsx`, but `tailwind.config.ts` never defines a
`muted-foreground` color — Tailwind silently drops an unrecognized utility class, so
that text has been rendering unstyled all along. The new `Badge` component below
also needs a `foreground` token. Fix both at once.

In `frontend/src/app/globals.css`, add two lines to the existing `:root` block
(after `--muted`):

```css
  --foreground: 220 9% 20%;
  --muted-foreground: 220 9% 46%;
```

In `frontend/tailwind.config.ts`, add two lines to `theme.extend.colors` (after
`muted`):

```typescript
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        "muted-foreground": "hsl(var(--muted-foreground) / <alpha-value>)",
```

- [ ] **Step 2: Write the failing Badge test**

```tsx
// frontend/tests/unit/badge.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Gültig</Badge>);
    expect(screen.getByText("Gültig")).toBeInTheDocument();
  });

  it("applies the outline variant's classes", () => {
    render(<Badge variant="outline">Ersetzt</Badge>);
    expect(screen.getByText("Ersetzt")).toHaveClass("border");
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- badge`
Expected: FAIL — `@/components/ui/badge` doesn't exist yet.

- [ ] **Step 4: Write the Badge component**

```tsx
// frontend/src/components/ui/badge.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-brand text-brand-foreground",
        outline: "border border-input text-foreground",
        muted: "bg-muted text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

export { Badge, badgeVariants };
```

- [ ] **Step 5: Run the Badge test to verify it passes**

Run: `cd frontend && npm test -- badge`
Expected: PASS (2 tests).

- [ ] **Step 6: Write the failing Pagination test**

```tsx
// frontend/tests/unit/pagination.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "@/components/ui/pagination";

describe("Pagination", () => {
  it("disables Previous on the first page and enables Next when more results remain", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={0}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    expect(screen.getByRole("button", { name: "Zurück" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Weiter" })).not.toBeDisabled();
  });

  it("calls onPageChange with the next offset when Next is clicked", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={0}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    expect(onPageChange).toHaveBeenCalledWith(20);
  });

  it("disables Next on the last page", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={40}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    expect(screen.getByRole("button", { name: "Weiter" })).toBeDisabled();
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && npm test -- pagination`
Expected: FAIL — `@/components/ui/pagination` doesn't exist yet.

- [ ] **Step 8: Write the Pagination component**

```tsx
// frontend/src/components/ui/pagination.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Button } from "@/components/ui/button";

export function Pagination({
  offset,
  limit,
  total,
  onPageChange,
  previousLabel,
  nextLabel,
}: {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (nextOffset: number) => void;
  previousLabel: string;
  nextLabel: string;
}) {
  const hasPrevious = offset > 0;
  const hasNext = offset + limit < total;
  return (
    <div className="flex items-center justify-between gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!hasPrevious}
        onClick={() => onPageChange(Math.max(0, offset - limit))}
      >
        {previousLabel}
      </Button>
      <span className="text-sm text-muted-foreground">
        {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} / {total}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={!hasNext}
        onClick={() => onPageChange(offset + limit)}
      >
        {nextLabel}
      </Button>
    </div>
  );
}
```

- [ ] **Step 9: Run the Pagination test to verify it passes**

Run: `cd frontend && npm test -- pagination`
Expected: PASS (3 tests).

- [ ] **Step 10: Add the new i18n keys**

In `frontend/src/lib/i18n/de.json`, add these three top-level objects (after
`history`):

```json
  "search": {
    "inputPlaceholder": "Regelwerk suchen…",
    "issuerFilterLabel": "Herausgeber",
    "searchButton": "Suchen",
    "empty": "Keine Treffer.",
    "previousPage": "Zurück",
    "nextPage": "Weiter",
    "rateLimited": "Zu viele Anfragen. Bitte melde dich an oder versuche es später erneut.",
    "notFound": "Regelwerk nicht gefunden."
  },
  "edgeType": {
    "references": "Verweist auf",
    "replaces": "Ersetzt",
    "withdrawn_by": "Zurückgezogen durch",
    "based_on_law": "Basiert auf Gesetz",
    "adopted_from": "Übernommen von"
  },
  "validity": {
    "valid": "Gültig",
    "replaced": "Ersetzt",
    "withdrawn": "Zurückgezogen"
  }
```

In `frontend/src/lib/i18n/en.json`, add the matching structure (same key shape,
English values):

```json
  "search": {
    "inputPlaceholder": "Search for a standard…",
    "issuerFilterLabel": "Issuer",
    "searchButton": "Search",
    "empty": "No results.",
    "previousPage": "Previous",
    "nextPage": "Next",
    "rateLimited": "Too many requests. Please log in or try again later.",
    "notFound": "Document not found."
  },
  "edgeType": {
    "references": "References",
    "replaces": "Replaces",
    "withdrawn_by": "Withdrawn by",
    "based_on_law": "Based on law",
    "adopted_from": "Adopted from"
  },
  "validity": {
    "valid": "Valid",
    "replaced": "Replaced",
    "withdrawn": "Withdrawn"
  }
```

- [ ] **Step 11: Run the i18n key-parity test**

Run: `cd frontend && npm test -- i18n`
Expected: PASS — `de.json` and `en.json` have identical key structure (this test
already exists from sub-project 1 and needs no code change; it just needs both
dictionaries to actually match, which the two blocks above do).

- [ ] **Step 12: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS.

- [ ] **Step 13: Commit**

```bash
git add frontend/src/app/globals.css frontend/tailwind.config.ts \
  frontend/src/components/ui/badge.tsx frontend/tests/unit/badge.test.tsx \
  frontend/src/components/ui/pagination.tsx frontend/tests/unit/pagination.test.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json
git commit -s -m "feat: add Badge/Pagination components, search/edge/validity i18n keys, and fix the missing muted-foreground token"
```

---

### Task 7: `/search` page (`frontend/`)

**Files:**
- Create: `frontend/src/app/search/page.tsx`
- Create: `frontend/src/app/search/search-page-content.tsx`
- Test: `frontend/tests/unit/search-page.test.tsx`

**Interfaces:**
- Consumes: `AppHeader`, `getInstanceConfig` (existing), `useTranslation` (existing),
  `useJurisdiction` (Task 4), `GET /api/documents/search` (Task 5), `Pagination`
  (Task 6), `Input`/`Button` (existing, Task 3 of sub-project 1).
- Produces: the `/search` page — consumed by no later task in this plan (a UI leaf).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/search-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { SearchPageContent } from "@/app/search/search-page-content";

const originalFetch = global.fetch;

function renderPage() {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <SearchPageContent />
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

describe("SearchPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the query and renders a result as a link to its detail page", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              id: "11111111-1111-1111-1111-111111111111",
              origin_issuer: "DGUV", origin_number: "Vorschrift 1",
              designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
            },
          ],
          total: 1,
        }),
        { status: 200 },
      ),
    );

    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Regelwerk suchen…"), {
      target: { value: "Vorschrift" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DGUV Vorschrift 1" })).toHaveAttribute(
        "href", "/documents/11111111-1111-1111-1111-111111111111",
      ),
    );
  });

  it("shows an empty state when there are no results", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => expect(screen.getByText("Keine Treffer.")).toBeInTheDocument());
  });

  it("shows a rate-limit message on a 429 without crashing", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "rate limit exceeded" }), { status: 429 }),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Zu viele Anfragen. Bitte melde dich an oder versuche es später erneut."),
      ).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- search-page`
Expected: FAIL — `@/app/search/search-page-content` doesn't exist yet.

- [ ] **Step 3: Write the page content component**

```tsx
// frontend/src/app/search/search-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { useTranslation } from "@/lib/i18n/provider";
import { useJurisdiction } from "@/lib/jurisdiction/provider";

interface DocumentSummary {
  id: string;
  origin_issuer: string;
  origin_number: string;
  designations: { designation: string; is_primary: boolean }[];
}

interface SearchResponse {
  results: DocumentSummary[];
  total: number;
}

const PAGE_SIZE = 20;

export function SearchPageContent() {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [q, setQ] = React.useState("");
  const [issuer, setIssuer] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [response, setResponse] = React.useState<SearchResponse | null>(null);
  const [isRateLimited, setIsRateLimited] = React.useState(false);

  const runSearch = React.useCallback(
    async (nextOffset: number) => {
      const params = new URLSearchParams({
        jurisdiction, limit: String(PAGE_SIZE), offset: String(nextOffset),
      });
      if (q) params.set("q", q);
      if (issuer) params.set("issuer", issuer);

      const result = await fetch(`/api/documents/search?${params.toString()}`);
      if (result.status === 429) {
        setIsRateLimited(true);
        return;
      }
      setIsRateLimited(false);
      setResponse(await result.json());
      setOffset(nextOffset);
    },
    [jurisdiction, q, issuer],
  );

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    runSearch(0);
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={submit} className="flex gap-2">
        <Input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("search.inputPlaceholder")}
          aria-label={t("search.inputPlaceholder")}
        />
        <Input
          value={issuer}
          onChange={(event) => setIssuer(event.target.value)}
          placeholder={t("search.issuerFilterLabel")}
          aria-label={t("search.issuerFilterLabel")}
          className="max-w-[10rem]"
        />
        <Button type="submit">{t("search.searchButton")}</Button>
      </form>

      {isRateLimited && <p className="text-sm text-red-600">{t("search.rateLimited")}</p>}

      {response !== null && !isRateLimited && response.results.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("search.empty")}</p>
      )}

      {response !== null && response.results.length > 0 && (
        <>
          <ul className="flex flex-col gap-2">
            {response.results.map((document) => {
              const primary =
                document.designations.find((d) => d.is_primary) ?? document.designations[0];
              return (
                <li key={document.id}>
                  <Link href={`/documents/${document.id}`} className="underline">
                    {primary?.designation ?? `${document.origin_issuer} ${document.origin_number}`}
                  </Link>
                </li>
              );
            })}
          </ul>
          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={response.total}
            onPageChange={runSearch}
            previousLabel={t("search.previousPage")}
            nextLabel={t("search.nextPage")}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write the page wrapper**

```tsx
// frontend/src/app/search/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { SearchPageContent } from "./search-page-content";

export default function SearchPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <SearchPageContent />
      </main>
    </>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- search-page`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS, `/search` listed as `ƒ` (Dynamic) in the build output.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/search/ frontend/tests/unit/search-page.test.tsx
git commit -s -m "feat: add the /search page (full-text search, issuer filter, pagination)"
```

---

### Task 8: `/documents/[id]` detail page (`frontend/`)

**Files:**
- Create: `frontend/src/app/documents/[id]/page.tsx`
- Create: `frontend/src/app/documents/[id]/document-detail-content.tsx`
- Test: `frontend/tests/unit/document-detail-page.test.tsx`

**Interfaces:**
- Consumes: `AppHeader`, `getInstanceConfig` (existing), `useTranslation` (existing),
  `useJurisdiction` (Task 4), `GET /api/documents/[id]` (existing, sub-project 1),
  `GET /api/documents/[id]/edges`, `GET /api/documents/[id]/validity` (Task 5),
  `Badge` (Task 6).
- Produces: the `/documents/[id]` page — the last page this plan builds, linked to
  from `/search` (Task 7) and from within itself (edge links to other documents).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/document-detail-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { DocumentDetailContent } from "@/app/documents/[id]/document-detail-content";

const originalFetch = global.fetch;

function renderDetail(documentId: string) {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <DocumentDetailContent documentId={documentId} />
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

const DOCUMENT_ID = "11111111-1111-1111-1111-111111111111";
const EDGE_TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("DocumentDetailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders designation, title, validity, and a resolved edge link", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes(`/api/documents/${DOCUMENT_ID}/edges`)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([{ edge_type: "references", to_document_id: EDGE_TARGET_ID }]),
            { status: 200 },
          ),
        );
      }
      if (url.includes(`/api/documents/${DOCUMENT_ID}/validity`)) {
        return Promise.resolve(
          new Response(JSON.stringify({ status: "valid" }), { status: 200 }),
        );
      }
      if (url.includes(`/api/documents/${EDGE_TARGET_ID}`)) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              designations: [{ designation: "DIN EN ISO 9001", is_primary: true }],
            }),
            { status: 200 },
          ),
        );
      }
      // GET /api/documents/{DOCUMENT_ID}
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: DOCUMENT_ID, origin_issuer: "DGUV", origin_number: "Vorschrift 1",
            designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
            titles: [{ language: "de", title: "Grundsätze der Prävention" }],
            source: { publisher: "DGUV", retrieval_path: "https://www.dguv.de/publikationen" },
          }),
          { status: 200 },
        ),
      );
    });

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "DGUV Vorschrift 1" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Grundsätze der Prävention")).toBeInTheDocument();
    expect(screen.getByText("Gültig")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DIN EN ISO 9001" })).toHaveAttribute(
        "href", `/documents/${EDGE_TARGET_ID}`,
      ),
    );
  });

  it("shows a not-found message on a 404", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 404 }));

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("Regelwerk nicht gefunden.")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- document-detail-page`
Expected: FAIL — `@/app/documents/[id]/document-detail-content` doesn't exist yet.

- [ ] **Step 3: Write the page content component**

```tsx
// frontend/src/app/documents/[id]/document-detail-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useJurisdiction } from "@/lib/jurisdiction/provider";

interface DocumentDetail {
  id: string;
  origin_issuer: string;
  origin_number: string;
  designations: { designation: string; is_primary: boolean }[];
  titles: { language: string; title: string }[];
  source: { publisher: string; retrieval_path: string };
}

interface RawEdge {
  edge_type: string;
  to_document_id: string;
}

interface ResolvedEdge extends RawEdge {
  label: string;
}

interface ValiditySummary {
  status: "valid" | "replaced" | "withdrawn";
}

const EDGE_TYPE_KEYS: Record<string, TranslationKey> = {
  references: "edgeType.references",
  replaces: "edgeType.replaces",
  withdrawn_by: "edgeType.withdrawn_by",
  based_on_law: "edgeType.based_on_law",
  adopted_from: "edgeType.adopted_from",
};

const VALIDITY_KEYS: Record<string, TranslationKey> = {
  valid: "validity.valid",
  replaced: "validity.replaced",
  withdrawn: "validity.withdrawn",
};

export function DocumentDetailContent({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [document, setDocument] = React.useState<DocumentDetail | null>(null);
  const [edges, setEdges] = React.useState<ResolvedEdge[]>([]);
  const [validity, setValidity] = React.useState<ValiditySummary | null>(null);
  const [notFound, setNotFound] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const query = `?jurisdiction=${encodeURIComponent(jurisdiction)}`;

    async function load() {
      const [documentResponse, edgesResponse, validityResponse] = await Promise.all([
        fetch(`/api/documents/${documentId}${query}`),
        fetch(`/api/documents/${documentId}/edges${query}`),
        fetch(`/api/documents/${documentId}/validity${query}`),
      ]);
      if (cancelled) return;

      if (documentResponse.status === 404) {
        setNotFound(true);
        return;
      }
      setDocument(await documentResponse.json());
      setValidity(validityResponse.ok ? await validityResponse.json() : null);

      const rawEdges: RawEdge[] = edgesResponse.ok ? await edgesResponse.json() : [];
      const resolved = await Promise.all(
        rawEdges.map(async (edge): Promise<ResolvedEdge> => {
          try {
            const targetResponse = await fetch(
              `/api/documents/${edge.to_document_id}${query}`,
            );
            const target = await targetResponse.json();
            const label =
              target.designations?.find((d: { is_primary: boolean }) => d.is_primary)
                ?.designation ?? edge.to_document_id;
            return { ...edge, label };
          } catch {
            return { ...edge, label: edge.to_document_id };
          }
        }),
      );
      if (!cancelled) setEdges(resolved);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [documentId, jurisdiction]);

  if (notFound) {
    return <p>{t("search.notFound")}</p>;
  }
  if (document === null) {
    return null;
  }

  const primaryDesignation =
    document.designations.find((d) => d.is_primary)?.designation ??
    `${document.origin_issuer} ${document.origin_number}`;
  const primaryTitle = document.titles[0]?.title;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">{primaryDesignation}</h1>
        {primaryTitle && <p className="text-muted-foreground">{primaryTitle}</p>}
      </div>

      {validity && (
        <Badge variant={validity.status === "valid" ? "default" : "outline"}>
          {t(VALIDITY_KEYS[validity.status])}
        </Badge>
      )}

      <a
        href={document.source.retrieval_path}
        className="text-sm underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {document.source.publisher}
      </a>

      {edges.length > 0 && (
        <ul className="flex flex-col gap-2">
          {edges.map((edge) => (
            <li key={`${edge.edge_type}-${edge.to_document_id}`} className="flex items-center gap-2">
              <Badge variant="muted">{t(EDGE_TYPE_KEYS[edge.edge_type] ?? "edgeType.references")}</Badge>
              <Link href={`/documents/${edge.to_document_id}`} className="underline">
                {edge.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write the page wrapper**

```tsx
// frontend/src/app/documents/[id]/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { DocumentDetailContent } from "./document-detail-content";

export default function DocumentDetailPage({ params }: { params: { id: string } }) {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <DocumentDetailContent documentId={params.id} />
      </main>
    </>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- document-detail-page`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS, `/documents/[id]` listed as `ƒ` (Dynamic).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/documents/ frontend/tests/unit/document-detail-page.test.tsx
git commit -s -m "feat: add the /documents/[id] detail page with clickable edges and validity"
```

---

### Task 9: Capstone — end-to-end tests and full regression

**Files:**
- Modify: `frontend/tests/e2e/chat-and-history.spec.ts` OR create:
  `frontend/tests/e2e/search-and-browse.spec.ts` (create a new file — cleaner than
  growing the existing one, and this plan's own feature area)

**Interfaces:**
- Consumes: everything from Tasks 1-8, plus real `api/` and `accounts/` processes
  (same pattern as sub-project 1's capstone).

- [ ] **Step 1: Write the end-to-end test**

Follow the exact environment setup already established in sub-project 1's own
capstone (`docker run` a Postgres container, run `core/`'s alembic migrations
against it, start `accounts/` and `api/` as background `uvicorn` processes with
`NORMLY_DATABASE_URL` pointed at that container, set the frontend's own
`NORMLY_API_BASE_URL`/`NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_CHAT_BASE_URL` env vars —
`api/` genuinely needs to be reachable this time, unlike sub-project 1's capstone
where it only needed to exist as an env var). Seed at least one real document via
`core/`'s repositories (same `_seed_document` pattern used in this plan's own
`core/`/`api/` tests) directly against the running Postgres container before the
Playwright run, since this flow has no UI-driven way to create data.

```typescript
// frontend/tests/e2e/search-and-browse.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("search and document detail", () => {
  test("searching finds a seeded document and its detail page shows validity", async ({
    page,
  }) => {
    await page.goto("/search");
    await page.getByPlaceholderText("Regelwerk suchen…").fill("Vorschrift");
    await page.getByRole("button", { name: "Suchen" }).click();

    await page.getByRole("link", { name: /DGUV Vorschrift/ }).click();
    await expect(page.getByText("Gültig")).toBeVisible();
  });

  test("the jurisdiction switcher is present and defaults to DE", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByLabel("Jurisdiktion")).toHaveValue("DE");
  });
});
```

(The exact seeded document's designation — `"DGUV Vorschrift 1"` or similar — must
match whatever this task's own seed step actually inserts; adjust the assertion
text to match the real seed data used when writing this task, rather than assuming
the literal string above.)

- [ ] **Step 2: Run the end-to-end suite**

Run: `cd frontend && npm run test:e2e`
Expected: PASS, given `accounts/` and `api/` are running with a seeded document, per
Step 1's setup.

- [ ] **Step 3: Run the full unit suite one final time**

Run: `cd frontend && npm test`
Expected: all pass, pristine output.

- [ ] **Step 4: Run the full core and api suites one final time**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: all pass — confirms this plan's Task 1/2 backend changes (rate limiting on
every endpoint, the new search endpoint) didn't break any pre-existing behavior.

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/e2e/search-and-browse.spec.ts
git commit -s -m "test: add end-to-end search-and-detail coverage"
```

---

## Self-Review

**Spec coverage:**

| Spec-Abschnitt | Task |
|---|---|
| Funktionsumfang: Suche + Detailseite + Graph-Browsing + Browse-nach-Herausgeber | Task 2 (Endpunkt deckt beides), Task 7, Task 8 |
| Ratenbegrenzung (REQ-ACC-003, Herkunftsadresse) | Task 1 |
| Sitzungsmerkmal für Ratenbegrenzung (`normly_anon_id`) | Task 3 (Vergabe), Task 1 (Nutzung im Schlüssel), Task 5 (Weiterleitung) |
| Jurisdiktion als app-weiter Zustand, behebt fest kodiertes "DE" im Chat | Task 4 |
| Neue BFF-Route-Handler (search/edges/validity) mit korrektem Encoding | Task 5 |
| Neue UI-Bausteine (Pagination, Badge) | Task 6 |
| i18n (Suche, Kantentyp-Bezeichnungen, Gültigkeitsstatus) | Task 6 |
| `/search`-Seite | Task 7 |
| `/documents/[id]`-Detailseite mit klickbaren Verweisen | Task 8 |
| Fehlerbehandlung (429, leere Trefferliste, 404, nicht erreichbar) | Task 7 (429, leer), Task 8 (404) |
| Testkonzept (core/api/frontend/e2e) | jede Task trägt ihre eigenen Tests; Task 9 bündelt e2e + Regression |

No gap found — every section of the approved spec maps to at least one task.

**Placeholder scan:** No "TBD"/"TODO" found. The spec's own "Offene Punkte" (full
anomaly detection, jurisdictions beyond DE/EU, full-text index) are out of this
plan's scope by explicit spec decision, not placeholders left behind by this plan.

**Type consistency:** `search_documents_for_jurisdiction`'s signature (Task 2, Step
3/4) is used identically in the router (Task 2, Step 11) and tested against directly
(Task 2, Step 1). `enforce_rate_limit` (Task 1) is imported by name, unchanged, in
Task 2's `main.py` wiring. `useJurisdiction()`'s `{ jurisdiction, setJurisdiction }`
shape (Task 4) is consumed identically in Task 7 and Task 8. `TranslationKey`-typed
`EDGE_TYPE_KEYS`/`VALIDITY_KEYS` maps (Task 8) use exactly the key strings added to
both dictionaries in Task 6, Step 10 — checked side by side above.

**One incidental fix folded in, not scope creep:** Task 6, Step 1 fixes a
pre-existing, silently-broken `text-muted-foreground` utility class (used in two
already-shipped components but never defined in `tailwind.config.ts`) — directly
required because this plan's new `Badge` component needs a working `foreground`
token, and leaving the existing bug in place while adding more code that depends on
the same missing token class would be building on a known-broken foundation.
