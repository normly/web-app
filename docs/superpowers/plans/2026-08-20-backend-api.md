# Backend-API (deterministische Graph-Anfragen, v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only, OpenAPI-documented FastAPI service (`api/`) exposing deterministic
graph queries — lookup, references, validity/replacement chains, and a full free-graph
export — over the data already ingested by `normly_core`.

**Architecture:** New top-level package `api/`, depending on `normly_core` as an installed
sibling dependency. FastAPI app under `api/src/normly_api/`, routers per resource, Pydantic
response models decoupled from `normly_core.graph.domain`. Every document-returning endpoint
gates through `DocumentRepository.get_document_for_jurisdiction` (the sole authorization
check) before touching any of the deliberately-ungated enrichment methods
(`list_designations`, `list_titles`, `find_by_designation`).

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (via `normly_core`), pytest +
`fastapi.testclient.TestClient`, real PostgreSQL via Testcontainers (same pattern as
`core/tests/conftest.py`).

## Global Constraints

- **License headers:** every new `.py` file in `api/` starts with
  `# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors`
  — the server implementation is part of the free core, same as `core/`. The OpenAPI
  specification itself (the generated `/openapi.json` document) is licensed separately as
  Apache-2.0, expressed via FastAPI's `license_info` on the app instance — not a per-file
  header, a runtime-configured field on the generated document.
- **DCO:** every commit uses `git commit -s`. Conventional Commits, SemVer.
- **The one gate:** `DocumentRepository`'s own docstring (`core/src/normly_core/graph/domain.py`)
  marks `list_designations`, `list_titles`, `find_by_designation`, and
  `get_document_unchecked` as ungated, internal-only methods — never the sole basis for what
  a response contains. Every endpoint that returns document content calls
  `get_document_for_jurisdiction(document_id, jurisdiction)` (or, for list endpoints,
  `list_documents_for_jurisdiction(jurisdiction)` / `list_edges_for_jurisdiction(...)`,
  which are themselves rights-classification-joined) as the sole authorization check. The
  ungated methods may only be called on a document identity that has already passed that
  gate, purely for enrichment (designations, titles) — never to decide visibility.
- **No writes.** No endpoint in this plan calls any repository method that mutates the
  database. If a task's code ever imports `record_delivery`, `create_document`,
  `add_designation`, `classify`, `create_edge`, `add_segment`, or `add_embedding`, that is a
  sign something has gone wrong.
- **`jurisdiction` is a required query parameter** on every endpoint that touches
  rights-gated content. Missing or empty → 400 (not FastAPI's default 422 — this plan
  configures a custom validation-error handler for that, see Task 8).
- **Test style:** no mocking of the database. Real PostgreSQL via Testcontainers, shared
  session-scoped container/migrated-engine, function-scoped `db_session` with savepoint
  rollback — the exact pattern already established in `core/tests/conftest.py`. Test data is
  built directly via `normly_core`'s repository classes (`PostgresSourceRepository`,
  `PostgresDeliveryRepository`, `PostgresDocumentRepository`, `PostgresRightsRepository`,
  `PostgresEdgeRepository`), never via HTTP self-seeding.
- **Test output must be pristine** (zero warnings) — run the full suite with `-W error`
  before every commit.
- **venv bootstrap:** `core/.venv`'s own `pip` may be broken in this sandbox (known issue,
  `ensurepip` unavailable). Prefer `.venv/bin/python -m pip install ...`; fall back to
  `/usr/bin/python3 -m pip install --target .venv/lib/python3<X>/site-packages ...` only if
  that also fails.

---

