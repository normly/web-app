# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
python -m normly_core.exchange
    {keygen|export|import|verify|info|tables|export-tombstones|import-tombstones}

The knowledge-base dump tooling (ADR-025). Commits happen here, never in the
repository.
"""

import argparse
import os
import sys
import tempfile
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.fetch import FetchError, fetch_dump
from normly_core.exchange.importer import ImportRefused, import_dump, verify_dump
from normly_core.exchange.signing import generate_keypair
from normly_core.exchange.tables import group_tables
from normly_core.exchange.tombstones import build_document, parse_document, row_count
from normly_core.graph.domain import ImportBlockedError
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository

_MODEL_REVISION_ENV = "NORMLY_EMBEDDING_MODEL_REVISION"
_KEY_FILE_ENV = "NORMLY_KB_PUBLIC_KEY_FILE"


def _packaged_public_key() -> bytes:
    return (resources.files("normly_core.exchange") / "keys" / "kb-signing.pub.pem").read_bytes()


def _require_env(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        print(f"{name} environment variable is required", file=sys.stderr)
    return value


def _write_new(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as out:
        out.write(data)


def _keygen(args) -> int:
    private, public = Path(args.private), Path(args.public)
    for path in (private, public):
        if path.exists():
            print(f"{path} exists; refusing to overwrite", file=sys.stderr)
            return 1
    private_pem, public_pem = generate_keypair()
    try:
        # O_EXCL: atomic "refuse to overwrite"; the mode applies from creation on.
        _write_new(private, private_pem, 0o600)
        _write_new(public, public_pem, 0o644)
    except FileExistsError as exc:
        print(f"{exc.filename} exists; refusing to overwrite", file=sys.stderr)
        return 1
    print(f"wrote {private} (keep offline) and {public} (commit to the repository)")
    return 0


def _public_key(args) -> bytes | None:
    """--public-key, else $NORMLY_KB_PUBLIC_KEY_FILE, else the packaged key."""
    key_file = args.public_key or os.environ.get(_KEY_FILE_ENV)
    if key_file:
        try:
            return Path(key_file).read_bytes()
        except OSError as exc:
            source = "--public-key" if args.public_key else _KEY_FILE_ENV
            print(f"cannot read the public key from {source}: {exc}", file=sys.stderr)
            return None
    try:
        return _packaged_public_key()
    except FileNotFoundError:
        print(
            "no public key packaged with this build; pass --public-key PATH",
            file=sys.stderr,
        )
        return None


def _verify(args) -> int:
    """Check a dump without touching the database (used before destructive steps)."""
    revision = _require_env(_MODEL_REVISION_ENV)
    if not revision:
        return 1
    public_pem = _public_key(args)
    if public_pem is None:
        return 1
    if args.fetch and not _require_env("NORMLY_KB_BASE_URL"):
        return 1
    from normly_core.pipeline.embeddings import MODEL_NAME  # heavy import, import only here

    with tempfile.TemporaryDirectory() as scratch:
        if args.fetch:
            try:
                dump_dir = fetch_dump(
                    os.environ["NORMLY_KB_BASE_URL"], args.fetch, Path(scratch),
                    public_key_pem=public_pem,
                )
            except FetchError as exc:
                print(f"fetch failed: {exc}", file=sys.stderr)
                return 1
        else:
            dump_dir = args.from_dir
        try:
            manifest = verify_dump(
                dump_dir, public_key_pem=public_pem,
                expected_model_name=MODEL_NAME, expected_model_revision=revision,
            )
        except ImportRefused as exc:
            print(f"verification refused: {exc}", file=sys.stderr)
            return 1
    print(f"verified knowledge base {manifest.dump_version}")
    return 0


def _export_tombstones(database_url: str) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            rows = PostgresKnowledgeExchangeRepository(session).export_tombstone_support()
            document = build_document(rows, created_at=datetime.now(timezone.utc))
    finally:
        engine.dispose()
    sys.stdout.write(document)
    return 0


def _import_tombstones(database_url: str) -> int:
    try:
        rows, created_at = parse_document(sys.stdin.read())
    except ValueError as exc:
        print(f"invalid tombstone document: {exc}", file=sys.stderr)
        return 1
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            try:
                PostgresKnowledgeExchangeRepository(session).restore_tombstone_support(
                    rows, restored_at=created_at
                )
            except ValueError as exc:
                session.rollback()
                print(f"invalid tombstone document: {exc}", file=sys.stderr)
                return 1
            session.commit()
            print(f"restored tombstone support: {row_count(rows)} rows")
            return 0
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m normly_core.exchange")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen")
    keygen.add_argument("--private", required=True)
    keygen.add_argument("--public", required=True)

    export = sub.add_parser("export")
    export.add_argument("--version", required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--private-key", type=Path, required=True)

    imp = sub.add_parser("import")
    source = imp.add_mutually_exclusive_group(required=True)
    source.add_argument("--from", dest="from_dir", type=Path)
    source.add_argument("--fetch", metavar="VERSION")
    key_help = (
        "PEM public key; default: $NORMLY_KB_PUBLIC_KEY_FILE, then the key packaged "
        "with this build"
    )
    imp.add_argument("--public-key", type=Path, help=key_help)
    imp.add_argument(
        "--allow-empty", action="store_true",
        help="apply a dump without documents even though the database holds some",
    )

    ver = sub.add_parser("verify", help="check a dump (no database needed)")
    ver_source = ver.add_mutually_exclusive_group(required=True)
    ver_source.add_argument("--from", dest="from_dir", type=Path)
    ver_source.add_argument("--fetch", metavar="VERSION")
    ver.add_argument("--public-key", type=Path, help=key_help)

    sub.add_parser("info")
    sub.add_parser(
        "export-tombstones",
        help="print the retired identifier rows and their parents as JSON (backup)",
    )
    sub.add_parser(
        "import-tombstones",
        help="restore the tombstone support JSON read from stdin (rollback)",
    )

    tables = sub.add_parser("tables")
    tables.add_argument("group", choices=["knowledge", "user", "pipeline", "all"])

    args = parser.parse_args(argv)

    if args.command == "keygen":
        return _keygen(args)
    if args.command == "tables":
        print("\n".join(group_tables(args.group)))
        return 0

    if args.command == "verify":
        return _verify(args)

    database_url = _require_env("NORMLY_DATABASE_URL")
    if not database_url:
        return 1
    if args.command == "export-tombstones":
        return _export_tombstones(database_url)
    if args.command == "import-tombstones":
        return _import_tombstones(database_url)
    revision = None
    if args.command != "info":
        revision = _require_env(_MODEL_REVISION_ENV)
        if not revision:
            return 1
    public_pem = None
    if args.command == "import":
        public_pem = _public_key(args)
        if public_pem is None:
            return 1
        if args.fetch and not os.environ.get("NORMLY_KB_BASE_URL"):
            print("NORMLY_KB_BASE_URL environment variable is required", file=sys.stderr)
            return 1

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            repository = PostgresKnowledgeExchangeRepository(session)
            if args.command == "info":
                record = repository.imported_version()
                print(record.dump_version if record else "none")
                return 0
            if args.command == "export":
                dump_dir = export_dump(
                    repository, out_dir=args.out, dump_version=args.version,
                    private_key_pem=args.private_key.read_bytes(),
                    embedding_model_revision=revision,
                )
                print(f"exported {dump_dir}")
                return 0
            # import
            from normly_core.pipeline.embeddings import MODEL_NAME  # heavy import, import only here

            with tempfile.TemporaryDirectory() as scratch:
                if args.fetch:
                    try:
                        dump_dir = fetch_dump(
                            os.environ["NORMLY_KB_BASE_URL"], args.fetch, Path(scratch),
                            public_key_pem=public_pem,
                        )
                    except FetchError as exc:
                        session.rollback()
                        print(f"fetch failed: {exc}", file=sys.stderr)
                        return 1
                else:
                    dump_dir = args.from_dir
                try:
                    record = import_dump(
                        repository, dump_dir=dump_dir, public_key_pem=public_pem,
                        expected_model_name=MODEL_NAME, expected_model_revision=revision,
                        allow_empty=args.allow_empty,
                    )
                except (ImportRefused, ImportBlockedError) as exc:
                    session.rollback()
                    print(f"import refused: {exc}", file=sys.stderr)
                    return 1
            session.commit()
            print(f"imported knowledge base {record.dump_version}")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
