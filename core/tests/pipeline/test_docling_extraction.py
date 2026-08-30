# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest

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
