# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest

from normly_core.pipeline.adapters.baua import BauaAdapter
from normly_core.pipeline.domain import RawRecord


def _write_publication_pdf(path: Path, lines: list[str]) -> None:
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    # Y-coordinate and gap sizes are empirically tuned for this Docling version (2.124.0).
    # The specific values (700, 10, 60) ensure that in common test cases, designation and
    # title stay in one Docling item while body text moves to separate items. The i==1
    # special case creates a larger gap after the title to enforce this separation.
    y = 700  # Start in middle of page for better extraction
    for i, line in enumerate(lines):
        if line:  # Only draw non-empty lines
            pdf.drawString(72, y, line)
        # Small gap between designation/title; large gap before body
        if i == 1:
            y -= 60  # Large gap after title
        else:
            y -= 10  # Small gap for designation/title
    pdf.save()


@pytest.mark.parametrize(
    "prefix, designation, title, filename",
    [
        ("TRGS", "TRGS 900", "Arbeitsplatzgrenzwerte", "baua_trgs_900.pdf"),
        ("TRBS", "TRBS 1201", "Prüfung von Arbeitsmitteln", "baua_trbs_1201.pdf"),
        ("TRBA", "TRBA 100", "Schutzmaßnahmen für Tätigkeiten mit biologischen Arbeitsstoffen in Laboratorien", "baua_trba_100.pdf"),
    ],
)
def test_fetch_splits_designation_and_title_per_series(
    tmp_path, prefix, designation, title, filename
):
    _write_publication_pdf(
        tmp_path / filename,
        [
            designation,
            title,
            "",
            "Diese Regel konkretisiert die Anforderungen im Rahmen ihres Anwendungsbereichs.",
        ],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == designation
    assert record.raw_issuer == "BAuA"
    assert record.raw_title == title
    assert record.full_text is not None
    assert "konkretisiert die Anforderungen" in record.full_text
    assert record.language == "de"


def test_fetch_parses_a_teil_suffixed_designation(tmp_path):
    _write_publication_pdf(
        tmp_path / "baua_trgs_500_teil_1.pdf",
        ["TRGS 500 Teil 1", "Schutzmaßnahmen", "", "Body text hier."],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert records[0].raw_designation == "TRGS 500 Teil 1"
    assert records[0].raw_title == "Schutzmaßnahmen"


def test_fetch_reads_all_three_series_and_ignores_other_sources_files(tmp_path):
    """`--directory` means the directory, not one hardcoded filename in it,
    and the three series share one adapter (design spec, "Ziel dieses
    Teilprojekts")."""
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf", ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."]
    )
    _write_publication_pdf(
        tmp_path / "baua_trbs_1201.pdf", ["TRBS 1201", "Prüfung von Arbeitsmitteln", "", "Text."]
    )
    _write_publication_pdf(
        tmp_path / "baua_trba_100.pdf", ["TRBA 100", "Schutzmaßnahmen", "", "Text."]
    )
    # A neighbouring source's file in the same directory stays untouched.
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", ["DGUV Vorschrift 1", "Grundsätze", "", "Text."]
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert sorted(record.raw_designation for record in records) == [
        "TRBA 100", "TRBS 1201", "TRGS 900",
    ]


def test_fetch_leaves_title_unset_when_docling_merges_the_whole_page(tmp_path):
    """A continuously-set publication (no blank lines between paragraphs)
    causes Docling to merge designation, title, and at least the start of the
    body into a single text item. Without a length cap, the designation
    pattern's `(.*)$` tail would then capture body prose as its "title".
    The length cap (_MAX_TITLE_WORDS=12) must fail toward `title=None`,
    never toward a fabricated title -- and `full_text` must keep everything
    regardless."""
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf",
        [
            "TRGS 900 Arbeitsplatzgrenzwerte Diese TRGS konkretisiert im Rahmen des",
            "Vollzuges der Gefahrstoffverordnung die Anforderungen an die Ermittlung",
            "und Beurteilung der Konzentration von Gefahrstoffen am Arbeitsplatz.",
        ],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert records[0].raw_designation == "TRGS 900"
    assert records[0].raw_title is None
    assert "Ermittlung" in records[0].full_text
    assert "Beurteilung der Konzentration" in records[0].full_text


def test_fetch_skips_an_unreadable_file_and_keeps_reading_the_rest(tmp_path, capsys):
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf", ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."]
    )
    (tmp_path / "baua_trbs_1201.pdf").write_text("this is not a PDF")
    _write_publication_pdf(
        tmp_path / "baua_trba_100.pdf", ["TRBA 100", "Schutzmaßnahmen", "", "Text."]
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert sorted(record.raw_designation for record in records) == ["TRBA 100", "TRGS 900"]
    assert "baua_trbs_1201.pdf" in capsys.readouterr().err


def test_fetch_does_not_skip_a_misconfigured_pipeline(tmp_path, capsys, monkeypatch):
    """A broken deployment must end the run, not be skipped once per file --
    identical reasoning and pattern to dguv.py's/eur_lex.py's own test of
    the same name."""
    from normly_core.pipeline import docling_extraction
    from normly_core.pipeline.docling_extraction import PipelineInitializationError

    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf", ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."]
    )

    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(tmp_path / "no_models_here"))
    docling_extraction._converters.clear()
    try:
        with pytest.raises(PipelineInitializationError):
            list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())
    finally:
        docling_extraction._converters.clear()

    assert "skipping" not in capsys.readouterr().err


def test_extract_structure_returns_one_full_text_segment():
    adapter = BauaAdapter(directory=Path("."), source_id=uuid.uuid4())
    record = RawRecord(
        source_id=adapter.source_id, content_hash="sha256:x",
        raw_designation="TRGS 900", raw_issuer="BAuA", raw_title="Arbeitsplatzgrenzwerte",
        full_text="Volltext hier.", language="de",
    )

    sections = adapter.extract_structure(record)

    assert len(sections) == 1
    assert sections[0].sequence_number == 1
    assert sections[0].heading is None
    assert sections[0].text == "Volltext hier."


def test_extract_structure_is_empty_without_full_text():
    adapter = BauaAdapter(directory=Path("."), source_id=uuid.uuid4())
    record = RawRecord(
        source_id=adapter.source_id, content_hash="sha256:x",
        raw_designation="TRGS 900", raw_issuer="BAuA", raw_title=None,
        full_text=None, language="de",
    )

    assert adapter.extract_structure(record) == []


def test_classify_rights_allows_full_processing():
    adapter = BauaAdapter(directory=Path("."), source_id=uuid.uuid4())
    record = RawRecord(
        source_id=adapter.source_id, content_hash="sha256:x",
        raw_designation="TRGS 900", raw_issuer="BAuA", raw_title="Arbeitsplatzgrenzwerte",
        full_text="Volltext hier.", language="de",
    )

    rule = adapter.classify_rights(record)

    assert rule.may_process is True
    assert rule.may_index_fulltext is True
    assert rule.may_cite_passages is True
    assert rule.may_export_free is True
    assert rule.jurisdiction == "DE"
    assert "TRGS/TRBS/TRBA" in rule.legal_basis_reference
