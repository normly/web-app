# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.adapters.eur_lex import EurLexAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_fetch_yields_the_legal_act_record_first():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())

    assert records[0].raw_designation == "2006/42/EC"
    assert records[0].raw_issuer == "EU"
    assert records[0].full_text is None
    # The Commission's summary list is English, not German.
    assert records[0].language == "en"


def test_fetch_yields_standard_records_with_based_on_law_reference():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())
    standard_records = [r for r in records if r.raw_designation != "2006/42/EC"]

    assert len(standard_records) >= 1
    first = standard_records[0]
    assert first.raw_issuer == "CEN"
    assert "EN ISO 12100" in first.raw_designation
    assert first.full_text is None
    assert len(first.raw_references) == 1
    reference = first.raw_references[0]
    assert reference.target_issuer == "EU"
    assert reference.target_designation == "2006/42/EC"
    assert reference.edge_type == EdgeType.BASED_ON_LAW


def test_fetch_reads_every_matching_file_and_ignores_other_sources_files(tmp_path):
    """`--directory` means the directory, not one hardcoded filename in it."""
    import shutil

    shutil.copy(
        FIXTURE_DIR / "eur_lex_machinery_summary.pdf",
        tmp_path / "eur_lex_machinery_summary_2026.pdf",
    )
    shutil.copy(
        FIXTURE_DIR / "dguv_sample_vorschrift.pdf", tmp_path / "dguv_sample_vorschrift.pdf"
    )
    adapter = EurLexAdapter(
        directory=tmp_path, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())

    assert records[0].raw_designation == "2006/42/EC"
    assert any("EN ISO 12100" in record.raw_designation for record in records)
    # Nothing from the DGUV file: that file is another adapter's business.
    assert all(not record.raw_designation.startswith("DGUV") for record in records)


def test_extract_structure_is_always_empty():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )
    records = list(adapter.fetch())

    assert adapter.extract_structure(records[1]) == []


def test_classify_rights_denies_fulltext_but_allows_export():
    adapter = EurLexAdapter(
        directory=FIXTURE_DIR, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )
    records = list(adapter.fetch())

    rule = adapter.classify_rights(records[1])

    assert rule.may_process is True
    assert rule.may_index_fulltext is False
    assert rule.may_cite_passages is False
    assert rule.may_export_free is True
