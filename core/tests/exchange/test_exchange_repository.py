# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date

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
    PostgresIdentityResolutionRepository,
    PostgresRightsRepository,
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


_SNAPSHOT_QUERIES = {
    "source": "SELECT id::text FROM source",
    "delivery": "SELECT id::text FROM delivery",
    "document": "SELECT id::text, work_id::text, retired_at FROM document",
    "edge": "SELECT id::text, retired_at FROM edge",
    "segment": "SELECT id::text FROM segment",
    "withdrawn": "SELECT id::text, withdrawn_at FROM delivery",
    "work": "SELECT id::text, status, merged_into_work_id::text, retired_at FROM work",
    "rights": (
        "SELECT document_id::text, jurisdiction, delivery_id::text "
        "FROM rights_classification"
    ),
}


def _snapshot(session):
    return {
        name: sorted(tuple(row) for row in session.execute(sa.text(query)))
        for name, query in _SNAPSHOT_QUERIES.items()
    }


def _ids(snapshot, name):
    return {row[0] for row in snapshot[name]}


def _record():
    return ImportRecord("2026.10.1", 1, "rev", NOW)


def test_replace_is_idempotent_and_retires_missing_rows(db_session):
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

    # remove one document from the dump; the import must retire it
    dump["document"] = [r for r in dump["document"] if r["id"] != str(drop.id)]
    dump["rights_classification"] = [
        r for r in dump["rights_classification"] if r["document_id"] != str(drop.id)
    ]
    frozen = {t: (lambda rows=rows: iter([rows])) for t, rows in dump.items()}

    repository.replace_knowledge_base(frozen, record=_record())
    first = _snapshot(db_session)
    repository.replace_knowledge_base(frozen, record=_record())

    assert _snapshot(db_session) == first
    # identifier row stays as a tombstone, its rights classification is gone
    documents = {row[0]: row for row in first["document"]}
    assert documents[str(drop.id)][2] is not None
    assert documents[str(keep.id)][2] is None
    assert str(drop.id) not in {row[0] for row in first["rights"]}
    assert str(keep.id) in {row[0] for row in first["rights"]}
    assert repository.imported_version().dump_version == "2026.10.1"


def test_user_data_never_blocks_an_import(db_session):
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
    watch_query = sa.text("SELECT id::text, account_id::text, work_id::text FROM watchlist")
    watches = sorted(tuple(r) for r in db_session.execute(watch_query))

    repository.replace_knowledge_base(empty, record=_record())

    assert sorted(tuple(r) for r in db_session.execute(watch_query)) == watches
    snapshot = _snapshot(db_session)
    works = {row[0]: row for row in snapshot["work"]}
    assert works[str(work.id)][3] is not None
    assert repository.imported_version().dump_version == "2026.10.1"


def _dump(repository):
    return {t: _all_rows(repository, t) for t in KNOWLEDGE_TABLES}


def _frozen(dump):
    return {t: (lambda rows=rows: iter([rows])) for t, rows in dump.items()}


def test_work_merge_exports_merged_work_and_reimports_cleanly(db_session):
    source = _source(db_session)
    delivery = _delivery(db_session, source, "m")
    doc_s = _document(db_session, delivery, "S")
    doc_t = _document(db_session, delivery, "T")
    repository = PostgresKnowledgeExchangeRepository(db_session)
    before = _dump(repository)

    identity = PostgresIdentityResolutionRepository(db_session)
    case = identity.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=doc_s.work_id,
        target_work_id=doc_t.work_id, reason="duplicate",
    )
    identity.resolve_work_merge_case(case.id, resolved_by="Test Reviewer")
    after = _dump(repository)

    merged_away = {r["id"]: r for r in after["work"]}[str(doc_s.work_id)]
    assert merged_away["merged_into_work_id"] == str(doc_t.work_id)

    repository.replace_knowledge_base(_frozen(before), record=_record())
    pre_merge = _snapshot(db_session)
    repository.replace_knowledge_base(_frozen(after), record=_record())
    assert _snapshot(db_session) != pre_merge

    # a dump that no longer mentions the merged-away work at all retires it
    # (tombstone); its documents have already moved to the target
    trimmed = dict(after)
    trimmed["work"] = [r for r in after["work"] if r["id"] != str(doc_s.work_id)]
    repository.replace_knowledge_base(_frozen(trimmed), record=_record())
    works = {row[0]: row for row in _snapshot(db_session)["work"]}
    assert works[str(doc_s.work_id)][3] is not None
    assert works[str(doc_t.work_id)][3] is None


def test_classification_switching_delivery_does_not_block_import(db_session):
    source = _source(db_session)
    d1 = _delivery(db_session, source, "d1")
    d2 = _delivery(db_session, source, "d2")
    document = _document(db_session, d2, "A")
    rights = PostgresRightsRepository(db_session)

    def classify(delivery):
        rights.classify(
            document_id=document.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=NOW,
            classified_by="Test Reviewer", delivery_id=delivery.id,
        )

    classify(d1)
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_a = _dump(repository)
    classify(d2)
    PostgresDeliveryRepository(db_session).revoke_delivery(d1.id)
    dump_b = _dump(repository)
    assert str(d1.id) not in {r["id"] for r in dump_b["delivery"]}

    repository.replace_knowledge_base(_frozen(dump_a), record=_record())
    repository.replace_knowledge_base(_frozen(dump_b), record=_record())

    snapshot = _snapshot(db_session)
    # the delivery stays as provenance, marked withdrawn
    withdrawn = {row[0]: row for row in snapshot["withdrawn"]}
    assert withdrawn[str(d1.id)][1] is not None
    assert snapshot["rights"] == [(str(document.id), "DE", str(d2.id))]


def test_unmerge_in_the_dump_does_not_falsely_block_retiring_the_old_target(db_session):
    """
    A kept work X points (merged_into) at work S, which the new dump drops
    while X's pointer moves. S is retired (tombstone) and X's pointer is
    cleared by the upsert; nothing may block.
    """
    source = _source(db_session)
    delivery = _delivery(db_session, source, "u")
    doc_s = _document(db_session, delivery, "S")
    doc_x = _document(db_session, delivery, "X")
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump = _dump(repository)

    db_session.execute(
        sa.text("UPDATE work SET status = 'merged', merged_into_work_id = :s WHERE id = :x"),
        {"s": doc_s.work_id, "x": doc_x.work_id},
    )
    dump["document"] = [r for r in dump["document"] if r["id"] != str(doc_s.id)]
    dump["rights_classification"] = [
        r for r in dump["rights_classification"] if r["document_id"] != str(doc_s.id)
    ]
    dump["work"] = [r for r in dump["work"] if r["id"] != str(doc_s.work_id)]

    repository.replace_knowledge_base(_frozen(dump), record=_record())

    snapshot = _snapshot(db_session)
    works = {row[0]: row for row in snapshot["work"]}
    assert works[str(doc_s.work_id)][3] is not None  # tombstone, not deleted
    assert works[str(doc_x.work_id)][2] is None
    assert works[str(doc_x.work_id)][3] is None
