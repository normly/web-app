# BAuA-Adapter (TRGS/TRBS/TRBA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `BauaAdapter` pipeline source that ingests BAuA's TRGS/TRBS/TRBA
technical-rule PDFs (one file per publication) into the graph, wired through the
existing source registry and CLI, satisfying REQ-PIPE-009's explicit mention of BAuA
alongside DGUV and EUR-Lex.

**Architecture:** One new adapter class, `BauaAdapter`, in
`core/src/normly_core/pipeline/adapters/baua.py`, built on the same shared
`docling_extraction.extract_document()` layer the DGUV and EUR-Lex adapters already
use. It reads three file-glob prefixes (one per rule series) under one publisher
registry entry, splits designation/title off the first extracted text element with a
single shared regex, and — deliberately, per the approved design — returns the whole
document as **one** full-text segment rather than building numbered-section detection
in this pass.

**Tech Stack:** Python 3.11+, `docling` (via the existing `docling_extraction` module,
no new dependency), `reportlab` (dev-only, test fixtures), `pytest`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-01-baua-adapter-design.md` — every task
  below implements a specific section of it; deviating from it needs a spec update
  first, not a silent code change.
- New source file needs the AGPL-3.0-or-later SPDX header + normly contributors
  copyright line, exactly matching `dguv.py`'s first two lines (CLAUDE.md).
- Every commit needs `Signed-off-by: normly <anonymous-jw@pm.me>` (DCO, CLAUDE.md).
- One `BauaAdapter` covers all three series (TRGS, TRBS, TRBA) under a single registry
  entry, publisher `"BAuA"` — not three adapters (spec, "Ziel dieses Teilprojekts").
- Legal basis category is **A** (amtliches Werk, § 5 UrhG "amtliche Bekanntmachungen")
  — same tier as the existing `"dguv"`/`"eur-lex"` registry entries (spec,
  "Rechtegrundlage: Kategorie A").
- `extract_structure()` returns exactly one segment holding the full document text,
  `heading=None` — no numbered-section splitting in this pass (spec, "Entscheidung:
  Struktur-Tiefe Phase 1"). Do not add heading detection as part of this plan.
- File-glob convention: `baua_trgs_*.pdf`, `baua_trbs_*.pdf`, `baua_trba_*.pdf` (spec,
  "Dateikonvention").
- No committed binary fixture PDFs for this adapter (deviates slightly from the DGUV/
  EUR-Lex precedent of one committed fixture each) — Phase 1 has no persistent
  "verify Docling's real element-classification behavior" assertion to anchor a fixed
  file against (see the DGUV design spec's "Empirischer Befund", which does not apply
  here since Phase 1 never inspects element types, only item text). All BAuA test
  fixtures are generated at test time with `reportlab`, same helper pattern
  `test_dguv_adapter.py` already uses.

---

### Task 1: `BauaAdapter` — fetch, designation/title split, structure, rights

**Files:**
- Create: `core/src/normly_core/pipeline/adapters/baua.py`
- Test: `core/tests/pipeline/test_baua_adapter.py`

**Interfaces:**
- Consumes: `normly_core.pipeline.docling_extraction.extract_document(path: Path) -> DoclingDocument`, `DocumentExtractionError`, `report_skipped_source(path: Path, error: Exception) -> None` (all already exist, same signatures `dguv.py`/`eur_lex.py` use). `normly_core.pipeline.domain.RawRecord`, `RawSection`, `RightsRule` (already exist, same shapes `dguv.py` uses).
- Produces: `BauaAdapter(directory: Path, source_id: uuid.UUID)` (keyword-only, matching `DguvAdapter`/`EurLexAdapter`) with `.fetch() -> Iterable[RawRecord]`, `.extract_structure(record: RawRecord) -> list[RawSection]`, `.classify_rights(record: RawRecord) -> RightsRule`. Task 2 imports this class by name from `normly_core.pipeline.adapters.baua`.

- [ ] **Step 1: Write the failing test for basic designation/title split, parametrized over all three series**

```python
# core/tests/pipeline/test_baua_adapter.py
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
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.pipeline.adapters.baua'`

- [ ] **Step 3: Write the minimal adapter implementation**

