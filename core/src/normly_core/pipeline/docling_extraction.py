# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Shared Docling document-extraction layer for all pipeline adapters.

Production/CI requirement (STACKIT-only constraint -- no runtime access to
external model sources, see CLAUDE.md): before deploying, pre-fetch
Docling's layout and table-structure models once with

    docling-tools models download layout tableformer -o <path>

and set NORMLY_DOCLING_ARTIFACTS_PATH to <path> in the runtime environment.
With that set, extract_document() never attempts a network connection
(verified by tests/pipeline/test_docling_offline.py). Without it (e.g.
local development), Docling manages its own cache directory and downloads
models on first use -- convenient for development, not acceptable in
production.

OCR is deliberately disabled (do_ocr=False): Docling's default pipeline
runs OCR even on pure vector-text PDFs like the two sources this codebase
ingests today, and does so by downloading additional models from
modelscope.cn -- a second external model source beyond Hugging Face that
this project has no reason to depend on before an actual OCR need exists.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError as _DoclingConversionError
from docling_core.types.doc import DoclingDocument

_ARTIFACTS_PATH_ENV = "NORMLY_DOCLING_ARTIFACTS_PATH"

# DocumentConverter eagerly loads the layout and TableFormer models when
# constructed -- roughly 1s of fixed overhead, independent of document size.
# Docling supports reusing one instance across many convert() calls (its own
# pipeline construction is guarded by a module-level lock to make this safe;
# see its docstring: models are "initialised once per pipeline instance and
# only read by worker threads"). Cache one converter per resolved
# artifacts_path value so adapters processing many files per fetch() run
# only pay the load cost once, while a test that monkeypatches
# NORMLY_DOCLING_ARTIFACTS_PATH between calls still gets a converter built
# for the path it set, not a stale one from a different path.
_converters: dict[str | None, DocumentConverter] = {}
_converters_lock = threading.Lock()


class DocumentExtractionError(Exception):
    """Raised when Docling cannot parse a source file."""


def _get_converter(artifacts_path_value: str | None) -> DocumentConverter:
    with _converters_lock:
        converter = _converters.get(artifacts_path_value)
        if converter is None:
            pipeline_options = PdfPipelineOptions(
                do_ocr=False,
                artifacts_path=(
                    Path(artifacts_path_value) if artifacts_path_value else None
                ),
            )
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            _converters[artifacts_path_value] = converter
        return converter


def extract_document(path: Path) -> DoclingDocument:
    artifacts_path_value = os.environ.get(_ARTIFACTS_PATH_ENV)
    converter = _get_converter(artifacts_path_value)
    try:
        result = converter.convert(path)
    except _DoclingConversionError as exc:
        raise DocumentExtractionError(f"Docling could not parse {path}: {exc}") from exc
    if result.status != ConversionStatus.SUCCESS:
        raise DocumentExtractionError(
            f"Docling only partially converted {path} (status={result.status}): "
            f"{result.errors}"
        )
    return result.document
