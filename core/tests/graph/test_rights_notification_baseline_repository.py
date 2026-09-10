# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.orm import RightsNotificationBaselineORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def _make_delivery(db_session, content_hash="sha256:baseline-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_document(db_session, delivery_id):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number="TST-BASE", edition="2026", part=None,
        delivery_id=delivery_id,
    )


def test_get_baseline_returns_none_when_absent(db_session):
    account = _make_account(db_session, "baseline-absent@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:baseline-absent-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresRightsNotificationBaselineRepository(db_session)

    assert repo.get_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    ) is None


def test_upsert_baseline_creates_on_first_call(db_session):
    account = _make_account(db_session, "baseline-create@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:baseline-create-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresRightsNotificationBaselineRepository(db_session)

    created = repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )
    assert created.account_id == account.id
    assert created.work_id == work.id
    assert created.trigger_document_id == document.id
    assert created.trigger_jurisdiction == "DE"
    assert created.may_process is True
    assert created.may_export_free is False

    found = repo.get_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    assert found is not None
    assert found.may_process is True
    assert found.may_export_free is False


def test_upsert_baseline_updates_in_place_on_a_second_call(db_session):
    account = _make_account(db_session, "baseline-update@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:baseline-update-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresRightsNotificationBaselineRepository(db_session)

    repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )
    repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=False, may_index_fulltext=False,
        may_cite_passages=True, may_export_free=True,
    )

    found = repo.get_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    assert found is not None
    assert found.may_process is False
    assert found.may_index_fulltext is False
    assert found.may_cite_passages is True
    assert found.may_export_free is True

    # It's still a single row for this key tuple, not a second one.
    same_key_via_get = repo.get_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    assert same_key_via_get.may_process is False


def test_upsert_baseline_updates_updated_at_on_a_second_upsert(db_session):
    account = _make_account(db_session, "baseline-updated-at@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:baseline-updated-at-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresRightsNotificationBaselineRepository(db_session)

    repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )

    # Postgres's now() is transaction-scoped -- force the first row's
    # updated_at to an explicit, unambiguous OLDER value so a second upsert
    # in this same test transaction produces a genuinely different value,
    # not a coincidentally-identical one. Same idiom as
    # test_detection.py's _set_created_at, adapted for this table's
    # composite primary key.
    old = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.execute(
        sa.update(RightsNotificationBaselineORM)
        .where(
            RightsNotificationBaselineORM.account_id == account.id,
            RightsNotificationBaselineORM.work_id == work.id,
            RightsNotificationBaselineORM.trigger_document_id == document.id,
            RightsNotificationBaselineORM.trigger_jurisdiction == "DE",
        )
        .values(updated_at=old)
    )
    db_session.flush()

    second = repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=False, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )

    assert second.updated_at > old
