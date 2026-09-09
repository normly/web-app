# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationPreference,
)
from normly_core.graph.postgres.orm import DocumentDesignationORM, SourceORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresSourceRepository,
    PostgresWatchlistRepository,
)
from normly_core.pipeline.cli import build_adapter, main

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"

# Every table the CLI writes into, ordered so the truncate below never fights a
# foreign key. `main()` opens its own engine and commits — unlike the
# transactional `db_session` fixture, nothing rolls its writes back, so the
# fixture that lets it commit has to clean up after itself.
_WRITTEN_TABLES = (
    "document_embedding",
    "embedding",
    "segment",
    "notification",
    "watchlist",
    "edge",
    "rights_classification",
    "identity_resolution_case",
    "document_title",
    "document_designation",
    "document",
    "delivery",
    "source",
    "account",
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


def test_backfill_document_embeddings_command_creates_embeddings(committed_db, capsys):
    from sqlalchemy.orm import Session

    with Session(committed_db) as session:
        source = PostgresSourceRepository(session).create_source(
            publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
            legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
            reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
        )
        delivery = PostgresDeliveryRepository(session).record_delivery(
            source_id=source.id, content_hash="sha256:cli-backfill",
            ingested_at=datetime.now(timezone.utc),
        )
        doc_repo = PostgresDocumentRepository(session)
        document = doc_repo.create_document(
            origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
            delivery_id=delivery.id,
        )
        doc_repo.add_designation(
            document_id=document.id, issuer="CEN", designation="EN ISO 9001:2018", language="de",
            edition=None, is_primary=True, delivery_id=delivery.id,
        )
        session.commit()

    exit_code = main(["backfill-document-embeddings"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "document_embeddings_created=1" in output


def test_main_notify_watchers_subcommand_runs_without_smtp_configured(committed_db, capsys):
    exit_code = main(["notify-watchers"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "watches_scanned=" in captured.out


def test_main_notify_watchers_without_smtp_configured_does_not_mark_emails_sent(
    committed_db, capsys, monkeypatch
):
    """
    Without NORMLY_SMTP_HOST, the CLI falls back to NullEmailSender, which
    always raises -- caught by detection.py's existing fail-soft try/except,
    so the run must still succeed (exit 0, no crash) but must NOT stamp
    emailed_at, since no email was actually delivered anywhere. Stamping it
    anyway (the old RecordingEmailSender fallback's bug) would silently fill
    the database with notifications falsely marked "delivered."
    """
    monkeypatch.delenv("NORMLY_SMTP_HOST", raising=False)

    from sqlalchemy.orm import Session

    with Session(committed_db) as session:
        source = PostgresSourceRepository(session).create_source(
            publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
            legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
            reviewed_at=date(2026, 1, 1), responsible_person="J. Weber",
        )
        delivery = PostgresDeliveryRepository(session).record_delivery(
            source_id=source.id, content_hash="sha256:cli-null-email",
            ingested_at=datetime.now(timezone.utc),
        )
        doc_repo = PostgresDocumentRepository(session)
        old = doc_repo.create_document(
            origin_issuer="DGUV", origin_number="cli-null-email", edition="2020", part=None,
            delivery_id=delivery.id,
        )
        new = doc_repo.create_document(
            origin_issuer="DGUV", origin_number="cli-null-email", edition="2026", part=None,
            delivery_id=delivery.id, work_id=old.work_id,
        )
        PostgresEdgeRepository(session).create_edge(
            from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
            jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
        )
        account = PostgresAccountRepository(session).create_account(
            email="cli-null-email-watcher@example.de", password_hash=None
        )
        PostgresAccountRepository(session).update_notification_preference(
            account.id, preference=NotificationPreference.EMAIL
        )
        watch = PostgresWatchlistRepository(session).add_watch(
            account_id=account.id, work_id=old.work_id
        )
        # notify-watchers only reports edges created after the watch. The
        # edge above was created in this same transaction, and Postgres's
        # now() is transaction-scoped, so both rows carry an identical
        # created_at -- which the strict "newer than the watch" rule treats
        # as history. Backdate the watch to make the edge unambiguously
        # newer, the ordering a real deployment gets for free.
        session.execute(
            sa.update(WatchlistORM)
            .where(WatchlistORM.id == watch.id)
            .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        )
        session.commit()
        account_id = account.id

    exit_code = main(["notify-watchers"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "notifications_created=1" in captured.out
    assert "emails_sent=0" in captured.out

    with Session(committed_db) as session:
        notifications = PostgresNotificationRepository(session).list_for_account(account_id)
        assert len(notifications) == 1
        assert notifications[0].emailed_at is None
