# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""The manifest signature is checked before any table part is requested."""

import io
import json

import pytest

from normly_core.exchange.fetch import FetchError, fetch_dump
from normly_core.exchange.importer import ImportRefused, verify_dump
from normly_core.exchange.signing import generate_keypair, sign

BASE = "https://kb.example/2026.10.1/"
PART = "tables/source/part-0000.parquet"


def _manifest() -> bytes:
    return (json.dumps({
        "exchange_schema_version": 1, "dump_version": "2026.10.1",
        "created_at": "x", "embedding_models": [], "embedding_model_revision": "r",
        "embedding_dimension": 1024, "deliveries": [],
        "tables": {"source": [{"path": PART, "sha256": "s", "rows": 0}]},
    }, sort_keys=True) + "\n").encode()


def _recording_opener(manifest, signature):
    requested: list[str] = []
    files = {
        BASE + "manifest.json": manifest,
        BASE + "manifest.json.sig": signature,
        BASE + PART: b"PAR1",
    }

    def opener(url, timeout=None):
        requested.append(url)
        return io.BytesIO(files[url])

    return opener, requested


def test_good_signature_downloads_the_parts(tmp_path):
    private, public = generate_keypair()
    manifest = _manifest()
    opener, requested = _recording_opener(manifest, sign(private, manifest))
    dump_dir = fetch_dump(
        "https://kb.example", "2026.10.1", tmp_path, public_key_pem=public, opener=opener
    )
    assert (dump_dir / PART).is_file()
    assert BASE + PART in requested


def test_wrong_key_requests_no_part(tmp_path):
    private, _ = generate_keypair()
    _, other_public = generate_keypair()
    manifest = _manifest()
    opener, requested = _recording_opener(manifest, sign(private, manifest))
    with pytest.raises(FetchError, match="signature"):
        fetch_dump(
            "https://kb.example", "2026.10.1", tmp_path,
            public_key_pem=other_public, opener=opener,
        )
    assert requested == [BASE + "manifest.json", BASE + "manifest.json.sig"]


def test_tampered_manifest_requests_no_part(tmp_path):
    private, public = generate_keypair()
    manifest = _manifest()
    tampered = manifest.replace(b'"rows": 0', b'"rows": 9')
    opener, requested = _recording_opener(tampered, sign(private, manifest))
    with pytest.raises(FetchError, match="signature"):
        fetch_dump(
            "https://kb.example", "2026.10.1", tmp_path, public_key_pem=public, opener=opener
        )
    assert not any(url.endswith(".parquet") for url in requested)


def test_malformed_key_is_a_clean_fetch_error(tmp_path):
    private, _ = generate_keypair()
    manifest = _manifest()
    opener, requested = _recording_opener(manifest, sign(private, manifest))
    with pytest.raises(FetchError, match="public key"):
        fetch_dump(
            "https://kb.example", "2026.10.1", tmp_path,
            public_key_pem=b"not a pem", opener=opener,
        )
    assert not any(url.endswith(".parquet") for url in requested)


def test_verify_dump_turns_a_malformed_key_into_import_refused(tmp_path):
    (tmp_path / "manifest.json").write_bytes(b"{}")
    (tmp_path / "manifest.json.sig").write_bytes(b"S" * 64)
    with pytest.raises(ImportRefused, match="public key"):
        verify_dump(
            tmp_path, public_key_pem=b"not a pem",
            expected_model_name="m", expected_model_revision="r",
        )


def test_without_a_key_nothing_is_verified_by_fetch(tmp_path):
    opener, _ = _recording_opener(_manifest(), b"S" * 64)
    assert fetch_dump("https://kb.example", "2026.10.1", tmp_path, opener=opener).is_dir()
