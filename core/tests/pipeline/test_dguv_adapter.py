# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

from normly_core.pipeline.adapters.dguv import DguvAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_fetch_yields_one_record_per_pdf_with_full_text():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())

    records = list(adapter.fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == "DGUV Vorschrift 1"
    assert record.raw_issuer == "DGUV"
    assert record.raw_title == "Grundsätze der Prävention"
    assert record.full_text is not None
    assert "§ 1 Geltungsbereich" in record.full_text


def test_extract_structure_splits_on_paragraph_headings():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    sections = adapter.extract_structure(record)

    assert len(sections) == 3
    assert sections[0].heading == "§ 1 Geltungsbereich"
    assert "Diese Vorschrift gilt" in sections[0].text
    assert sections[1].heading == "§ 2 Pflichten des Unternehmers"
    assert sections[2].heading == "§ 3 Pflichten der Versicherten"
    assert [s.sequence_number for s in sections] == [1, 2, 3]


def test_classify_rights_allows_full_processing():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    rule = adapter.classify_rights(record)

    assert rule.may_process is True
    assert rule.may_index_fulltext is True
    assert rule.may_cite_passages is True
    assert rule.may_export_free is True
    assert rule.jurisdiction == "DE"
