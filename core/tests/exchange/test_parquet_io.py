# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.exchange.parquet_io import read_rows, write_parts
from normly_core.graph.domain import ExchangeColumn

COLUMNS = [
    ExchangeColumn("id", "string"),
    ExchangeColumn("ok", "bool"),
    ExchangeColumn("n", "int"),
    ExchangeColumn("at", "timestamp"),
    ExchangeColumn("day", "date"),
    ExchangeColumn("vector", "vector"),
    ExchangeColumn("note", "string"),
]


def _row(i):
    return {
        "id": f"id-{i}", "ok": i % 2 == 0, "n": i,
        "at": datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc),
        "day": date(2026, 10, 9), "vector": [0.5, -1.0, float(i)],
        "note": None,
    }


def test_roundtrip_across_parts(tmp_path):
    rows = [_row(i) for i in range(5)]
    entries = write_parts(tmp_path, "t", COLUMNS, iter([rows[:3], rows[3:]]), rows_per_part=2)

    assert [e.rows for e in entries] == [2, 2, 1]
    assert entries[0].path == "tables/t/part-0000.parquet"
    read = [r for e in entries for b in read_rows(tmp_path / e.path) for r in b]
    assert read == rows


def test_batch_larger_than_part_size_rotates_exactly(tmp_path):
    rows = [_row(i) for i in range(7)]
    entries = write_parts(tmp_path, "t", COLUMNS, iter([rows]), rows_per_part=3)
    assert [e.rows for e in entries] == [3, 3, 1]
    assert entries[-1].path == "tables/t/part-0002.parquet"


def test_empty_table_still_writes_one_part(tmp_path):
    entries = write_parts(tmp_path, "t", COLUMNS, iter([]), rows_per_part=10)
    assert [e.rows for e in entries] == [0]
    assert list(read_rows(tmp_path / entries[0].path)) == []
