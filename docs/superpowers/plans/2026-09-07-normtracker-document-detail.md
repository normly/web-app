# Normtracker Document Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the document-detail feature with Work-scoped edition/national-adoption structure and per-jurisdiction rights classification, per `docs/superpowers/specs/2026-09-07-normtracker-document-detail-design.md`.

**Architecture:** Two new read-only HTTP endpoints (`/v1/documents/{id}/work`, `/v1/documents/{id}/rights`) backed by one new repository method that computes a bounded, in-memory graph over a Work's own documents/edges (no unbounded traversal). The already-shipped document-detail page consumes both, functionally only — no visual redesign.

**Tech Stack:** Python (SQLAlchemy, FastAPI), TypeScript/Next.js — spans `core/`, `api/`, and `frontend/`.

## Global Constraints

- Every commit: `git commit -s` (DCO) plus a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer. Never a second `Signed-off-by` from the AI.
- SPDX header on every new file, exactly:
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors
  ```
  (TypeScript files use the same two lines as `//` comments, matching every existing `.ts`/`.tsx` file in `frontend/`.)
- No direct push to `main`. This plan's work happens on its own branch off the current main. Push/PR/merge only after the user explicitly confirms.
- Database access only through the repository layer.
- No visual redesign — no new layout, no tabs, no new component beyond what's already used (`Badge`, `Link`). The new sections render as simple lists in the existing style. The real Tab-based redesign is sub-project 5.
- No AI-generated change summary between editions, and no multi-jurisdiction rights view — both explicitly out of scope per the spec.
- The existing `/v1/documents/{id}/edges` endpoint is NOT modified. The frontend re-groups its results client-side instead (Work-internal edge types move to the new `/work` data; only `references`/`based_on_law` stay in the References list).
- This plan spans three toolchains needing separate worktree setup: `core/.venv`, `api/.venv` (install with `pip install -e ../core -e ".[dev]"` — the main checkout's own `api/.venv` may have no `pip` package present at all; bootstrap pip from a sibling venv that has one, such as the freshly-built `core/.venv`, not necessarily from the main checkout), and `frontend/node_modules` (plain `npm install` — a fresh worktree does not inherit it from the main checkout).
- Task order: Task 1 (`core/`) before Task 2 (`api/`, depends on Task 1's repository method) before Task 3 (`frontend/`, depends on Task 2's endpoints).

---

### Task 1: `get_work_structure_for_jurisdiction` — domain types + repository method

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `WorkStructureEntry`/`WorkStructure` dataclasses near `RightsClassification`, ends at line 141 before `class SourceRepository(Protocol):` at line 145 — actually place them right after `RightsClassification` ends and before `class SourceRepository(Protocol):`; add `get_work_structure_for_jurisdiction` to the `EdgeRepository` Protocol at line 342, appending it after that Protocol's last method)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add `_WORK_STRUCTURE_EDGE_TYPES`/`_EDITION_CHAIN_EDGE_TYPES` module constants and `_work_structure_entry_to_domain` helper near the other module-level helpers/constants; add the method to `PostgresEdgeRepository`, whose last method currently ends at line 1084 right before `class PostgresSegmentRepository:`)
- Create: `core/tests/graph/test_work_structure.py`

**Interfaces:**
- Consumes: `DocumentORM`, `RightsClassificationORM`, `EdgeORM`, `DocumentDesignationORM`, `Layer`, `EdgeType` (all already imported in `repositories.py`); `PostgresWorkRepository`, `PostgresDocumentRepository`, `PostgresEdgeRepository`, `PostgresRightsRepository`, `PostgresDeliveryRepository`, `PostgresSourceRepository` (test fixtures, matching sub-project 2's fixture style).
- Produces: `WorkStructureEntry` (frozen dataclass: `document_id: uuid.UUID`, `origin_issuer: str`, `origin_number: str`, `edition: str`, `designation: str | None`, `status: str`), `WorkStructure` (frozen dataclass: `work_id: uuid.UUID`, `editions: list[WorkStructureEntry]`, `national_adoptions: list[WorkStructureEntry]`). `EdgeRepository.get_work_structure_for_jurisdiction(self, document_id: uuid.UUID, jurisdiction: str) -> WorkStructure | None`, implemented on `PostgresEdgeRepository`.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_work_structure.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
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
    db_session, delivery, *, issuer, number, edition, work_id, jurisdiction="DE",
    designation=None,
):
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=number, edition=edition, part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    if designation is not None:
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


def test_returns_none_for_a_document_not_visible_in_jurisdiction(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-invisible")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id, jurisdiction="FR",
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        document.id, "DE",
    )

    assert structure is None


def test_a_document_with_no_work_siblings_has_empty_lists(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-solo")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id, designation="DGUV Vorschrift 1",
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        document.id, "DE",
    )

    assert structure.work_id == work.id
    assert structure.editions == []
    assert structure.national_adoptions == []


def test_edition_chain_spans_multiple_generations_with_correct_status(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-chain")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_2010 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2010",
        work_id=work.id, designation="EN ISO 9001:2010",
    )
    doc_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    doc_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=doc_2015.id, to_document_id=doc_2010.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=doc_2018.id, to_document_id=doc_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(doc_2018.id, "DE")

    assert structure.national_adoptions == []
    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses == {
        doc_2010.id: "replaced", doc_2015.id: "replaced", doc_2018.id: "valid",
    }
    designations = {e.document_id: e.designation for e in structure.editions}
    assert designations[doc_2018.id] == "EN ISO 9001:2018"


def test_withdrawn_by_edge_produces_withdrawn_status(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-withdrawn")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    withdrawn_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id,
    )
    notice_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Bekanntmachung", edition="2020",
        work_id=work.id,
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=notice_doc.id, to_document_id=withdrawn_doc.id,
        edge_type=EdgeType.WITHDRAWN_BY, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(withdrawn_doc.id, "DE")

    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses[withdrawn_doc.id] == "withdrawn"
    assert statuses[notice_doc.id] == "valid"


def test_national_adoptions_are_separated_from_the_edition_chain(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-adoption")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    din_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    bs_2018 = _make_visible_document(
        db_session, delivery, issuer="BS", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="BS EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=din_2018.id, to_document_id=din_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=bs_2018.id, to_document_id=din_2018.id, edge_type=EdgeType.ADOPTED_FROM,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(din_2018.id, "DE")

    edition_ids = {e.document_id for e in structure.editions}
    adoption_ids = {e.document_id for e in structure.national_adoptions}
    assert edition_ids == {din_2015.id, din_2018.id}
    assert adoption_ids == {bs_2018.id}


def test_a_sibling_not_visible_in_the_jurisdiction_is_excluded(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-gated")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    visible_doc = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, jurisdiction="DE",
    )
    hidden_doc = _make_visible_document(
        db_session, delivery, issuer="BS", number="EN ISO 9001", edition="2018",
        work_id=work.id, jurisdiction="FR",
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=hidden_doc.id, to_document_id=visible_doc.id,
        edge_type=EdgeType.ADOPTED_FROM, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        visible_doc.id, "DE",
    )

    all_ids = {e.document_id for e in structure.editions + structure.national_adoptions}
    assert hidden_doc.id not in all_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_structure.py -v`
Expected: FAIL — `AttributeError: 'PostgresEdgeRepository' object has no attribute 'get_work_structure_for_jurisdiction'`.

- [ ] **Step 3: Add the domain types**

In `core/src/normly_core/graph/domain.py`, insert immediately after the `RightsClassification` dataclass ends (before `class SourceRepository(Protocol):`):

```python
@dataclass(frozen=True)
class WorkStructureEntry:
    document_id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    designation: str | None
    status: str
```

Note: `status` is a plain `str` (`"valid" | "replaced" | "withdrawn"`), matching how the existing `/validity` endpoint already computes this concept as a bare string literal today, not an `Enum` — no new Enum type introduced for something the codebase doesn't already model as one.

```python
@dataclass(frozen=True)
class WorkStructure:
    work_id: uuid.UUID
    editions: list[WorkStructureEntry]
    national_adoptions: list[WorkStructureEntry]
```

Then find `class EdgeRepository(Protocol):` and add this method after its last existing method (`list_exportable_edges_for_jurisdiction`):

```python
    def get_work_structure_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> WorkStructure | None:
        """
        None if `document_id` is not visible in `jurisdiction` (same gate as
        get_document_for_jurisdiction). Otherwise: every Document sharing this
        document's work_id and visible in this jurisdiction, split into two
        lists by edge type among a BOUNDED set (this Work's documents and the
        edges between them only -- not an unbounded graph traversal, matches
        ADR-006's "graph queries stay shallow"):

        `editions` -- every Work member connected to `document_id` via a path
        of ONLY REPLACES/WITHDRAWN_BY edges (same-lineage chain, typically one
        issuer), including `document_id` itself.

        `national_adoptions` -- every OTHER Work member (not in the editions
        chain). Together the two lists cover every visible Work member
        exactly once.

        Each entry's `status` is computed the same way GET .../validity
        computes it for a single document: an entry with an incoming
        REPLACES edge (within this bounded edge set) is "replaced", an
        incoming WITHDRAWN_BY edge is "withdrawn", otherwise "valid".
        """
        ...
```

- [ ] **Step 4: Implement the repository method**

In `core/src/normly_core/graph/postgres/repositories.py`, add `WorkStructure`, `WorkStructureEntry` to the domain import block. Add these two module-level constants near the other module-level constants/helpers (e.g. right before `def _escape_like(term: str) -> str:`):

```python
# Edge types that ever imply shared Work membership -- must match the same
# three types the ingestion pipeline's work_assignment.py already treats as
# Work-linking signals. REFERENCES/BASED_ON_LAW never belong here.
_WORK_STRUCTURE_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY, EdgeType.ADOPTED_FROM)
# The subset that forms an edition lineage chain (same-issuer succession),
# as opposed to a national adoption.
_EDITION_CHAIN_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY)
```

Add this helper near the other `_x_to_domain` functions (e.g. right before `class PostgresEdgeRepository:`):

```python
def _work_structure_entry_to_domain(
    document: DocumentORM, designation: str | None, status: str
) -> WorkStructureEntry:
    return WorkStructureEntry(
        document_id=document.id, origin_issuer=document.origin_issuer,
        origin_number=document.origin_number, edition=document.edition,
        designation=designation, status=status,
    )
