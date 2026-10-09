# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Download a dump over HTTPS. Everything fetched here is untrusted until
import_dump has verified the signature, so version and manifest paths are
validated before they touch the file system or a URL.
"""

import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from normly_core.exchange.manifest import Manifest

_TIMEOUT_SECONDS = 60
_LATEST_MAX_BYTES = 1024
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_PLAIN_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1"}


class FetchError(Exception):
    """The dump could not be downloaded, or the server sent something unusable."""


def _describe(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    return f"{type(exc).__name__}: {exc}"


def _get(url: str, opener, max_bytes: int | None = None) -> bytes:
    try:
        with opener(url, timeout=_TIMEOUT_SECONDS) as response:
            if max_bytes is None:
                return response.read()
            data = response.read(max_bytes + 1)
    except OSError as exc:  # HTTPError, URLError and timeouts are all OSErrors
        raise FetchError(f"{_describe(exc)} for {url}") from exc
    if len(data) > max_bytes:
        raise FetchError(f"response from {url} exceeds {max_bytes} bytes")
    return data


def _download(url: str, destination: Path, opener) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with opener(url, timeout=_TIMEOUT_SECONDS) as response, destination.open("wb") as out:
            shutil.copyfileobj(response, out)
    except OSError as exc:
        raise FetchError(f"{_describe(exc)} for {url}") from exc


def _check_base_url(base: str) -> None:
    parts = urlsplit(base)
    if parts.scheme == "https" and parts.hostname:
        return
    if parts.scheme == "http" and parts.hostname in _PLAIN_HTTP_HOSTS:
        return
    raise FetchError(
        f"knowledge-base URL must use https:// (http:// only for localhost): {base!r}"
    )


def _check_version(version: str) -> str:
    if version in (".", "..") or not _VERSION_PATTERN.fullmatch(version):
        raise FetchError(f"invalid dump version {version[:64]!r}")
    return version


def _safe_target(dump_dir: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    if not relative or candidate.is_absolute() or "\\" in relative:
        raise FetchError(f"manifest lists an unsafe path: {relative!r}")
    root = dump_dir.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target == root:
        raise FetchError(f"manifest lists a path outside the dump: {relative!r}")
    return dump_dir / relative


def fetch_dump(
    base_url: str, version: str, destination: Path, *, opener=urllib.request.urlopen
) -> Path:
    """Download a dump into destination/<version>. Verifies nothing: import_dump does."""
    base = base_url.rstrip("/")
    _check_base_url(base)
    if version == "latest":
        version = _get(f"{base}/latest", opener, _LATEST_MAX_BYTES).decode(
            "utf-8", errors="replace"
        ).strip()
    _check_version(version)
    dump_dir = destination / version
    for name in ("manifest.json", "manifest.json.sig"):
        _download(f"{base}/{quote(version)}/{name}", dump_dir / name, opener)
    try:
        manifest = Manifest.from_bytes((dump_dir / "manifest.json").read_bytes())
        paths = [e.path for entries in manifest.tables.values() for e in entries]
    except Exception as exc:  # noqa: BLE001 - any parse failure means a bad manifest
        raise FetchError(f"invalid manifest in dump {version}: {_describe(exc)}") from exc
    targets = [(path, _safe_target(dump_dir, path)) for path in paths]
    for path, target in targets:
        _download(f"{base}/{quote(version)}/{quote(path, safe='/')}", target, opener)
    return dump_dir
