# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm

from normly_core.exchange.manifest import (
    EMBEDDING_DIMENSION,
    EXCHANGE_SCHEMA_VERSION,
    Manifest,
    sha256_file,
)
from normly_core.exchange.parquet_io import read_rows, vector_dimension_ok
from normly_core.exchange.signing import SignatureError, verify
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import ImportRecord, KnowledgeExchangeRepository


class ImportRefused(Exception):
    """The dump cannot be imported; nothing was changed."""


def verify_dump(
    dump_dir: Path,
    *,
    public_key_pem: bytes,
    expected_model_name: str,
    expected_model_revision: str,
) -> Manifest:
    """
    Everything that can be checked without a database: signature, versions,
    embedding model and revision, tables, path guard, checksums and vector
    dimensions. Raises ImportRefused; returns the verified manifest.
    """
    try:
        manifest_bytes = (dump_dir / "manifest.json").read_bytes()
    except OSError as exc:
        raise ImportRefused(f"manifest.json is missing or unreadable: {exc}") from exc
    try:
        signature = (dump_dir / "manifest.json.sig").read_bytes()
    except OSError as exc:
        raise ImportRefused(f"signature file is missing or unreadable: {exc}") from exc
    try:
        verify(public_key_pem, manifest_bytes, signature)
    except SignatureError as exc:
        raise ImportRefused(f"signature check failed: {exc}") from exc
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise ImportRefused(f"the public key is not a usable Ed25519 key: {exc}") from exc

    try:
        manifest = Manifest.from_bytes(manifest_bytes)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        # JSONDecodeError and UnicodeDecodeError are ValueErrors.
        raise ImportRefused(f"manifest is malformed: {exc!r}") from exc

    if manifest.exchange_schema_version != EXCHANGE_SCHEMA_VERSION:
        raise ImportRefused(
            f"exchange schema version {manifest.exchange_schema_version} is not supported "
            f"(this build reads {EXCHANGE_SCHEMA_VERSION}); use a matching application version"
        )
    if manifest.embedding_dimension != EMBEDDING_DIMENSION:
        raise ImportRefused(f"embedding dimension {manifest.embedding_dimension} unsupported")
    if set(manifest.embedding_models) - {expected_model_name}:
        raise ImportRefused(
            f"dump embeddings use {manifest.embedding_models}, this instance runs "
            f"{expected_model_name}"
        )
    if manifest.embedding_model_revision != expected_model_revision:
        raise ImportRefused(
            f"embedding model revision {manifest.embedding_model_revision} in the dump "
            f"differs from {expected_model_revision} on this instance"
        )
    missing = [name for name in KNOWLEDGE_TABLES if name not in manifest.tables]
    if missing:
        raise ImportRefused(f"dump lacks tables: {missing}")

    root = dump_dir.resolve()
    for name in KNOWLEDGE_TABLES:
        for entry in manifest.tables[name]:
            path = dump_dir / entry.path
            if not path.resolve().is_relative_to(root):
                raise ImportRefused(f"path {entry.path} leaves the dump directory")
            if not path.is_file() or sha256_file(path) != entry.sha256:
                raise ImportRefused(f"checksum mismatch for {entry.path}")
            if name in ("embedding", "document_embedding") and not vector_dimension_ok(path):
                raise ImportRefused(f"vector dimension mismatch in {entry.path}")

    return manifest


def import_dump(
    repository: KnowledgeExchangeRepository,
    *,
    dump_dir: Path,
    public_key_pem: bytes,
    expected_model_name: str,
    expected_model_revision: str,
    now: datetime | None = None,
) -> ImportRecord:
    """
    Verify the dump (see verify_dump) and replace the knowledge base with it.
    A takedown always wins (ADR-026): what the dump no longer contains is
    deleted (content) or retired (identifiers); user data never blocks the
    import, only an unexpected foreign key raises ImportBlockedError.

    All checks run before the first write, so ImportRefused leaves the
    database untouched. This function never commits: the caller owns the
    transaction and must commit on success and roll back on any exception
    (ImportBlockedError from the repository included), otherwise no
    half-imported state is avoided.
    """
    manifest = verify_dump(
        dump_dir,
        public_key_pem=public_key_pem,
        expected_model_name=expected_model_name,
        expected_model_revision=expected_model_revision,
    )

    def batches(name: str):
        def produce():
            for entry in manifest.tables[name]:
                yield from read_rows(dump_dir / entry.path)

        return produce

    record = ImportRecord(
        dump_version=manifest.dump_version,
        exchange_schema_version=manifest.exchange_schema_version,
        embedding_model_revision=manifest.embedding_model_revision,
        imported_at=now or datetime.now(timezone.utc),
    )
    repository.replace_knowledge_base(
        {name: batches(name) for name in KNOWLEDGE_TABLES}, record=record
    )
    return record
