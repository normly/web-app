# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io
import json
import urllib.error

import pytest

from normly_core.exchange.fetch import FetchError, fetch_dump

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


def _manifest(path):
    raw = json.loads(FILES["https://kb.example/2026.10.1/manifest.json"])
    raw["tables"]["source"][0]["path"] = path
    return json.dumps(raw).encode()


def _opener_with(manifest_bytes, latest=b"2026.10.1\n"):
    files = {
        **FILES,
        "https://kb.example/latest": latest,
        "https://kb.example/2026.10.1/manifest.json": manifest_bytes,
    }

    def opener(url, timeout=None):
        return io.BytesIO(files[url])

    return opener


def test_fetch_latest_downloads_manifest_and_all_listed_files(tmp_path):
    dump_dir = fetch_dump("https://kb.example", "latest", tmp_path, opener=_opener)

    assert dump_dir == tmp_path / "2026.10.1"
    assert (dump_dir / "manifest.json.sig").read_bytes() == b"S" * 64
    assert (dump_dir / "tables/source/part-0000.parquet").read_bytes() == b"PAR1"


@pytest.mark.parametrize("latest", [b"..", b".", b"/etc", b"a/b", b"../x", b"", b"a b"])
def test_fetch_rejects_malicious_latest(tmp_path, latest):
    with pytest.raises(FetchError):
        fetch_dump("https://kb.example", "latest", tmp_path / "dest",
                   opener=_opener_with(b"{}", latest=latest))
    assert not (tmp_path / "dest").exists()


@pytest.mark.parametrize("version", ["..", "a/b", "/abs"])
def test_fetch_rejects_malicious_explicit_version(tmp_path, version):
    with pytest.raises(FetchError):
        fetch_dump("https://kb.example", version, tmp_path / "dest", opener=_opener)


@pytest.mark.parametrize(
    "path", ["../escape.parquet", "tables/../../escape", "/tmp/normly-escape.parquet"]
)
def test_fetch_rejects_manifest_paths_outside_the_dump_dir(tmp_path, path):
    dest = tmp_path / "dest"
    with pytest.raises(FetchError):
        fetch_dump("https://kb.example", "2026.10.1", dest,
                   opener=_opener_with(_manifest(path)))
    written = {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()}
    assert all(str(p).startswith("dest/2026.10.1/manifest.json") for p in written)


def test_fetch_wraps_http_errors(tmp_path):
    def opener(url, timeout=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    with pytest.raises(FetchError, match="404"):
        fetch_dump("https://kb.example", "2026.10.1", tmp_path, opener=opener)


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("unreachable"), TimeoutError("slow"), OSError("reset")]
)
def test_fetch_wraps_network_errors(tmp_path, error):
    def opener(url, timeout=None):
        raise error

    with pytest.raises(FetchError):
        fetch_dump("https://kb.example", "latest", tmp_path, opener=opener)


def test_fetch_wraps_malformed_manifest(tmp_path):
    with pytest.raises(FetchError, match="manifest"):
        fetch_dump("https://kb.example", "2026.10.1", tmp_path,
                   opener=_opener_with(b"not json"))


@pytest.mark.parametrize(
    "url", ["http://kb.example", "ftp://kb.example", "kb.example", "file:///x"]
)
def test_fetch_rejects_insecure_base_urls(tmp_path, url):
    with pytest.raises(FetchError, match="https"):
        fetch_dump(url, "2026.10.1", tmp_path, opener=_opener)


def test_fetch_allows_plain_http_for_localhost(tmp_path):
    files = {k.replace("https://kb.example", "http://localhost:8080"): v for k, v in FILES.items()}

    def opener(url, timeout=None):
        return io.BytesIO(files[url])

    assert fetch_dump("http://localhost:8080", "latest", tmp_path, opener=opener).is_dir()


def test_fetch_caps_the_latest_response(tmp_path):
    with pytest.raises(FetchError):
        fetch_dump("https://kb.example", "latest", tmp_path,
                   opener=_opener_with(b"{}", latest=b"1" * 5000))
