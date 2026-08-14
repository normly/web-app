# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import IdentityResolutionStatus, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:identity-case-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_enqueue_and_list_pending_cases(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)

    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="EN ???", raw_issuer="CEN",
        reason="unparseable_designation",
    )

    pending = repo.list_pending_cases()
    assert case.id in {c.id for c in pending}
    assert case.status == IdentityResolutionStatus.PENDING


def test_resolve_case(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="EN 9001:2015", raw_issuer="CEN",
        reason="ambiguous_match",
    )

    resolved = repo.resolve_case(case.id, resolved_document_id=document.id, resolved_by="J. Weber")

    assert resolved.status == IdentityResolutionStatus.RESOLVED
    assert resolved.resolved_document_id == document.id
    assert case.id not in {c.id for c in repo.list_pending_cases()}


def test_reject_case(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_case(
        delivery_id=delivery.id, raw_designation="???", raw_issuer=None,
        reason="unparseable_designation",
    )

    rejected = repo.reject_case(case.id, resolved_by="J. Weber")

    assert rejected.status == IdentityResolutionStatus.REJECTED
    assert case.id not in {c.id for c in repo.list_pending_cases()}
