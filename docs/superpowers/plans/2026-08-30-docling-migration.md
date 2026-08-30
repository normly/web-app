# Docling Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `pdfplumber` with `docling` as the PDF-extraction engine
for both existing ingestion adapters (`DguvAdapter`, `EurLexAdapter`),
behind a new shared extraction layer that future adapters can reuse without
duplicating Docling configuration.

**Architecture:** A new `docling_extraction.py` module wraps
`docling.document_converter.DocumentConverter` with OCR disabled and a
configurable local model path, returning a `DoclingDocument` per file. Each
adapter keeps its own small, source-specific logic to map that document
into `RawRecord`/`RawSection` domain objects — DGUV via pattern-matched
text segments, EUR-Lex via table cells.

**Tech Stack:** Python (`core/`), `docling` (MIT, replaces `pdfplumber`),
existing `pytest` + real fixture PDFs.

## Global Constraints

- Every new/modified source file keeps its two-line SPDX header,
  `AGPL-3.0-or-later`.
- DCO `Signed-off-by` on every commit (`git commit -s`).
- Database access only through the repository layer (ADR-006) — not
  directly relevant to this plan's files, but do not introduce any.
- `PdfPipelineOptions(do_ocr=False)` is **required**, not optional — Docling's
  default pipeline runs OCR even on pure vector-text PDFs and pulls extra
  models from `modelscope.cn` (not Hugging Face) if OCR stays enabled.
  Empirically verified during design (see
  `docs/superpowers/specs/2026-08-30-docling-migration-design.md`).
- Docling must **never** attempt a network fetch for models at runtime in
  production (STACKIT-only constraint, `CLAUDE.md`). The extraction layer
  reads a `NORMLY_DOCLING_ARTIFACTS_PATH` environment variable; when set, it
  points `PdfPipelineOptions.artifacts_path` at that pre-populated directory.
  When unset (local development), Docling manages its own cache and
  downloads on first use — acceptable for development, not for production.
- **No Dockerfile or CI pipeline changes in this plan** — none exist yet
  anywhere in the repository, and creating the first one is out of scope
  for a library swap. This plan only produces the code-level requirement
  (the env var above) and documents the exact command
  (`docling-tools models download layout tableformer -o <path>`) needed to
  populate that directory — a future containerization effort wires this in.
- **No generic Docling→domain-object mapping abstraction.** Each adapter
  keeps its own small mapping logic (YAGNI — the ingestion spec already
  rejected a generic, config-driven adapter once).
- Structure/boundary detection for a given source is **pattern-based on
  Docling's segmented text**, never blind trust in Docling's semantic
  element classification (`SectionHeaderItem` vs. `ListItem` vs.
  `TextItem`) without first verifying that classification against a real
  fixture of that source — verified empirically during design that
  `SectionHeaderItem` is not reliable for DGUV's plainly-formatted §-headings
  (they come back as `ListItem`). See the design doc's "Entscheidungsverfahren
  für künftige Adapter" for the procedure every future adapter should follow.

---

### Task 1: Shared Docling extraction layer (`core/`)

**Files:**
- Create: `core/src/normly_core/pipeline/docling_extraction.py`
- Modify: `core/pyproject.toml` (add `docling` dependency)
- Test: `core/tests/pipeline/test_docling_extraction.py`

**Interfaces:**
- Consumes: nothing new (fixture PDFs already exist at
  `core/tests/fixtures/dguv_sample_vorschrift.pdf` and
  `eur_lex_machinery_summary.pdf`).
- Produces: `extract_document(path: Path) -> DoclingDocument` and
  `DocumentExtractionError` (both importable from
  `normly_core.pipeline.docling_extraction`) — consumed by Tasks 2 and 3.

This is the first task to touch Docling in this codebase. Running it for
the first time (locally, without `NORMLY_DOCLING_ARTIFACTS_PATH` set) will
download Docling's layout and table-structure models from Hugging Face —
this requires network access once; subsequent runs use the local cache.

