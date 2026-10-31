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

_INSERT = (
    "INSERT INTO account_token (id, account_id, email, purpose, token, expires_at) "
    "VALUES (gen_random_uuid(), :a, :e, :p, :t, now() + interval '1 hour')"
)


def _alembic(db_url) -> Config:
    cfg = Config(str(CORE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _insert(connection, account, email, purpose, token):
    connection.execute(sa.text(_INSERT), {"a": account, "e": email, "p": purpose, "t": token})


def _rejected(engine, account, email, purpose, token) -> bool:
    try:
        with engine.begin() as connection:
            _insert(connection, account, email, purpose, token)
    except IntegrityError:
        return True
    return False


def test_0042_round_trip_binds_the_pending_address_to_email_change_tokens(
    db_url, migrated_engine,
):
    cfg = _alembic(db_url)
    account = uuid.uuid4()
    with migrated_engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0042@example.de')"),
            {"a": account},
        )
    try:
        # At head: an email-change token carries both; other purposes still not.
        with migrated_engine.begin() as connection:
            _insert(connection, account, "pending@example.de", "email_change", "mig42-both")
            _insert(connection, account, None, "email_change", "mig42-legacy")
        assert _rejected(migrated_engine, account, "x@example.de", "magic_link", "mig42-ml")
        assert _rejected(migrated_engine, None, "x@example.de", "email_change", "mig42-noacc")

        command.downgrade(cfg, "0041")
        with migrated_engine.begin() as connection:
            tokens = connection.execute(sa.text(
                "SELECT token FROM account_token WHERE account_id = :a ORDER BY token"
            ), {"a": account}).scalars().all()
        # The both-set token has no shape in the old constraint and is dropped.
        assert tokens == ["mig42-legacy"]
        assert _rejected(migrated_engine, account, "y@example.de", "email_change", "mig42-old")

        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            _insert(connection, account, "again@example.de", "email_change", "mig42-again")
    finally:
        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM account_token WHERE account_id = :a"), {"a": account})
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})


def test_the_orm_mirrors_the_0042_constraint():
    from normly_core.graph.postgres.orm import AccountTokenORM

    [check] = [c for c in AccountTokenORM.__table__.constraints
               if c.name == "ck_account_token_account_or_email"]
    assert "email_change" in str(check.sqltext)
