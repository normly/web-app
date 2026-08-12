# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:designation-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="CEN/CENELEC",
        retrieval_path="https://standards.cencenelec.eu",
        legal_basis_category=LegalBasisCategory.B,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_three_national_adoptions_stay_one_node(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    for issuer, designation, language in [
        ("DIN", "DIN EN ISO 9001", "de"),
        ("BSI", "BS EN ISO 9001", "en"),
        ("AFNOR", "NF EN ISO 9001", "fr"),
    ]:
        doc_repo.add_designation(
            document_id=document.id,
            issuer=issuer,
            designation=designation,
            language=language,
            edition=None,
            is_primary=False,
            delivery_id=delivery.id,
        )

    designations = doc_repo.list_designations(document.id)
    assert len(designations) == 3
    assert {d.issuer for d in designations} == {"DIN", "BSI", "AFNOR"}
    assert doc_repo.get_document(document.id).id == document.id


def test_document_titles_are_multilingual(db_session):
    delivery = _make_delivery(db_session, content_hash="sha256:title-fixture")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    doc_repo.add_title(
        document_id=document.id,
        language="en",
        title="Quality management systems — Requirements",
        delivery_id=delivery.id,
    )
    doc_repo.add_title(
        document_id=document.id,
        language="de",
        title="Qualitätsmanagementsysteme — Anforderungen",
        delivery_id=delivery.id,
    )

    titles = doc_repo.list_titles(document.id)
    assert {t.language for t in titles} == {"en", "de"}
