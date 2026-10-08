# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
End-to-end coverage for the structural (no-model) path.

Deliberately NOT gated behind NORMLY_TEST_OLLAMA_BASE_URL the way
test_end_to_end.py is: a structural question is answered from the reference
graph alone, without any Ollama call (ADR-008). What it does need is real --
a real api/ subprocess, a real database, and real seeded graph data, so the
edge DIRECTION that api/ actually returns is exercised rather than assumed by
a fake.
"""

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import delete
from sqlalchemy.orm import Session

from normly_core.graph.domain import EdgeType, Layer, LegalBasisCategory
from normly_core.graph.postgres.orm import (
    DeliveryORM,
    DocumentDesignationORM,
    DocumentORM,
    EdgeORM,
    RightsClassificationORM,
    SourceORM,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


@pytest.fixture()
def replaced_standard(migrated_engine):
    """
    Seeds a superseded document and its successor, joined by a REPLACES edge
    pointing FROM the successor TO the superseded one -- the real direction the
    graph stores.

    Committed for real through a standalone Session, because api_process is a
    separate OS process that cannot see the savepoint-scoped db_session (same
    reasoning as test_end_to_end.py's dguv_fixture), and cleaned up afterwards
    in FK-safe order.

    IMPORTANT -- fixture ORDER matters in every test below: this fixture must
    be requested BEFORE structural_client. Answering a chat request inserts a
    chat_message_citation referencing the seeded document, which makes
    Postgres hold a FOR KEY SHARE lock on that document row for as long as
    db_session's (never-committed, rolled-back-at-teardown) transaction is
    open. Deleting the document from this second connection blocks until that
    transaction ends. pytest finalizes fixtures in reverse setup order, so
    requesting this one first is what guarantees db_session has already rolled
    back by the time the deletes below run. The lock_timeout is a backstop: if
    the ordering is ever broken again, teardown fails loudly instead of
    hanging the whole suite forever.
    """
    session = Session(migrated_engine)
    try:
        source = PostgresSourceRepository(session).create_source(
            publisher="DIN", retrieval_path="https://example.de/din-structural-e2e",
            legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
            reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
        )
        delivery = PostgresDeliveryRepository(session).record_delivery(
            source_id=source.id, content_hash="sha256:chat-structural-e2e",
            ingested_at=datetime.now(timezone.utc),
        )
        doc_repo = PostgresDocumentRepository(session)
        superseded = doc_repo.create_document(
            origin_issuer="ISO", origin_number="9001", edition="2008", part=None,
            delivery_id=delivery.id,
        )
        successor = doc_repo.create_document(
            origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
            delivery_id=delivery.id,
        )
        # Only the superseded document carries the DIN designation the chat
        # message names -- the question is asked about the OLD document, which
        # is precisely the case that used to fall back.
        doc_repo.add_designation(
            document_id=superseded.id, issuer="DIN", designation="DIN EN ISO 9001",
            language="de", edition=None, is_primary=True, delivery_id=delivery.id,
        )

        rights_repo = PostgresRightsRepository(session)
        for document in (superseded, successor):
            rights_repo.classify(
                document_id=document.id, jurisdiction="DE", may_process=True,
                may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
                legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
                classified_by="Test", delivery_id=delivery.id,
            )

        edge = PostgresEdgeRepository(session).create_edge(
            from_document_id=successor.id, to_document_id=superseded.id,
            edge_type=EdgeType.REPLACES, jurisdiction="DE", layer=Layer.FREE,
            delivery_id=delivery.id,
        )
        session.commit()

        yield superseded, successor

        session.execute(sa.text("SET LOCAL lock_timeout = '15s'"))
        session.execute(delete(EdgeORM).where(EdgeORM.id == edge.id))
        session.execute(
            delete(DocumentDesignationORM).where(
                DocumentDesignationORM.document_id == superseded.id
            )
        )
        session.execute(
            delete(RightsClassificationORM).where(
                RightsClassificationORM.document_id.in_([superseded.id, successor.id])
            )
        )
        session.execute(
            delete(DocumentORM).where(DocumentORM.id.in_([superseded.id, successor.id]))
        )
        session.execute(delete(DeliveryORM).where(DeliveryORM.id == delivery.id))
        session.execute(delete(SourceORM).where(SourceORM.id == source.id))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def structural_client(db_url, monkeypatch, db_session, api_process):
    """
    Like conftest's e2e_client, but without Ollama: the structural path never
    calls the model, so this fixture runs everywhere. The Ollama and accounts
    base URLs still have to be set for create_app's lifespan, but nothing in
    these tests reaches either service.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    monkeypatch.setenv("NORMLY_API_BASE_URL", api_process)
    monkeypatch.setenv("NORMLY_ACCOUNTS_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("NORMLY_LLM_MODEL", "test-model")
    from fastapi.testclient import TestClient

    from normly_chat.dependencies import get_session
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client


def _ask(client, message):
    response = client.post(
        "/v1/chat",
        json={"jurisdiction": "DE", "language": "de", "message": message},
    )
    assert response.status_code == 200
    return response.json()


def test_a_validity_question_reports_the_replaced_status(replaced_standard, structural_client):
    superseded, _ = replaced_standard
    body = _ask(structural_client, "Ist DIN EN ISO 9001 noch gültig?")

    assert body["answer_type"] == "structural"
    assert "ersetzt" in body["answer"]
    assert [c["document_id"] for c in body["citations"]] == [str(superseded.id)]


def test_a_replacement_question_about_the_superseded_document_is_not_a_fallback(
    replaced_standard, structural_client,
):
    """
    Regression test for the direction bug. A REPLACES edge points FROM the
    successor TO the superseded document, so GET /v1/documents/{superseded}/edges
    -- which lists OUTGOING edges only -- returns [] for exactly the document
    this question names. Answering from the edge listing alone always fell
    back here, even though the same document's validity endpoint (which reads
    incoming edges) knows the successor. Proven through the real router and a
    real api/ process, not a fake.
    """
    superseded, successor = replaced_standard
    body = _ask(structural_client, "Was ersetzt DIN EN ISO 9001?")

    assert body["answer_type"] == "structural"
    assert body["answer_type"] != "fallback"
    # The successor is named in the answer, not merely implied.
    assert str(successor.id) in body["answer"]
    assert [c["document_id"] for c in body["citations"]] == [str(superseded.id)]


def test_an_english_replacement_question_answers_in_english(
    replaced_standard, structural_client,
):
    _, successor = replaced_standard
    response = structural_client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "en",
            "message": "What replaces DIN EN ISO 9001?",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "structural"
    assert body["answer"] == f"DIN EN ISO 9001 has been replaced by: {successor.id}."


def test_an_unknown_designation_falls_back_without_calling_the_model(structural_client):
    body = _ask(structural_client, "Ist DIN EN ISO 99999 noch gültig?")
    assert body["answer_type"] == "fallback"
    assert body["citations"] == []
