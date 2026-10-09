# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import (
    ContradictoryWorkMergeError,
    IdentityResolutionCaseType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    WorkCreatedVia,
    WorkStatus,
)
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash="sha256:work-merge-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_enqueue_work_merge_case(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    source_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    target_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    repo = PostgresIdentityResolutionRepository(db_session)

    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=source_work.id, target_work_id=target_work.id,
        reason="curator_identified_duplicate",
    )

    assert case.case_type == IdentityResolutionCaseType.WORK_MERGE
    assert case.source_work_id == source_work.id
    assert case.target_work_id == target_work.id
    assert case.raw_designation is None
    assert case in repo.list_pending_cases()


def test_resolve_work_merge_case_reassigns_documents_and_retires_source(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    source_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    target_work = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_doc = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=source_work.id,
    )
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=source_work.id, target_work_id=target_work.id,
        reason="curator_identified_duplicate",
    )

    resolved = repo.resolve_work_merge_case(case.id, resolved_by="Test Reviewer")

    assert resolved.status == IdentityResolutionStatus.RESOLVED
    moved_doc = doc_repo.get_document_unchecked(din_doc.id)
    assert moved_doc.work_id == target_work.id
    merged_source = work_repo.get_work(source_work.id)
    assert merged_source.id == target_work.id  # get_work redirects transparently
    assert case not in repo.list_pending_cases()


def test_resolve_work_merge_case_rejects_self_merge(db_session):
    delivery = _make_delivery(db_session)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    repo = PostgresIdentityResolutionRepository(db_session)
    case = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=work.id, target_work_id=work.id,
        reason="bad_case",
    )

    with pytest.raises(ContradictoryWorkMergeError):
        repo.resolve_work_merge_case(case.id, resolved_by="Test Reviewer")


def test_resolve_work_merge_case_rejects_an_already_merged_target(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)
    a = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    b = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    c = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    first_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=a.id, target_work_id=b.id, reason="merge-a-into-b",
    )
    repo.resolve_work_merge_case(first_merge.id, resolved_by="Test Reviewer")
    second_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=c.id, target_work_id=a.id, reason="merge-c-into-a",
    )

    with pytest.raises(ContradictoryWorkMergeError):
        repo.resolve_work_merge_case(second_merge.id, resolved_by="Test Reviewer")


def test_a_second_merge_re_points_earlier_merges_to_keep_one_hop(db_session):
    delivery = _make_delivery(db_session)
    work_repo = PostgresWorkRepository(db_session)
    repo = PostgresIdentityResolutionRepository(db_session)
    a = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    b = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    c = work_repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)

    first_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=a.id, target_work_id=b.id, reason="merge-a-into-b",
    )
    repo.resolve_work_merge_case(first_merge.id, resolved_by="Test Reviewer")

    second_merge = repo.enqueue_work_merge_case(
        delivery_id=delivery.id, source_work_id=b.id, target_work_id=c.id, reason="merge-b-into-c",
    )
    repo.resolve_work_merge_case(second_merge.id, resolved_by="Test Reviewer")

    # A originally redirected to B, but B has since been merged into C -- A
    # must now redirect all the way to C, the live Work, not to the retired B.
    assert work_repo.get_work(a.id).id == c.id
