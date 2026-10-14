# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import shutil
from datetime import datetime, timezone
from pathlib import Path

from normly_core.exchange.manifest import (
    EMBEDDING_DIMENSION,
    EXCHANGE_SCHEMA_VERSION,
    DeliveryEntry,
    Manifest,
)
from normly_core.exchange.parquet_io import write_parts
from normly_core.exchange.signing import sign
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.domain import KnowledgeExchangeRepository


def export_dump(
    repository: KnowledgeExchangeRepository,
    *,
    out_dir: Path,
    dump_version: str,
    private_key_pem: bytes,
    embedding_model_revision: str,
    rows_per_part: int = 100_000,
    now: datetime | None = None,
) -> Path:
    """
    Write a signed dump to ``<out_dir>/<dump_version>``. Versions are
    immutable: an existing directory raises FileExistsError. A failed export
    removes its partial directory.
    """
    dump_dir = out_dir / dump_version
    dump_dir.mkdir(parents=True, exist_ok=False)
    try:
        _write_dump(
            repository, dump_dir, dump_version, private_key_pem,
            embedding_model_revision, rows_per_part, now,
        )
    except BaseException:
        shutil.rmtree(dump_dir, ignore_errors=True)
        raise
    return dump_dir


def _write_dump(
    repository: KnowledgeExchangeRepository,
    dump_dir: Path,
    dump_version: str,
    private_key_pem: bytes,
    embedding_model_revision: str,
    rows_per_part: int,
    now: datetime | None,
) -> None:
    tables = {}
    models: set[str] = set()
    for name in KNOWLEDGE_TABLES:
        columns = repository.exchange_columns(name)

        def batches(name=name):
            for batch in repository.iter_exportable_rows(name):
                if name in ("embedding", "document_embedding"):
                    models.update(row["model_name"] for row in batch)
                yield batch

        tables[name] = write_parts(
            dump_dir, name, columns, batches(), rows_per_part=rows_per_part
        )

    manifest = Manifest(
        exchange_schema_version=EXCHANGE_SCHEMA_VERSION,
        dump_version=dump_version,
        created_at=(now or datetime.now(timezone.utc)).isoformat(),
        embedding_models=sorted(models),
        embedding_model_revision=embedding_model_revision,
        embedding_dimension=EMBEDDING_DIMENSION,
        deliveries=[DeliveryEntry(*d) for d in repository.exportable_deliveries()],
        tables=tables,
    )
    data = manifest.to_bytes()
    (dump_dir / "manifest.json").write_bytes(data)
    (dump_dir / "manifest.json.sig").write_bytes(sign(private_key_pem, data))
