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


def test_two_jurisdiction_exports_differ(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:export-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    de_only = doc_repo.create_document(
        origin_issuer="BAuA", origin_number="TRGS 900", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    both = doc_repo.create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    rights_repo.classify(
        document_id=de_only.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="Test Reviewer",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="Test Reviewer",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="US", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="Test Reviewer",
        delivery_id=delivery.id,
    )

    de_export = {d.id for d in doc_repo.list_documents_for_jurisdiction("DE")}
    us_export = {d.id for d in doc_repo.list_documents_for_jurisdiction("US")}

    assert de_export == {de_only.id, both.id}
    assert us_export == {both.id}
    assert de_export != us_export


def test_list_results_are_ordered_deterministically(db_session):
    """
    An export must not depend on whatever order the planner happens to
    return — the same data has to yield the same sequence every time.
    """
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:ordering-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    documents = []
    for number in range(6):
        document = doc_repo.create_document(
            origin_issuer="BAuA", origin_number=f"TRGS {900 + number}", edition="2026",
            part=None, delivery_id=delivery.id,
        )
        rights_repo.classify(
            document_id=document.id, jurisdiction="DE", may_process=True,
            may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="Test Reviewer", delivery_id=delivery.id,
        )
        documents.append(document)

    hub = documents[0]
    for target in documents[1:]:
        edge_repo.create_edge(
            from_document_id=hub.id, to_document_id=target.id,
            edge_type=EdgeType.REFERENCES, jurisdiction=None, layer=Layer.FREE,
            delivery_id=delivery.id,
        )
    for index in range(len(documents) - 1):
        doc_repo.add_designation(
            document_id=hub.id, issuer=f"ISS{index}", designation=f"HUB {index}",
            language="de", edition=None, is_primary=False, delivery_id=delivery.id,
        )
        doc_repo.add_title(
            document_id=hub.id, language=f"l{index}", title=f"Titel {index}",
            delivery_id=delivery.id,
        )

    exported = doc_repo.list_documents_for_jurisdiction("DE")
    edges = edge_repo.list_edges_for_jurisdiction(hub.id, "DE")

    # These two are genuinely ordered by id (see the repository methods) --
    # ascending-id is their real, intended contract, unrelated to how
    # designations/titles are ordered below.
    for rows in (exported, edges):
        assert len(rows) > 1
        assert [row.id for row in rows] == sorted(row.id for row in rows)

    assert [d.id for d in doc_repo.list_documents_for_jurisdiction("DE")] == [
        d.id for d in exported
    ]

    # designations/titles are ordered by the ingesting delivery's
    # ingested_at, not by id (a random uuid4 -- see
    # PostgresDocumentRepository.list_designations/list_titles). All rows in
    # this fixture share one delivery, so their ingested_at values tie and
    # id merely breaks the tie; asserting ascending id here would therefore
    # pass by the same coincidence the ordering fix replaced, not because
    # ascending id is the actual contract. What genuinely holds regardless
    # of that tie is determinism: the same query returns the same sequence
    # every time. The (ingested_at, id) contract itself, exercised where id
    # order and ingested_at order disagree, is locked in by
    # test_designations_and_titles_are_ordered_by_delivery_ingestion_time
    # below.
    designations = doc_repo.list_designations(hub.id)
    titles = doc_repo.list_titles(hub.id)
    for rows in (designations, titles):
        assert len(rows) > 1
    assert [d.id for d in doc_repo.list_designations(hub.id)] == [d.id for d in designations]
    assert [t.id for t in doc_repo.list_titles(hub.id)] == [t.id for t in titles]


def test_designations_and_titles_are_ordered_by_delivery_ingestion_time(db_session):
    """
    list_designations/list_titles order by the ingesting delivery's
    ingested_at, not by the row's own id -- a random uuid4 that carries no
    temporal meaning. Built so id order and ingested_at order disagree: the
    older delivery's rows are added second, after the newer delivery's rows.
    A regression back to `ORDER BY id` would not reliably fail this test
    (uuid4 has no relationship to insertion order either way), but it would
    not reliably pass it either -- unlike the fixture above, this one does
    not let a coincidence stand in for the contract.
    """
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="Test Reviewer",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    older_delivery = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:older-delivery",
        ingested_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    newer_delivery = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:newer-delivery",
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    document = doc_repo.create_document(
        origin_issuer="BAuA", origin_number="TRGS 900", edition="2026", part=None,
        delivery_id=older_delivery.id,
    )

    # Added via the newer delivery FIRST, so an id-based order and an
    # ingested_at-based order would disagree about which comes first.
    newer_designation = doc_repo.add_designation(
        document_id=document.id, issuer="NEW", designation="NEW DESIGNATION",
        language="de", edition=None, is_primary=False, delivery_id=newer_delivery.id,
    )
    older_designation = doc_repo.add_designation(
        document_id=document.id, issuer="OLD", designation="OLD DESIGNATION",
        language="de", edition=None, is_primary=False, delivery_id=older_delivery.id,
    )
    newer_title = doc_repo.add_title(
        document_id=document.id, language="en", title="Newer title",
        delivery_id=newer_delivery.id,
    )
    older_title = doc_repo.add_title(
        document_id=document.id, language="de", title="Older title",
        delivery_id=older_delivery.id,
    )

    designations = doc_repo.list_designations(document.id)
    titles = doc_repo.list_titles(document.id)

    assert [d.id for d in designations] == [older_designation.id, newer_designation.id]
    assert [t.id for t in titles] == [older_title.id, newer_title.id]

    # Same query, called again -- confirms the order is a property of the
    # query itself, not an artifact of one particular execution.
    assert [d.id for d in doc_repo.list_designations(document.id)] == [
        d.id for d in designations
    ]
    assert [t.id for t in doc_repo.list_titles(document.id)] == [t.id for t in titles]