```python
# core/src/normly_core/pipeline/adapters/baua.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.pipeline.docling_extraction import (
    DocumentExtractionError,
    extract_document,
    report_skipped_source,
)
from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

# BAuA's three technical-rule series share one designation shape: a series
# prefix, a running number, and an optional "Teil N" suffix for a
# multi-part rule (e.g. "TRGS 500 Teil 1"). See design spec, "Designation-
# Erkennung".
_DESIGNATION_PATTERN = re.compile(
    r"^(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)\s*(.*)$"
)

# A title's own first line is short. Phase 1 deliberately runs no
# sentence-boundary heuristic (see design spec) -- but a continuously-set
# publication (see docs/superpowers/specs/2026-08-30-docling-migration-design.md,
# "Empirischer Befund") merges the *entire* page into one Docling text item,
# and without any bound the pattern's `(.*)$` tail would then capture the
# whole document as its "title". A bare length cap is not a sentence
# heuristic: it only ever costs a missed title (falls back to `None`, same
# as an unmatched designation), never a fabricated one, and `full_text`
# keeps the complete text regardless.
_MAX_TITLE_WORDS = 12

# One glob per series so a directory holding several BAuA series -- or a
# neighbouring source's files, as the DGUV/EUR-Lex fixtures already share
# one -- is read correctly.
_FILE_PATTERNS = ("baua_trgs_*.pdf", "baua_trbs_*.pdf", "baua_trba_*.pdf")


class BauaAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        paths = sorted(
            path for pattern in _FILE_PATTERNS for path in self.directory.glob(pattern)
        )
        for pdf_path in paths:
            # One unreadable file must cost only that file -- the runner
            # cannot isolate a failure raised inside fetch() itself (it
            # surfaces while pulling the next record, outside the runner's
            # per-record guard, and a generator that raised cannot be
            # resumed), so the adapter does it here and reports on stderr
            # instead of aborting the run. See dguv.py/eur_lex.py for the
            # identical pattern.
            #
            # DocumentExtractionError only: a PipelineInitializationError is
            # a broken deployment, not a broken file, and must end the run
            # rather than be skipped once per file.
            try:
                yield from self._fetch_file(pdf_path)
            except DocumentExtractionError as error:
                report_skipped_source(pdf_path, error)

    def _fetch_file(self, pdf_path: Path) -> Iterable[RawRecord]:
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

        document = extract_document(pdf_path)
        texts = [
            text for item, _level in document.iterate_items()
            if (text := getattr(item, "text", None))
        ]
        first_text = texts[0] if texts else ""

        match = _DESIGNATION_PATTERN.match(first_text)
        if match:
            designation = f"{match.group(1)} {match.group(2)}"
            tail = match.group(3).strip()
            title = tail if tail and len(tail.split()) <= _MAX_TITLE_WORDS else None
        else:
            designation = first_text
            title = None

        yield RawRecord(
            source_id=self.source_id,
            content_hash=content_hash,
            raw_designation=designation,
            raw_issuer="BAuA",
            raw_title=title,
            full_text="\n".join(texts),
            language="de",
            fetched_at=datetime.now(timezone.utc),
        )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        # Phase 1 (design spec, "Entscheidung: Struktur-Tiefe Phase 1"): one
        # segment holding the whole document, no numbered-section splitting
        # yet -- deliberately deferred, not forgotten.
        if record.full_text is None:
            return []
        return [RawSection(sequence_number=1, heading=None, text=record.full_text)]

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: every
        # TRGS/TRBS/TRBA is an amtliche Bekanntmachung, so this source is
        # always classifiable and never hands the runner a "cannot
        # classify". See design spec, "Rechtegrundlage: Kategorie A".
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference=(
                "§ 5 UrhG — amtliche Bekanntmachung (TRGS/TRBS/TRBA, BAuA im GMBl)"
            ),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (3 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/pipeline/adapters/baua.py core/tests/pipeline/test_baua_adapter.py
git commit -m "feat: add BauaAdapter with designation/title extraction

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 6: Write the failing test for the "Teil N" suffix**

```python
def test_fetch_parses_a_teil_suffixed_designation(tmp_path):
    _write_publication_pdf(
        tmp_path / "baua_trgs_500_teil_1.pdf",
        ["TRGS 500 Teil 1", "Schutzmaßnahmen", "", "Body text hier."],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert records[0].raw_designation == "TRGS 500 Teil 1"
    assert records[0].raw_title == "Schutzmaßnahmen"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py::test_fetch_parses_a_teil_suffixed_designation -v`
Expected: FAIL — `_DESIGNATION_PATTERN`'s number group is `\d+`, so it stops before
`Teil 1` and the designation comes back as `"TRGS 500"` with title `"Teil 1
Schutzmaßnahmen"`.

*(This step should already pass if Step 3's pattern — which includes `(?:\s+Teil\s+\d+)?`
in the number group — was copied verbatim. If it fails, the pattern in `baua.py` was
not copied exactly as written in Step 3; fix it to match, do not weaken the test.)*

- [ ] **Step 8: Confirm the test passes with no further code change**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (4 tests total)

- [ ] **Step 9: Commit**

```bash
git add core/tests/pipeline/test_baua_adapter.py
git commit -m "test: cover the BAuA 'Teil N' designation suffix

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 10: Write the failing test for multi-series directory reads and ignoring other sources' files**

```python
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
```

- [ ] **Step 11: Run test to verify it fails**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py::test_fetch_reads_all_three_series_and_ignores_other_sources_files -v`
Expected: PASS already, since Step 3's implementation globs all three patterns and
each pattern is series-specific by construction. If it fails, `_FILE_PATTERNS` in
`baua.py` was not copied exactly as written in Step 3.

- [ ] **Step 12: Run the full file and commit**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (5 tests total)

```bash
git add core/tests/pipeline/test_baua_adapter.py
git commit -m "test: cover BauaAdapter reading all three series from one directory

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 13: Write the failing test for the title length-cap safety net**

```python
def test_fetch_leaves_title_unset_when_docling_merges_the_whole_page(tmp_path):
    """A continuously-set publication (no blank lines between paragraphs)
    makes Docling merge the entire page into one text item -- verified
    behavior for this document family, see
    docs/superpowers/specs/2026-08-30-docling-migration-design.md,
    "Empirischer Befund". Without a bound, the designation pattern's `(.*)$`
    tail would then capture the rest of the document as its "title". The
    length cap must fail toward `title=None`, never toward a fabricated
    title -- and `full_text` must keep everything regardless."""
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
```

- [ ] **Step 14: Run test to verify it fails**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py::test_fetch_leaves_title_unset_when_docling_merges_the_whole_page -v`
Expected: PASS already if `_MAX_TITLE_WORDS` from Step 3 was copied verbatim (the
merged tail is far longer than 12 words). If it fails — i.e. `raw_title` is not
`None` — the cap was omitted or set too high; fix `baua.py` to match Step 3 exactly,
do not loosen this assertion.

- [ ] **Step 15: Run the full file and commit**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (6 tests total)

```bash
git add core/tests/pipeline/test_baua_adapter.py
git commit -m "test: cover the BAuA title length-cap safety net

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 16: Write the failing tests for error isolation (unreadable file, misconfigured pipeline)**

```python
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
```

- [ ] **Step 17: Run tests to verify they fail or pass as expected**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -k "unreadable or misconfigured" -v`
Expected: both PASS already — `fetch()`'s per-file `try/except DocumentExtractionError`
from Step 3 already implements this. If either fails, `baua.py`'s `fetch()` was not
copied exactly as written in Step 3.

- [ ] **Step 18: Run the full file and commit**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (8 tests total)

```bash
git add core/tests/pipeline/test_baua_adapter.py
git commit -m "test: cover BauaAdapter error isolation

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 19: Write the failing tests for `extract_structure` and `classify_rights`**

```python
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
```

- [ ] **Step 20: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/pipeline/test_baua_adapter.py -v`
Expected: PASS (11 tests total) — Step 3's `extract_structure()`/`classify_rights()`
already implement this.

- [ ] **Step 21: Commit**

```bash
git add core/tests/pipeline/test_baua_adapter.py
git commit -m "test: cover BauaAdapter.extract_structure and classify_rights

Signed-off-by: normly <anonymous-jw@pm.me>"
```

---

### Task 2: Source registry entry and CLI wiring

**Files:**
- Modify: `core/src/normly_core/pipeline/sources.py`
- Modify: `core/src/normly_core/pipeline/cli.py`
- Modify: `core/tests/pipeline/test_cli.py`

**Interfaces:**
- Consumes: `BauaAdapter` from Task 1 (`normly_core.pipeline.adapters.baua.BauaAdapter(directory: Path, source_id: uuid.UUID)`). `SourceRegistryEntry`, `SOURCE_REGISTRY`, `resolve_source` (already exist, unchanged shape). `build_adapter(source: str, *, directory: Path, session: Session) -> SourceAdapter` (already exists in `cli.py`, unchanged signature — only its body and the `choices=` list grow a `"baua"` case).
- Produces: `build_adapter("baua", ...)` returns a working `BauaAdapter` bound to a resolved `"BAuA"` `Source` row. `python -m normly_core.pipeline ingest baua --directory <dir>` works end to end.

- [ ] **Step 1: Write the failing test for the registry entry and CLI wiring**

```python
# core/tests/pipeline/test_cli.py -- add near the existing build_adapter tests

def test_build_adapter_returns_baua_adapter_for_baua_source(db_session):
    adapter = build_adapter("baua", directory=FIXTURE_DIR, session=db_session)
    assert type(adapter).__name__ == "BauaAdapter"


def test_build_adapter_registers_baua_with_category_a(db_session):
    adapter = build_adapter("baua", directory=FIXTURE_DIR, session=db_session)

    registered = db_session.get(SourceORM, adapter.source_id)
    assert registered is not None
    assert registered.publisher == "BAuA"
    assert registered.jurisdiction == "DE"
```

Also add, near `test_main_ingests_a_directory_end_to_end`:

```python
def test_main_ingests_a_baua_directory_end_to_end(committed_db, capsys, tmp_path):
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(tmp_path / "baua_trgs_900.pdf"))
    for y, line in zip(
        range(800, 700, -20),
        ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."],
    ):
        pdf.drawString(72, y, line)
    pdf.save()

    exit_code = main(["ingest", "baua", "--directory", str(tmp_path)])

    assert exit_code == 0
    assert "failed=0" in capsys.readouterr().out
    with committed_db.connect() as connection:
        designation = connection.execute(
            sa.select(DocumentDesignationORM.designation).where(
                DocumentDesignationORM.issuer == "BAuA"
            )
        ).scalar_one()
    assert designation == "TRGS 900"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && python -m pytest tests/pipeline/test_cli.py -k baua -v`
Expected: FAIL — `build_adapter` raises `ValueError: unknown source: 'baua'` for the
first two; the CLI test fails the same way via `main()`.

- [ ] **Step 3: Add the registry entry**

In `core/src/normly_core/pipeline/sources.py`, add to `SOURCE_REGISTRY` (after the
existing `"dguv"` entry):

```python
    "baua": SourceRegistryEntry(
        publisher="BAuA",
        retrieval_path="https://www.baua.de/DE/Angebote/Regelwerk",
        # TRGS/TRBS/TRBA sind amtliche Bekanntmachungen einer
        # Bundesoberbehörde (BAuA im GMBl) -- § 5 UrhG, wie die DGUV- und
        # EUR-Lex-Einträge. Siehe design spec, "Rechtegrundlage: Kategorie A".
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 9, 1),
        responsible_person="J. Weber",
    ),
```

- [ ] **Step 4: Wire the CLI**

In `core/src/normly_core/pipeline/cli.py`:

```python
from normly_core.pipeline.adapters.baua import BauaAdapter
```

(added alongside the existing `DguvAdapter`/`EurLexAdapter` imports). In
`build_adapter()`, add before the final `raise ValueError`:

```python
    if source == "baua":
        return BauaAdapter(directory=directory, source_id=registered.id)
```

And in `main()`'s argparse setup:

```python
    ingest_parser.add_argument("source", choices=["eur-lex", "dguv", "baua"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && python -m pytest tests/pipeline/test_cli.py -v`
Expected: PASS, all tests including the three new ones and the pre-existing ones
(check nothing else regressed).

- [ ] **Step 6: Run the full pipeline test suite**

Run: `cd core && python -m pytest tests/pipeline/ -v`
Expected: PASS, all tests (Task 1's `test_baua_adapter.py` included).

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/pipeline/sources.py core/src/normly_core/pipeline/cli.py core/tests/pipeline/test_cli.py
git commit -m "feat: register BAuA as a pipeline source and wire it into the CLI

Signed-off-by: normly <anonymous-jw@pm.me>"
```

---

## After both tasks

- Run the full `core` test suite once more (`cd core && python -m pytest -v`) to
  confirm nothing outside `tests/pipeline/` regressed.
- Update `docs/superpowers/specs/2026-09-01-baua-adapter-design.md`'s "Offene Punkte"
  is already accurate as written (real-document verification and automated procurement
  remain open) — no spec edit needed unless implementation surfaced a new deviation.
- Update the `project_baua_adapter_brainstorm` memory to reflect completion once this
  plan is fully executed and committed (out of scope for the plan itself — a
  post-implementation housekeeping step, same as done for the Docling migration and
  Sub-project 3).
