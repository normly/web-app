# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresSourceRepository
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import RecordingEmailSender, SmtpEmailSender
from normly_core.pipeline.adapters.baua import BauaAdapter
from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.document_embedding import backfill_document_embeddings
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.runner import run_adapter
from normly_core.pipeline.sources import resolve_source


def build_adapter(source: str, *, directory: Path, session: Session) -> SourceAdapter:
    """
    Build the adapter for `source`, bound to its registry entry.

    The registry entry is resolved (and registered on first use) before the
    adapter exists at all: without it there is no `Source` row for a delivery to
    descend from, and no legal-basis category behind the ingestion.
    """
    registered = resolve_source(PostgresSourceRepository(session), source)

    if source == "eur-lex":
        return EurLexAdapter(
            directory=directory, source_id=registered.id,
            legislation_reference="2006/42/EC",
        )
    if source == "dguv":
        return DguvAdapter(directory=directory, source_id=registered.id)
    if source == "baua":
        return BauaAdapter(directory=directory, source_id=registered.id)
    raise ValueError(f"unknown source: {source!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("source", choices=["eur-lex", "dguv", "baua"])
    ingest_parser.add_argument(
        "--directory", type=Path, required=True,
        help="local directory containing the source's raw files",
    )

    subparsers.add_parser("backfill-document-embeddings")

    subparsers.add_parser("notify-watchers")

    args = parser.parse_args(argv)

    database_url = os.environ.get("NORMLY_DATABASE_URL")
    if not database_url:
        print("NORMLY_DATABASE_URL environment variable is required", file=sys.stderr)
        return 1

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            if args.command == "ingest":
                adapter = build_adapter(args.source, directory=args.directory, session=session)
                summary = run_adapter(adapter, session)
                session.commit()
                print(
                    f"processed={summary.records_processed} skipped={summary.records_skipped} "
                    f"failed={summary.records_failed} "
                    f"documents_created={summary.documents_created} "
                    f"segments_created={summary.segments_created} "
                    f"embeddings_created={summary.embeddings_created} "
                    f"enqueued_for_review={summary.records_enqueued_for_review}"
                )
            elif args.command == "backfill-document-embeddings":
                created = backfill_document_embeddings(session)
                session.commit()
                print(f"document_embeddings_created={created}")
            elif args.command == "notify-watchers":
                smtp_host = os.environ.get("NORMLY_SMTP_HOST")
                if smtp_host:
                    email_sender = SmtpEmailSender(
                        host=smtp_host,
                        port=int(os.environ.get("NORMLY_SMTP_PORT", "587")),
                        from_address=os.environ.get(
                            "NORMLY_SMTP_FROM", "no-reply@normly.example"
                        ),
                        username=os.environ.get("NORMLY_SMTP_USERNAME"),
                        password=os.environ.get("NORMLY_SMTP_PASSWORD"),
                    )
                else:
                    email_sender = RecordingEmailSender()
                summary = run_notify_watchers(session, email_sender)
                session.commit()
                print(
                    f"watches_scanned={summary.watches_scanned} "
                    f"notifications_created={summary.notifications_created} "
                    f"emails_sent={summary.emails_sent}"
                )
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main())
