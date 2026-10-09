# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Takedown semantics of the knowledge-base import (ADR-026)."""

import uuid
from types import SimpleNamespace

import sqlalchemy as sa

from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import (
    ChatAnswerType,
    ChatMessageRole,
    EdgeType,
    ImportRecord,
    Layer,
    NotificationTriggerType,
)
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresChatRepository,
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresEmbeddingRepository,
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresSegmentRepository,
    PostgresWatchlistRepository,
)

from .helpers import NOW, make_delivery, make_document, make_source

RECORD = ImportRecord("2026.10.2", 1, "rev", NOW)
LATER = ImportRecord("2026.10.3", 1, "rev", NOW.replace(day=20))
MODEL = "test-model"


def _dump(repository):
    return {
        t: [row for batch in repository.iter_exportable_rows(t) for row in batch]
        for t in KNOWLEDGE_TABLES
    }


def _frozen(dump):
    return {t: (lambda rows=rows: iter([rows])) for t, rows in dump.items()}


def _without_document(dump, document_id):
    """The dump as if `document_id` had been taken down at the source."""
    drop = str(document_id)
    out = {t: list(rows) for t, rows in dump.items()}
    segment_ids = {r["id"] for r in out["segment"] if r["document_id"] == drop}
    work_ids = {r["work_id"] for r in out["document"] if r["id"] == drop}
    out["work"] = [r for r in out["work"] if r["id"] not in work_ids]
    for table in ("document_designation", "document_title"):
        out[table] = [r for r in out[table] if r["document_id"] != drop]
    out["document"] = [r for r in out["document"] if r["id"] != drop]
    out["rights_classification"] = [
        r for r in out["rights_classification"] if r["document_id"] != drop
    ]
    out["segment"] = [r for r in out["segment"] if r["document_id"] != drop]
    out["embedding"] = [r for r in out["embedding"] if r["segment_id"] not in segment_ids]
    out["document_embedding"] = [
        r for r in out["document_embedding"] if r["document_id"] != drop
    ]
    out["edge"] = [
        r for r in out["edge"]
        if drop not in (r["from_document_id"], r["to_document_id"])
    ]
    return out


def _scenario(db_session):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "td")
    keep = make_document(db_session, delivery, "KEEP")
    drop = make_document(db_session, delivery, "DROP")
    segments = PostgresSegmentRepository(db_session)
    embeddings = PostgresEmbeddingRepository(db_session)
    for document in (keep, drop):
        segment, _ = segments.add_segment(
            document_id=document.id, delivery_id=delivery.id, sequence_number=1,
            heading="1", text=f"text {document.id}", language="de",
        )
        embeddings.add_embedding(
            segment_id=segment.id, delivery_id=delivery.id, model_name=MODEL,
            vector=[0.5] * 1024,
        )
        PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
            document_id=document.id, delivery_id=delivery.id, model_name=MODEL,
            vector=[0.25] * 1024,
        )
        if document is drop:
            drop_segment = segment
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=keep.id, to_document_id=drop.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="user@example.org", password_hash="x"
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=drop.work_id
    )
    notification = PostgresNotificationRepository(db_session).create(
        account_id=account.id, work_id=drop.work_id,
        trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge.id, trigger_document_id=drop.id, trigger_jurisdiction="DE",
        may_process=True, may_index_fulltext=True, may_cite_passages=True,
        may_export_free=True, emailed_at=None,
    )
    PostgresNotifiedEdgeRepository(db_session).mark_notified(
        account_id=account.id, work_id=drop.work_id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge.id,
    )
    PostgresRightsNotificationBaselineRepository(db_session).upsert_baseline(
        account_id=account.id, work_id=drop.work_id, trigger_document_id=drop.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True,
    )
    chat = PostgresChatRepository(db_session)
    chat_session = chat.create_session(
        session_token="token-1", jurisdiction="DE", language="de", created_at=NOW,
        account_id=account.id,
    )
    message = chat.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content="answer",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=NOW,
    )
    citation = chat.add_citation(
        message_id=message.id, document_id=drop.id, segment_id=drop_segment.id
    )
    repository = PostgresKnowledgeExchangeRepository(db_session)
    full = _dump(repository)
    return SimpleNamespace(
        repository=repository, delivery=delivery, keep=keep, drop=drop, edge=edge,
        watch=watch, notification=notification, message=message, citation=citation,
        account=account, full=full, without=_without_document(full, drop.id),
    )


