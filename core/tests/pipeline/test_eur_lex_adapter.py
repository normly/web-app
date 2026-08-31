# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest

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


def test_fetch_skips_an_unreadable_file_and_keeps_reading_the_rest(tmp_path, capsys):
    """One unreadable file must not take the rest of the run with it. The
    runner cannot isolate a failure raised inside fetch() -- it surfaces while
    the runner pulls the next record, outside its per-record guard, and a
    generator that raised cannot be resumed -- so the adapter does it, and
    reports the skipped file on stderr."""
    import shutil

    (tmp_path / "eur_lex_broken.pdf").write_text("this is not a PDF")
    shutil.copy(
        FIXTURE_DIR / "eur_lex_machinery_summary.pdf",
        tmp_path / "eur_lex_machinery_summary.pdf",
    )
    adapter = EurLexAdapter(
        directory=tmp_path, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    records = list(adapter.fetch())

    # The broken file sorts first, so the good file's records prove the run
    # continued past it -- and only one legal-act record was yielded, from the
    # file that could actually be read.
    assert [r.raw_designation for r in records].count("2006/42/EC") == 1
    assert any("EN ISO 12100" in record.raw_designation for record in records)
    assert "eur_lex_broken.pdf" in capsys.readouterr().err


def test_fetch_does_not_skip_a_misconfigured_pipeline(tmp_path, capsys, monkeypatch):
    """A broken deployment must end the run, not be skipped once per file.

    The per-file skip above would otherwise absorb it for every file alike --
    NORMLY_DOCLING_ARTIFACTS_PATH pointing at a path with no models fails the
    same way on all of them -- and the run would report success over zero
    records. The failure is a separate exception class so this cannot happen.
    """
    import shutil

    from normly_core.pipeline import docling_extraction
    from normly_core.pipeline.docling_extraction import PipelineInitializationError

    shutil.copy(
        FIXTURE_DIR / "eur_lex_machinery_summary.pdf",
        tmp_path / "eur_lex_machinery_summary.pdf",
    )
    adapter = EurLexAdapter(
        directory=tmp_path, source_id=uuid.uuid4(), legislation_reference="2006/42/EC",
    )

    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(tmp_path / "no_models_here"))
    docling_extraction._converters.clear()
    try:
        with pytest.raises(PipelineInitializationError):
            list(adapter.fetch())
    finally:
        docling_extraction._converters.clear()

    assert "skipping" not in capsys.readouterr().err


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
