# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import (
    DeliveryORM,
    DocumentORM,
    EmbeddingORM,
    RightsClassificationORM,
    SegmentORM,
    SourceORM,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel

pytestmark = pytest.mark.skipif(
    "NORMLY_TEST_OLLAMA_BASE_URL" not in os.environ,
    reason="requires a running Ollama server; set NORMLY_TEST_OLLAMA_BASE_URL",
)


@pytest.fixture()
def dguv_fixture(migrated_engine):
    # api_process/accounts_process are separate OS subprocesses, each with
    # their own fresh connection to the test database. The savepoint-scoped
    # db_session used elsewhere in this suite is invisible to them no matter
    # how many times it's "committed" -- commit() there only releases the
    # SAVEPOINT within the outer, test-teardown-rolled-back transaction. A
    # standalone Session bound directly to migrated_engine, committed for
    # real, is the only way data seeded here is visible to those subprocesses
    # (same pattern as accounts/tests/test_session_persistence.py). Since
    # this really persists, the fixture is responsible for deleting what it
    # created afterwards, in FK-safe (children-before-parents) order.
    #
    # Every test below requests this fixture BEFORE e2e_client, and must keep
    # doing so: answering a chat request inserts a chat_message_citation
    # referencing this document, so Postgres holds a FOR KEY SHARE lock on the
    # document row until db_session's rolled-back transaction ends. Deleting it
    # from this second connection blocks until then, and pytest finalizes
    # fixtures in reverse setup order -- so requesting this one first is what
    # keeps teardown from hanging.
    session = Session(migrated_engine)
    try:
        source = PostgresSourceRepository(session).create_source(
            publisher="DGUV", retrieval_path="https://example.de/dguv-e2e",
            legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
            reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
        )
        delivery = PostgresDeliveryRepository(session).record_delivery(
            source_id=source.id, content_hash="sha256:chat-e2e", ingested_at=datetime.now(timezone.utc),
        )
        document = PostgresDocumentRepository(session).create_document(
            origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
            delivery_id=delivery.id,
        )
        PostgresRightsRepository(session).classify(
            document_id=document.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="Test", delivery_id=delivery.id,
        )
        segment, _ = PostgresSegmentRepository(session).add_segment(
            document_id=document.id, delivery_id=delivery.id, sequence_number=1, heading=None,
            text="Beim Schweißen ist eine Schutzbrille zu tragen, um die Augen vor "
                 "Funkenflug und ultravioletter Strahlung zu schützen.",
            language="de",
        )
        model = EmbeddingModel()
        PostgresEmbeddingRepository(session).add_embedding(
            segment_id=segment.id, delivery_id=delivery.id, model_name=MODEL_NAME,
            vector=model.embed(segment.text),
        )
        session.commit()

        yield document, segment

        session.execute(delete(EmbeddingORM).where(EmbeddingORM.segment_id == segment.id))
        session.execute(delete(SegmentORM).where(SegmentORM.id == segment.id))
        session.execute(
            delete(RightsClassificationORM).where(
                RightsClassificationORM.document_id == document.id,
                RightsClassificationORM.jurisdiction == "DE",
            )
        )
        session.execute(delete(DocumentORM).where(DocumentORM.id == document.id))
        session.execute(delete(DeliveryORM).where(DeliveryORM.id == delivery.id))
        session.execute(delete(SourceORM).where(SourceORM.id == source.id))
        session.commit()
    finally:
        session.close()


def test_synthesis_question_returns_a_paraphrased_answer_with_citations(
    dguv_fixture, e2e_client,
):
    document, segment = dguv_fixture
    response = e2e_client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "de",
            "message": "Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "synthesis"
    assert len(body["citations"]) > 0
    assert body["citations"][0]["document_id"] == str(document.id)
    # No Ollama call happened for a structural question, and this IS a
    # synthesis question, so the answer must not be a verbatim copy of the
    # source segment -- a real paraphrase check against the real model.
    assert body["answer"] != segment.text


def test_synthesis_question_in_english_answers_in_english_against_german_segments(
    dguv_fixture, e2e_client,
):
    response = e2e_client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "en",
            "message": "What protective equipment is required for welding?",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "synthesis"
    # Cheap heuristic for "this is English, not German": common German
    # function words absent, common English ones present.
    lowered = body["answer"].lower()
    assert " der " not in lowered and " und " not in lowered
    assert len(body["citations"]) > 0


def test_anonymous_requests_are_answered_without_a_session_token(dguv_fixture, e2e_client):
    # Anonymous chats are not stored, so no session continues across requests.
    for message in ("Erste Frage zum Schweißen?", "Zweite Frage zum Schweißen?"):
        response = e2e_client.post(
            "/v1/chat", json={"jurisdiction": "DE", "language": "de", "message": message},
        )
        assert response.status_code == 200
        assert response.json()["session_token"] is None


def test_synthesis_with_no_relevant_segments_returns_a_fallback_without_calling_ollama(
    e2e_client, db_session,
):
    # No DGUV fixture seeded in this test's own (rolled-back) transaction --
    # nothing to retrieve, so the fallback must trigger before any Ollama
    # call, per ADR-008.
    response = e2e_client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "de",
            "message": "Eine völlig unabgedeckte Frage ohne jede Relevanz zu irgendetwas.",
        },
    )
    assert response.status_code == 200
    assert response.json()["answer_type"] == "fallback"


def test_openapi_schema_documents_the_chat_endpoint(e2e_client):
    schema = e2e_client.get("/openapi.json").json()
    assert "/v1/chat" in schema["paths"]
