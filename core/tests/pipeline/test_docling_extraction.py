# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter

from normly_core.pipeline import docling_extraction
from normly_core.pipeline.docling_extraction import (
    DocumentExtractionError,
    PipelineInitializationError,
    extract_document,
)

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
    # _get_converter() now initialises the pipeline eagerly, which for a set
    # artifacts_path means loading the models from it. This test is about the
    # cache key, not about model files, and tmp_path holds no models -- so the
    # initialisation is stubbed out here rather than populated.
    with patch.object(DocumentConverter, "initialize_pipeline"):
        docling_extraction._get_converter(other_path)

    assert set(docling_extraction._converters) == {None, other_path}
    assert docling_extraction._converters[None] is not docling_extraction._converters[other_path]


def test_a_bad_artifacts_path_raises_a_normly_error_when_the_converter_is_built(
    monkeypatch, tmp_path
):
    """Docling signals an artifacts_path that is not a directory with a bare
    RuntimeError from its pipeline constructor. That must not escape this
    module: raw Docling errors stay inside it, and callers guard against its
    own classes.

    It must also happen here, at converter-construction time. Docling builds
    its pipeline lazily on the first convert() call, so an unmounted or
    typo'd model path would otherwise stay invisible until real ingestion
    traffic arrives.
    """
    missing = tmp_path / "nowhere"
    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(missing))
    docling_extraction._converters.clear()

    with patch.object(DocumentConverter, "convert") as convert:
        with pytest.raises(PipelineInitializationError, match="initialise"):
            docling_extraction._get_converter(str(missing))

    # Eager: no document was ever converted, and none had to be.
    convert.assert_not_called()
    # A converter whose pipeline failed must not be cached as if it worked.
    assert docling_extraction._converters == {}


def test_an_artifacts_path_without_models_raises_a_normly_error_too(monkeypatch, tmp_path):
    """The other half of the same misconfiguration: the path is a directory,
    but the pre-fetched models are not in it. Docling raises FileNotFoundError
    for that one; the caller must not have to know the difference."""
    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(tmp_path))
    docling_extraction._converters.clear()

    with pytest.raises(PipelineInitializationError, match="initialise"):
        docling_extraction._get_converter(str(tmp_path))

    assert docling_extraction._converters == {}


def test_a_bad_artifacts_path_raises_a_normly_error_from_extract_document(
    monkeypatch, tmp_path
):
    """The same failure, seen from the call adapters actually make."""
    missing = tmp_path / "nowhere"
    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(missing))
    docling_extraction._converters.clear()

    with pytest.raises(PipelineInitializationError):
        extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")


def test_a_pipeline_failure_is_not_a_document_extraction_error():
    """The class relationship is the whole mechanism, so it is asserted.

    Adapters catch DocumentExtractionError per file and carry on -- one
    corrupt PDF must block only itself. A pipeline that cannot be built fails
    the same way for every file, so being caught by that clause would turn a
    misconfigured deployment into a run that skips everything and still exits
    0 reporting success. Making PipelineInitializationError a subclass here
    would silently restore exactly that.
    """
    assert not issubclass(PipelineInitializationError, DocumentExtractionError)
    assert not issubclass(DocumentExtractionError, PipelineInitializationError)


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
