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
