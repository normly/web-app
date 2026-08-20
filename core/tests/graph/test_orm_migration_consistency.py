# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import sqlalchemy as sa

from normly_core.graph.postgres.orm import Base


def _datetime_columns():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.DateTime):
                yield table.name, column.name, column.type


def test_every_orm_datetime_column_is_timezone_aware():
    naive = [
        f"{table}.{column}"
        for table, column, type_ in _datetime_columns()
        if not type_.timezone
    ]
    assert naive == []


def _orm_unique_constraints():
    return {
        constraint.name: (table.name, tuple(column.name for column in constraint.columns))
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def test_deployed_unique_constraints_match_the_orm(migrated_engine):
    """
    Alembic infers nothing from the ORM here: a changed key has to be written
    into the migration and the ORM separately, and the two drift apart in
    silence. This is what notices.
    """
    with migrated_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT tc.constraint_name, tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'public'
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """
            )
        ).all()

    deployed: dict[str, tuple[str, list[str]]] = {}
    for constraint_name, table_name, column_name in rows:
        deployed.setdefault(constraint_name, (table_name, []))[1].append(column_name)

    assert {
        name: (table, tuple(columns)) for name, (table, columns) in deployed.items()
    } == _orm_unique_constraints()


def test_deployed_schema_matches_the_orm_on_timezone_awareness(migrated_engine):
    with migrated_engine.connect() as connection:
        deployed = dict(
            connection.execute(
                sa.text(
                    """
                    SELECT table_name || '.' || column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND data_type LIKE 'timestamp%'
                    """
                )
            ).all()
        )

    expected = {f"{table}.{column}" for table, column, _ in _datetime_columns()}
    assert set(deployed) == expected
    assert set(deployed.values()) == {"timestamp with time zone"}