### Task 1: `api/` package scaffolding

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/src/normly_api/__init__.py`
- Create: `api/src/normly_api/main.py`
- Create: `api/src/normly_api/dependencies.py`
- Create: `api/tests/__init__.py`
- Create: `api/tests/conftest.py`
- Test: `api/tests/test_main.py`

**Interfaces:**
- Consumes: `normly_core` as an installed sibling package (already built, unchanged by this
  task).
- Produces: `create_app() -> FastAPI` in `normly_api.main`, `get_session` dependency in
  `normly_api.dependencies` — both used by every later task's router.

- [ ] **Step 1: Create the package manifest**

```toml
# api/pyproject.toml
[project]
name = "normly-api"
version = "0.1.0"
description = "normly free core: read-only HTTP API over the reference graph"
requires-python = ">=3.11"
license = { text = "AGPL-3.0-or-later" }
dependencies = [
    "normly-core",
    "fastapi>=0.115,<0.120",
    "uvicorn[standard]>=0.30,<1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "httpx>=0.27,<1.0",
    "testcontainers[postgres]>=4.15,<5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/normly_api"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Set up the venv and install both packages**

```bash
cd api
python3 -m venv .venv
# If ensurepip fails here too (same known issue as core/), use:
#   /usr/bin/python3 -m pip install --target .venv/lib/python3<X>/site-packages -e ../core -e ".[dev]"
.venv/bin/python -m pip install -e ../core -e ".[dev]"
```

`normly-core` is installed editable from the sibling `core/` checkout — no PyPI publish
step, no version pin needed for a same-repo dependency.

- [ ] **Step 3: Write `dependencies.py`**

```python
# api/src/normly_api/dependencies.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
```

- [ ] **Step 4: Write `main.py`**

```python
# api/src/normly_api/main.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import create_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ["NORMLY_DATABASE_URL"]
    engine = create_engine(database_url)
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    return FastAPI(
        title="normly API",
        version="1.0.0",
        description=(
            "Deterministic reference-graph queries over normly's free content. "
            "No authentication required for free-tier jurisdictions."
        ),
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        lifespan=lifespan,
    )


app = create_app()
```

`create_app()` is a factory (not just a module-level `app`) so tests can construct fresh
instances with dependency overrides without import-order side effects.

- [ ] **Step 5: Write `api/src/normly_api/__init__.py` and `api/tests/__init__.py`**

```python
# api/src/normly_api/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# api/tests/__init__.py
```

- [ ] **Step 6: Write `conftest.py`**

```python
# api/tests/conftest.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

API_DIR = Path(__file__).parents[1]
CORE_DIR = API_DIR.parent / "core"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as container:
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
    nested = connection.begin_nested()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    if nested.is_active:
        nested.rollback()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_url, monkeypatch, db_session):
    """
    A TestClient whose requests are served from this test's own db_session
    connection (via a dependency override), so data set up through db_session
    is visible to HTTP calls and everything rolls back together at teardown.

    The app's own lifespan still needs NORMLY_DATABASE_URL set (it creates its
    own, separate engine on startup) even though requests never use that
    engine directly -- the override intercepts get_session before it would.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_api.dependencies import get_session
    from normly_api.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client
```

Identical container/migration/session-savepoint pattern to `core/tests/conftest.py`
(`CORE_DIR` there is `Path(__file__).parents[1]`; here it's the sibling `../core`, since
`api/` and `core/` are separate top-level packages in the same repo).

- [ ] **Step 7: Write the failing smoke test**

```python
# api/tests/test_main.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_openapi_schema_is_served_and_licensed_apache_2_0(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["license"]["name"] == "Apache-2.0"
```

- [ ] **Step 8: Run the test**

Run: `cd api && .venv/bin/python -m pytest tests/test_main.py -v`
Expected: PASS (nothing to fail against here — this is the scaffolding's own acceptance
test, not a TDD red/green pair; the app either boots and serves `/openapi.json` correctly or
it doesn't).

- [ ] **Step 9: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output.

- [ ] **Step 10: Commit**

```bash
git add api/pyproject.toml api/src/normly_api/__init__.py api/src/normly_api/main.py \
  api/src/normly_api/dependencies.py api/tests/__init__.py api/tests/conftest.py \
  api/tests/test_main.py
git commit -s -m "feat: scaffold the normly-api package"
```

---

### Task 2: Pydantic response schemas

**Files:**
- Create: `api/src/normly_api/schemas.py`

**Interfaces:**
- Consumes: nothing beyond the standard library and Pydantic.
- Produces: `DesignationResponse`, `TitleResponse`, `SourceResponse`, `DocumentResponse`,
  `EdgeResponse`, `ValidityResponse`, `LicenseNotice`, `ExportResponse` — used by every
  router task from here on.

No test file for this task — the schemas are pure data declarations with no behavior of
their own; they are exercised through every later task's endpoint tests. (A schema-only file
skipping a dedicated test is consistent with how `pipeline.domain`'s dataclasses were
introduced without their own behavioral tests in the previous sub-project — behavior lives
in what uses them.)

- [ ] **Step 1: Write the schemas**

```python
# api/src/normly_api/schemas.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DesignationResponse(BaseModel):
    issuer: str
    designation: str
    language: str
    is_primary: bool


class TitleResponse(BaseModel):
    language: str
    title: str


class SourceResponse(BaseModel):
    publisher: str
    retrieval_path: str
    legal_basis_category: str
    jurisdiction: str


class DocumentResponse(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    designations: list[DesignationResponse]
    titles: list[TitleResponse]
    source: SourceResponse


class EdgeResponse(BaseModel):
    edge_type: str
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    jurisdiction: str | None
    layer: str


class ValidityResponse(BaseModel):
    document_id: uuid.UUID
    status: Literal["valid", "replaced", "withdrawn"]
    replaced_by: list[uuid.UUID]
    withdrawn_reference: str | None


class LicenseNotice(BaseModel):
    license_name: str
    license_url: str
    attribution: str


class ExportResponse(BaseModel):
    license: LicenseNotice
    schema_version: str
    jurisdiction: str
    generated_at: datetime
    documents: list[DocumentResponse]
    edges: list[EdgeResponse]


class ErrorResponse(BaseModel):
    detail: str
```

`ErrorResponse` is new relative to the design spec's sketch — added here as the one
structured error body shape every error path in this plan returns (`{"detail": "..."}`,
matching FastAPI's own default `HTTPException` shape so it needs no custom exception
rendering beyond what Task 8 adds for the 400/503 cases).

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd api && .venv/bin/python -c "from normly_api import schemas"`
Expected: no output, exit code 0.

- [ ] **Step 3: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: all pass (unchanged from Task 1), pristine output.

- [ ] **Step 4: Commit**

```bash
git add api/src/normly_api/schemas.py
git commit -s -m "feat: add API response schemas"
```

---

### Task 3: `GET /v1/documents` — search by designation

**Files:**
- Create: `api/src/normly_api/routers/__init__.py`
- Create: `api/src/normly_api/routers/documents.py`
- Test: `api/tests/test_documents_search.py`

**Interfaces:**
- Consumes: `get_session` (Task 1), `DocumentResponse`/`DesignationResponse`/
  `TitleResponse`/`SourceResponse` (Task 2), `PostgresDocumentRepository`,
  `PostgresDeliveryRepository`, `PostgresSourceRepository` (from `normly_core.graph.postgres.repositories`).
- Produces: `documents_router` (an `APIRouter`), a `_document_to_response` helper reused by
  Tasks 4 and 7.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_documents_search.py
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


def _seed_document(db_session, *, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-search-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_finds_a_classified_document(client, db_session):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1", "jurisdiction": "DE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(document.id)
    assert body["source"]["publisher"] == "DGUV"
    assert body["source"]["retrieval_path"] == "https://www.dguv.de/publikationen"


def test_search_hides_a_document_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    _seed_document(db_session, jurisdiction="DE")

    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1", "jurisdiction": "FR"},
    )

    assert response.status_code == 404


def test_search_returns_404_for_an_unknown_designation(client, db_session):
    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "does-not-exist", "jurisdiction": "DE"},
    )

    assert response.status_code == 404


def test_search_returns_400_when_jurisdiction_is_missing(client, db_session):
    response = client.get(
        "/v1/documents", params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1"}
    )

    assert response.status_code == 400
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_search.py -v`
Expected: FAIL — `documents_router` and the `/v1/documents` route don't exist yet, and
`main.py` doesn't mount any router (404s for a different reason than intended, or import
errors).

