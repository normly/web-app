# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

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
        responsible_person="Test Reviewer",
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
    assert doc_repo.get_document_unchecked(document.id).id == document.id


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


def test_add_designation_is_idempotent_by_issuer_designation(db_session):
    delivery = _make_delivery(db_session, content_hash="sha256:idempotent-designation")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    first = doc_repo.add_designation(
        document_id=document.id,
        issuer="DIN",
        designation="DIN EN ISO 9001",
        language="de",
        edition=None,
        is_primary=False,
        delivery_id=delivery.id,
    )

    second = doc_repo.add_designation(
        document_id=document.id,
        issuer="DIN",
        designation="DIN EN ISO 9001",
        language="de",
        edition=None,
        is_primary=False,
        delivery_id=delivery.id,
    )

    assert first.id == second.id
    designations = doc_repo.list_designations(document.id)
    assert len(designations) == 1


def test_same_designation_on_a_second_document_is_rejected_not_silently_merged(db_session):
    """
    A designation identifies exactly one node worldwide. Attaching one that
    already belongs to another document is an identity-resolution error and
    must surface, not silently hand back the other document's row.
    """
    delivery = _make_delivery(db_session, content_hash="sha256:designation-collision")
    doc_repo = PostgresDocumentRepository(db_session)
    first_document = doc_repo.create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    second_document = doc_repo.create_document(
        origin_issuer="ISO", origin_number="14001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    doc_repo.add_designation(
        document_id=first_document.id,
        issuer="DIN",
        designation="DIN EN ISO 9001",
        language="de",
        edition=None,
        is_primary=True,
        delivery_id=delivery.id,
    )

    with pytest.raises(IntegrityError):
        doc_repo.add_designation(
            document_id=second_document.id,
            issuer="DIN",
            designation="DIN EN ISO 9001",
            language="de",
            edition=None,
            is_primary=True,
            delivery_id=delivery.id,
        )

    assert doc_repo.list_designations(second_document.id) == []
    kept = doc_repo.list_designations(first_document.id)
    assert [d.document_id for d in kept] == [first_document.id]


def test_add_title_is_idempotent_by_document_language_title(db_session):
    delivery = _make_delivery(db_session, content_hash="sha256:idempotent-title")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    first = doc_repo.add_title(
        document_id=document.id,
        language="en",
        title="Quality management systems — Requirements",
        delivery_id=delivery.id,
    )

    second = doc_repo.add_title(
        document_id=document.id,
        language="en",
        title="Quality management systems — Requirements",
        delivery_id=delivery.id,
    )

    assert first.id == second.id
    titles = doc_repo.list_titles(document.id)
    assert len(titles) == 1