def _scalar(db_session, query, **params):
    return db_session.execute(sa.text(query), params).scalar_one()


def _count(db_session, table, where, **params):
    return _scalar(db_session, f"SELECT count(*) FROM {table} WHERE {where}", **params)


def _user_snapshot(db_session):
    queries = {
        "watchlist": "SELECT id::text, account_id::text, work_id::text FROM watchlist",
        "notification": (
            "SELECT id::text, work_id::text, trigger_edge_id::text, "
            "trigger_document_id::text FROM notification"
        ),
        "notified_edge": "SELECT work_id::text, trigger_edge_id::text FROM notified_edge",
        "baseline": (
            "SELECT work_id::text, trigger_document_id::text "
            "FROM rights_notification_baseline"
        ),
        "message": "SELECT id::text FROM chat_message",
    }
    return {
        name: sorted(tuple(r) for r in db_session.execute(sa.text(query)))
        for name, query in queries.items()
    }


_FULL_SNAPSHOT = {
    "work": "SELECT id::text, status, merged_into_work_id::text, retired_at FROM work",
    "document": "SELECT id::text, work_id::text, retired_at FROM document",
    "edge": "SELECT id::text, retired_at FROM edge",
    "delivery": "SELECT id::text, withdrawn_at FROM delivery",
    "segment": "SELECT id::text FROM segment",
    "embedding": "SELECT id::text FROM embedding",
    "document_embedding": "SELECT document_id::text FROM document_embedding",
    "rights": "SELECT document_id::text, delivery_id::text FROM rights_classification",
    "citation": "SELECT id::text, document_id::text, segment_id::text FROM chat_message_citation",
}


def _snapshot(db_session):
    return {
        name: sorted(tuple(r) for r in db_session.execute(sa.text(query)))
        for name, query in _FULL_SNAPSHOT.items()
    }


def test_takedown_deletes_content_and_keeps_identifiers(db_session):
    s = _scenario(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)

    drop = {"d": s.drop.id}
    assert _count(db_session, "segment", "document_id = :d", **drop) == 0
    assert _count(db_session, "document_embedding", "document_id = :d", **drop) == 0
    assert _count(db_session, "rights_classification", "document_id = :d", **drop) == 0
    assert _scalar(db_session, "SELECT count(*) FROM embedding") == 1  # KEEP's only
    assert _count(
        db_session, "document", "id = :d AND retired_at IS NOT NULL", **drop
    ) == 1
    assert _count(
        db_session, "work", "id = :w AND retired_at IS NOT NULL", w=s.drop.work_id
    ) == 1
    assert _count(db_session, "document", "id = :d AND retired_at IS NULL", d=s.keep.id) == 1
    assert _count(
        db_session, "work", "id = :w AND retired_at IS NULL", w=s.keep.work_id
    ) == 1
    assert _count(
        db_session, "edge", "id = :e AND retired_at IS NOT NULL", e=s.edge.id
    ) == 1
    assert _count(db_session, "delivery", "id = :d", d=s.delivery.id) == 1
    assert _count(db_session, "delivery", "id = :d AND withdrawn_at IS NULL", d=s.delivery.id) == 1
    assert _scalar(db_session, "SELECT count(*) FROM source") == 1


def test_takedown_keeps_user_data_and_only_clears_the_citation_segment(db_session):
    s = _scenario(db_session)
    before = _user_snapshot(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)

    assert _user_snapshot(db_session) == before
    assert before["watchlist"] and before["notification"] and before["notified_edge"]
    assert before["baseline"] and before["message"]
    row = db_session.execute(
        sa.text("SELECT document_id, segment_id FROM chat_message_citation WHERE id = :i"),
        {"i": s.citation.id},
    ).one()
    assert row.document_id == s.drop.id
    assert row.segment_id is None


def test_takedown_removes_the_document_from_every_gated_read(db_session):
    s = _scenario(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)
    db_session.expire_all()

    documents = PostgresDocumentRepository(db_session)
    listed = {d.id for d in documents.list_documents_for_jurisdiction("DE")}
    searched = {d.id for d in documents.search_documents_for_jurisdiction("DE")[0]}
    exportable = {d.id for d in documents.list_exportable_documents_for_jurisdiction("DE")}
    exported = {
        row["id"] for batch in s.repository.iter_exportable_rows("document") for row in batch
    }

    assert s.drop.id not in listed | searched | exportable
    assert str(s.drop.id) not in exported
    assert s.keep.id in listed and s.keep.id in searched and s.keep.id in exportable
    assert str(s.keep.id) in exported