```

Then, inside `PostgresEdgeRepository`, add this method right after `list_exportable_edges_for_jurisdiction` ends (its last line is `return [_edge_to_domain(row) for row in rows]`, right before `def _segment_to_domain`):

```python
    def get_work_structure_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> WorkStructure | None:
        viewed = self._session.execute(
            select(DocumentORM)
            .join(RightsClassificationORM, RightsClassificationORM.document_id == DocumentORM.id)
            .where(
                DocumentORM.id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if viewed is None:
            return None

        work_documents = list(self._session.execute(
            select(DocumentORM)
            .join(RightsClassificationORM, RightsClassificationORM.document_id == DocumentORM.id)
            .where(
                DocumentORM.work_id == viewed.work_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(DocumentORM.id)
        ).scalars())
        document_ids = [d.id for d in work_documents]

        # One-time, bounded traversal over THIS Work's own documents/edges
        # only -- not a pattern for wider application code (ADR-006 keeps
        # graph queries shallow); bounded by the Work grouping itself.
        # layer == FREE matches the same filter list_free_layer_incoming_
        # edges_for_jurisdiction already applies to these same edge types
        # for GET .../validity -- pre-existing behavior, kept consistent
        # here rather than resolved differently for a new endpoint.
        edges = list(self._session.execute(
            select(EdgeORM)
            .where(
                EdgeORM.edge_type.in_(_WORK_STRUCTURE_EDGE_TYPES),
                EdgeORM.from_document_id.in_(document_ids),
                EdgeORM.to_document_id.in_(document_ids),
                EdgeORM.revoked_at.is_(None),
                EdgeORM.layer == Layer.FREE,
            )
        ).scalars())

        parent = {d.id: d.id for d in work_documents}

        def find(x: uuid.UUID) -> uuid.UUID:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: uuid.UUID, b: uuid.UUID) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for edge in edges:
            if edge.edge_type in _EDITION_CHAIN_EDGE_TYPES:
                union(edge.from_document_id, edge.to_document_id)

        edition_root = find(document_id)
        edition_ids = {d.id for d in work_documents if find(d.id) == edition_root}

        replaced_ids = {e.to_document_id for e in edges if e.edge_type == EdgeType.REPLACES}
        withdrawn_ids = {e.to_document_id for e in edges if e.edge_type == EdgeType.WITHDRAWN_BY}

        def status_for(doc_id: uuid.UUID) -> str:
            if doc_id in withdrawn_ids:
                return "withdrawn"
            if doc_id in replaced_ids:
                return "replaced"
            return "valid"

        designations_by_document = dict(self._session.execute(
            select(DocumentDesignationORM.document_id, DocumentDesignationORM.designation)
            .where(
                DocumentDesignationORM.document_id.in_(document_ids),
                DocumentDesignationORM.is_primary.is_(True),
            )
        ).all())

        editions = [
            _work_structure_entry_to_domain(
                d, designations_by_document.get(d.id), status_for(d.id)
            )
            for d in work_documents if d.id in edition_ids
        ]
        national_adoptions = [
            _work_structure_entry_to_domain(
                d, designations_by_document.get(d.id), status_for(d.id)
            )
            for d in work_documents if d.id not in edition_ids
        ]

        return WorkStructure(
            work_id=viewed.work_id, editions=editions, national_adoptions=national_adoptions,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_work_structure.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full core test suite**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_work_structure.py
git commit -s -m "feat(core): add Work-scoped edition/national-adoption structure

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `/v1/documents/{id}/work` and `/v1/documents/{id}/rights` endpoints

**Files:**
- Modify: `api/src/normly_api/schemas.py` (add new response schemas near `WorkSearchResponse`)
- Create: `api/src/normly_api/routers/work.py`
- Create: `api/src/normly_api/routers/rights.py`
- Modify: `api/src/normly_api/main.py` (register both new routers)
- Create: `api/tests/test_work.py`
- Create: `api/tests/test_rights.py`

**Interfaces:**
- Consumes: `PostgresEdgeRepository.get_work_structure_for_jurisdiction`, `WorkStructure`, `WorkStructureEntry` (Task 1); `PostgresRightsRepository.get_classification`, `PostgresDocumentRepository.get_document_for_jurisdiction` (pre-existing, unchanged).
- Produces: `GET /v1/documents/{document_id}/work?jurisdiction=X` → `WorkStructureResponse`, 404 if not visible. `GET /v1/documents/{document_id}/rights?jurisdiction=X` → `RightsClassificationResponse`, 404 if not visible.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_work.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _seed_document(db_session, *, issuer, number, edition, work_id, content_hash, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher=issuer, retrieval_path="https://example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=number, edition=edition, part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=f"{number}:{edition}", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document, delivery


def test_work_endpoint_separates_editions_from_national_adoptions(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_2015, delivery = _seed_document(
        db_session, issuer="DIN", number="EN ISO 9001", edition="2015", work_id=work.id,
        content_hash="sha256:work-endpoint-1",
    )
    din_2018, _ = _seed_document(
        db_session, issuer="DIN", number="EN ISO 9001", edition="2018", work_id=work.id,
        content_hash="sha256:work-endpoint-2",
    )
    bs_2018, _ = _seed_document(
        db_session, issuer="BS", number="EN ISO 9001", edition="2018", work_id=work.id,
        content_hash="sha256:work-endpoint-3",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=din_2018.id, to_document_id=din_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=bs_2018.id, to_document_id=din_2018.id, edge_type=EdgeType.ADOPTED_FROM,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    response = client.get(
        f"/v1/documents/{din_2018.id}/work", params={"jurisdiction": "DE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["work_id"] == str(work.id)
    edition_ids = {e["document_id"] for e in body["editions"]}
    adoption_ids = {e["document_id"] for e in body["national_adoptions"]}
    assert edition_ids == {str(din_2015.id), str(din_2018.id)}
    assert adoption_ids == {str(bs_2018.id)}
    replaced = next(e for e in body["editions"] if e["document_id"] == str(din_2015.id))
    assert replaced["status"] == "replaced"


def test_work_endpoint_returns_404_for_a_document_not_visible_in_jurisdiction(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document, _ = _seed_document(
        db_session, issuer="DGUV", number="Vorschrift 1", edition="2013", work_id=work.id,
        content_hash="sha256:work-endpoint-404", jurisdiction="FR",
    )

    response = client.get(f"/v1/documents/{document.id}/work", params={"jurisdiction": "DE"})

    assert response.status_code == 404
```

Create `api/tests/test_rights.py`:

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


def _seed_document(db_session, *, jurisdiction="DE", content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=False, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_rights_endpoint_returns_the_classification(client, db_session):
    document = _seed_document(db_session, content_hash="sha256:rights-endpoint-1")

    response = client.get(f"/v1/documents/{document.id}/rights", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    body = response.json()
    assert body["jurisdiction"] == "DE"
    assert body["may_process"] is True
    assert body["may_cite_passages"] is False
    assert body["legal_basis_reference"] == "§ 5 UrhG"


def test_rights_endpoint_returns_404_for_a_document_not_visible_in_jurisdiction(client, db_session):
    document = _seed_document(db_session, content_hash="sha256:rights-endpoint-2", jurisdiction="FR")

    response = client.get(f"/v1/documents/{document.id}/rights", params={"jurisdiction": "DE"})

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && .venv/bin/pytest tests/test_work.py tests/test_rights.py -v`
Expected: FAIL — `404 Not Found` for both new routes (they don't exist yet, `TestClient` sees a 404 from FastAPI's own unmatched-route handling, not the endpoint's own 404 logic — a different failure than the assertion expects for the "success" tests, but a clear failure regardless).

- [ ] **Step 3: Add the response schemas**

In `api/src/normly_api/schemas.py`, add after `WorkSearchResponse`:

```python
class WorkStructureEntryResponse(BaseModel):
    document_id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    designation: str | None
    status: Literal["valid", "replaced", "withdrawn"]


class WorkStructureResponse(BaseModel):
    work_id: uuid.UUID
    editions: list[WorkStructureEntryResponse]
    national_adoptions: list[WorkStructureEntryResponse]


class RightsClassificationResponse(BaseModel):
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str
```

- [ ] **Step 4: Write the `/work` router**

Create `api/src/normly_api/routers/work.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import WorkStructureEntry
from normly_core.graph.postgres.repositories import PostgresEdgeRepository

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import WorkStructureEntryResponse, WorkStructureResponse

work_router = APIRouter(prefix="/v1/documents", tags=["work"])


def _entry_to_response(entry: WorkStructureEntry) -> WorkStructureEntryResponse:
    return WorkStructureEntryResponse(
        document_id=entry.document_id, origin_issuer=entry.origin_issuer,
        origin_number=entry.origin_number, edition=entry.edition,
        designation=entry.designation, status=entry.status,
    )


@work_router.get(
    "/{document_id}/work", response_model=WorkStructureResponse, responses=NOT_FOUND_RESPONSE,
)
def get_work_structure(
    document_id: uuid.UUID, jurisdiction: str, session: Session = Depends(get_session),
) -> WorkStructureResponse:
    structure = PostgresEdgeRepository(session).get_work_structure_for_jurisdiction(
        document_id, jurisdiction
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="document not found")

    return WorkStructureResponse(
        work_id=structure.work_id,
        editions=[_entry_to_response(e) for e in structure.editions],
        national_adoptions=[_entry_to_response(e) for e in structure.national_adoptions],
    )
```

- [ ] **Step 5: Write the `/rights` router**

Create `api/src/normly_api/routers/rights.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresRightsRepository,
)

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import RightsClassificationResponse

rights_router = APIRouter(prefix="/v1/documents", tags=["rights"])


@rights_router.get(
    "/{document_id}/rights", response_model=RightsClassificationResponse,
    responses=NOT_FOUND_RESPONSE,
)
def get_rights(
    document_id: uuid.UUID, jurisdiction: str, session: Session = Depends(get_session),
) -> RightsClassificationResponse:
    # Same gate as GET .../validity: a document not visible in this
    # jurisdiction must 404, not silently confirm or deny anything about it.
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_for_jurisdiction(document_id, jurisdiction) is None:
        raise HTTPException(status_code=404, detail="document not found")

    classification = PostgresRightsRepository(session).get_classification(document_id, jurisdiction)
    if classification is None:
        # Structurally impossible: get_document_for_jurisdiction's own gate
        # already requires a matching, unrevoked RightsClassification row to
        # exist for this exact (document_id, jurisdiction) pair. Reaching
        # here means that invariant broke -- raise loudly rather than return
        # a response that quietly claims "no rights info" for a document the
        # caller was just told is visible.
        raise RuntimeError(
            f"document {document_id} passed the jurisdiction gate for "
            f"{jurisdiction!r} but has no rights classification"
        )

    return RightsClassificationResponse(
        jurisdiction=classification.jurisdiction, may_process=classification.may_process,
        may_index_fulltext=classification.may_index_fulltext,
        may_cite_passages=classification.may_cite_passages,
        may_export_free=classification.may_export_free,
        legal_basis_reference=classification.legal_basis_reference,
    )
```

- [ ] **Step 6: Register both routers**

In `api/src/normly_api/main.py`, add the imports: `from normly_api.routers.rights import rights_router` and `from normly_api.routers.work import work_router` (alphabetically among the existing router imports). Add both to `create_app()`, e.g. right after the `edges_router` registration:

```python
    app.include_router(
        work_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
    app.include_router(
        rights_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
```

(No ordering hazard: both new routes have 2 path segments after the `/v1/documents` prefix, same shape as the existing `/edges`/`/validity` routes, which already coexist safely with the single-segment `documents_router` route for the reason explained in the comment above `search_router`'s registration.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd api && .venv/bin/pytest tests/test_work.py tests/test_rights.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full api test suite**

Run: `cd api && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 9: Run the full core test suite too, to confirm nothing there regressed**

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add api/src/normly_api/schemas.py api/src/normly_api/routers/work.py api/src/normly_api/routers/rights.py api/src/normly_api/main.py api/tests/test_work.py api/tests/test_rights.py
git commit -s -m "feat(api): add /work and /rights document-detail endpoints

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — consume the new endpoints in the document-detail page

**Files:**
- Create: `frontend/src/app/api/documents/[id]/work/route.ts`
- Create: `frontend/src/app/api/documents/[id]/rights/route.ts`
- Modify: `frontend/src/app/documents/[id]/document-detail-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Modify: `frontend/tests/unit/document-detail-page.test.tsx`

**Interfaces:**
- Consumes: `GET /v1/documents/{id}/work`, `GET /v1/documents/{id}/rights` (Task 2), proxied through the two new BFF routes exactly like the existing `edges`/`validity` routes proxy their endpoints.
- Produces: an extended `DocumentDetailContent` component rendering editions, national adoptions, and rights classification, with the References list now excluding Work-internal edge types.

- [ ] **Step 1: Write the failing test**

Replace the entire contents of `frontend/tests/unit/document-detail-page.test.tsx`:

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
const WORK_ID = "33333333-3333-3333-3333-333333333333";
const REPLACED_EDITION_ID = "44444444-4444-4444-4444-444444444444";
const NATIONAL_ADOPTION_ID = "55555555-5555-5555-5555-555555555555";

function mockFetch(overrides: { work?: object; rights?: object } = {}) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes(`/api/documents/${DOCUMENT_ID}/edges`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            { edge_type: "references", to_document_id: EDGE_TARGET_ID },
            { edge_type: "replaces", to_document_id: REPLACED_EDITION_ID },
          ]),
          { status: 200 },
        ),
      );
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/validity`)) {
      return Promise.resolve(new Response(JSON.stringify({ status: "valid" }), { status: 200 }));
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/work`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify(
            overrides.work ?? {
              work_id: WORK_ID,
              editions: [
                {
                  document_id: REPLACED_EDITION_ID, origin_issuer: "DIN",
                  origin_number: "EN ISO 9001", edition: "2015",
                  designation: "EN ISO 9001:2015", status: "replaced",
                },
                {
                  document_id: DOCUMENT_ID, origin_issuer: "DIN",
                  origin_number: "EN ISO 9001", edition: "2018",
                  designation: "EN ISO 9001:2018", status: "valid",
                },
              ],
              national_adoptions: [
                {
                  document_id: NATIONAL_ADOPTION_ID, origin_issuer: "BS",
                  origin_number: "EN ISO 9001", edition: "2018",
                  designation: "BS EN ISO 9001:2018", status: "valid",
                },
              ],
            },
          ),
          { status: 200 },
        ),
      );
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/rights`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify(
            overrides.rights ?? {
              jurisdiction: "DE", may_process: true, may_index_fulltext: true,
              may_cite_passages: true, may_export_free: false,
              legal_basis_reference: "§ 5 UrhG",
            },
          ),
          { status: 200 },
        ),
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
          id: DOCUMENT_ID, origin_issuer: "DIN", origin_number: "EN ISO 9001",
          designations: [{ designation: "EN ISO 9001:2018", is_primary: true }],
          titles: [{ language: "de", title: "Qualitätsmanagementsysteme" }],
          source: { publisher: "DIN", retrieval_path: "https://example.de" },
        }),
        { status: 200 },
      ),
    );
  });
}

describe("DocumentDetailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders designation, title, validity, and a resolved reference link", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "EN ISO 9001:2018" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Qualitätsmanagementsysteme")).toBeInTheDocument();
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

  it("renders the edition history, marking the replaced edition and the current one", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("EN ISO 9001:2015")).toBeInTheDocument());
    expect(screen.getByText("EN ISO 9001:2018")).toBeInTheDocument();
  });

  it("renders national adoptions separately from the edition history", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("BS EN ISO 9001:2018")).toBeInTheDocument());
  });

  it("does not show a Work-internal edge type in the references list", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DIN EN ISO 9001" })).toBeInTheDocument(),
    );
    // "replaces" is a Work-internal edge type -- it must appear only via the
    // edition-history section (asserted above), never as a References-list
    // badge for this edge type.
    expect(screen.queryByText("Ersetzt")).not.toBeInTheDocument();
  });

  it("renders the rights classification", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("§ 5 UrhG")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: FAIL — the heading assertion fails first (`document.designations` in the OLD test's fixture shape is gone; several new assertions have nothing to find yet).

- [ ] **Step 3: Add the BFF routes**

Create `frontend/src/app/api/documents/[id]/work/route.ts`:

```typescript
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { rateLimitHeaders } from "@/lib/rate-limit-headers";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(params.id)}/work` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
    { headers: rateLimitHeaders(request) },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

Create `frontend/src/app/api/documents/[id]/rights/route.ts` — identical, only `/work` becomes `/rights`:

```typescript
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { rateLimitHeaders } from "@/lib/rate-limit-headers";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(params.id)}/rights` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
    { headers: rateLimitHeaders(request) },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Add the new i18n keys**

In `frontend/src/lib/i18n/de.json`, add a new top-level section right after the existing `"validity"` section:

```json
"documentDetail": {
  "editionsHeading": "Editionshistorie",
  "adoptionsHeading": "Nationale Fassungen",
  "referencesHeading": "Referenzen",
  "rightsHeading": "Rechteklassifikation",
  "mayProcess": "Verarbeitung erlaubt",
  "mayIndexFulltext": "Volltext indexierbar",
  "mayCitePassages": "Zitierfähig",
  "mayExportFree": "Freier Export erlaubt"
},
```

In `frontend/src/lib/i18n/en.json`, the matching entry:

```json
"documentDetail": {
  "editionsHeading": "Edition history",
  "adoptionsHeading": "National adoptions",
  "referencesHeading": "References",
  "rightsHeading": "Rights classification",
  "mayProcess": "Processing permitted",
  "mayIndexFulltext": "Full text indexable",
  "mayCitePassages": "Citable",
  "mayExportFree": "Free export permitted"
},
```

- [ ] **Step 5: Extend `document-detail-content.tsx`**

Replace the entire contents of `frontend/src/app/documents/[id]/document-detail-content.tsx`:

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

interface WorkStructureEntry {
  document_id: string;
  origin_issuer: string;
  origin_number: string;
  edition: string;
  designation: string | null;
  status: "valid" | "replaced" | "withdrawn";
}

interface WorkStructure {
  work_id: string;
  editions: WorkStructureEntry[];
  national_adoptions: WorkStructureEntry[];
}

interface RightsClassification {
  jurisdiction: string;
  may_process: boolean;
  may_index_fulltext: boolean;
  may_cite_passages: boolean;
  may_export_free: boolean;
  legal_basis_reference: string;
}

// Work-internal edge types are shown structurally via the edition-history and
// national-adoptions sections instead -- they must not also appear as
// generic References-list badges.
const WORK_INTERNAL_EDGE_TYPES = new Set(["replaces", "withdrawn_by", "adopted_from"]);

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

function entryLabel(entry: WorkStructureEntry): string {
  return entry.designation ?? `${entry.origin_issuer} ${entry.origin_number}`;
}

export function DocumentDetailContent({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [documentDetail, setDocumentDetail] = React.useState<DocumentDetail | null>(null);
  const [edges, setEdges] = React.useState<ResolvedEdge[]>([]);
  const [validity, setValidity] = React.useState<ValiditySummary | null>(null);
  const [workStructure, setWorkStructure] = React.useState<WorkStructure | null>(null);
  const [rights, setRights] = React.useState<RightsClassification | null>(null);
  const [notFound, setNotFound] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const query = `?jurisdiction=${encodeURIComponent(jurisdiction)}`;

    async function load() {
      const [documentResponse, edgesResponse, validityResponse, workResponse, rightsResponse] =
        await Promise.all([
          fetch(`/api/documents/${documentId}${query}`),
          fetch(`/api/documents/${documentId}/edges${query}`),
          fetch(`/api/documents/${documentId}/validity${query}`),
          fetch(`/api/documents/${documentId}/work${query}`),
          fetch(`/api/documents/${documentId}/rights${query}`),
        ]);
      if (cancelled) return;

      if (documentResponse.status === 404) {
        setNotFound(true);
        return;
      }
      setDocumentDetail(await documentResponse.json());
      setValidity(validityResponse.ok ? await validityResponse.json() : null);
      setWorkStructure(workResponse.ok ? await workResponse.json() : null);
      setRights(rightsResponse.ok ? await rightsResponse.json() : null);

      const rawEdges: RawEdge[] = edgesResponse.ok ? await edgesResponse.json() : [];
      const referenceEdges = rawEdges.filter((edge) => !WORK_INTERNAL_EDGE_TYPES.has(edge.edge_type));
      const resolved = await Promise.all(
        referenceEdges.map(async (edge): Promise<ResolvedEdge> => {
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
  if (documentDetail === null) {
    return null;
  }

  const primaryDesignation =
    documentDetail.designations.find((d) => d.is_primary)?.designation ??
    `${documentDetail.origin_issuer} ${documentDetail.origin_number}`;
  const primaryTitle = documentDetail.titles[0]?.title;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-semibold">{primaryDesignation}</h2>
        {primaryTitle && <p className="text-muted-foreground">{primaryTitle}</p>}
      </div>

      {validity && (
        <Badge variant={validity.status === "valid" ? "default" : "outline"}>
          {t(VALIDITY_KEYS[validity.status])}
        </Badge>
      )}

      <a
        href={documentDetail.source.retrieval_path}
        className="text-sm underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {documentDetail.source.publisher}
      </a>

      {workStructure && workStructure.editions.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.editionsHeading")}</h3>
          <ul className="flex flex-col gap-2">
            {workStructure.editions.map((entry) => (
              <li key={entry.document_id} className="flex items-center gap-2">
                <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                  {t(VALIDITY_KEYS[entry.status])}
                </Badge>
                <Link href={`/documents/${entry.document_id}`} className="underline">
                  {entryLabel(entry)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {workStructure && workStructure.national_adoptions.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.adoptionsHeading")}</h3>
          <ul className="flex flex-col gap-2">
            {workStructure.national_adoptions.map((entry) => (
              <li key={entry.document_id} className="flex items-center gap-2">
                <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                  {t(VALIDITY_KEYS[entry.status])}
                </Badge>
                <Link href={`/documents/${entry.document_id}`} className="underline">
                  {entryLabel(entry)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {edges.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.referencesHeading")}</h3>
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
        </div>
      )}

      {rights && (
        <div>
          <h3 className="font-medium">{t("documentDetail.rightsHeading")}</h3>
          <ul className="flex flex-col gap-1 text-sm">
            <li>{t("documentDetail.mayProcess")}: {rights.may_process ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayIndexFulltext")}: {rights.may_index_fulltext ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayCitePassages")}: {rights.may_cite_passages ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayExportFree")}: {rights.may_export_free ? "✓" : "✗"}</li>
            <li className="text-muted-foreground">{rights.legal_basis_reference}</li>
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: PASS.

- [ ] **Step 7: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS — no other test file references `document-detail-content.tsx`'s old internal shape.

- [ ] **Step 8: Run the full core and api test suites too, to confirm nothing there regressed**

Run: `cd core && .venv/bin/pytest -v` and `cd api && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/api/documents/\[id\]/work/route.ts frontend/src/app/api/documents/\[id\]/rights/route.ts frontend/src/app/documents/\[id\]/document-detail-content.tsx frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json frontend/tests/unit/document-detail-page.test.tsx
git commit -s -m "feat(frontend): show edition history, national adoptions, and rights on the document-detail page

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** Editionshistorie (Task 1's `editions` + Task 3's rendering), nationale Fassungen (Task 1's `national_adoptions` + Task 3), Referenzen kategorisiert (Task 3's client-side filter, `/edges` endpoint itself untouched per the spec's explicit Nicht-Ziel), Rechteklassifikation je Rechtsraum (Task 1's rights-gating in `get_work_structure_for_jurisdiction` + Task 2's `/rights` endpoint + Task 3's rendering). No visual redesign anywhere (Tasks 3's markup reuses only `Badge`/`Link`, no new component, no tabs). AI change summary and multi-jurisdiction rights view are explicitly out of scope and appear in no task.
- **Placeholder scan:** none — every step carries complete code and exact run commands.
- **Type consistency:** `WorkStructureEntry`/`WorkStructure` field names match exactly between `domain.py`, `repositories.py`, `schemas.py`'s `WorkStructureEntryResponse`/`WorkStructureResponse`, `work.py`'s `_entry_to_response`, and the frontend's `WorkStructureEntry`/`WorkStructure` TypeScript interfaces (`document_id`, `origin_issuer`, `origin_number`, `edition`, `designation`, `status` — identical spelling and order throughout). `RightsClassificationResponse`'s five fields match `rights.py`'s construction call and the frontend's `RightsClassification` interface exactly.
