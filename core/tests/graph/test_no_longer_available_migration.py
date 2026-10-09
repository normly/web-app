# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DataError

CORE_DIR = Path(__file__).parents[2]
_INSERT = (
    "INSERT INTO notification (id, account_id, work_id, trigger_type) "
    "VALUES (:id, :account, :work, 'no_longer_available')"
)


def _length(connection, table):
    return connection.execute(
        sa.text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'trigger_type'"
        ),
        {"t": table},
    ).scalar_one()


def test_0034_round_trip_with_a_no_longer_available_notification(db_url, migrated_engine):
    # Same approach as test_work_backfill_migration.py: drives Alembic against
    # the shared session-scoped database and leaves it at "head" again.
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    account, work = uuid.uuid4(), uuid.uuid4()
    row = {"id": uuid.uuid4(), "account": account, "work": work}
    try:
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0034@example.de')"),
                {"a": account},
            )
            connection.execute(sa.text("INSERT INTO work (id, created_via) VALUES (:w, 'manual')"), {"w": work})
            connection.execute(sa.text(_INSERT), row)

        command.downgrade(alembic_cfg, "0033")
        with migrated_engine.begin() as connection:
            assert connection.execute(
                sa.text("SELECT count(*) FROM notification WHERE id = :id"), row
            ).scalar_one() == 0
            assert _length(connection, "notification") == 17
            assert _length(connection, "notified_edge") == 17
        with pytest.raises(DataError):
            with migrated_engine.begin() as connection:
                connection.execute(sa.text(_INSERT), row)

        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            assert _length(connection, "notification") == 19
            connection.execute(sa.text(_INSERT), row)
    finally:
        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM notification WHERE account_id = :a"), {"a": account})
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})
            connection.execute(sa.text("DELETE FROM work WHERE id = :w"), {"w": work})
