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
