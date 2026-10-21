# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

CORE_DIR = Path(__file__).parents[2]


def _has_locale(connection) -> bool:
    return connection.execute(
        sa.text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'account' AND column_name = 'locale'"
        )
    ).scalar_one() == 1


def test_0039_round_trip_gives_existing_accounts_german(db_url, migrated_engine):
    # Same approach as test_no_longer_available_migration.py: drives Alembic
    # against the shared database and leaves it at "head" again.
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    account = uuid.uuid4()
    try:
        command.downgrade(alembic_cfg, "0038")
        with migrated_engine.begin() as connection:
            assert not _has_locale(connection)
            connection.execute(
                sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0039@example.de')"),
                {"a": account},
            )

        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            assert _has_locale(connection)
            assert connection.execute(
                sa.text("SELECT locale FROM account WHERE id = :a"), {"a": account}
            ).scalar_one() == "de"
    finally:
        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})