- [ ] **Step 1: Add the dependency**

In `core/pyproject.toml`, replace the `pdfplumber` line in
`[project].dependencies` (do not remove it yet — Task 3 removes it once the
last consumer is migrated) by adding `docling` alongside it:

```toml
dependencies = [
    "sqlalchemy>=2.0,<3.0",
    "alembic>=1.13,<2.0",
    "psycopg[binary]>=3.1,<4.0",
    "pgvector>=0.3,<0.4",
    "sentence-transformers>=3.0,<4.0",
    "pdfplumber>=0.11,<0.12",
    "docling>=2.123,<3.0",
]
```

Run `cd core && .venv/bin/python -m pip install -e ".[dev]"` to pick up the
new dependency. This will download a substantial dependency chain (torch is
already present from `sentence-transformers`, but Docling adds its own
layout/table models, `docling-ibm-models`, `docling-parse`, and others) —
expect this install to take a few minutes.

- [ ] **Step 2: Write the failing test**

```python
# core/tests/pipeline/test_docling_extraction.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest

from normly_core.pipeline.docling_extraction import DocumentExtractionError, extract_document

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_extract_document_returns_text_content_for_a_real_pdf():
    document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")

    texts = [
        item.text
        for item, _level in document.iterate_items()
        if hasattr(item, "text") and item.text
    ]
    assert any("§ 1 Geltungsbereich" in t for t in texts)


def test_extract_document_returns_tables_for_a_real_pdf():
    document = extract_document(FIXTURE_DIR / "eur_lex_machinery_summary.pdf")

    assert len(document.tables) >= 1
    first_row = document.tables[0].data.grid[0]
    assert any(cell is not None and "ESO" in cell.text for cell in first_row)


def test_extract_document_raises_a_normly_error_on_a_corrupt_file(tmp_path):
    corrupt = tmp_path / "not_a_real.pdf"
    corrupt.write_text("this is not a PDF")

    with pytest.raises(DocumentExtractionError):
        extract_document(corrupt)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_docling_extraction.py -v`
Expected: FAIL — `normly_core.pipeline.docling_extraction` doesn't exist yet.

- [ ] **Step 4: Write the extraction layer**

```python
# core/src/normly_core/pipeline/docling_extraction.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Shared Docling document-extraction layer for all pipeline adapters.

Production/CI requirement (STACKIT-only constraint -- no runtime access to
external model sources, see CLAUDE.md): before deploying, pre-fetch
Docling's layout and table-structure models once with

    docling-tools models download layout tableformer -o <path>

and set NORMLY_DOCLING_ARTIFACTS_PATH to <path> in the runtime environment.
With that set, extract_document() never attempts a network connection
(verified by tests/pipeline/test_docling_offline.py). Without it (e.g.
local development), Docling manages its own cache directory and downloads
models on first use -- convenient for development, not acceptable in
production.

OCR is deliberately disabled (do_ocr=False): Docling's default pipeline
runs OCR even on pure vector-text PDFs like the two sources this codebase
ingests today, and does so by downloading additional models from
modelscope.cn -- a second external model source beyond Hugging Face that
this project has no reason to depend on before an actual OCR need exists.
"""

from __future__ import annotations

import os
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError as _DoclingConversionError
from docling_core.types.doc import DoclingDocument

_ARTIFACTS_PATH_ENV = "NORMLY_DOCLING_ARTIFACTS_PATH"


class DocumentExtractionError(Exception):
    """Raised when Docling cannot parse a source file."""


def extract_document(path: Path) -> DoclingDocument:
    artifacts_path_value = os.environ.get(_ARTIFACTS_PATH_ENV)
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        artifacts_path=Path(artifacts_path_value) if artifacts_path_value else None,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    try:
        result = converter.convert(path)
    except _DoclingConversionError as exc:
        raise DocumentExtractionError(f"Docling could not parse {path}: {exc}") from exc
    return result.document
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_docling_extraction.py -v`
Expected: PASS (3 tests). The first run downloads Docling's models (one-time,
needs network); subsequent runs are fast from the local cache.

