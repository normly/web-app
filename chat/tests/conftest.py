# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

CHAT_DIR = Path(__file__).parents[1]
CORE_DIR = CHAT_DIR.parent / "core"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def _wait_for(url: str, timeout: float = 30.0) -> None:
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not become ready within {timeout}s")


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
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    monkeypatch.setenv("NORMLY_API_BASE_URL", "http://localhost:8001")
    monkeypatch.setenv("NORMLY_ACCOUNTS_BASE_URL", "http://localhost:8002")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("NORMLY_LLM_MODEL", "test-model")
    from normly_chat.dependencies import get_session
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def api_process(db_url):
    port = _free_port()
    env = {**os.environ, "NORMLY_DATABASE_URL": db_url}
    proc = subprocess.Popen(
        [str(CHAT_DIR.parent / "api" / ".venv" / "bin" / "uvicorn"),
         "normly_api.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "api"), env=env,
    )
    _wait_for(f"http://localhost:{port}/openapi.json")
    yield f"http://localhost:{port}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def accounts_process(db_url):
    port = _free_port()
    env = {**os.environ, "NORMLY_DATABASE_URL": db_url}
    proc = subprocess.Popen(
        [str(CHAT_DIR.parent / "accounts" / ".venv" / "bin" / "uvicorn"),
         "normly_accounts.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "accounts"), env=env,
    )
    _wait_for(f"http://localhost:{port}/openapi.json")
    yield f"http://localhost:{port}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture()
def e2e_client(db_url, monkeypatch, db_session, api_process, accounts_process):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    monkeypatch.setenv("NORMLY_API_BASE_URL", api_process)
    monkeypatch.setenv("NORMLY_ACCOUNTS_BASE_URL", accounts_process)
    monkeypatch.setenv("NORMLY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", os.environ["NORMLY_TEST_OLLAMA_BASE_URL"])
    monkeypatch.setenv(
        "NORMLY_LLM_MODEL", os.environ.get("NORMLY_TEST_OLLAMA_MODEL", "gemma4:e4b"),
    )
    from normly_chat.dependencies import get_session
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client
