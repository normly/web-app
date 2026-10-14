# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import DocumentORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def test_find_delivery_returns_none_when_absent(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)

    assert delivery_repo.find_delivery(source.id, "sha256:never-seen") is None


def test_find_delivery_returns_existing_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    created = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:find-me", ingested_at=datetime.now(timezone.utc)
    )

    found = delivery_repo.find_delivery(source.id, "sha256:find-me")

    assert found is not None
    assert found.id == created.id


def test_find_by_designation_returns_none_when_absent(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    assert doc_repo.find_by_designation("CEN", "EN 0000:0000") is None


def test_find_by_designation_returns_matching_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:designation-find", ingested_at=datetime.now(timezone.utc)
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")

    assert found is not None
    assert found.id == document.id


def test_find_by_designation_returns_the_newest_edition_when_none_is_specified(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:newest-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    older = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=older.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )
    newer = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2022-06-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=newer.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2022-06-01", is_primary=True, delivery_id=delivery.id,
    )
    # DocumentORM.created_at is server_default=sa.func.now(), and Postgres's
    # now() is transaction-scoped -- it returns the SAME value for every
    # statement inside one transaction. db_session (see conftest.py) runs
    # this whole test in a single outer transaction, so two back-to-back
    # create_document() calls get an identical created_at here; sleeping
    # would not help. Force one document explicitly older via a direct
    # UPDATE instead, matching the established pattern in
    # test_work_search.py::test_best_match_is_the_most_recently_created_document_in_a_work.
    db_session.execute(
        sa.update(DocumentORM)
        .where(DocumentORM.id == older.id)
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()

    found = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1")

    assert found is not None
    assert found.id == newer.id


def test_find_by_designation_with_edition_matches_exactly(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:edition-exact-match",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    older = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=older.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )
    newer = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2022-06-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=newer.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2022-06-01", is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1", edition="2013-11-01")

    assert found is not None
    assert found.id == older.id


def test_find_by_designation_without_edition_still_matches_a_single_edition_designation(
    db_session,
):
    """Regression guard for EUR-Lex/BAuA-style designations, which never set
    an edition at all -- confirms the edition-less lookup path still works
    exactly as it did before this task for the common single-edition case."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:no-edition-regression",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")

    assert found is not None
    assert found.id == document.id


def test_find_by_designation_without_edition_is_deterministic_on_a_created_at_tie(db_session):
    """A genuine created_at tie is plausible in production (e.g. a bulk
    backfill inserting multiple editions inside one transaction, where
    Postgres's transaction-scoped now() gives them byte-identical
    timestamps). Without a secondary sort key, ORDER BY created_at DESC
    gives no guarantee which row comes back, and a different, physically
    arbitrary row could be returned across runs. This asserts the query
    instead reliably returns the same row every time, matching the
    secondary sort key (id desc) -- not a claim about which edition is
    semantically "newer"."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:created-at-tie",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 2", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=first.id, issuer="DGUV", designation="DGUV Vorschrift 2",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 2", edition="2022-06-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=second.id, issuer="DGUV", designation="DGUV Vorschrift 2",
        language="de", edition="2022-06-01", is_primary=True, delivery_id=delivery.id,
    )
    # Force a genuine tie: both documents get the identical created_at,
    # simulating what Postgres's transaction-scoped now() already does to
    # any two documents created within one transaction (see the
    # test_work_search.py precedent referenced elsewhere in this file).
    db_session.execute(
        sa.update(DocumentORM)
        .where(DocumentORM.id.in_([first.id, second.id]))
        .values(created_at=datetime(2024, 3, 1, tzinfo=timezone.utc))
    )
    db_session.flush()
    expected = first if str(first.id) > str(second.id) else second

    found = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 2")

    assert found is not None
    assert found.id == expected.id


def _make_dguv_edition(db_session, delivery_id, *, designation: str, edition: str):
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number=designation, edition=edition,
        part=None, delivery_id=delivery_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation=designation,
        language="de", edition=edition, is_primary=True, delivery_id=delivery_id,
    )
    return document


def test_find_previous_edition_skips_over_a_non_adjacent_edition(db_session):
    """With 2013/2019/2022 all present, before_edition=2022 must return 2019
    (the immediately preceding edition), not 2013 -- proving the lookup
    orders by edition value, not by insertion order or created_at."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:previous-edition-skip",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    edition_2013 = _make_dguv_edition(
        db_session, delivery.id, designation="DGUV Vorschrift 3", edition="2013-11-01"
    )
    edition_2019 = _make_dguv_edition(
        db_session, delivery.id, designation="DGUV Vorschrift 3", edition="2019-01-01"
    )
    _make_dguv_edition(
        db_session, delivery.id, designation="DGUV Vorschrift 3", edition="2022-06-01"
    )

    found = doc_repo.find_previous_edition(
        "DGUV", "DGUV Vorschrift 3", before_edition="2022-06-01"
    )

    assert found is not None
    assert found.id == edition_2019.id
    assert found.id != edition_2013.id


def test_find_previous_edition_returns_none_for_the_oldest_known_edition(db_session):
    """The out-of-order-archive-arrival case: before_edition is the OLDEST
    edition present, so there is no predecessor -- must return None, never
    fall back to some other unrelated document (e.g. a later edition)."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:previous-edition-oldest",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    _make_dguv_edition(
        db_session, delivery.id, designation="DGUV Vorschrift 4", edition="2022-06-01"
    )

    found = doc_repo.find_previous_edition(
        "DGUV", "DGUV Vorschrift 4", before_edition="2013-11-01"
    )

    assert found is None


def test_find_previous_edition_returns_none_when_no_other_edition_exists(db_session):
    doc_repo = PostgresDocumentRepository(db_session)

    found = doc_repo.find_previous_edition(
        "DGUV", "DGUV Vorschrift 5", before_edition="2026-01-01"
    )

    assert found is None
