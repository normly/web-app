# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io
import json

from normly_core.exchange.fetch import fetch_dump

FILES = {
    "https://kb.example/latest": b"2026.10.1\n",
    "https://kb.example/2026.10.1/manifest.json": json.dumps({
        "exchange_schema_version": 1, "dump_version": "2026.10.1",
        "created_at": "x", "embedding_models": [], "embedding_model_revision": "r",
        "embedding_dimension": 1024, "deliveries": [],
        "tables": {"source": [{"path": "tables/source/part-0000.parquet", "sha256": "s", "rows": 0}]},
    }).encode(),
    "https://kb.example/2026.10.1/manifest.json.sig": b"S" * 64,
    "https://kb.example/2026.10.1/tables/source/part-0000.parquet": b"PAR1",
}


def _opener(url, timeout=None):
    return io.BytesIO(FILES[url])


def test_fetch_latest_downloads_manifest_and_all_listed_files(tmp_path):
    dump_dir = fetch_dump("https://kb.example", "latest", tmp_path, opener=_opener)

    assert dump_dir == tmp_path / "2026.10.1"
    assert (dump_dir / "manifest.json.sig").read_bytes() == b"S" * 64
    assert (dump_dir / "tables/source/part-0000.parquet").read_bytes() == b"PAR1"