- [ ] **Step 3: Write the implementation**

```python
# api/src/normly_api/routers/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# api/src/normly_api/routers/documents.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Document
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)

from normly_api.dependencies import get_session
from normly_api.schemas import (
    DesignationResponse,
    DocumentResponse,
    SourceResponse,
    TitleResponse,
)

documents_router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _document_to_response(document: Document, session: Session) -> DocumentResponse:
    """
    Build the full DocumentResponse for a document that has ALREADY passed the
    jurisdiction gate (get_document_for_jurisdiction returned non-None for it).
    Only after that gate may the ungated enrichment methods below run.
    """
    doc_repo = PostgresDocumentRepository(session)
    designations = [
        DesignationResponse(
            issuer=d.issuer, designation=d.designation, language=d.language,
            is_primary=d.is_primary,
        )
        for d in doc_repo.list_designations(document.id)
    ]
    titles = [
        TitleResponse(language=t.language, title=t.title)
        for t in doc_repo.list_titles(document.id)
    ]

    delivery = PostgresDeliveryRepository(session).get_delivery(document.created_via_delivery_id)
    source = PostgresSourceRepository(session).get_source(delivery.source_id)
    source_response = SourceResponse(
        publisher=source.publisher, retrieval_path=source.retrieval_path,
        legal_basis_category=source.legal_basis_category.value,
        jurisdiction=source.jurisdiction,
    )

    return DocumentResponse(
        id=document.id, origin_issuer=document.origin_issuer,
        origin_number=document.origin_number, edition=document.edition, part=document.part,
        designations=designations, titles=titles, source=source_response,
    )


@documents_router.get("", response_model=DocumentResponse)
def search_documents(
    issuer: str, designation: str, jurisdiction: str,
    session: Session = Depends(get_session),
) -> DocumentResponse:
    doc_repo = PostgresDocumentRepository(session)
    found = doc_repo.find_by_designation(issuer, designation)
    if found is None:
        raise HTTPException(status_code=404, detail="no document matches this designation")

    gated = doc_repo.get_document_for_jurisdiction(found.id, jurisdiction)
    if gated is None:
        raise HTTPException(
            status_code=404, detail="no document matches this designation"
        )

    return _document_to_response(gated, session)
```

