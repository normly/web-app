# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

CORE_DIR = Path(__file__).parents[1]

# Docling's own internal pipeline code (docling/pipeline/standard_pdf_pipeline.py)
# reads its own deprecated PipelineOptions.generate_table_images field on every
# convert() call; nothing in normly_core touches this field. pytest applies a
# bare `-W error` command-line flag *after* (and therefore with higher priority
# than) the ini-level `filterwarnings` entry in pyproject.toml, so that entry
# alone cannot suppress this warning when the suite is run with `-W error` --
# only a `filterwarnings` mark, which pytest applies last and therefore wins,
# can. Remove this alongside the matching pyproject.toml entry once docling
# stops triggering the warning internally, or if docling is dropped.
_DOCLING_DEPRECATED_TABLE_IMAGES_FILTER = (
    "ignore:This field is deprecated\\. Use `generate_page_images=True` and call "
    "`TableItem\\.get_image\\(\\)` to extract table images from page images\\."
    ":DeprecationWarning:docling.*"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    marker = pytest.mark.filterwarnings(_DOCLING_DEPRECATED_TABLE_IMAGES_FILTER)
    for item in items:
        item.add_marker(marker)


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
