# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
from pathlib import Path

import pytest
import sqlalchemy as sa

from normly_core.graph.domain import LegalBasisCategory
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


def test_build_adapter_returns_baua_adapter_for_baua_source(db_session):
    adapter = build_adapter("baua", directory=FIXTURE_DIR, session=db_session)
    assert type(adapter).__name__ == "BauaAdapter"


def test_build_adapter_registers_baua_with_category_a(db_session):
    adapter = build_adapter("baua", directory=FIXTURE_DIR, session=db_session)

    registered = db_session.get(SourceORM, adapter.source_id)
    assert registered is not None
    assert registered.publisher == "BAuA"
    assert registered.jurisdiction == "DE"
    assert registered.legal_basis_category == LegalBasisCategory.A


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


def test_main_ingests_a_baua_directory_end_to_end(committed_db, capsys, tmp_path):
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(tmp_path / "baua_trgs_900.pdf"))
    # This geometry is untuned (unlike _write_publication_pdf's empirically-tuned
    # gaps in test_baua_adapter.py) and does not reliably keep designation and
    # title in one Docling item vs. separate ones. That is fine here: this test
    # only asserts raw_designation, which survives either way -- title-extraction
    # reliability is irrelevant to what this test checks.
    for y, line in zip(
        range(800, 700, -20),
        ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."],
    ):
        pdf.drawString(72, y, line)
    pdf.save()

    exit_code = main(["ingest", "baua", "--directory", str(tmp_path)])

    assert exit_code == 0
    assert "failed=0" in capsys.readouterr().out
    with committed_db.connect() as connection:
        designation = connection.execute(
            sa.select(DocumentDesignationORM.designation).where(
                DocumentDesignationORM.issuer == "BAuA"
            )
        ).scalar_one()
    assert designation == "TRGS 900"


def test_main_reuses_the_same_source_row_on_a_second_run(committed_db):
    assert main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)]) == 0
    assert main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)]) == 0

    with committed_db.connect() as connection:
        sources = connection.execute(
            sa.select(SourceORM.id).where(SourceORM.publisher == "DGUV")
        ).scalars().all()
    assert len(sources) == 1


def test_main_fails_hard_on_a_misconfigured_artifacts_path(
    committed_db, monkeypatch, capsys
):
    """A broken model path must not produce a successful-looking run.

    The adapters skip a file they cannot extract and carry on, so that one
    corrupt PDF blocks only itself. A misconfigured
    NORMLY_DOCLING_ARTIFACTS_PATH fails identically for *every* file, and if
    that skip absorbed it the run would print its summary line and return 0
    having ingested nothing -- indistinguishable, unattended, from a healthy
    run. It has to reach main() and end it.
    """
    from normly_core.pipeline import docling_extraction
    from normly_core.pipeline.docling_extraction import PipelineInitializationError

    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(FIXTURE_DIR / "no_models_here"))
    docling_extraction._converters.clear()
    try:
        with pytest.raises(PipelineInitializationError):
            main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)])
    finally:
        docling_extraction._converters.clear()

    # No summary line: main() never got past run_adapter(), so it never
    # committed and never reported anything as processed.
    assert "processed=" not in capsys.readouterr().out


def test_the_process_exits_non_zero_on_a_misconfigured_artifacts_path(db_url, tmp_path):
    """The same failure at the boundary an operator actually sees.

    main() letting the error through is only half the guarantee; what a shell
    script or a scheduler reads is the exit code. Run as a real process, since
    that is the only place `python -m normly_core.pipeline` can be observed.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "normly_core.pipeline", "ingest", "dguv",
         "--directory", str(FIXTURE_DIR)],
        capture_output=True, text=True,
        env={
            **os.environ,
            "NORMLY_DATABASE_URL": db_url,
            "NORMLY_DOCLING_ARTIFACTS_PATH": str(tmp_path / "no_models_here"),
        },
    )

    assert result.returncode != 0
    assert "PipelineInitializationError" in result.stderr
    # The message names what to fix, and no success line was printed.
    assert "no_models_here" in result.stderr
    assert "processed=" not in result.stdout


def test_main_reports_a_missing_database_url(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)

    exit_code = main(["ingest", "dguv", "--directory", str(FIXTURE_DIR)])

    assert exit_code == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err
