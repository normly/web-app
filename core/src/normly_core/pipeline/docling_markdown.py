# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Opt-in local Markdown sidecars for source PDFs converted by Docling."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from docling_core.types.doc import DoclingDocument

from normly_core.pipeline.domain import RightsRule

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SAFE_STEM_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def export_document_markdown(
    document: DoclingDocument,
    *,
    source_path: Path,
    content_hash: str,
    output_dir: Path,
    rights_rule: RightsRule | None,
) -> Path | None:
    """Atomically write Docling's Markdown when the source permits free export.

    The adapter supplies the same ``DoclingDocument`` instance it uses to build
    its ``RawRecord``. The sidecar is deliberately not a database artifact; its
    name records the input's content hash and the Markdown itself remains
    unmodified by generated metadata.
    """
    if (
        rights_rule is None
        or not rights_rule.may_process
        or not rights_rule.may_export_free
    ):
        return None

    digest = content_hash.removeprefix("sha256:")
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"expected a SHA-256 content hash, got {content_hash!r}")

    markdown = document.export_to_markdown()
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _SAFE_STEM_PATTERN.sub("_", source_path.stem).strip("._-")
    filename = f"{safe_stem or 'document'}--{digest}.md"
    destination = output_dir / filename
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_dir,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(markdown)
        os.replace(temporary_path, destination)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return destination