- [ ] **Step 6: Run the full `core/` suite to confirm no regressions**

Run: `cd core && .venv/bin/python -m pytest -v`
Expected: all pass (pdfplumber-based adapters are untouched so far — this
task only adds new, independent code).

- [ ] **Step 7: Commit**

```bash
git add core/pyproject.toml core/src/normly_core/pipeline/docling_extraction.py \
  core/tests/pipeline/test_docling_extraction.py
git commit -s -m "feat: add a shared Docling document-extraction layer"
```

---

### Task 2: Migrate `DguvAdapter` to Docling (`core/`)

**Files:**
- Modify: `core/src/normly_core/pipeline/adapters/dguv.py`
- Test: `core/tests/pipeline/test_dguv_adapter.py` (extend)

**Interfaces:**
- Consumes: `extract_document`, `DocumentExtractionError` (Task 1).
- Produces: nothing new — `DguvAdapter`'s public shape (`fetch()`,
  `extract_structure()`, `classify_rights()`) is unchanged, only its
  internals change.

Only `fetch()` needs to change. `extract_structure()` and
`classify_rights()` stay **completely untouched** — verified during design
that `extract_structure()` already operates purely on `record.full_text`
(via `.splitlines()`), and `fetch()`'s new code still produces a `full_text`
string with the same one-segment-per-line shape Docling's items give,
joined with `"\n"`. The existing regex-based boundary logic keeps working
unmodified against that string — this is a deliberate design choice (see
`docs/superpowers/specs/2026-08-30-docling-migration-design.md`,
"Empirischer Befund"), not an oversight.

- [ ] **Step 1: Write the failing test for the classification finding**

Add this test to the existing `core/tests/pipeline/test_dguv_adapter.py`
(the file already exists — add this as one more test in it, do not replace
the file):

```python
def test_docling_classifies_paragraph_headings_as_list_items_not_section_headers():
    """
    Documents a real, empirically verified Docling behavior (2.123.1):
    §-paragraph headings in DGUV-style plainly-formatted legal text come
    back as ListItem, not SectionHeaderItem -- Docling's layout model has
    no visual cue (larger font, boldness, spacing) to distinguish them from
    a numbered list. This is exactly why extract_structure() stays
    pattern-based instead of trusting Docling's element classification --
    see docs/superpowers/specs/2026-08-30-docling-migration-design.md,
    "Empirischer Befund" and "Entscheidungsverfahren für künftige Adapter".

    If this test starts failing after a future Docling version upgrade,
    that is a deliberate signal that the classification behavior changed --
    re-run the decision procedure in the design doc, do not just delete or
    "fix" this assertion.
    """
    from docling_core.types.doc import ListItem, SectionHeaderItem

    from normly_core.pipeline.docling_extraction import extract_document

    document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")
    known_headings = {
        "§ 1 Geltungsbereich", "§ 2 Pflichten des Unternehmers",
        "§ 3 Pflichten der Versicherten",
    }
    heading_items = [
        item for item, _level in document.iterate_items()
        if getattr(item, "text", None) in known_headings
    ]

    assert len(heading_items) == 3
    assert all(isinstance(item, ListItem) for item in heading_items)
    assert not any(isinstance(item, SectionHeaderItem) for item in heading_items)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_dguv_adapter.py::test_docling_classifies_paragraph_headings_as_list_items_not_section_headers -v`
Expected: FAIL — `DguvAdapter.fetch()` still uses `pdfplumber`, unrelated to
this test's own direct use of `extract_document`, but this test can already
run once Task 1 is in place; it should pass immediately since it only calls
`extract_document` directly. If it does NOT pass as written, stop and
re-verify the classification finding empirically against the real fixture
before proceeding — do not adjust the assertion to make it pass without
understanding why the behavior differed from what's documented above.