def test_returning_document_clears_retired_at_and_restores_content(db_session):
    s = _scenario(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)
    user_before = _user_snapshot(db_session)
    s.repository.replace_knowledge_base(_frozen(s.full), record=LATER)

    assert _count(db_session, "document", "retired_at IS NOT NULL") == 0
    assert _count(db_session, "work", "retired_at IS NOT NULL") == 0
    assert _count(db_session, "edge", "retired_at IS NOT NULL") == 0
    d = {"d": s.drop.id}
    assert _count(db_session, "segment", "document_id = :d", **d) == 1
    assert _count(db_session, "document_embedding", "document_id = :d", **d) == 1
    assert _count(db_session, "rights_classification", "document_id = :d", **d) == 1
    assert _scalar(db_session, "SELECT count(*) FROM embedding") == 2
    assert _user_snapshot(db_session) == user_before
    segment_id = _scalar(
        db_session, "SELECT segment_id FROM chat_message_citation WHERE id = :i",
        i=s.citation.id,
    )
    assert segment_id is None  # the detached reference is never restored


def test_withdrawn_delivery_gets_withdrawn_at(db_session):
    s = _scenario(db_session)
    other_delivery = make_delivery(db_session, make_source(db_session, publisher="Other"), "o")
    other = make_document(db_session, other_delivery, "OTHER")
    full = _dump(s.repository)
    without = _without_document(full, other.id)
    gone = str(other_delivery.id)
    without["delivery"] = [r for r in without["delivery"] if r["id"] != gone]
    without["source"] = [r for r in without["source"] if r["id"] != str(other_delivery.source_id)]

    s.repository.replace_knowledge_base(_frozen(without), record=RECORD)
    stamp = _scalar(db_session, "SELECT withdrawn_at FROM delivery WHERE id = :i", i=other_delivery.id)
    assert stamp is not None
    assert _count(
        db_session, "delivery", "id = :i AND withdrawn_at IS NULL", i=s.delivery.id
    ) == 1
    assert _count(db_session, "source", "id = :i", i=other_delivery.source_id) == 1

    s.repository.replace_knowledge_base(_frozen(without), record=LATER)
    assert _scalar(
        db_session, "SELECT withdrawn_at FROM delivery WHERE id = :i", i=other_delivery.id
    ) == stamp


def test_second_import_changes_nothing(db_session):
    s = _scenario(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)
    first = _snapshot(db_session)
    s.repository.replace_knowledge_base(_frozen(s.without), record=LATER)
    assert _snapshot(db_session) == first
    assert any(row[-1] is not None for row in first["document"])


def test_import_inside_a_savepoint_rolls_back_cleanly(db_session):
    s = _scenario(db_session)
    before = _snapshot(db_session)
    user_before = _user_snapshot(db_session)

    savepoint = db_session.begin_nested()
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)
    assert _snapshot(db_session) != before
    savepoint.rollback()

    assert _snapshot(db_session) == before
    assert _user_snapshot(db_session) == user_before
    assert s.repository.imported_version() is None


def test_natural_key_collision_with_a_purged_row_does_not_block(db_session):
    s = _scenario(db_session)
    old = next(r for r in s.full["segment"] if r["document_id"] == str(s.keep.id))
    replacement = dict(old, id=str(uuid.uuid4()))
    dump = {t: list(rows) for t, rows in s.full.items()}
    dump["segment"] = [r for r in dump["segment"] if r["id"] != old["id"]] + [replacement]
    dump["embedding"] = [r for r in dump["embedding"] if r["segment_id"] != old["id"]]

    s.repository.replace_knowledge_base(_frozen(dump), record=RECORD)

    ids = {
        str(i) for (i,) in db_session.execute(
            sa.text("SELECT id FROM segment WHERE document_id = :d"), {"d": s.keep.id}
        )
    }
    assert ids == {replacement["id"]}


def _live_edge_scenario(db_session):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "le")
    a = make_document(db_session, delivery, "A")
    b = make_document(db_session, delivery, "B")
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=a.id, to_document_id=b.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    repository = PostgresKnowledgeExchangeRepository(db_session)
    full = _dump(repository)
    without = dict(full, edge=[r for r in full["edge"] if r["id"] != str(edge.id)])
    return repository, a, edge, full, without


