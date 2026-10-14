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


def test_every_knowledge_table_has_exactly_one_import_class():
    classes = [
        set(tables.TOMBSTONE_TABLES),
        set(tables.RETAINED_TABLES),
        set(tables.PURGE_TABLES),
    ]
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            assert a.isdisjoint(b)
    assert set().union(*classes) == set(tables.KNOWLEDGE_TABLES)


def test_purge_tables_keep_knowledge_table_order():
    order = [t for t in tables.KNOWLEDGE_TABLES if t in set(tables.PURGE_TABLES)]
    assert list(tables.PURGE_TABLES) == order


def test_every_foreign_key_from_outside_the_knowledge_base_has_a_rule():
    """
    Fail-closed: a table outside the knowledge base that points into it must
    point at a tombstone/retained table (the row survives a takedown), or be
    listed in DETACHED_REFERENCES (the reference is cleared when the target is
    purged). A new table with a reference but no rule fails this test.
    """
    kept = set(tables.TOMBSTONE_TABLES) | set(tables.RETAINED_TABLES)
    knowledge = set(tables.KNOWLEDGE_TABLES)
    for table in Base.metadata.sorted_tables:
        if table.name in knowledge:
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                target = fk.column.table.name
                if target not in knowledge:
                    continue
                if target in kept:
                    continue
                assert (table.name, column.name) in tables.DETACHED_REFERENCES, (
                    f"{table.name}.{column.name} -> {target} has no import rule"
                )
                assert tables.DETACHED_REFERENCES[(table.name, column.name)] == target
                assert column.nullable, f"{table.name}.{column.name} cannot be cleared"


def test_detached_references_point_at_purge_tables():
    for (child, column), parent in tables.DETACHED_REFERENCES.items():
        assert parent in tables.PURGE_TABLES
        assert column in Base.metadata.tables[child].columns


def test_designations_and_titles_are_purged_not_retained():
    # Re-delivery creates them again with new ids; keeping stale rows would
    # collide on their natural unique keys. No user data references them.
    assert tables.RETAINED_TABLES == ("source", "delivery")
    assert {"document_designation", "document_title"} <= set(tables.PURGE_TABLES)


def test_deletion_log_is_a_user_table_without_foreign_keys():
    assert "deletion_log" in tables.USER_TABLES
    assert _foreign_targets("deletion_log") == set()