- [ ] **Step 3: Run it to confirm it actually passes on its own**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_dguv_adapter.py::test_docling_classifies_paragraph_headings_as_list_items_not_section_headers -v`
Expected: PASS. (This test doesn't depend on `DguvAdapter`'s internals at
all — it directly verifies the Docling behavior the rest of this task's
design relies on. Steps 2-3 exist to make you actually run and observe this
before writing the adapter code that depends on it.)

- [ ] **Step 4: Rewrite `fetch()`**

Replace the full content of `core/src/normly_core/pipeline/adapters/dguv.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.pipeline.docling_extraction import extract_document
from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

_HEADING_PATTERN = re.compile(r"^§\s*\d+\s+.+")

# Docling merges visually adjacent lines into one text block -- the
# fixture's designation ("DGUV Vorschrift 1") and title ("Grundsätze der
# Prävention") are two separate lines in the source PDF but arrive as a
# single Docling text item, unlike pdfplumber's per-line output. Split them
# back apart by the designation's known "DGUV Vorschrift <N>" prefix rather
# than assuming two separate elements.
_DESIGNATION_PATTERN = re.compile(r"^(DGUV Vorschrift \d+)\s*(.*)$")

# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of DGUV publications.
_FILE_PATTERN = "dguv_*.pdf"


class DguvAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        for pdf_path in sorted(self.directory.glob(_FILE_PATTERN)):
            content = pdf_path.read_bytes()
            content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

            document = extract_document(pdf_path)
            texts = [
                item.text
                for item, _level in document.iterate_items()
                if hasattr(item, "text") and item.text
            ]

            first = texts[0].strip() if texts else ""
            match = _DESIGNATION_PATTERN.match(first)
            if match:
                designation = match.group(1)
                title = match.group(2).strip() or None
            else:
                designation = first
                title = None
            full_text = "\n".join(texts)

            yield RawRecord(
                source_id=self.source_id,
                content_hash=content_hash,
                raw_designation=designation,
                raw_issuer="DGUV",
                raw_title=title,
                full_text=full_text,
                language="de",
                fetched_at=datetime.now(timezone.utc),
            )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        assert record.full_text is not None
        lines = record.full_text.splitlines()

        sections: list[RawSection] = []
        current_heading: str | None = None
        current_body: list[str] = []
        sequence_number = 0

        def _flush() -> None:
            nonlocal sequence_number
            if current_heading is None:
                return
            sequence_number += 1
            sections.append(
                RawSection(
                    sequence_number=sequence_number,
                    heading=current_heading,
                    text=" ".join(line.strip() for line in current_body if line.strip()),
                )
            )

        for line in lines:
            if _HEADING_PATTERN.match(line.strip()):
                _flush()
                current_heading = line.strip()
                current_body = []
            elif current_heading is not None:
                current_body.append(line)
        _flush()

        return sections

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: every
        # DGUV-Vorschrift is an amtliches Werk, so this source is always
        # classifiable and never hands the runner a "cannot classify".
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG — amtliches Werk (DGUV-Vorschrift)",
        )
```

- [ ] **Step 5: Run the DGUV adapter's full test file**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_dguv_adapter.py -v`
Expected: PASS (all existing tests plus the new classification test — 6
tests total). The pre-existing assertions
(`record.raw_designation == "DGUV Vorschrift 1"`,
`record.raw_title == "Grundsätze der Prävention"`,
`sections[0].heading == "§ 1 Geltungsbereich"`, etc.) all pass unchanged —
this was verified against real Docling output during design, not assumed.
If any of them fail, do not adjust the assertions — re-check the
`_DESIGNATION_PATTERN`/`_HEADING_PATTERN` logic against the actual Docling
output for the fixture first.

- [ ] **Step 6: Run the full `core/` suite**

