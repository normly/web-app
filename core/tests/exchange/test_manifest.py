# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.exchange.manifest import (
    DeliveryEntry,
    FileEntry,
    Manifest,
    sha256_file,
)


def _manifest() -> Manifest:
    return Manifest(
        exchange_schema_version=1,
        dump_version="2026.10.1",
        created_at="2026-10-09T10:00:00+00:00",
        embedding_models=["intfloat/multilingual-e5-large"],
        embedding_model_revision="3d7cfbd",
        embedding_dimension=1024,
        deliveries=[DeliveryEntry("d-1", "BAuA", "A")],
        tables={"source": [FileEntry("tables/source/part-0000.parquet", "ab", 3)]},
    )


def test_roundtrip_is_lossless():
    manifest = _manifest()
    assert Manifest.from_bytes(manifest.to_bytes()) == manifest


def test_serialisation_is_canonical():
    assert _manifest().to_bytes() == _manifest().to_bytes()
    assert b'"dump_version": "2026.10.1"' in _manifest().to_bytes()


def test_sha256_file(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    assert sha256_file(path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
