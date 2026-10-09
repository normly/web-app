# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange import tables
from normly_core.graph.postgres import orm  # noqa: F401  (registers all tables)
from normly_core.graph.postgres.orm import Base


def test_every_orm_table_belongs_to_exactly_one_group():
    groups = [
        set(tables.KNOWLEDGE_TABLES),
        set(tables.USER_TABLES),
        set(tables.PIPELINE_STATE_TABLES),
        set(tables.SYSTEM_TABLES),
    ]
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert a.isdisjoint(b)
    assert set().union(*groups) == set(Base.metadata.tables)


def _foreign_targets(table_name):
    table = Base.metadata.tables[table_name]
    return {fk.column.table.name for column in table.columns for fk in column.foreign_keys}


@pytest.mark.parametrize("group", [tables.KNOWLEDGE_TABLES, tables.USER_TABLES])
def test_group_order_is_foreign_key_safe(group):
    seen = set()
    for name in group:
        in_group_parents = _foreign_targets(name) & set(group) - {name}
        assert in_group_parents <= seen, f"{name} listed before {in_group_parents - seen}"
        seen.add(name)


def test_knowledge_tables_never_reference_user_tables():
    for name in tables.KNOWLEDGE_TABLES:
        assert _foreign_targets(name).isdisjoint(tables.USER_TABLES)


def test_group_tables_lookup():
    assert tables.group_tables("knowledge") == tables.KNOWLEDGE_TABLES
    assert set(tables.group_tables("all")) >= set(tables.USER_TABLES) | {"alembic_version"}
    with pytest.raises(ValueError):
        tables.group_tables("nope")
