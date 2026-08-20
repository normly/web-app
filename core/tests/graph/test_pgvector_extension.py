# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from sqlalchemy import text


def test_vector_extension_is_enabled(migrated_engine):
    with migrated_engine.connect() as connection:
        result = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        rows = list(result)
    assert len(rows) == 1
