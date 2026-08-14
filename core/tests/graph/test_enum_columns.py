# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer, TdmOptOutResult
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresSourceRepository,
)


def _make_source(db_session, **overrides):
    kwargs = dict(
        publisher="BAuA",
        retrieval_path="https://www.baua.de/technische-regeln",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    kwargs.update(overrides)
    return PostgresSourceRepository(db_session).create_source(**kwargs)


def test_enum_columns_persist_values_not_member_names(db_session):
    """The stored string must be the enum's .value, matching the migration DDL."""
    source = _make_source(
        db_session,
        tdm_opt_out_checked_at=date(2026, 1, 15),
        tdm_opt_out_result=TdmOptOutResult.OPT_OUT_PRESENT,
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:enum-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="BAuA", origin_number="TRGS 900", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="BAuA", origin_number="TRGS 900", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    raw_source = db_session.execute(
        sa.text(
            "SELECT legal_basis_category, tdm_opt_out_result FROM source WHERE id = :id"
        ),
        {"id": source.id},
    ).one()
    raw_edge = db_session.execute(
        sa.text("SELECT edge_type, layer FROM edge WHERE id = :id"), {"id": edge.id}
    ).one()

    assert raw_source.legal_basis_category == LegalBasisCategory.A.value
    assert raw_source.tdm_opt_out_result == TdmOptOutResult.OPT_OUT_PRESENT.value
    assert raw_edge.edge_type == EdgeType.REPLACES.value
    assert raw_edge.layer == Layer.FREE.value

    # ... and the values round-trip back into the domain enums.
    assert PostgresSourceRepository(db_session).get_source(source.id).tdm_opt_out_result is (
        TdmOptOutResult.OPT_OUT_PRESENT
    )


@pytest.mark.parametrize(
    ("table", "column", "enum_cls"),
    [
        ("source", "legal_basis_category", LegalBasisCategory),
        ("source", "tdm_opt_out_result", TdmOptOutResult),
        ("edge", "edge_type", EdgeType),
        ("edge", "layer", Layer),
    ],
)
def test_every_enum_column_has_a_database_check_constraint(
    migrated_engine, table, column, enum_cls
):
    """
    The rights gate must not depend on the application layer alone: every enum
    column carries a CHECK constraint listing exactly its valid values.
    """
    with migrated_engine.connect() as connection:
        clauses = connection.execute(
            sa.text(
                """
                SELECT pg_get_constraintdef(c.oid) AS definition
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = :table AND c.contype = 'c'
                """
            ),
            {"table": table},
        ).scalars().all()

    value_clauses = [
        clause
        for clause in clauses
        if column in clause
        and all(f"'{member.value}'" in clause for member in enum_cls)
    ]
    assert value_clauses, (
        f"{table}.{column} has no CHECK constraint covering "
        f"{[member.value for member in enum_cls]}: {clauses}"
    )


def test_database_rejects_an_unknown_legal_basis_category(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.text(
                """
                INSERT INTO source (
                    id, publisher, retrieval_path, legal_basis_category, jurisdiction,
                    reviewed_at, responsible_person, commercial_catalog
                ) VALUES (
                    gen_random_uuid(), 'X', 'https://example.invalid', 'Z', 'DE',
                    DATE '2026-01-15', 'J. Weber', false
                )
                """
            )
        )
