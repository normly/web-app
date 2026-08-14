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
