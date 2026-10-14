# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from normly_core.exchange.manifest import EMBEDDING_DIMENSION, FileEntry, sha256_file
from normly_core.graph.domain import ExchangeColumn

_ARROW_TYPES = {
    "string": pa.string(),
    "bool": pa.bool_(),
    "int": pa.int64(),
    "float": pa.float64(),
    "timestamp": pa.timestamp("us", tz="UTC"),
    "date": pa.date32(),
    "vector": pa.list_(pa.float32()),
}


def schema_for(columns: list[ExchangeColumn]) -> pa.Schema:
    return pa.schema([pa.field(c.name, _ARROW_TYPES[c.kind]) for c in columns])


def write_parts(
    directory: Path,
    table: str,
    columns: list[ExchangeColumn],
    batches: Iterator[list[dict[str, Any]]],
    *,
    rows_per_part: int,
) -> list[FileEntry]:
    """
    Write ``tables/<table>/part-NNNN.parquet`` files of at most
    ``rows_per_part`` rows. An empty table still gets one empty part, so a
    table is never "missing" from the manifest.
    """
    schema = schema_for(columns)
    table_dir = directory / "tables" / table
    table_dir.mkdir(parents=True, exist_ok=True)
    entries: list[FileEntry] = []
    writer: pq.ParquetWriter | None = None
    rows_in_part = 0
    part_path: Path | None = None

    def open_part() -> pq.ParquetWriter:
        nonlocal writer, part_path
        part_path = table_dir / f"part-{len(entries):04d}.parquet"
        writer = pq.ParquetWriter(part_path, schema, compression="zstd")
        return writer

    def close_part() -> None:
        nonlocal writer, rows_in_part, part_path
        if writer is None:
            return
        writer.close()
        assert part_path is not None
        entries.append(
            FileEntry(
                path=part_path.relative_to(directory).as_posix(),
                sha256=sha256_file(part_path),
                rows=rows_in_part,
            )
        )
        writer, rows_in_part, part_path = None, 0, None

    try:
        for batch in batches:
            chunk = batch
            while chunk:
                current = writer if writer is not None else open_part()
                room = rows_per_part - rows_in_part
                head, chunk = chunk[:room], chunk[room:]
                current.write_table(pa.Table.from_pylist(head, schema=schema))
                rows_in_part += len(head)
                if rows_in_part >= rows_per_part:
                    close_part()
        close_part()
        if not entries:
            open_part()
            close_part()
    finally:
        if writer is not None:  # error path: do not leak an open file handle
            writer.close()
    return entries


def read_rows(path: Path, batch_size: int = 5000) -> Iterator[list[dict[str, Any]]]:
    for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_size):
        yield batch.to_pylist()


def vector_dimension_ok(path: Path) -> bool:
    """True when every vector in the file has EMBEDDING_DIMENSION entries."""
    for batch in read_rows(path):
        for row in batch:
            for value in row.values():
                if isinstance(value, list) and value and len(value) != EMBEDDING_DIMENSION:
                    return False
    return True
