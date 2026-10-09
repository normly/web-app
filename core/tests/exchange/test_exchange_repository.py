# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date

import pytest
import sqlalchemy as sa

from .helpers import (
    NOW,
    make_delivery as _delivery,
    make_document as _document,
    make_source as _source,
)

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
    PostgresAccountRepository,
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
