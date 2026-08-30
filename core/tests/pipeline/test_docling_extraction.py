# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter

from normly_core.pipeline import docling_extraction
from normly_core.pipeline.docling_extraction import DocumentExtractionError, extract_document

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_extract_document_returns_text_content_for_a_real_pdf():
    document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")

    texts = [
        item.text
        for item, _level in document.iterate_items()
        if hasattr(item, "text") and item.text
    ]
    assert any("§ 1 Geltungsbereich" in t for t in texts)


def test_extract_document_returns_tables_for_a_real_pdf():
    document = extract_document(FIXTURE_DIR / "eur_lex_machinery_summary.pdf")

    assert len(document.tables) >= 1
    first_row = document.tables[0].data.grid[0]
    assert any(cell is not None and "ESO" in cell.text for cell in first_row)


def test_extract_document_raises_a_normly_error_on_a_corrupt_file(tmp_path):
    corrupt = tmp_path / "not_a_real.pdf"
    corrupt.write_text("this is not a PDF")

    with pytest.raises(DocumentExtractionError):
        extract_document(corrupt)


def test_extract_document_reuses_the_cached_converter_across_calls(monkeypatch):
    """Model loading (~1s fixed cost) must happen once, not per call -- see
    the caching rationale in docling_extraction.py's module docstring."""
    monkeypatch.delenv("NORMLY_DOCLING_ARTIFACTS_PATH", raising=False)
    docling_extraction._converters.clear()

    extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")
    assert list(docling_extraction._converters) == [None]
    first_converter = docling_extraction._converters[None]

    extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")
    second_converter = docling_extraction._converters[None]

    # Same cache key still maps to the exact same instance -- no rebuild.
    assert first_converter is second_converter
    assert len(docling_extraction._converters) == 1


def test_extract_document_caches_separately_per_artifacts_path(monkeypatch, tmp_path):
    """A differing NORMLY_DOCLING_ARTIFACTS_PATH must not reuse a converter
    built for a different path."""
    docling_extraction._converters.clear()

    monkeypatch.delenv("NORMLY_DOCLING_ARTIFACTS_PATH", raising=False)
    docling_extraction._get_converter(None)

    other_path = str(tmp_path)
    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", other_path)
    docling_extraction._get_converter(other_path)

    assert set(docling_extraction._converters) == {None, other_path}
    assert docling_extraction._converters[None] is not docling_extraction._converters[other_path]


def test_extract_document_raises_on_a_partial_success_conversion(monkeypatch):
    """Docling's convert() only raises on genuine failure -- PARTIAL_SUCCESS
    (some pages failed layout/table inference) returns normally with a
    truncated document. extract_document() must treat that as a failure
    too, rather than silently handing adapters an incomplete document.

    Real Docling has no reliably reproducible PARTIAL_SUCCESS fixture, so
    this mocks DocumentConverter.convert's return value -- the corrupt-file
    test above already covers the ConversionError/raises_on_error path with
    a real file.
    """
    monkeypatch.delenv("NORMLY_DOCLING_ARTIFACTS_PATH", raising=False)
    docling_extraction._converters.clear()

    fake_result = MagicMock()
    fake_result.status = ConversionStatus.PARTIAL_SUCCESS
    fake_result.errors = ["page 3: layout model failed"]

    with patch.object(DocumentConverter, "convert", return_value=fake_result):
        with pytest.raises(DocumentExtractionError, match="partial"):
            extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")
