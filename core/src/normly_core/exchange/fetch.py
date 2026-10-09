# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import shutil
import urllib.request
from pathlib import Path

from normly_core.exchange.manifest import Manifest

_TIMEOUT_SECONDS = 60


def _get(url: str, opener) -> bytes:
    with opener(url, timeout=_TIMEOUT_SECONDS) as response:
        return response.read()


def _download(url: str, destination: Path, opener) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with opener(url, timeout=_TIMEOUT_SECONDS) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def fetch_dump(
    base_url: str, version: str, destination: Path, *, opener=urllib.request.urlopen
) -> Path:
    """Download a dump into destination/<version>. Verifies nothing: import_dump does."""
    base = base_url.rstrip("/")
    if version == "latest":
        version = _get(f"{base}/latest", opener).decode("utf-8").strip()
    dump_dir = destination / version
    for name in ("manifest.json", "manifest.json.sig"):
        _download(f"{base}/{version}/{name}", dump_dir / name, opener)
    manifest = Manifest.from_bytes((dump_dir / "manifest.json").read_bytes())
    for entries in manifest.tables.values():
        for entry in entries:
            _download(f"{base}/{version}/{entry.path}", dump_dir / entry.path, opener)
    return dump_dir
