# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_visible_document(
    db_session, delivery, *, issuer, number, edition, work_id, jurisdiction="DE",
    designation=None,
):
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=number, edition=edition, part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    if designation is not None:
        doc_repo.add_designation(
            document_id=document.id, issuer=issuer, designation=designation, language="de",
            edition=None, is_primary=True, delivery_id=delivery.id,
        )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_returns_none_for_a_document_not_visible_in_jurisdiction(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-invisible")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id, jurisdiction="FR",
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        document.id, "DE",
    )

    assert structure is None


def test_a_document_with_no_work_siblings_has_empty_lists(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-solo")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id, designation="DGUV Vorschrift 1",
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        document.id, "DE",
    )

    assert structure.work_id == work.id
    assert structure.editions == []
    assert structure.national_adoptions == []


def test_edition_chain_spans_multiple_generations_with_correct_status(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-chain")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_2010 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2010",
        work_id=work.id, designation="EN ISO 9001:2010",
    )
    doc_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    doc_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=doc_2015.id, to_document_id=doc_2010.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=doc_2018.id, to_document_id=doc_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(doc_2018.id, "DE")

    assert structure.national_adoptions == []
    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses == {
        doc_2010.id: "replaced", doc_2015.id: "replaced", doc_2018.id: "valid",
    }
    designations = {e.document_id: e.designation for e in structure.editions}
    assert designations[doc_2018.id] == "EN ISO 9001:2018"


def test_withdrawn_by_edge_produces_withdrawn_status(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-withdrawn")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    withdrawn_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id,
    )
    notice_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Bekanntmachung", edition="2020",
        work_id=work.id,
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=notice_doc.id, to_document_id=withdrawn_doc.id,
        edge_type=EdgeType.WITHDRAWN_BY, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(withdrawn_doc.id, "DE")

    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses[withdrawn_doc.id] == "withdrawn"
    assert statuses[notice_doc.id] == "valid"


def test_national_adoptions_are_separated_from_the_edition_chain(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-adoption")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    din_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    bs_2018 = _make_visible_document(
        db_session, delivery, issuer="BS", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="BS EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=din_2018.id, to_document_id=din_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=bs_2018.id, to_document_id=din_2018.id, edge_type=EdgeType.ADOPTED_FROM,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(din_2018.id, "DE")

    edition_ids = {e.document_id for e in structure.editions}
    adoption_ids = {e.document_id for e in structure.national_adoptions}
    assert edition_ids == {din_2015.id, din_2018.id}
    assert adoption_ids == {bs_2018.id}


def test_a_sibling_not_visible_in_the_jurisdiction_is_excluded(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-gated")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    visible_doc = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, jurisdiction="DE",
    )
    hidden_doc = _make_visible_document(
        db_session, delivery, issuer="BS", number="EN ISO 9001", edition="2018",
        work_id=work.id, jurisdiction="FR",
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=hidden_doc.id, to_document_id=visible_doc.id,
        edge_type=EdgeType.ADOPTED_FROM, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = PostgresEdgeRepository(db_session).get_work_structure_for_jurisdiction(
        visible_doc.id, "DE",
    )

    all_ids = {e.document_id for e in structure.editions + structure.national_adoptions}
    assert hidden_doc.id not in all_ids


def test_editions_are_sorted_chronologically_by_edition_not_document_id(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-order")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_2010 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2010",
        work_id=work.id, designation="EN ISO 9001:2010",
    )
    doc_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    doc_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    # Insert edges in an order deliberately different from the expected
    # chronological sort, so ordering by DocumentORM.id (a random UUID)
    # would scramble the result while ordering by edition would not.
    edge_repo.create_edge(
        from_document_id=doc_2018.id, to_document_id=doc_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=doc_2015.id, to_document_id=doc_2010.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(doc_2018.id, "DE")

    assert [e.edition for e in structure.editions] == ["2010", "2015", "2018"]


def test_an_edge_scoped_to_another_jurisdiction_is_ignored(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-jurisdiction-edge")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_2015 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2015",
        work_id=work.id, designation="EN ISO 9001:2015",
    )
    doc_2018 = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    doc_notice = _make_visible_document(
        db_session, delivery, issuer="DIN", number="Bekanntmachung", edition="2020",
        work_id=work.id, designation="Bekanntmachung 2020",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    # Real, always-visible chain edge: 2018 replaces 2015.
    edge_repo.create_edge(
        from_document_id=doc_2018.id, to_document_id=doc_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    # This edge is scoped to FR, but the structure below is queried for DE.
    # If the jurisdiction filter is missing, this WITHDRAWN_BY edge would
    # incorrectly (a) mark doc_2018 as "withdrawn" and (b) union doc_notice
    # into doc_2018's edition partition. Neither must happen for a DE query.
    edge_repo.create_edge(
        from_document_id=doc_notice.id, to_document_id=doc_2018.id,
        edge_type=EdgeType.WITHDRAWN_BY, jurisdiction="FR", layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(doc_2018.id, "DE")

    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses[doc_2018.id] == "valid"
    assert statuses[doc_2015.id] == "replaced"
    edition_ids = {e.document_id for e in structure.editions}
    assert doc_notice.id not in edition_ids


def test_a_document_with_only_an_adopted_from_sibling_has_no_self_referential_editions(
    db_session,
):
    delivery = _make_delivery(db_session, "sha256:work-structure-adopted-only")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_doc = _make_visible_document(
        db_session, delivery, issuer="DIN", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="EN ISO 9001:2018",
    )
    bs_doc = _make_visible_document(
        db_session, delivery, issuer="BS", number="EN ISO 9001", edition="2018",
        work_id=work.id, designation="BS EN ISO 9001:2018",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    # ONLY an ADOPTED_FROM edge -- no REPLACES/WITHDRAWN_BY at all, so
    # din_doc has no edition-chain sibling and must not appear as a
    # self-referential 1-entry `editions` list.
    edge_repo.create_edge(
        from_document_id=bs_doc.id, to_document_id=din_doc.id, edge_type=EdgeType.ADOPTED_FROM,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(din_doc.id, "DE")

    assert structure.editions == []
    adoption_ids = {e.document_id for e in structure.national_adoptions}
    assert adoption_ids == {din_doc.id, bs_doc.id}


def test_a_document_with_both_replaces_and_withdrawn_by_reports_replaced(db_session):
    delivery = _make_delivery(db_session, "sha256:work-structure-both-edges")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    old_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2013",
        work_id=work.id, designation="DGUV Vorschrift 1:2013",
    )
    new_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Vorschrift 1", edition="2020",
        work_id=work.id, designation="DGUV Vorschrift 1:2020",
    )
    notice_doc = _make_visible_document(
        db_session, delivery, issuer="DGUV", number="Bekanntmachung", edition="2021",
        work_id=work.id, designation="Bekanntmachung 2021",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    # old_doc has BOTH an incoming REPLACES edge and an incoming
    # WITHDRAWN_BY edge -- /validity checks replaced_by before withdrawn_by,
    # so status_for() must match that order and report "replaced".
    edge_repo.create_edge(
        from_document_id=new_doc.id, to_document_id=old_doc.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=notice_doc.id, to_document_id=old_doc.id,
        edge_type=EdgeType.WITHDRAWN_BY, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    structure = edge_repo.get_work_structure_for_jurisdiction(old_doc.id, "DE")

    statuses = {e.document_id: e.status for e in structure.editions}
    assert statuses[old_doc.id] == "replaced"
