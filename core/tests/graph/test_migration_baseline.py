# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from sqlalchemy import text


def test_migrated_engine_reaches_alembic_head(migrated_engine):
    with migrated_engine.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        rows = list(result)
    assert len(rows) == 1
