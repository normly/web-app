# api/tests/conftest.py
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

API_DIR = Path(__file__).parents[1]
CORE_DIR = API_DIR.parent / "core"


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
def client(db_url, monkeypatch, db_session):
    """
    A TestClient whose requests are served from this test's own db_session
    connection (via a dependency override), so data set up through db_session
    is visible to HTTP calls and everything rolls back together at teardown.

    The app's own lifespan still needs NORMLY_DATABASE_URL set (it creates its
    own, separate engine on startup) even though requests never use that
    engine directly -- the override intercepts get_session before it would.

    enforce_rate_limit is overridden to a no-op by default. It deliberately
    ignores get_session and opens its own committing session (see
    rate_limit.py), so without this override every test in the suite would
    write real, persisted rows into the session-scoped container's
    rate_limit_bucket. Nearly all tests share one TestClient origin and send
    no anon-id, so the whole suite would share a single bucket key inside one
    real-world minute and start 429-ing unrelated tests once it crossed the
    limit. Tests that are *about* rate limiting pop this override to exercise
    the real dependency -- see tests/test_rate_limit.py.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_api.dependencies import get_session
    from normly_api.main import create_app
    from normly_api.rate_limit import enforce_rate_limit

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[enforce_rate_limit] = lambda: None

    with TestClient(app) as test_client:
        yield test_client
