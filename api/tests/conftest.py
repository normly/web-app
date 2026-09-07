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


class _FakeEmbeddingModel:
    """
    A cheap, deterministic stand-in for the real (multi-hundred-MB)
    EmbeddingModel, used as the `client` fixture's default so ordinary API
    tests don't pay the real model's load cost -- mirrors how
    `enforce_rate_limit` is overridden to a no-op by default in this same
    fixture, for the same reason (tests that aren't ABOUT the real thing
    shouldn't pay for it). Tests that need to embed a query the same way the
    app will (e.g. to pre-compute a matching DocumentEmbedding) request the
    `fake_embedding_model` fixture below directly instead of the real model.
    """

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * 1024
        vector[hash(text) % 1024] = 1.0
        return vector


@pytest.fixture()
def fake_embedding_model() -> _FakeEmbeddingModel:
    return _FakeEmbeddingModel()


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
def client(db_url, monkeypatch, db_session, fake_embedding_model):
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

    get_embedding_model is overridden to the fake_embedding_model fixture by
    default, for the same reason: the real EmbeddingModel is a real,
    multi-hundred-MB model, and the app's own lifespan still loads it once at
    startup (see main.py) regardless of this override -- without this,
    nothing about request handling would be slow, but tests that want to
    exercise the real model still can by popping this override. Using the
    fixture instance (not a fresh _FakeEmbeddingModel()) means a test that
    calls fake_embedding_model.embed_query(...) directly gets the exact same
    vector the running app will compute for the same text.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_api.dependencies import get_embedding_model, get_session
    from normly_api.main import create_app
    from normly_api.rate_limit import enforce_rate_limit

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[enforce_rate_limit] = lambda: None
    app.dependency_overrides[get_embedding_model] = lambda: fake_embedding_model

    with TestClient(app) as test_client:
        yield test_client
