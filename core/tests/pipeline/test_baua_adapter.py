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
    # special case creates a larger gap after the fixture's *second line* -- whatever its
    # content is (a title in most callers, but body prose for the whole-page-merge test)
    # -- to enforce this separation.
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


def test_fetch_normalizes_irregular_whitespace_before_matching_designation(tmp_path):
    """Docling can emit irregular whitespace (extra spaces, embedded
    newlines) inside a merged text item. The designation becomes this
    document's identity key (identity.resolve() matches on exact string
    equality; it flows into document.origin_number via runner.py), so an
    un-normalized whitespace difference between two PDFs of the *same* rule
    would fork them into two unrelated document nodes. The designation search
    tolerates any whitespace shape (`\\s+` matches a run of any length), but
    without normalizing first, that irregular run could be captured verbatim
    into the designation string -- the bug is not a failed match, it is a
    designation whose exact text varies with incidental source formatting."""
    _write_publication_pdf(
        tmp_path / "baua_trgs_500_teil_1.pdf",
        ["TRGS 500  Teil  1", "Schutzmaßnahmen", "", "Body text hier."],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert records[0].raw_designation == "TRGS 500 Teil 1"


def test_fetch_finds_designation_after_cover_matter(tmp_path):
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf",
        [
            "Ausgabe Juli 2025",
            "Technische Regeln für Gefahrstoffe",
            "TRGS 900 Arbeitsplatzgrenzwerte",
            "",
            "1 Anwendungsbereich",
            "Diese Regel gilt für Tätigkeiten mit Gefahrstoffen.",
        ],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_designation == "TRGS 900"
    # Cover text before the designation makes the adjacent tail ambiguous;
    # identity is recovered, but title extraction fails closed.
    assert records[0].raw_title is None


def test_fetch_leaves_designation_empty_when_front_matter_has_no_candidate(tmp_path):
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf",
        ["Ausgabe Juli 2025", "Allgemeine Veröffentlichung", "Text ohne Kennnummer."],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_designation == ""
    assert records[0].raw_title is None


def test_find_designation_ignores_mentions_after_the_front_matter():
    from types import SimpleNamespace

    from normly_core.pipeline.adapters.baua import _find_designation

    items = [
        SimpleNamespace(text="Ausgabe Juli 2025", prov=[SimpleNamespace(page_no=1)]),
        SimpleNamespace(text="TRGS 900 Titel", prov=[SimpleNamespace(page_no=1)]),
        SimpleNamespace(text="TRGS 901", prov=[SimpleNamespace(page_no=6)]),
    ]

    assert _find_designation(items) == ("TRGS 900", "Titel")


def test_find_designation_fails_closed_on_competing_front_matter_candidates():
    from types import SimpleNamespace

    from normly_core.pipeline.adapters.baua import _find_designation

    items = [
        SimpleNamespace(text="TRGS 900", prov=[SimpleNamespace(page_no=1)]),
        SimpleNamespace(text="TRGS 901", prov=[SimpleNamespace(page_no=2)]),
    ]

    assert _find_designation(items) == ("", None)


def test_filename_designation_hint_must_be_confirmed_in_front_matter():
    from types import SimpleNamespace

    from normly_core.pipeline.adapters.baua import _find_designation

    items = [
        SimpleNamespace(text="TRGS 900", prov=[SimpleNamespace(page_no=1)]),
        SimpleNamespace(text="TRGS 901", prov=[SimpleNamespace(page_no=2)]),
    ]

    assert _find_designation(items, filename_hint="TRGS 901") == ("TRGS 901", None)
    assert _find_designation(items, filename_hint="TRGS 902") == ("", None)


def test_designation_hint_from_filename_supports_parts():
    from normly_core.pipeline.adapters.baua import _designation_hint_from_filename

    assert _designation_hint_from_filename(Path("baua_trgs_500_teil_1.pdf")) == (
        "TRGS 500 Teil 1"
    )


def test_fetch_reads_all_three_series_and_ignores_other_sources_files(tmp_path):
    """`--directory` means the directory, not one hardcoded filename in it,
    and the three series share one adapter (design spec, "Goal of this
    sub-project")."""
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


def test_fetch_leaves_title_unset_when_docling_merges_designation_title_and_body(tmp_path):
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


def test_extract_structure_splits_numbered_headings_and_preserves_preamble():
    adapter = BauaAdapter(directory=Path("."), source_id=uuid.uuid4())
    record = RawRecord(
        source_id=adapter.source_id,
        content_hash="sha256:x",
        raw_designation="TRGS 900",
        raw_issuer="BAuA",
        raw_title=None,
        full_text=(
            "Cover information\n\n"
            "1 Scope\nBody for section one.\n\n"
            "2.1 Definitions\nBody for subsection 2.1.\n\n"
            "2.2 Duties\nBody for subsection 2.2."
        ),
        language="de",
    )

    sections = adapter.extract_structure(record)

    assert [section.sequence_number for section in sections] == [1, 2, 3, 4]
    assert [section.heading for section in sections] == [
        None, "1 Scope", "2.1 Definitions", "2.2 Duties",
    ]
    assert sections[0].text == "Cover information"
    assert sections[1].text == "Body for section one."
    assert sections[2].text == "Body for subsection 2.1."
    assert sections[3].text == "Body for subsection 2.2."


def test_extract_structure_keeps_numbered_prose_as_one_segment():
    adapter = BauaAdapter(directory=Path("."), source_id=uuid.uuid4())
    text = "1. This is a numbered sentence that continues as ordinary prose."
    record = RawRecord(
        source_id=adapter.source_id,
        content_hash="sha256:x",
        raw_designation="TRGS 900",
        raw_issuer="BAuA",
        raw_title=None,
        full_text=text,
        language="de",
    )

    sections = adapter.extract_structure(record)

    assert len(sections) == 1
    assert sections[0].heading is None
    assert sections[0].text == text


def test_numbered_heading_detector_uses_docling_labels_conservatively():
    from normly_core.pipeline.adapters.baua import _numbered_heading

    assert _numbered_heading("1 Scope", "section_header")
    assert _numbered_heading("2.1 Definitions", "list_item")
    assert not _numbered_heading("1 Scope", "list_item")
    assert not _numbered_heading("1 This is a sentence.", "section_header")
    assert not _numbered_heading("1 Scope", "text")


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
