# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange.tables import EXCLUDED_EXCHANGE_COLUMNS
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from normly_core.graph.domain import EdgeType, Layer
from normly_core.graph.postgres.orm import Base
from normly_core.graph.postgres.repositories import PostgresEdgeRepository

from .helpers import make_delivery, make_document, make_source


@pytest.mark.parametrize("table", sorted(EXCLUDED_EXCHANGE_COLUMNS))
def test_retired_at_exists_in_the_orm_but_not_in_the_exchange(db_session, table):
    assert "retired_at" in Base.metadata.tables[table].columns
    repository = PostgresKnowledgeExchangeRepository(db_session)
    assert "retired_at" not in {c.name for c in repository.exchange_columns(table)}


@pytest.mark.parametrize("table", sorted(EXCLUDED_EXCHANGE_COLUMNS))
def test_exported_rows_do_not_carry_retired_at(db_session, table):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "x")
    a = make_document(db_session, delivery, "TRGS 900")
    b = make_document(db_session, delivery, "TRGS 901")
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=a.id, to_document_id=b.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    repository = PostgresKnowledgeExchangeRepository(db_session)
    rows = [row for batch in repository.iter_exportable_rows(table) for row in batch]
    assert rows
    assert all("retired_at" not in row for row in rows)
