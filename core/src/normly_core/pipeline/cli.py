# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresNotificationRepository,
    PostgresSourceRepository,
)
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import NullEmailSender, SmtpEmailSender
from normly_core.pipeline.adapters.baua import BauaAdapter
from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.document_embedding import backfill_document_embeddings
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.runner import run_adapter
from normly_core.pipeline.sources import resolve_source


# Arbitrary but stable key for the Postgres session-level advisory lock that
# serialises notify-watchers runs. The whole job runs in one transaction and
# commits only at the end, while emails are sent during the loop -- so two
# overlapping runs (a stuck one plus a fresh cron trigger) could deliver mail
# whose Notification rows are then rolled back, and mail it all again on the
# next run. The lock lives here rather than in detection.py: it is an
# operational concurrency concern, and run_notify_watchers stays a pure,
# lock-agnostic function.
_NOTIFY_WATCHERS_LOCK_KEY = 8234701

# Starting point, not a carefully-derived number -- revisit once real usage
# data exists. Only read notifications are ever eligible for cleanup; unread
# ones are kept regardless of age (see delete_read_before).
_NOTIFICATION_RETENTION_DAYS = 60


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

    subparsers.add_parser("cleanup-notifications")

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
            elif args.command == "cleanup-notifications":
                cutoff = datetime.now(timezone.utc) - timedelta(days=_NOTIFICATION_RETENTION_DAYS)
                deleted = PostgresNotificationRepository(session).delete_read_before(cutoff)
                session.commit()
                print(f"notifications_deleted={deleted}")
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
                    email_sender = NullEmailSender()
                acquired = session.execute(
                    sa.text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": _NOTIFY_WATCHERS_LOCK_KEY},
                ).scalar()
                if not acquired:
                    # An expected, non-error condition: the previous run is
                    # still going, and it will cover everything this one
                    # would have. Exit 0 so a scheduler does not alert.
                    print("notify-watchers: another run is already in progress, exiting")
                    return 0
                try:
                    summary = run_notify_watchers(session, email_sender)
                finally:
                    session.execute(
                        sa.text("SELECT pg_advisory_unlock(:key)"),
                        {"key": _NOTIFY_WATCHERS_LOCK_KEY},
                    )
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
