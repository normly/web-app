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

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def make_source(
    session, category=LegalBasisCategory.A, commercial=False, publisher="BAuA",
    responsible_person="Test Reviewer",
):
    return PostgresSourceRepository(session).create_source(
        publisher=publisher, retrieval_path="https://example.org",
        legal_basis_category=category, jurisdiction="DE", reviewed_at=date(2026, 1, 1),
        responsible_person=responsible_person, commercial_catalog=commercial,
        contract_reference="V-1" if category == LegalBasisCategory.C else None,
    )


def make_delivery(session, source, tag):
    return PostgresDeliveryRepository(session).record_delivery(
        source_id=source.id, content_hash=f"sha256:{tag}", ingested_at=NOW
    )


def make_document(
    session, delivery, number, *, export=True, process=True, jurisdiction="DE",
    classified_by="Test Reviewer",
):
    document = PostgresDocumentRepository(session).create_document(
        origin_issuer="BAuA", origin_number=number, edition="2026", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=process,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=export,
        legal_basis_reference="§ 5 UrhG", classified_at=NOW, classified_by=classified_by,
        delivery_id=delivery.id,
    )
    return document