Run: `cd core && .venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/pipeline/adapters/dguv.py core/tests/pipeline/test_dguv_adapter.py
git commit -s -m "feat: migrate DguvAdapter from pdfplumber to Docling"
```

---

### Task 3: Migrate `EurLexAdapter` to Docling and remove pdfplumber (`core/`)

**Files:**
- Modify: `core/src/normly_core/pipeline/adapters/eur_lex.py`
- Modify: `core/pyproject.toml` (remove `pdfplumber` — last consumer)
- Test: `core/tests/pipeline/test_eur_lex_adapter.py` (unchanged, run as
  regression)

**Interfaces:**
- Consumes: `extract_document` (Task 1).
- Produces: nothing new — `EurLexAdapter`'s public shape is unchanged.

- [ ] **Step 1: Rewrite `_fetch_file()`**

Replace the full content of `core/src/normly_core/pipeline/adapters/eur_lex.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.docling_extraction import extract_document
from normly_core.pipeline.domain import (
    RawRecord,
    RawReference,
    RawSection,
    RightsRule,
)

# Column indices in the Commission's "Summary list of harmonised standards"
# table, 0-based -- verified against the real fixture PDF's Docling table
# extraction (`table.data.grid`): ['Legislation reference (A)', 'ESO (B)',
# 'Reference number of the standard (C)', 'Title of the standard (D)',
# 'Type (E)', ...]. Same column layout Docling produces as pdfplumber did.
# Unlike pdfplumber, Docling's header cells carry no embedded line break
# ("ESO (B)", not pdfplumber's "ESO\n(B)") -- the prefix filter below still
# works correctly either way, so it's kept rather than narrowed to an exact
# match.
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3

# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of Commission summary lists.
_FILE_PATTERN = "eur_lex_*.pdf"


class EurLexAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID, legislation_reference: str):
        self.directory = directory
        self.source_id = source_id
        self.legislation_reference = legislation_reference

    def fetch(self) -> Iterable[RawRecord]:
        for pdf_path in sorted(self.directory.glob(_FILE_PATTERN)):
            yield from self._fetch_file(pdf_path)

    def _fetch_file(self, pdf_path: Path) -> Iterable[RawRecord]:
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        now = datetime.now(timezone.utc)

        yield RawRecord(
            source_id=self.source_id,
            content_hash=f"{content_hash}:legal-act",
            raw_designation=self.legislation_reference,
            raw_issuer="EU",
            raw_title=None,
            full_text=None,
            # The Commission publishes this summary list in English.
            language="en",
            fetched_at=now,
        )

        document = extract_document(pdf_path)
        seen_designations: set[str] = set()
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_TITLE:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                title_cell = row[_COLUMN_TITLE]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                title = (title_cell.text if title_cell else "").strip()
                if not eso or not designation or eso.startswith("ESO"):
                    continue
                if designation in seen_designations:
                    continue
                seen_designations.add(designation)
                yield RawRecord(
                    source_id=self.source_id,
                    content_hash=f"{content_hash}:{designation}",
                    raw_designation=designation,
                    raw_issuer=eso,
                    raw_title=title or None,
                    full_text=None,
                    language="en",
                    raw_references=[
                        RawReference(
                            target_issuer="EU",
                            target_designation=self.legislation_reference,
                            edge_type=EdgeType.BASED_ON_LAW,
                        )
                    ],
                    fetched_at=now,
                )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        return []

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: the
        # Commission's summary list carries no standard full text, so every
        # record it yields is classifiable and never returns "cannot classify".
        if record.raw_designation == self.legislation_reference:
            return RightsRule(
                jurisdiction="EU", may_process=True, may_index_fulltext=False,
                may_cite_passages=False, may_export_free=True,
                legal_basis_reference="§ 5 UrhG / amtliches Werk (Rechtsakt)",
            )
        return RightsRule(
            jurisdiction="EU", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True,
            legal_basis_reference="Kategorie A — Kommissions-Zusammenfassung, kein Normvolltext",
        )
```

