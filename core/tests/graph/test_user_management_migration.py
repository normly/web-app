# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

CORE_DIR = Path(__file__).parents[2]


def _alembic(db_url) -> Config:
    cfg = Config(str(CORE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_0041_round_trip_makes_existing_accounts_users(db_url, migrated_engine):
    cfg = _alembic(db_url)
    account = uuid.uuid4()
    try:
        command.downgrade(cfg, "0040")
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0041@example.de')"),
                {"a": account},
            )
        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            row = connection.execute(
                sa.text("SELECT role, publisher_id, blocked_at FROM account WHERE id = :a"),
                {"a": account},
            ).one()
        assert tuple(row) == ("user", None, None)
    finally:
        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})


@pytest.mark.parametrize("statement", [
    # publisher without binding
    "INSERT INTO account (id, email, role) VALUES (gen_random_uuid(), 'x1@example.de', 'publisher')",
    # binding without publisher role
    "INSERT INTO account (id, email, role, publisher_id) VALUES "
    "(gen_random_uuid(), 'x2@example.de', 'user', (SELECT id FROM publisher LIMIT 1))",
    # block time without reason
    "INSERT INTO account (id, email, blocked_at) VALUES (gen_random_uuid(), 'x3@example.de', now())",
    # unknown role
    "INSERT INTO account (id, email, role) VALUES (gen_random_uuid(), 'x4@example.de', 'owner')",
])
def test_account_constraints_reject_inconsistent_rows(db_session, statement):
    db_session.execute(sa.text(
        "INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'Constraint Verlag')"
    ))
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(sa.text(statement))


def test_publisher_names_are_unique_ignoring_case(db_session):
    db_session.execute(sa.text("INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'VDE Verlag')"))
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(
                sa.text("INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'vde verlag')")
            )