`find_by_designation` here decides identity only (which `document_id`, if any, matches this
designation string) — the response is built exclusively from `gated`, the
`get_document_for_jurisdiction` result. The two 404s use the same message deliberately: a
caller cannot distinguish "no such designation" from "exists, not visible in this
jurisdiction" from the response alone, which is the intended non-disclosure behavior.

- [ ] **Step 4: Mount the router**

Modify `api/src/normly_api/main.py` — add the import and mount call:

```python
from normly_api.routers.documents import documents_router
```

Add inside `create_app()`, after constructing `app` and before `return app`:

```python
    app.include_router(documents_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_search.py -v`
Expected: three of four PASS. `test_search_returns_400_when_jurisdiction_is_missing` is
expected to FAIL here — FastAPI's default behavior for a missing required query parameter is
422, not 400. Confirm this is the actual failure (422 returned, not a crash) and leave it
failing; Task 8 adds the global handler that turns it into 400. Do not work around this
locally in this task's router — the fix belongs in one place for every endpoint, not
duplicated per-router.

- [ ] **Step 6: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: all PASS except the one documented, deliberately-deferred 400-vs-422 case from
Step 5.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api/routers/__init__.py api/src/normly_api/routers/documents.py \
  api/src/normly_api/main.py api/tests/test_documents_search.py
git commit -s -m "feat: add GET /v1/documents search endpoint"
```

---

### Task 4: `GET /v1/documents/{id}` — document detail

**Files:**
- Modify: `api/src/normly_api/routers/documents.py`
- Test: `api/tests/test_documents_detail.py`

**Interfaces:**
- Consumes: `_document_to_response` (Task 3, unchanged).
- Produces: nothing new for later tasks — this is a leaf endpoint.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_documents_detail.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from tests.test_documents_search import _seed_document


def test_detail_returns_a_classified_document(client, db_session):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(f"/v1/documents/{document.id}", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)


def test_detail_hides_a_document_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(f"/v1/documents/{document.id}", params={"jurisdiction": "FR"})

    assert response.status_code == 404


def test_detail_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(f"/v1/documents/{uuid.uuid4()}", params={"jurisdiction": "DE"})

    assert response.status_code == 404
```

`from tests.test_documents_search import _seed_document` reuses the fixture helper —
acceptable coupling between two test modules for this plan's size; if a third test module
needs it, promote it to a `conftest.py` fixture instead rather than importing across a third
file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_detail.py -v`
Expected: FAIL with 404 on every request (no `/v1/documents/{id}` route registered yet — the
existing `search_documents` route is registered at the router's bare prefix, not a
sub-path).

- [ ] **Step 3: Add the detail route**

Add to `api/src/normly_api/routers/documents.py`, after `search_documents`:

```python
@documents_router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> DocumentResponse:
    doc_repo = PostgresDocumentRepository(session)
    gated = doc_repo.get_document_for_jurisdiction(document_id, jurisdiction)
    if gated is None:
        raise HTTPException(status_code=404, detail="document not found")

    return _document_to_response(gated, session)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_documents_detail.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: same pass/fail split as the end of Task 3 (the one deferred 400-vs-422 case still
open, everything else green).

- [ ] **Step 6: Commit**

```bash
git add api/src/normly_api/routers/documents.py api/tests/test_documents_detail.py
git commit -s -m "feat: add GET /v1/documents/{id} detail endpoint"
```

---

### Task 5: `GET /v1/documents/{id}/edges` — references and relationships

**Files:**
- Create: `api/src/normly_api/routers/edges.py`
- Test: `api/tests/test_edges.py`

**Interfaces:**
- Consumes: `get_session` (Task 1), `EdgeResponse` (Task 2), `PostgresDocumentRepository`,
  `PostgresEdgeRepository`.
- Produces: `edges_router`, mounted alongside `documents_router`.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_edges.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _seed_two_documents_with_an_edge(db_session, *, edge_type=EdgeType.BASED_ON_LAW):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-edges-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    rights_repo = PostgresRightsRepository(db_session)
    for doc in (standard, legal_act):
        rights_repo.classify(
            document_id=doc.id, jurisdiction="EU", may_process=True,
            may_index_fulltext=False, may_cite_passages=False, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="test", delivery_id=delivery.id,
        )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=standard.id, to_document_id=legal_act.id, edge_type=edge_type,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    return standard, legal_act


