# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.pipeline.adapters.dguv import DguvAdapter
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter
from normly_core.pipeline.domain import SourceAdapter
from normly_core.pipeline.runner import run_adapter

_EUR_LEX_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DGUV_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def build_adapter(source: str, *, directory: Path) -> SourceAdapter:
    if source == "eur-lex":
        return EurLexAdapter(
            directory=directory, source_id=_EUR_LEX_SOURCE_ID,
            legislation_reference="2006/42/EC",
        )
    if source == "dguv":
        return DguvAdapter(directory=directory, source_id=_DGUV_SOURCE_ID)
    raise ValueError(f"unknown source: {source!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("source", choices=["eur-lex", "dguv"])
    ingest_parser.add_argument(
        "--directory", type=Path, required=True,
        help="local directory containing the source's raw files",
    )

    args = parser.parse_args(argv)

    database_url = os.environ.get("NORMLY_DATABASE_URL")
    if not database_url:
        print("NORMLY_DATABASE_URL environment variable is required", file=sys.stderr)
        return 1

    adapter = build_adapter(args.source, directory=args.directory)
    engine = create_engine(database_url)
    with Session(engine) as session:
        summary = run_adapter(adapter, session)
        session.commit()

    print(
        f"processed={summary.records_processed} skipped={summary.records_skipped} "
        f"documents_created={summary.documents_created} "
        f"segments_created={summary.segments_created} "
        f"embeddings_created={summary.embeddings_created} "
        f"enqueued_for_review={summary.records_enqueued_for_review}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
