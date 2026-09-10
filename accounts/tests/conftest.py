# accounts/tests/conftest.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from normly_core.notifications.email import RecordingEmailSender

ACCOUNTS_DIR = Path(__file__).parents[1]
CORE_DIR = ACCOUNTS_DIR.parent / "core"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as container:
        yield container


@pytest.fixture(scope="session")
def db_url(postgres_container) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def migrated_engine(db_url):
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(migrated_engine):
    connection = migrated_engine.connect()
    transaction = connection.begin()
    nested = connection.begin_nested()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    if nested.is_active:
        nested.rollback()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def email_sender():
    return RecordingEmailSender()


@pytest.fixture()
def client(db_url, monkeypatch, db_session, email_sender):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_accounts.dependencies import get_email_sender, get_session
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def real_client(db_url, monkeypatch, email_sender):
    # Unlike `client`, this does NOT override get_session -- the app builds
    # its own real Session against its own real engine, so get_session()'s
    # own session.commit() at dependency teardown genuinely runs. Use this
    # fixture only for tests that specifically need to prove a write is
    # durable via an independent connection (see test_account_management.py
    # and test_set_password.py for examples) -- everything else should keep
    # using the faster, transactionally-isolated `client` fixture.
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_accounts.dependencies import get_email_sender
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    with TestClient(app) as test_client:
        yield test_client