def _visible_edges(db_session, repository, document):
    edges = PostgresEdgeRepository(db_session)
    return {
        "all": edges.list_edges_for_jurisdiction(document.id, "DE"),
        "free": edges.list_free_layer_edges_for_jurisdiction(document.id, "DE"),
        "exportable": edges.list_exportable_edges_for_jurisdiction(document.id, "DE"),
        "dump": [r for b in repository.iter_exportable_rows("edge") for r in b],
    }


def test_retired_edge_between_live_documents_is_unreadable_until_it_returns(db_session):
    repository, a, edge, full, without = _live_edge_scenario(db_session)
    assert all(_visible_edges(db_session, repository, a).values())

    repository.replace_knowledge_base(_frozen(without), record=RECORD)
    db_session.expire_all()
    assert not any(_visible_edges(db_session, repository, a).values())
    row = db_session.execute(
        sa.text("SELECT retired_at, revoked_at FROM edge WHERE id = :i"), {"i": edge.id}
    ).one()
    assert row.retired_at is not None and row.revoked_at == RECORD.imported_at

    repository.replace_knowledge_base(_frozen(full), record=LATER)
    db_session.expire_all()
    assert all(_visible_edges(db_session, repository, a).values())
    row = db_session.execute(
        sa.text("SELECT retired_at, revoked_at FROM edge WHERE id = :i"), {"i": edge.id}
    ).one()
    assert row.retired_at is None and row.revoked_at is None


def test_redelivery_with_new_ids_does_not_block_on_natural_keys(db_session):
    source = make_source(db_session)
    d1 = make_delivery(db_session, source, "r1")
    d2 = make_delivery(db_session, source, "r2")
    a = make_document(db_session, d1, "A")
    b = make_document(db_session, d1, "B")
    documents = PostgresDocumentRepository(db_session)
    edges = PostgresEdgeRepository(db_session)

    def add_all(delivery):
        documents.add_title(document_id=a.id, language="de", title="Titel", delivery_id=delivery.id)
        documents.add_designation(
            document_id=a.id, issuer="BAuA", designation="A 1", language="de",
            edition="2026", is_primary=True, delivery_id=delivery.id,
        )
        return edges.create_edge(
            from_document_id=a.id, to_document_id=b.id, edge_type=EdgeType.REFERENCES,
            jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
        )

    old_edge = add_all(d1)
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_a = _dump(repository)

    # Producer side, rolled back afterwards: d1 is revoked upstream and the
    # re-delivery d2 recreates edge, title and designation with new ids.
    producer = db_session.begin_nested()
    PostgresDeliveryRepository(db_session).revoke_delivery(d1.id)
    db_session.execute(
        sa.text("UPDATE document SET created_via_delivery_id = :d"), {"d": d2.id}
    )
    from normly_core.graph.postgres.repositories import PostgresRightsRepository
    for document in (a, b):
        PostgresRightsRepository(db_session).classify(
            document_id=document.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=NOW,
            classified_by="Test Reviewer", delivery_id=d2.id,
        )
    new_edge = add_all(d2)
    dump_b = _dump(repository)
    producer.rollback()
    assert new_edge.id != old_edge.id
    assert {r["id"] for r in dump_b["edge"]} == {str(new_edge.id)}

    repository.replace_knowledge_base(_frozen(dump_a), record=RECORD)
    repository.replace_knowledge_base(_frozen(dump_b), record=LATER)

    ids = lambda q: {str(r[0]) for r in db_session.execute(sa.text(q))}  # noqa: E731
    assert str(new_edge.id) in ids("SELECT id FROM edge WHERE retired_at IS NULL AND revoked_at IS NULL")
    assert str(old_edge.id) in ids("SELECT id FROM edge WHERE retired_at IS NOT NULL")
    assert len(ids("SELECT id FROM document_title")) == 1
    assert len(ids("SELECT id FROM document_designation")) == 1


def test_stale_designations_and_titles_of_a_retired_document_are_gone(db_session):
    s = _scenario(db_session)
    documents = PostgresDocumentRepository(db_session)
    documents.add_title(document_id=s.drop.id, language="de", title="T", delivery_id=s.delivery.id)
    documents.add_designation(
        document_id=s.drop.id, issuer="BAuA", designation="D 1", language="de",
        edition="2026", is_primary=True, delivery_id=s.delivery.id,
    )
    full = _dump(s.repository)
    s.repository.replace_knowledge_base(_frozen(_without_document(full, s.drop.id)), record=RECORD)
    for table in ("document_title", "document_designation"):
        assert _count(db_session, table, "document_id = :d", d=s.drop.id) == 0
