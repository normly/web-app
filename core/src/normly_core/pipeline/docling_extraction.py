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
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError as _DoclingConversionError
from docling_core.types.doc import DoclingDocument

_ARTIFACTS_PATH_ENV = "NORMLY_DOCLING_ARTIFACTS_PATH"


class DocumentExtractionError(Exception):
    """Raised when Docling cannot parse a source file."""


def extract_document(path: Path) -> DoclingDocument:
    artifacts_path_value = os.environ.get(_ARTIFACTS_PATH_ENV)
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        artifacts_path=Path(artifacts_path_value) if artifacts_path_value else None,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    try:
        result = converter.convert(path)
    except _DoclingConversionError as exc:
        raise DocumentExtractionError(f"Docling could not parse {path}: {exc}") from exc
    return result.document
