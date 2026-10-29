# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Opt-in BAuA extraction checks using PDFs kept outside the repository.

Run explicitly with:
    BAUA_REAL_DOCUMENTS_DIR=/tmp/opencode/baua-review \
        ../.venv/bin/pytest tests/pipeline/test_baua_adapter_real.py

The module is skipped in CI and ordinary local runs unless the environment
variable is set. It reports no extracted document text.
"""

import os
import uuid
from pathlib import Path

import pytest

from normly_core.pipeline.adapters.baua import BauaAdapter


_DOCUMENT_DIR = os.environ.get("BAUA_REAL_DOCUMENTS_DIR")
pytestmark = pytest.mark.skipif(
    not _DOCUMENT_DIR,
    reason="set BAUA_REAL_DOCUMENTS_DIR to opt in to local BAuA PDFs",
)


@pytest.mark.parametrize(
    "filename, designation, staged_name, expected_first_heading, expected_last_heading",
    [
        (
            "TRGS-401.pdf", "TRGS 401", "baua_trgs_401.pdf",
            "1 Anwendungsbereich", "7 Arbeitsmedizinische Vorsorge",
        ),
        (
            "TRGS-402.pdf", "TRGS 402", "baua_trgs_402.pdf",
            "1 Anwendungsbereich", "7 Dokumentation",
        ),
    ],
)
def test_real_document_designation_and_section_extraction(
    tmp_path: Path,
    filename: str,
    designation: str,
    staged_name: str,
    expected_first_heading: str,
    expected_last_heading: str,
):
    source = Path(_DOCUMENT_DIR) / filename
    if not source.is_file():
        pytest.skip(f"local real-document sample is absent: {filename}")

    (tmp_path / staged_name).symlink_to(source)
    adapter = BauaAdapter(directory=tmp_path, source_id=uuid.uuid4())

    records = list(adapter.fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == designation
    assert bool(record.full_text)

    sections = adapter.extract_structure(record)
    assert sections
    assert [section.sequence_number for section in sections] == list(
        range(1, len(sections) + 1)
    )
    headings = [section.heading for section in sections if section.heading is not None]
    if not headings:
        pytest.fail(f"{filename}: no section headings extracted")
    if headings[0] != expected_first_heading:
        pytest.fail(f"{filename}: first section heading mismatch")
    if headings[-1] != expected_last_heading:
        pytest.fail(f"{filename}: last section heading mismatch")


def test_real_document_without_matching_designation_remains_unresolved(tmp_path: Path):
    source = Path(_DOCUMENT_DIR) / "TRGS-001.pdf"
    if not source.is_file():
        pytest.skip("local real-document sample is absent: TRGS-001.pdf")

    (tmp_path / "baua_trgs_001.pdf").symlink_to(source)
    adapter = BauaAdapter(directory=tmp_path, source_id=uuid.uuid4())

    records = list(adapter.fetch())

    assert len(records) == 1
    assert records[0].raw_designation == ""
    assert records[0].raw_title is None