- [ ] **Step 2: Run the EUR-Lex adapter's test file**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_eur_lex_adapter.py -v`
Expected: PASS (all 5 existing tests, unchanged assertions — verified
against real Docling output during design: 7 standard records found for
the fixture, first one has `raw_issuer == "CEN"` and
`"EN ISO 12100" in raw_designation`, matching `test_fetch_yields_standard_records_with_based_on_law_reference`).

- [ ] **Step 3: Remove pdfplumber — this was its last consumer**

In `core/pyproject.toml`, remove the `pdfplumber` line from
`[project].dependencies`:

```toml
dependencies = [
    "sqlalchemy>=2.0,<3.0",
    "alembic>=1.13,<2.0",
    "psycopg[binary]>=3.1,<4.0",
    "pgvector>=0.3,<0.4",
    "sentence-transformers>=3.0,<4.0",
    "docling>=2.123,<3.0",
]
```

Run `cd core && .venv/bin/python -m pip install -e ".[dev]"` again to sync
the environment (this uninstalls `pdfplumber` and its now-unused direct
dependencies, `pdfminer.six`/`pypdfium2`, from the venv — `Pillow` stays,
Docling depends on it too).

- [ ] **Step 4: Grep the codebase to confirm pdfplumber is fully gone**

Run: `grep -rn "pdfplumber" core/src/ core/pyproject.toml`
Expected: no matches. (A historical reference remains in
`docs/superpowers/plans/2026-08-14-ingestion-pipeline.md` — that is a past
plan document recording what was actually built at the time; it is
deliberately left unedited, not a miss — see Task 5.)

- [ ] **Step 5: Run the full `core/` suite**

Run: `cd core && .venv/bin/python -m pytest -v`
Expected: all pass, no import errors from the removed dependency.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/adapters/eur_lex.py core/pyproject.toml
git commit -s -m "feat: migrate EurLexAdapter from pdfplumber to Docling, remove pdfplumber"
```

---

### Task 4: Offline verification test (`core/`)

**Files:**
- Create: `core/tests/pipeline/test_docling_offline.py`

**Interfaces:**
- Consumes: `extract_document` (Task 1).
- Produces: nothing consumed by later tasks — this is a leaf verification
  test.

This test is **expected to skip** in a normal local/CI run that hasn't
pre-fetched Docling's models into a dedicated directory — that's by design,
matching the "documented command, no Dockerfile" scope decision (this plan
does not stand up the actual production model-baking pipeline). Running it
for real requires the operator to first run
`docling-tools models download layout tableformer -o <path>` and set
`NORMLY_DOCLING_ARTIFACTS_PATH=<path>` — exactly the production requirement
this test verifies.

- [ ] **Step 1: Write the test**

```python
# core/tests/pipeline/test_docling_offline.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from normly_core.pipeline.docling_extraction import extract_document

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"

_ARTIFACTS_PATH_ENV = "NORMLY_DOCLING_ARTIFACTS_PATH"


@pytest.mark.skipif(
    not os.environ.get(_ARTIFACTS_PATH_ENV),
    reason=(
        f"Set {_ARTIFACTS_PATH_ENV} to a directory populated by "
        "`docling-tools models download layout tableformer -o <path>` to "
        "run this test -- it proves extraction needs no network access once "
        "models are pre-fetched, matching the production deployment "
        "requirement (no runtime access to external model sources, "
        "CLAUDE.md's STACKIT-only constraint)."
    ),
)
def test_extraction_makes_no_network_connection_when_models_are_pre_fetched():
    def _blocked_connect(self, address, *args, **kwargs):
        raise AssertionError(
            f"Docling attempted a network connection to {address!r} during "
            "extraction -- with NORMLY_DOCLING_ARTIFACTS_PATH set, this must "
            "never happen; models must come only from the pre-fetched path."
        )

    with patch.object(socket.socket, "connect", _blocked_connect):
        document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")

    assert document is not None
