# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

CORE_DIR = Path(__file__).parents[2]


def test_downgrade_and_upgrade_round_trip_is_deterministic(db_url, migrated_engine):
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    tables_before = set(inspect(migrated_engine).get_table_names())

    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    tables_after = set(inspect(migrated_engine).get_table_names())
    assert tables_before == tables_after
