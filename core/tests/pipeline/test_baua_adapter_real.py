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
    assert_heading_canaries(
        adapter,
        records[0],
        sample_name=filename,
        expected_designation=designation,
        expected_first_heading=expected_first_heading,
        expected_last_heading=expected_last_heading,
    )


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
