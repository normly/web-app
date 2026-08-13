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
        responsible_person="J. Weber",
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
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=both.id, jurisdiction="US", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="freie Lizenz",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
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
        responsible_person="J. Weber",
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
            classified_by="J. Weber", delivery_id=delivery.id,
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
    designations = doc_repo.list_designations(hub.id)
    titles = doc_repo.list_titles(hub.id)

    for rows in (exported, edges, designations, titles):
        assert len(rows) > 1
        assert [row.id for row in rows] == sorted(row.id for row in rows)

    assert [d.id for d in doc_repo.list_documents_for_jurisdiction("DE")] == [
        d.id for d in exported
    ]
