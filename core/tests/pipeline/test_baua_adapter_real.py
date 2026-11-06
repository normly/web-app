# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Opt-in BAuA extraction checks using samples from the private data submodule.

Initialize the submodule from the repository root with:
    git submodule update --init web-app-raw-data

Then run from core/ with:
    BAUA_REAL_DOCUMENTS_DIR=../web-app-raw-data/raw_data_test/BAuA \
        ../.venv/bin/pytest tests/pipeline/test_baua_adapter_real.py

The submodule is not initialized in CI. This module is skipped in CI and
ordinary local runs unless the environment variable is set. It reports no
extracted document text.
"""

import hashlib
import os
import uuid
from pathlib import Path

import pytest

from normly_core.pipeline.adapters.baua import BauaAdapter
from .baua_test_support import (
    BAUA_REAL_DOCUMENT_HEADING_CANARIES,
    assert_heading_canaries,
)


_DOCUMENT_DIR = os.environ.get("BAUA_REAL_DOCUMENTS_DIR")
pytestmark = pytest.mark.skipif(
    not _DOCUMENT_DIR,
    reason="set BAUA_REAL_DOCUMENTS_DIR to opt in to local BAuA PDFs",
)


@pytest.mark.parametrize(
    "filename, designation, staged_name, expected_first_heading, expected_last_heading",
    BAUA_REAL_DOCUMENT_HEADING_CANARIES,
)
def test_real_document_designation_and_section_extraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    designation: str,
    staged_name: str,
    expected_first_heading: str,
    expected_last_heading: str,
):
    from normly_core.pipeline.adapters import baua

    source = Path(_DOCUMENT_DIR).resolve() / filename
    if not source.is_file():
        pytest.skip(f"local real-document sample is absent: {filename}")

    (tmp_path / staged_name).symlink_to(source)
    converted_documents = []
    extract = baua.extract_document

    def capture_conversion(path: Path):
        document = extract(path)
        converted_documents.append(document)
        return document

    monkeypatch.setattr(baua, "extract_document", capture_conversion)
    markdown_dir = tmp_path / "markdown"
    adapter = BauaAdapter(
        directory=tmp_path,
        source_id=uuid.uuid4(),
        docling_markdown_dir=markdown_dir,
    )

    records = list(adapter.fetch())

    assert len(records) == 1
    assert_heading_canaries(
        adapter,
        records[0],
        sample_name=filename,
        expected_designation=designation,
        expected_first_heading=expected_first_heading,
        expected_last_heading=expected_last_heading,
    )
    assert len(converted_documents) == 1
    markdown_paths = list(markdown_dir.glob("*.md"))
    assert len(markdown_paths) == 1
    sidecar_digest = hashlib.sha256(markdown_paths[0].read_bytes()).digest()
    document_digest = hashlib.sha256(
        converted_documents[0].export_to_markdown().encode("utf-8")
    ).digest()
    assert sidecar_digest == document_digest


def test_real_document_without_matching_designation_remains_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from normly_core.pipeline.adapters import baua

    source = Path(_DOCUMENT_DIR).resolve() / "TRGS-001.pdf"
    if not source.is_file():
        pytest.skip("local real-document sample is absent: TRGS-001.pdf")

    (tmp_path / "baua_trgs_001.pdf").symlink_to(source)
    converted_documents = []
    extract = baua.extract_document

    def capture_conversion(path: Path):
        document = extract(path)
        converted_documents.append(document)
        return document

    monkeypatch.setattr(baua, "extract_document", capture_conversion)
    markdown_dir = tmp_path / "markdown"
    adapter = BauaAdapter(
        directory=tmp_path,
        source_id=uuid.uuid4(),
        docling_markdown_dir=markdown_dir,
    )

    records = list(adapter.fetch())

    assert len(records) == 1
    assert records[0].raw_designation == ""
    assert records[0].raw_title is None
    assert len(converted_documents) == 1
    markdown_paths = list(markdown_dir.glob("*.md"))
    assert len(markdown_paths) == 1
    sidecar_digest = hashlib.sha256(markdown_paths[0].read_bytes()).digest()
    document_digest = hashlib.sha256(
        converted_documents[0].export_to_markdown().encode("utf-8")
    ).digest()
    assert sidecar_digest == document_digest
