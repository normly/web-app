# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
import sqlalchemy as sa

from normly_core.graph.postgres.orm import DocumentDesignationORM, SourceORM
from normly_core.pipeline.cli import build_adapter, main

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"

# Every table the CLI writes into, ordered so the truncate below never fights a
# foreign key. `main()` opens its own engine and commits — unlike the
# transactional `db_session` fixture, nothing rolls its writes back, so the
# fixture that lets it commit has to clean up after itself.
_WRITTEN_TABLES = (
    "embedding",
    "segment",
    "edge",
    "rights_classification",
    "identity_resolution_case",
    "document_title",
    "document_designation",
    "document",
    "delivery",
    "source",
)


@pytest.fixture()
def committed_db(migrated_engine, db_url, monkeypatch):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    try:
        yield migrated_engine
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text(f"TRUNCATE {', '.join(_WRITTEN_TABLES)} CASCADE")
            )


def test_build_adapter_returns_eur_lex_adapter_for_eur_lex_source(db_session):
    adapter = build_adapter("eur-lex", directory=FIXTURE_DIR, session=db_session)
    assert type(adapter).__name__ == "EurLexAdapter"


def test_build_adapter_returns_dguv_adapter_for_dguv_source(db_session):
    adapter = build_adapter("dguv", directory=FIXTURE_DIR, session=db_session)
    assert type(adapter).__name__ == "DguvAdapter"


def test_build_adapter_rejects_unknown_source(db_session):
    with pytest.raises(ValueError, match="unknown source"):
        build_adapter("not-a-real-source", directory=FIXTURE_DIR, session=db_session)


def test_build_adapter_registers_the_source_it_binds_the_adapter_to(db_session):
    adapter = build_adapter("dguv", directory=FIXTURE_DIR, session=db_session)

    registered = db_session.get(SourceORM, adapter.source_id)
    assert registered is not None
    assert registered.publisher == "DGUV"
    assert registered.jurisdiction == "DE"


def test_main_ingests_a_directory_end_to_end(committed_db, capsys):
    exit_code = main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)])

    assert exit_code == 0
    assert "failed=0" in capsys.readouterr().out
    with committed_db.connect() as connection:
        designation = connection.execute(
            sa.select(DocumentDesignationORM.designation).where(
                DocumentDesignationORM.issuer == "DGUV"
            )
        ).scalar_one()
    assert designation == "DGUV Vorschrift 1"


def test_main_reuses_the_same_source_row_on_a_second_run(committed_db):
    assert main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)]) == 0
    assert main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)]) == 0

    with committed_db.connect() as connection:
        sources = connection.execute(
            sa.select(SourceORM.id).where(SourceORM.publisher == "DGUV")
        ).scalars().all()
    assert len(sources) == 1


def test_main_reports_a_missing_database_url(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)

    exit_code = main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)])

    assert exit_code == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err