def test_edges_lists_relationships_for_a_classified_document(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)

    response = client.get(f"/v1/documents/{standard.id}/edges", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    edges = response.json()
    assert len(edges) == 1
    assert edges[0]["to_document_id"] == str(legal_act.id)
    assert edges[0]["edge_type"] == "based_on_law"


def test_edges_filters_by_edge_type(client, db_session):
    standard, _ = _seed_two_documents_with_an_edge(db_session, edge_type=EdgeType.REFERENCES)

    matching = client.get(
        f"/v1/documents/{standard.id}/edges",
        params={"jurisdiction": "EU", "edge_type": "references"},
    )
    non_matching = client.get(
        f"/v1/documents/{standard.id}/edges",
        params={"jurisdiction": "EU", "edge_type": "replaces"},
    )

    assert len(matching.json()) == 1
    assert len(non_matching.json()) == 0


def test_edges_returns_empty_list_for_a_document_not_classified_in_this_jurisdiction(
    client, db_session
):
    standard, _ = _seed_two_documents_with_an_edge(db_session)

    response = client.get(f"/v1/documents/{standard.id}/edges", params={"jurisdiction": "FR"})

    assert response.status_code == 200
    assert response.json() == []


def test_edges_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(
        f"/v1/documents/{uuid.uuid4()}/edges", params={"jurisdiction": "EU"}
    )

    assert response.status_code == 404
```

This test module deliberately proves the asymmetry the design spec calls for: an unknown
`document_id` is 404, but a real document with no visible edges in the requested
jurisdiction is 200 with an empty list — the two cases must be distinguishable, which is why
this router (unlike `documents.py`'s detail endpoint) needs an explicit existence check
alongside the gated list call.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_edges.py -v`
Expected: FAIL — no `/v1/documents/{id}/edges` route exists.

- [ ] **Step 3: Write the implementation**

```python
# api/src/normly_api/routers/edges.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEdgeRepository,
)

from normly_api.dependencies import get_session
from normly_api.schemas import EdgeResponse

edges_router = APIRouter(prefix="/v1/documents", tags=["edges"])


@edges_router.get("/{document_id}/edges", response_model=list[EdgeResponse])
def list_edges(
    document_id: uuid.UUID, jurisdiction: str, edge_type: str | None = None,
    session: Session = Depends(get_session),
) -> list[EdgeResponse]:
    # list_edges_for_jurisdiction alone cannot distinguish "no such document" from
    # "document exists, no edges visible in this jurisdiction" -- both produce an
    # empty result from that join. get_document_unchecked is the one sanctioned use
    # of an otherwise-internal method: an existence check that reveals nothing about
    # rights-gated content, only whether the id refers to a real document at all.
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_unchecked(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")

    edges = PostgresEdgeRepository(session).list_edges_for_jurisdiction(
        document_id, jurisdiction
    )
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type.value == edge_type]

    return [
        EdgeResponse(
            edge_type=e.edge_type.value, from_document_id=e.from_document_id,
            to_document_id=e.to_document_id, jurisdiction=e.jurisdiction,
            layer=e.layer.value,
        )
        for e in edges
    ]
```

- [ ] **Step 4: Mount the router**

Add to `api/src/normly_api/main.py`:

```python
from normly_api.routers.edges import edges_router
```

and, alongside the existing `app.include_router(documents_router)`:

```python
    app.include_router(edges_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_edges.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: same as before, only the one deferred 400-vs-422 case open.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api/routers/edges.py api/src/normly_api/main.py api/tests/test_edges.py
git commit -s -m "feat: add GET /v1/documents/{id}/edges endpoint"
```

---

### Task 6: `GET /v1/documents/{id}/validity` — replacement and withdrawal status

**Files:**
- Create: `api/src/normly_api/routers/validity.py`
- Test: `api/tests/test_validity.py`

**Interfaces:**
- Consumes: `get_session` (Task 1), `ValidityResponse` (Task 2),
  `PostgresDocumentRepository`, `PostgresEdgeRepository`.
- Produces: `validity_router`, mounted alongside the others.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_validity.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _seed_classified_document(db_session, *, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-validity-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 2", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document, delivery


def test_validity_reports_valid_for_a_document_with_no_replaces_or_withdrawn_by_edges(
    client, db_session
):
    document, _ = _seed_classified_document(db_session)

    response = client.get(
        f"/v1/documents/{document.id}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["replaced_by"] == []


def test_validity_reports_replaced_when_a_replaces_edge_points_at_this_document(
    client, db_session
):
    document, delivery = _seed_classified_document(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    successor = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 2", edition="2021", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=successor.id, jurisdiction="DE", may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=successor.id, to_document_id=document.id,
        edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    response = client.get(
        f"/v1/documents/{document.id}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "replaced"
    assert body["replaced_by"] == [str(successor.id)]


def test_validity_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(
        f"/v1/documents/{uuid.uuid4()}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 404
```

`withdrawn` is intentionally not covered by its own test here: `WITHDRAWN_BY` follows the
exact same edge-inspection pattern as `REPLACES` (see Step 3), and Task 13's EUR-Lex fixture
already deliberately does not model withdrawal-with-successor (see the ingestion-pipeline
spec's Offene Punkte) — there is no real withdrawal edge anywhere in the ingested data yet to
build a meaningfully different fixture against. If a future adapter starts producing
`WITHDRAWN_BY` edges, add the test then, against real data, rather than a synthetic one now.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_validity.py -v`
Expected: FAIL — no `/v1/documents/{id}/validity` route exists.

- [ ] **Step 3: Write the implementation**

```python
# api/src/normly_api/routers/validity.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import EdgeType
from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEdgeRepository,
)

from normly_api.dependencies import get_session
from normly_api.schemas import ValidityResponse

validity_router = APIRouter(prefix="/v1/documents", tags=["validity"])


@validity_router.get("/{document_id}/validity", response_model=ValidityResponse)
def get_validity(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> ValidityResponse:
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_unchecked(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")

    # REPLACES/WITHDRAWN_BY edges point FROM the successor/withdrawal-notice
    # document TO this one -- list_edges_for_jurisdiction returns edges on
    # both sides of document_id, so filter to the incoming direction.
    edges = PostgresEdgeRepository(session).list_edges_for_jurisdiction(
        document_id, jurisdiction
    )
    incoming = [e for e in edges if e.to_document_id == document_id]

    replaced_by = [e.from_document_id for e in incoming if e.edge_type == EdgeType.REPLACES]
    withdrawn_by = [e for e in incoming if e.edge_type == EdgeType.WITHDRAWN_BY]

    if replaced_by:
        status = "replaced"
    elif withdrawn_by:
        status = "withdrawn"
    else:
        status = "valid"

    return ValidityResponse(
        document_id=document_id, status=status, replaced_by=replaced_by,
        withdrawn_reference=(
            str(withdrawn_by[0].from_document_id) if withdrawn_by else None
        ),
    )
```

- [ ] **Step 4: Mount the router**

Add to `api/src/normly_api/main.py`:

```python
from normly_api.routers.validity import validity_router
```

and:

```python
    app.include_router(validity_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_validity.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: same as before.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api/routers/validity.py api/src/normly_api/main.py \
  api/tests/test_validity.py
git commit -s -m "feat: add GET /v1/documents/{id}/validity endpoint"
```

---

### Task 7: `GET /v1/export` — full free-graph dump

**Files:**
- Create: `api/src/normly_api/routers/export.py`
- Test: `api/tests/test_export.py`

**Interfaces:**
- Consumes: `get_session` (Task 1), `_document_to_response` (Task 3),
  `ExportResponse`/`LicenseNotice`/`EdgeResponse` (Task 2), `PostgresDocumentRepository`,
  `PostgresEdgeRepository`.
- Produces: `export_router`, mounted alongside the others. Nothing later depends on this
  task.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_export.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from tests.test_edges import _seed_two_documents_with_an_edge


def test_export_returns_a_license_notice_and_the_classified_graph(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    body = response.json()
    assert body["license"]["license_name"] == "ODbL-1.0"
    assert body["jurisdiction"] == "EU"
    document_ids = {d["id"] for d in body["documents"]}
    assert str(standard.id) in document_ids
    assert str(legal_act.id) in document_ids
    assert len(body["edges"]) == 1


def test_export_excludes_documents_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "FR"})

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_export_rejects_an_unsupported_format(client, db_session):
    response = client.get("/v1/export", params={"jurisdiction": "EU", "format": "xml"})

    assert response.status_code == 400
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_export.py -v`
Expected: FAIL — no `/v1/export` route exists.

- [ ] **Step 3: Write the implementation**

```python
# api/src/normly_api/routers/export.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEdgeRepository,
)

from normly_api.dependencies import get_session
from normly_api.routers.documents import _document_to_response
from normly_api.schemas import EdgeResponse, ExportResponse, LicenseNotice

export_router = APIRouter(prefix="/v1", tags=["export"])

_SCHEMA_VERSION = "1.0"


@export_router.get("/export", response_model=ExportResponse)
def export_free_graph(
    jurisdiction: str, format: str = "json",
    session: Session = Depends(get_session),
) -> ExportResponse:
    if format != "json":
        raise HTTPException(
            status_code=400, detail=f"unsupported export format: {format!r}"
        )

    doc_repo = PostgresDocumentRepository(session)
    edge_repo = PostgresEdgeRepository(session)

    documents = doc_repo.list_documents_for_jurisdiction(jurisdiction)
    document_responses = [_document_to_response(d, session) for d in documents]

    seen_edge_ids: set = set()
    edge_responses: list[EdgeResponse] = []
    for document in documents:
        for edge in edge_repo.list_edges_for_jurisdiction(document.id, jurisdiction):
            if edge.id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge.id)
            edge_responses.append(
                EdgeResponse(
                    edge_type=edge.edge_type.value, from_document_id=edge.from_document_id,
                    to_document_id=edge.to_document_id, jurisdiction=edge.jurisdiction,
                    layer=edge.layer.value,
                )
            )

    return ExportResponse(
        license=LicenseNotice(
            license_name="ODbL-1.0",
            license_url="https://opendatacommons.org/licenses/odbl/1-0/",
            attribution="normly contributors",
        ),
        schema_version=_SCHEMA_VERSION,
        jurisdiction=jurisdiction,
        generated_at=datetime.now(timezone.utc),
        documents=document_responses,
        edges=edge_responses,
    )
```

`list_documents_for_jurisdiction` is itself the gate here (already filters on
`may_process`/`rights_classification` per jurisdiction) — every document in `documents` has
already passed the one gate before `_document_to_response` runs its enrichment, same
invariant as Tasks 3-4.

- [ ] **Step 4: Mount the router**

Add to `api/src/normly_api/main.py`:

```python
from normly_api.routers.export import export_router
```

and:

```python
    app.include_router(export_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_export.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: same as before.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api/routers/export.py api/src/normly_api/main.py \
  api/tests/test_export.py
git commit -s -m "feat: add GET /v1/export endpoint"
```

---

### Task 8: Global error handling — 400 for validation, 503 for a down database

**Files:**
- Modify: `api/src/normly_api/main.py`
- Create: `api/src/normly_api/errors.py`
- Test: `api/tests/test_error_handling.py`

**Interfaces:**
- Consumes: `ErrorResponse` (Task 2).
- Produces: nothing consumed by later tasks — this is the last piece closing the design
  spec's Fehlerbehandlung table.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_error_handling.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from fastapi.testclient import TestClient

from normly_api.dependencies import get_session
from normly_api.main import create_app


def test_missing_required_query_parameter_is_400_not_422(client):
    response = client.get("/v1/documents")

    assert response.status_code == 400
    assert "detail" in response.json()


def test_a_broken_database_dependency_is_503(monkeypatch, db_url):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    app = create_app()

    def _broken_session():
        raise ConnectionError("simulated database outage")
        yield  # pragma: no cover -- unreachable, keeps this a generator

    app.dependency_overrides[get_session] = _broken_session

    with TestClient(app, raise_server_exceptions=False) as broken_client:
        response = broken_client.get(
            "/v1/documents", params={"issuer": "x", "designation": "y", "jurisdiction": "DE"}
        )

    assert response.status_code == 503
    assert "detail" in response.json()
    assert "outage" not in response.json()["detail"]
```

The second test is the one narrow, deliberate exception to this plan's "no mocking the
database" rule: a `ConnectionError` raised inside the dependency itself is the cheapest,
most direct way to exercise the 503 path without provisioning a real broken Postgres
instance. It tests infrastructure-level error handling, not business logic — the same kind
of narrow exception already used in the previous sub-project's forced-`IntegrityError` test.
`raise_server_exceptions=False` is required so `TestClient` returns the response instead of
re-raising the exception into the test itself.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_error_handling.py -v`
Expected: FAIL — `test_missing_required_query_parameter_is_400_not_422` gets 422 (this is
the same failure already observed and deliberately deferred in Task 3); the broken-database
test gets 500 (FastAPI's default for an unhandled exception) instead of 503.

- [ ] **Step 3: Write the exception handlers**

```python
# api/src/normly_api/errors.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_as_400(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "invalid or missing query parameter"},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_as_503(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "service temporarily unavailable"},
        )
```

The catch-all `Exception` handler deliberately never includes `str(exc)` in the response
body — an internal error message (e.g. a connection string, a stack detail) is exactly the
kind of "kein Detail-Leak" the design spec's error table calls for.

- [ ] **Step 4: Wire the handlers into the app**

Modify `api/src/normly_api/main.py` — add the import:

```python
from normly_api.errors import register_exception_handlers
```

and, inside `create_app()`, immediately before `return app`:

```python
    register_exception_handlers(app)
    return app
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_error_handling.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: every test from Tasks 1-8 passes, including every previously-deferred 400-vs-422
case across `test_documents_search.py` — pristine output.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api/errors.py api/src/normly_api/main.py \
  api/tests/test_error_handling.py
git commit -s -m "feat: add global 400/503 exception handlers"
```

---

### Task 9: Capstone — OpenAPI completeness and end-to-end read path

**Files:**
- Test: `api/tests/test_openapi_and_end_to_end.py`

**Interfaces:**
- Consumes: everything from Tasks 1-8. No new production code expected unless this test
  reveals a real integration gap — if so, fix it in the task that owns the affected file.

- [ ] **Step 1: Write the tests**

```python
# api/tests/test_openapi_and_end_to_end.py
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


def test_openapi_schema_documents_every_v1_endpoint(client):
    schema = client.get("/openapi.json").json()

    paths = set(schema["paths"].keys())
    assert paths == {
        "/v1/documents",
        "/v1/documents/{document_id}",
        "/v1/documents/{document_id}/edges",
        "/v1/documents/{document_id}/validity",
        "/v1/export",
    }
    assert schema["info"]["license"]["name"] == "Apache-2.0"


def test_full_read_path_across_all_endpoints_for_a_realistic_graph(client, db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:capstone-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=standard.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    rights_repo = PostgresRightsRepository(db_session)
    for doc in (standard, legal_act):
        rights_repo.classify(
            document_id=doc.id, jurisdiction="EU", may_process=True,
            may_index_fulltext=False, may_cite_passages=False, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="test", delivery_id=delivery.id,
        )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=standard.id, to_document_id=legal_act.id,
        edge_type=EdgeType.BASED_ON_LAW, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    search = client.get(
        "/v1/documents",
        params={"issuer": "CEN", "designation": "EN ISO 12100:2010", "jurisdiction": "EU"},
    )
    assert search.status_code == 200
    document_id = search.json()["id"]
    assert search.json()["source"]["retrieval_path"] == (
        "https://single-market-economy.ec.europa.eu"
    )

    detail = client.get(f"/v1/documents/{document_id}", params={"jurisdiction": "EU"})
    assert detail.status_code == 200
    assert detail.json()["designations"][0]["designation"] == "EN ISO 12100:2010"

    edges = client.get(f"/v1/documents/{document_id}/edges", params={"jurisdiction": "EU"})
    assert edges.status_code == 200
    assert edges.json()[0]["edge_type"] == "based_on_law"

    validity = client.get(
        f"/v1/documents/{document_id}/validity", params={"jurisdiction": "EU"}
    )
    assert validity.status_code == 200
    assert validity.json()["status"] == "valid"

    export = client.get("/v1/export", params={"jurisdiction": "EU"})
    assert export.status_code == 200
    assert document_id in {d["id"] for d in export.json()["documents"]}

    forbidden = client.get(f"/v1/documents/{document_id}", params={"jurisdiction": "FR"})
    assert forbidden.status_code == 404
```

- [ ] **Step 2: Run the tests**

Run: `cd api && .venv/bin/python -m pytest tests/test_openapi_and_end_to_end.py -v`
Expected: PASS. If a specific assertion fails, trace whether the gap is in this test's
expectations (fix the test) or in a router from an earlier task (fix that task's file, not
this test).

- [ ] **Step 3: Run the entire test suite one final time**

Run: `cd api && .venv/bin/python -m pytest -v -W error`
Expected: every test from Tasks 1-9 passes, pristine output, no warnings.

- [ ] **Step 4: Commit**

```bash
git add api/tests/test_openapi_and_end_to_end.py
git commit -s -m "test: verify OpenAPI completeness and full end-to-end read path"
```

---

## Self-Review

**Spec coverage:**

| Spec-Abschnitt | Task |
|---|---|
| `api/`-Paketstruktur, FastAPI, Apache-2.0-`license_info` | Task 1 |
| Schema-Grenze (Pydantic statt Domain-Dataclasses) | Task 2 |
| `GET /v1/documents` (Suche) | Task 3 |
| `GET /v1/documents/{id}` (Detail, inkl. Quelle/URL) | Task 4 |
| `GET /v1/documents/{id}/edges` | Task 5 |
| `GET /v1/documents/{id}/validity` | Task 6 |
| `GET /v1/export` | Task 7 |
| Fehlerbehandlung (404/400/503/`format`) | Tasks 3-8 (404s per-endpoint, 400/503 centralized in Task 8) |
| „Das eine Tor" (kein zweiter Prüfpfad) | Tasks 3-7, jeweils `get_document_for_jurisdiction`/`list_documents_for_jurisdiction`/`list_edges_for_jurisdiction` vor jeder Anreicherung |
| Testkonzept (echtes Postgres, `/openapi.json`-Prüfung, Rechte-Asymmetrie) | Task 1 (Infrastruktur), Task 9 (OpenAPI + Kapstein-Test), Tasks 3/4/5/7 (Asymmetrie je Endpunkt) |

Keine Lücke gefunden.

**Placeholder-Scan:** Kein „TBD"/„TODO"/„similar to Task N" gefunden. Der einzige bewusst
offengelassene Punkt ist Task 3 Schritt 5/Task 8 Schritt 2 (400-vs-422), explizit als
zwischenzeitlich fehlschlagender, dokumentierter Zustand markiert, nicht als Lücke in der
Spezifikation.

**Typkonsistenz:** Repository-/Domänen-Namen aus `normly_core` (`Document`, `Edge`, `Source`,
`Delivery`, `get_document_for_jurisdiction`, `list_documents_for_jurisdiction`,
`list_edges_for_jurisdiction`, `get_document_unchecked`, `get_delivery`, `get_source`)
stimmen mit ihrer Verwendung über alle Tasks hinweg überein — geprüft gegen die tatsächlichen
Protocol-/Implementierungssignaturen in `core/src/normly_core/graph/domain.py` und
`core/src/normly_core/graph/postgres/repositories.py`. `_document_to_response` (Task 3) wird
unverändert in Task 7 wiederverwendet, keine Signaturabweichung.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-20-backend-api.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