```

- [ ] **Step 2: Run it without the env var set, to confirm the skip works**

Run: `cd core && .venv/bin/python -m pytest tests/pipeline/test_docling_offline.py -v`
Expected: SKIPPED, with the reason message shown above.

- [ ] **Step 3: Populate a local model directory and run it for real**

```bash
cd core
.venv/bin/docling-tools models download layout tableformer -o /tmp/docling-models
NORMLY_DOCLING_ARTIFACTS_PATH=/tmp/docling-models .venv/bin/python -m pytest tests/pipeline/test_docling_offline.py -v
```

Expected: PASS. If it fails with the network-connection `AssertionError`,
that means Docling tried to reach the network even with a local
`artifacts_path` set — stop and investigate (check the exact model names
`docling-tools models download` fetched match what `PdfPipelineOptions`
expects to find locally) before considering this task done.

- [ ] **Step 4: Run the full `core/` suite** (without the env var — matching
normal CI/dev conditions where this one test is expected to skip)

Run: `cd core && .venv/bin/python -m pytest -v`
Expected: all pass, one skip (this new test).

- [ ] **Step 5: Commit**

```bash
git add core/tests/pipeline/test_docling_offline.py
git commit -s -m "test: verify Docling extraction needs no network access with pre-fetched models"
```

---

### Task 5: Capstone — full regression and consistency check (`core/`)

**Files:**
- Test: none new — this task verifies, it doesn't add functionality.

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: nothing — this is the plan's final task.

- [ ] **Step 1: Run the full `core/` test suite one more time, from a clean state**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass (one skip for the offline test, unless
`NORMLY_DOCLING_ARTIFACTS_PATH` happens to be set in this shell).

- [ ] **Step 2: Confirm pdfplumber is genuinely gone from the installed environment**

Run: `cd core && .venv/bin/python -c "import pdfplumber"`
Expected: `ModuleNotFoundError` — if pdfplumber is still importable, the
venv wasn't properly synced after Task 3's `pyproject.toml` change; re-run
`.venv/bin/python -m pip install -e ".[dev]"` and re-check.

- [ ] **Step 3: Confirm Docling is used exactly where expected, nowhere else**

Run: `grep -rln "import docling\|from docling" core/src/`
Expected: exactly two files —
`core/src/normly_core/pipeline/docling_extraction.py` and no others (the
two adapters import `extract_document` from the shared layer, not Docling
directly — confirms the architecture's "adapter-specific dependencies
confined, shared mechanics centralized" principle held).

- [ ] **Step 4: Confirm SPDX headers are present on all new/modified files**

Run: `grep -L "SPDX-License-Identifier: AGPL-3.0-or-later" core/src/normly_core/pipeline/docling_extraction.py core/src/normly_core/pipeline/adapters/dguv.py core/src/normly_core/pipeline/adapters/eur_lex.py core/tests/pipeline/test_docling_extraction.py core/tests/pipeline/test_docling_offline.py`
Expected: no output (every file has the header; the command lists files
that are *missing* it).

- [ ] **Step 5: Deliberately confirm the historical plan document is left as-is**

`docs/superpowers/plans/2026-08-14-ingestion-pipeline.md` still lists
`pdfplumber` in its Tech Stack line. This is intentional: it is a record of
what was actually built at the time the ingestion pipeline was first
implemented, not a living document — the current spec at
`docs/superpowers/specs/2026-08-30-docling-migration-design.md` and this
plan are the authoritative record of the current state. No action needed;
this step exists so a reviewer doesn't flag it as a missed update.

- [ ] **Step 6: Final full-suite run**

Run: `cd core && .venv/bin/python -m pytest -v`
Expected: all pass.

No commit for this task — it's verification-only, nothing changed.
