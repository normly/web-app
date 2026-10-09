# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.orm import DocumentORM
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
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
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


def test_semantic_tier_excludes_a_document_beyond_the_distance_threshold(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-semantic-far")
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 39",
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.0, 1.0] + [0.0] * 1022,
    )

    hits, total = PostgresDocumentRepository(db_session).search_works_for_jurisdiction(
        "DE", q="kein Treffer im Titel",
        query_vector=[1.0] + [0.0] * 1023, embedding_model_name="test-model",
    )

    assert total == 0
    assert hits == []


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


def test_tier1_is_not_truncated_by_the_semantic_candidate_pool(db_session):
    # Regression test: Tier 1 must not share _SEMANTIC_CANDIDATE_POOL (200)
    # with Tier 2's ANN cap -- otherwise `total` undercounts and offsets past
    # 200 silently return nothing, even though 201 documents genuinely match.
    delivery = _make_delivery(db_session, "sha256:work-search-tier1-not-capped")
    match_count = 201
    for n in range(match_count):
        _make_visible_document(
            db_session, delivery, issuer="DGUV", designation=f"DGUV Vorschrift {n}",
        )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction(
        "DE", q="Vorschrift", limit=10, offset=match_count - 1,
    )

    assert total == match_count
    assert len(hits) == 1


def test_semantic_tier_respects_the_issuer_filter(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-tier2-issuer")
    din_document = _make_visible_document(db_session, delivery, issuer="DIN", designation="DIN 4102")
    dguv_document = _make_visible_document(
        db_session, delivery, issuer="DGUV", designation="DGUV Vorschrift 38",
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=din_document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[1.0] + [0.0] * 1023,
    )
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=dguv_document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[1.0] + [0.0] * 1023,
    )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction(
        "DE", issuer="DIN", query_vector=[1.0] + [0.0] * 1023, embedding_model_name="test-model",
    )

    assert total == 1
    assert hits[0].best_match.id == din_document.id


def test_best_match_is_the_most_recently_created_document_in_a_work(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-best-match-recency")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    older_document = _make_visible_document(
        db_session, delivery, issuer="DIN", designation="EN ISO 9001:2008", work_id=work.id,
    )
    newer_document = _make_visible_document(
        db_session, delivery, issuer="DIN", designation="EN ISO 9001:2018", work_id=work.id,
    )
    # DocumentORM.created_at is server_default=sa.func.now(), and Postgres's
    # now() is transaction-scoped -- it returns the SAME value for every
    # statement inside one transaction. db_session (see conftest.py) runs
    # this whole test in a single outer transaction, so two back-to-back
    # create_document() calls (with or without a time.sleep() between them)
    # get an identical created_at here; sleeping would not help. Force one
    # document explicitly older via a direct UPDATE instead, so the ordering
    # under test is real rather than relying on timing Postgres won't honour.
    db_session.execute(
        sa.update(DocumentORM)
        .where(DocumentORM.id == older_document.id)
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction("DE", q="ISO 9001")

    assert total == 1
    assert hits[0].work_id == work.id
    assert hits[0].best_match.id == newer_document.id


def test_other_editions_count_excludes_a_sibling_classified_for_a_different_jurisdiction(db_session):
    delivery = _make_delivery(db_session, "sha256:work-search-edition-count-gate")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    _make_visible_document(
        db_session, delivery, issuer="DIN", designation="EN ISO 9001:2018", work_id=work.id,
    )
    _make_visible_document(
        db_session, delivery, issuer="BS", designation="EN ISO 9001:2018 UK", work_id=work.id,
        jurisdiction="FR",
    )
    doc_repo = PostgresDocumentRepository(db_session)

    hits, total = doc_repo.search_works_for_jurisdiction("DE", q="ISO 9001")

    assert total == 1
    assert hits[0].other_editions_count == 0
