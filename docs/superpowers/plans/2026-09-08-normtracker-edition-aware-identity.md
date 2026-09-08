# Editions-bewusste Identitätsauflösung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `identity.resolve()` and `find_by_designation` edition-aware so a new DGUV Vorschrift edition sharing its predecessor's exact designation is recognized as a genuinely new `Document` (not silently merged into the existing one), inherits the predecessor's `work_id`, and gets a real `REPLACES` edge to it.

**Architecture:** DGUV already parses (and discards) its "vom `<Datum>`" issue date — capture it into a new `RawRecord.edition` field. Make `find_by_designation` accept an optional `edition` filter, and make `identity.resolve()` use it to tell "same edition, re-ingested" apart from "known designation, new edition" apart from "genuinely new designation." Wire the new "new edition" outcome into `runner.py` to reuse the predecessor's Work and create a `REPLACES` edge, alongside (not instead of) the existing Inkrafttreten-section-based detection.

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, pytest, Postgres via testcontainers (already used throughout `core/tests/`).

## Global Constraints

- No changes to `core/src/normly_core/pipeline/adapters/eur_lex.py` or `core/src/normly_core/pipeline/adapters/baua.py` — neither populates `RawRecord.edition`; every change in this plan must be provably a no-op for their existing edition-less `find_by_designation`/`resolve()` calls.
- No backfill logic in the migration — dev/test database only (confirmed by the project owner), a plain schema change is sufficient.
- `create_edge`'s existing dedup logic (`_active_edge_query` + `IntegrityError` fallback, already in `core/src/normly_core/graph/postgres/repositories.py`, unchanged by this plan) already prevents a duplicate edge if the new auto-REPLACES mechanism and the existing `_extract_predecessor_reference` path both fire for the same pair — no new dedup logic needed, just confirm this with a test.
- TDD discipline throughout: write the failing test, run it, read the actual failure, then implement the minimal fix, then confirm green.
- License headers already present in every file this plan modifies. The one new file (the Alembic migration) needs the same `# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors` header every other migration in `core/migrations/versions/` already carries.
- `EdgeType.REPLACES` edges point from the successor document to the superseded one (established convention, confirmed throughout this codebase) — the new auto-REPLACES edge in this plan must follow it: `from_document_id` = the new edition, `to_document_id` = the previous edition.

---

### Task 1: `RawRecord.edition` + DGUV issue-date capture

**Files:**
- Modify: `core/src/normly_core/pipeline/domain.py:28-40` (`RawRecord`)
- Modify: `core/src/normly_core/pipeline/adapters/dguv.py:99-111` (`_ISSUE_DATE_PREFIX`), `:470-503` (`_fetch_file`)
- Test: `core/tests/pipeline/test_dguv_adapter.py`

**Interfaces:**
- Consumes: nothing from another task in this plan — fully independent, may be executed first or in any order relative to Task 2.
- Produces: `RawRecord.edition: str | None` (new field, default `None`) — Task 4 reads this. `_normalise_issue_date` / the updated `_ISSUE_DATE_PREFIX` stay private to `dguv.py`, not consumed elsewhere.

**Ground truth, verified this session:**
- `RawRecord` (`core/src/normly_core/pipeline/domain.py:28-40`) is a frozen dataclass:
  ```python
  @dataclass(frozen=True)
  class RawRecord:
      source_id: uuid.UUID
      content_hash: str
      raw_designation: str
      raw_issuer: str | None
      raw_title: str | None
      full_text: str | None
      # The language of this record's designation, title and text. `None` leaves
      # the choice to the runner, which falls back to German.
      language: str | None = None
      raw_references: list[RawReference] = field(default_factory=list)
      fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  ```
  Every `RawRecord(...)` call site in `eur_lex.py`, `baua.py`, and `dguv.py` uses keyword arguments exclusively (confirmed by grep this session) — a new field with a default is safe to insert anywhere.
- `dguv.py`'s current designation/title split, in `_fetch_file` (lines 483-490):
  ```python
          first = lines[0] if lines else ""
          match = _DESIGNATION_PATTERN.match(first)
          if match:
              designation = match.group(1)
              title = match.group(2).strip() or None
          else:
              designation = first
              title = None
  ```
  `_DESIGNATION_PATTERN` is `r"^(DGUV (?:Vorschrift \d+|(?:Regel|Information|Grundsatz) \d{3}-\d{3}))\s*(.*)$"` — group 2 is everything after the designation number, e.g. for a real publication set as `"DGUV Vorschrift 1 vom 1. November 2013 Grundsätze der Prävention"`, group 2 is `"vom 1. November 2013 Grundsätze der Prävention"`.
- `_ISSUE_DATE_PREFIX` (lines 109-111), current form (no capture groups):
  ```python
  _ISSUE_DATE_PREFIX = re.compile(
      r"^vom\s+(?:\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\d{1,2}\.\s*\w+\s+\d{4})\s*"
  )
  ```
  Its only current use site is inside `_is_publication_title_line()` (line 245): `tail = _ISSUE_DATE_PREFIX.sub("", match.group(2).strip(), count=1)` — matched text is discarded via `.sub("", ...)`, only used to check what remains looks like a title. `_fetch_file` never applies this regex at all today, so `title` currently comes out as `"vom 1. November 2013 Grundsätze der Prävention"` (date glued onto the front) for any publication that sets an issue date.

- [ ] **Step 1: Write the failing tests**

Add to `core/tests/pipeline/test_dguv_adapter.py` (near the existing `_write_publication_pdf`/`_write_publication_pdf_with_sections` helpers — both already exist in this file from the just-merged sub-project, reuse them as-is, do not modify them):

```python
def test_fetch_captures_the_issue_date_as_edition(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf",
        "DGUV Vorschrift 1",
        "vom 1. November 2013 Grundsätze der Prävention",
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition == "2013-11-01"
    assert records[0].raw_title == "Grundsätze der Prävention"


def test_fetch_captures_a_numeric_issue_date_as_edition(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_2.pdf",
        "DGUV Vorschrift 2",
        "vom 1.6.2022 Betriebsärzte und Fachkräfte für Arbeitssicherheit",
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition == "2022-06-01"
    assert records[0].raw_title == "Betriebsärzte und Fachkräfte für Arbeitssicherheit"


def test_fetch_leaves_edition_none_when_no_issue_date_is_present(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_3.pdf", "DGUV Vorschrift 3", "Erste Hilfe"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition is None
    assert records[0].raw_title == "Erste Hilfe"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/pipeline/test_dguv_adapter.py -v -k captures_the_issue_date_or_leaves_edition_none`
(if the `-k` expression matches nothing due to pytest's substring matching, instead run `-k "issue_date or edition_none"`)
Expected: the first two FAIL with `AttributeError: 'RawRecord' object has no attribute 'edition'` (the field doesn't exist yet); the third also fails the same way once you add the `records[0].edition is None` assertion — all three fail on the missing attribute, confirming the field must be added before anything else.

- [ ] **Step 3: Add `RawRecord.edition`**

In `core/src/normly_core/pipeline/domain.py`, add one field to `RawRecord` (insert after `raw_title`, before `full_text` — keeps designation-adjacent fields grouped together):

```python
@dataclass(frozen=True)
class RawRecord:
    source_id: uuid.UUID
    content_hash: str
    raw_designation: str
    raw_issuer: str | None
    raw_title: str | None
    edition: str | None
    full_text: str | None
    # The language of this record's designation, title and text. `None` leaves
    # the choice to the runner, which falls back to German.
    language: str | None = None
    raw_references: list[RawReference] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Wait — `edition` has no default and sits before fields that also have no default (`full_text`), which is fine positionally, but since every call site uses keyword arguments (confirmed in the Ground Truth above), this is safe either way. To avoid forcing every existing keyword call site in `eur_lex.py`/`baua.py`/`dguv.py`'s OTHER `RawRecord(...)` calls (the ones this task does not touch) to add `edition=None` explicitly, give it a default instead: `edition: str | None = None`. Since `raw_references` and `fetched_at` already have defaults and come after it, a defaulted `edition` sitting before `full_text` (which has none) is fine in a `@dataclass` as long as `full_text` is passed by keyword everywhere — confirmed true. Final field:

```python
    edition: str | None = None
```

placed immediately after `raw_title: str | None` and before `full_text: str | None`.

- [ ] **Step 4: Run to confirm the AttributeError is gone, tests still fail on missing capture**

Run: `.venv/bin/pytest tests/pipeline/test_dguv_adapter.py -v -k "issue_date or edition_none"`
Expected: `test_fetch_leaves_edition_none_when_no_issue_date_is_present` now PASSES (edition really is `None` by default). The two issue-date tests FAIL differently now — `AssertionError: assert None == '2013-11-01'` (attribute exists, just not populated yet) — confirming the next step is the real fix.

- [ ] **Step 5: Capture the issue date in `dguv.py`**

Replace `_ISSUE_DATE_PREFIX` (lines 109-111) with a version carrying capture groups for both date shapes it already matches:

```python
_ISSUE_DATE_PREFIX = re.compile(
    r"^vom\s+(?:(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})|(\d{1,2})\.\s*(\w+)\s+(\d{4}))\s*"
)
```

Group 1-3 capture the numeric form (`day.month.year`); group 4-6 capture the worded form (`day. MonthName year`) — exactly one triplet is populated depending which alternative matched, matching this regex's own existing two-alternative shape. Its behavior at the existing use site (`_is_publication_title_line`, line 245, `_ISSUE_DATE_PREFIX.sub("", match.group(2).strip(), count=1)`) is unchanged — `.sub()` with a replacement of `""` doesn't care how many groups the pattern has.

Add a German-month lookup and a normalizing helper, placed near `_ISSUE_DATE_PREFIX` (module-level, before `_fetch_file`'s class):

```python
_GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
}


def _normalise_issue_date(match: re.Match[str]) -> str | None:
    """ISO-normalise a matched `_ISSUE_DATE_PREFIX` issue date.

    German month names are matched explicitly rather than via `%B`/locale,
    since this deployment cannot assume a German locale is configured.
    """
    day, month, year = match.group(1), match.group(2), match.group(3)
    if day is None:
        day, month_name, year = match.group(4), match.group(5), match.group(6)
        month = _GERMAN_MONTHS.get(month_name.lower())
        if month is None:
            return None
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None
```

Add `from datetime import date, datetime, timezone` to the existing `from datetime import datetime, timezone` import line near the top of `dguv.py` (just add `date` to the existing import, don't duplicate the line).

Now change `_fetch_file`'s designation/title split (lines 483-490) to also extract the edition:

```python
        first = lines[0] if lines else ""
        match = _DESIGNATION_PATTERN.match(first)
        edition: str | None = None
        if match:
            designation = match.group(1)
            tail = match.group(2).strip()
            date_match = _ISSUE_DATE_PREFIX.match(tail)
            if date_match:
                edition = _normalise_issue_date(date_match)
                tail = _ISSUE_DATE_PREFIX.sub("", tail, count=1)
            title = tail.strip() or None
        else:
            designation = first
            title = None
```

And add `edition=edition,` to the `yield RawRecord(...)` call (immediately after `raw_title=title,`, matching the new field's position in the dataclass):

```python
        yield RawRecord(
            source_id=self.source_id,
            content_hash=content_hash,
            raw_designation=designation,
            raw_issuer="DGUV",
            raw_title=title,
            edition=edition,
            full_text=full_text,
            language="de",
            raw_references=[predecessor_reference] if predecessor_reference else [],
            fetched_at=datetime.now(timezone.utc),
        )
```

(Read the actual current end of `_fetch_file`'s `yield RawRecord(...)` call yourself first — this plan's authors verified it ends with `raw_references=[predecessor_reference] if predecessor_reference else [], fetched_at=datetime.now(timezone.utc),` per the just-merged sub-project, but confirm before editing since exactness matters.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/pipeline/test_dguv_adapter.py -v`
Expected: every test in the file PASSES, including the 3 new ones and every pre-existing one (in particular, tests using `_write_publication_pdf`/`_write_publication_pdf_with_sections` with a title that does NOT start with "vom `<date>`" — e.g. `"Grundsätze der Prävention"` alone — must still produce the exact same `raw_title` as before; this proves the new date-stripping logic doesn't fire when there's no date to strip).

Run full suite: `.venv/bin/pytest tests -q`
Expected: all pass, no regressions (in particular, confirm no EUR-Lex or BAuA test references `RawRecord.edition` in a way that would break — they shouldn't, since the field defaults to `None` and neither adapter constructs it explicitly).

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/pipeline/domain.py core/src/normly_core/pipeline/adapters/dguv.py core/tests/pipeline/test_dguv_adapter.py
git commit -s -m "feat(core): capture DGUV's issue date as RawRecord.edition"
```

---

### Task 2: DB migration — loosen the designation unique constraint

**Files:**
- Create: `core/migrations/versions/0026_scope_designation_unique_to_edition.py`
- Test: `core/tests/pipeline/test_migrations.py` if this file exists (check first — search `core/tests/` for any existing migration-level test file; if none exists, add the coexistence assertion as a repository-level test in Task 3 instead, since Task 3 is the first task that actually needs two same-designation, different-edition rows to coexist in the database — see Task 3's own tests, which double as this migration's regression proof).

**Interfaces:**
- Consumes: nothing from another task in this plan.
- Produces: nothing another task's *code* directly imports — but Task 3's tests require this migration to have run (the test database is migrated automatically by `core/tests/conftest.py`'s `testcontainers` fixture, confirm this yourself by reading `conftest.py` — every prior sub-project's tests already relied on this). **Task 2 must be committed and its migration must be part of the migration chain before Task 3's tests are written**, or Task 3's own "two editions coexist" test will fail with a `psycopg.errors.UniqueViolation` against the OLD constraint. This is a real, load-bearing ordering dependency, not a preference — do not swap Task 2 and Task 3.

**Ground truth, verified this session:**
- `core/migrations/versions/` currently ends at `0025_create_document_embedding.py` (`revision = "0025"`, `down_revision = "0024"`). The new migration is `0026`, `down_revision = "0025"`.
- `DocumentDesignationORM` (`core/src/normly_core/graph/postgres/orm.py:128-148`):
  ```python
  class DocumentDesignationORM(Base):
      __tablename__ = "document_designation"
      ...
      edition: Mapped[str | None]
      ...
      __table_args__ = (
          sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
      )
  ```
  `edition` is already a nullable column on this table — no column addition needed, only the constraint.
- The exact precedent to follow, `core/migrations/versions/0012_scope_segment_unique_to_delivery.py` (read this file yourself for its full docstring style before writing the new one):
  ```python
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 normly contributors

  """scope the segment unique constraint to the delivery
  ...
  Revision ID: 0012
  Revises: 0011
  Create Date: 2026-08-20
  """

  from alembic import op

  revision = "0012"
  down_revision = "0011"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.drop_constraint("uq_segment_document_sequence", "segment", type_="unique")
      op.create_unique_constraint(
          "uq_segment_document_delivery_sequence",
          "segment",
          ["document_id", "delivery_id", "sequence_number"],
      )


  def downgrade() -> None:
      op.drop_constraint(
          "uq_segment_document_delivery_sequence", "segment", type_="unique"
      )
      op.create_unique_constraint(
          "uq_segment_document_sequence", "segment", ["document_id", "sequence_number"]
      )
  ```
  Note this precedent's naming convention: the constraint's NAME changes to reflect its new columns (`uq_segment_document_sequence` → `uq_segment_document_delivery_sequence`), it isn't kept under the old name. Follow the same convention: `uq_designation_issuer_designation` → `uq_designation_issuer_designation_edition`.

- [ ] **Step 1: Write the migration**

Create `core/migrations/versions/0026_scope_designation_unique_to_edition.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""scope the designation unique constraint to the edition

A designation identifies one edition of a Regelwerk, not the Regelwerk as a
whole -- keyed on (issuer, designation) alone, a genuinely new edition
sharing its predecessor's exact designation string (e.g. a DGUV Vorschrift
reissued under the same "DGUV Vorschrift N" number) could never be recorded
as its own DocumentDesignation row, forcing identity resolution to treat it
as an update to the predecessor's own Document instead of a new edition.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-08
"""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_designation_issuer_designation", "document_designation", type_="unique")
    op.create_unique_constraint(
        "uq_designation_issuer_designation_edition",
        "document_designation",
        ["issuer", "designation", "edition"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_designation_issuer_designation_edition", "document_designation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_designation_issuer_designation", "document_designation", ["issuer", "designation"]
    )
```

- [ ] **Step 2: Update the ORM's constraint to match**

In `core/src/normly_core/graph/postgres/orm.py`, `DocumentDesignationORM.__table_args__` (line 146-148), change:

```python
    __table_args__ = (
        sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
    )
```

to:

```python
    __table_args__ = (
        sa.UniqueConstraint(
            "issuer", "designation", "edition", name="uq_designation_issuer_designation_edition"
        ),
    )
```

(The ORM's own declared constraint and the migration must describe the same end state — this is what `core/tests/conftest.py`'s schema-matches-migrations check, if one exists, would catch; check for such a check by reading `conftest.py`, and if one exists, this step is what keeps it passing.)

- [ ] **Step 3: Run the full suite to confirm the migration applies cleanly**

Run: `.venv/bin/pytest tests -q`
Expected: all pass. This migration alone doesn't change any Python-level behavior that an existing test exercises (nothing yet inserts two same-designation-different-edition rows), so this step's purpose is purely to confirm the migration itself runs without error against the real `testcontainers` Postgres every test session already spins up — a broken migration would surface here as every single DB-backed test failing at fixture setup, not as a specific assertion failure.

- [ ] **Step 4: Commit**

```bash
git add core/migrations/versions/0026_scope_designation_unique_to_edition.py core/src/normly_core/graph/postgres/orm.py
git commit -s -m "feat(core): scope the designation unique constraint to the edition"
```

---

### Task 3: `find_by_designation` becomes edition-aware

**Files:**
- Modify: `core/src/normly_core/graph/domain.py:314` (`DocumentRepository.find_by_designation` Protocol)
- Modify: `core/src/normly_core/graph/postgres/repositories.py:569-581` (`PostgresDocumentRepository.find_by_designation`)
- Test: `core/tests/graph/test_delivery_find_and_document_find.py` (confirmed this session — the file's two existing `find_by_designation` tests, `test_find_by_designation_returns_none_when_absent` and `test_find_by_designation_returns_matching_document`, build every fixture inline with no shared setup helper; match that style exactly, do not introduce a new helper)

**Interfaces:**
- Consumes: Task 2's migration must already be applied (the new constraint `(issuer, designation, edition)` must exist, or this task's own "two editions coexist" test will hit a `UniqueViolation` against the old two-column constraint). **Task 2 must run before this task.**
- Produces: `DocumentRepository.find_by_designation(self, issuer: str, designation: str, edition: str | None = None) -> Document | None` — Task 4 calls this both with and without `edition` set.

**Ground truth, verified this session:**
- Protocol (`core/src/normly_core/graph/domain.py:314`): `def find_by_designation(self, issuer: str, designation: str) -> Document | None: ...`
- Implementation (`core/src/normly_core/graph/postgres/repositories.py:569-581`):
  ```python
      def find_by_designation(self, issuer: str, designation: str) -> Document | None:
          orm = self._session.execute(
              select(DocumentORM)
              .join(
                  DocumentDesignationORM,
                  DocumentDesignationORM.document_id == DocumentORM.id,
              )
              .where(
                  DocumentDesignationORM.issuer == issuer,
                  DocumentDesignationORM.designation == designation,
              )
          ).scalar_one_or_none()
          return _document_to_domain(orm) if orm else None
  ```
- `DocumentORM.created_at` (`core/src/normly_core/graph/postgres/orm.py:123-125`): `Mapped[datetime]`, `server_default=sa.func.now()` — usable for `.order_by(DocumentORM.created_at.desc())`.
- `find_by_designation` is called from exactly two places today: `core/src/normly_core/pipeline/identity.py:48` and `core/src/normly_core/pipeline/references.py:28-30` — both currently call it with 2 positional/keyword arguments only (no `edition`). Both must keep working unchanged; Task 4 is the only place that will pass `edition=`.

- [ ] **Step 1: Write the failing tests**

Add these tests to `core/tests/graph/test_delivery_find_and_document_find.py`, matching its existing inline style exactly (no shared setup helper — every test builds its own source/delivery/document):

```python
def test_find_by_designation_returns_the_newest_edition_when_none_is_specified(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:newest-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    older = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=older.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )
    newer = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2022-06-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=newer.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2022-06-01", is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1")

    assert found is not None
    assert found.id == newer.id


def test_find_by_designation_with_edition_matches_exactly(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:edition-exact-match",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    older = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=older.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )
    newer = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2022-06-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=newer.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2022-06-01", is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("DGUV", "DGUV Vorschrift 1", edition="2013-11-01")

    assert found is not None
    assert found.id == older.id


def test_find_by_designation_without_edition_still_matches_a_single_edition_designation(
    db_session,
):
    """Regression guard for EUR-Lex/BAuA-style designations, which never set
    an edition at all -- confirms the edition-less lookup path still works
    exactly as it did before this task for the common single-edition case."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:no-edition-regression",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    found = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")

    assert found is not None
    assert found.id == document.id
```

(`_setup` above is a placeholder name for whatever this file's own existing setup helper is actually called — read the file first and use its real name/shape; do not invent a new helper if one already exists that does the same source/delivery bootstrapping.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest core/tests/graph/test_delivery_find_and_document_find.py -v -k "find_by_designation"`
Expected: `test_find_by_designation_returns_the_newest_edition_when_none_is_specified` and `test_find_by_designation_with_edition_matches_exactly` both FAIL — the first with `sqlalchemy.exc.MultipleResultsFound` (today's `.scalar_one_or_none()` can't handle two rows), the second with `TypeError: find_by_designation() got an unexpected keyword argument 'edition'`. The third test PASSES already (single-edition case, unaffected by the bug this task fixes).

- [ ] **Step 3: Implement**

In `core/src/normly_core/graph/domain.py`, change the Protocol method (line 314):

```python
    def find_by_designation(
        self, issuer: str, designation: str, edition: str | None = None
    ) -> Document | None: ...
```

In `core/src/normly_core/graph/postgres/repositories.py`, replace `find_by_designation` (lines 569-581):

```python
    def find_by_designation(
        self, issuer: str, designation: str, edition: str | None = None
    ) -> Document | None:
        query = (
            select(DocumentORM)
            .join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
            )
        )
        if edition is not None:
            query = query.where(DocumentDesignationORM.edition == edition)
            orm = self._session.execute(query).scalar_one_or_none()
        else:
            # Without a specific edition, several DocumentDesignation rows can
            # now legitimately share (issuer, designation) -- one per edition
            # (see migration 0026). The caller gets the most recent one
            # deterministically, rather than an ambiguous match; a
            # single-edition designation (the common case today, and the
            # only case for EUR-Lex/BAuA) still returns its one match exactly
            # as before.
            orm = self._session.execute(
                query.order_by(DocumentORM.created_at.desc()).limit(1)
            ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest core/tests/graph/test_delivery_find_and_document_find.py -v`
Expected: every test in the file PASSES, including the 3 new ones and every pre-existing `find_by_designation`-related test.

Run full suite: `.venv/bin/pytest tests -q`
Expected: all pass, no regressions — in particular confirm `test_identity.py` and `test_references.py` (both call `find_by_designation` without `edition`) are unaffected.

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_delivery_find_and_document_find.py
git commit -s -m "feat(core): make find_by_designation edition-aware"
```

---

### Task 4: `identity.resolve()` edition-awareness + runner integration

**Files:**
- Modify: `core/src/normly_core/pipeline/domain.py` (`IdentityResolution`)
- Modify: `core/src/normly_core/pipeline/identity.py:38-54` (`resolve`)
- Modify: `core/src/normly_core/pipeline/runner.py:1-25` (imports), `:94-141` (`process`'s `is_new` branch and `add_designation` call)
- Test: `core/tests/pipeline/test_identity.py`, `core/tests/pipeline/test_end_to_end.py`

**Interfaces:**
- Consumes: Task 1's `RawRecord.edition` field; Task 3's edition-aware `find_by_designation(issuer, designation, edition=...)`. **Both Task 1 and Task 3 (and transitively Task 2) must be complete before this task starts.**
- Produces: `IdentityResolution.previous_edition_document_id: uuid.UUID | None` — nothing outside this task consumes it (the runner change in this same task is the only consumer).

**Ground truth, verified this session:**
- `IdentityResolution` (`core/src/normly_core/pipeline/domain.py:53-58`):
  ```python
  @dataclass(frozen=True)
  class IdentityResolution:
      document_id: uuid.UUID | None
      is_new: bool
      is_ambiguous: bool
      reason: str | None
  ```
- `identity.resolve()` (`core/src/normly_core/pipeline/identity.py:38-54`), full current body:
  ```python
  def resolve(record: RawRecord, document_repo: DocumentRepository) -> IdentityResolution:
      try:
          parse_designation(record.raw_designation)
      except UnparseableDesignationError:
          return IdentityResolution(
              document_id=None, is_new=False, is_ambiguous=True,
              reason="unparseable_designation",
          )

      if record.raw_issuer is not None:
          existing = document_repo.find_by_designation(record.raw_issuer, record.raw_designation)
          if existing is not None:
              return IdentityResolution(
                  document_id=existing.id, is_new=False, is_ambiguous=False, reason=None
              )

      return IdentityResolution(document_id=None, is_new=True, is_ambiguous=False, reason=None)
  ```
- `runner.py`'s `process()`, the exact `is_new` branch and the `add_designation` call immediately after it (confirmed this session, current lines ~94-141):
  ```python
          if result.is_new:
              parsed = identity.parse_designation(record.raw_designation)
              assignment = work_assignment.determine_work_assignment(record, document_repo)
              if assignment.is_ambiguous:
                  document = document_repo.create_document(
                      origin_issuer=record.raw_issuer or "unknown",
                      origin_number=parsed.number,
                      edition=parsed.edition or "",
                      part=None,
                      delivery_id=delivery.id,
                      work_id=None,
                  )
                  delta.documents_created += 1
                  target_work_id = min(assignment.candidate_work_ids, key=str)
                  identity_repo.enqueue_work_merge_case(
                      delivery_id=delivery.id,
                      source_work_id=document.work_id,
                      target_work_id=target_work_id,
                      reason=assignment.reason,
                  )
              else:
                  document = document_repo.create_document(
                      origin_issuer=record.raw_issuer or "unknown",
                      origin_number=parsed.number,
                      edition=parsed.edition or "",
                      part=None,
                      delivery_id=delivery.id,
                      work_id=assignment.work_id,
                  )
                  delta.documents_created += 1
          else:
              document = document_repo.get_document_unchecked(result.document_id)

          if record.raw_issuer is not None:
              document_repo.add_designation(
                  document_id=document.id,
                  issuer=record.raw_issuer,
                  designation=record.raw_designation,
                  language=language,
                  edition=None,
                  is_primary=True,
                  delivery_id=delivery.id,
              )
  ```
  Note `document_repo.create_document(...)` uses `edition=parsed.edition or ""` — `parsed` comes from `identity.parse_designation(record.raw_designation)`, the colon-split helper, which returns `edition=None` for any designation without an embedded colon (i.e. every DGUV designation). Also note the *unconditional* `edition=None` in the `add_designation(...)` call — this is a second, independent place the new `record.edition` value needs to reach.
- `runner.py`'s current imports (top of file): `from normly_core.graph.domain import Delivery` — needs `EdgeType`, `Layer` added for the new `create_edge` call this task adds.
- `edge_repo.create_edge(...)`'s exact signature (confirmed in the just-merged sub-project, `core/src/normly_core/graph/postgres/repositories.py`):
  ```python
  def create_edge(
      self, *, from_document_id: uuid.UUID, to_document_id: uuid.UUID, edge_type: EdgeType,
      jurisdiction: str | None, layer: Layer, delivery_id: uuid.UUID,
  ) -> Edge: ...
  ```
  `references.py`'s own layer derivation (already-established convention to mirror exactly): `layer = Layer.FREE if rule.may_export_free else Layer.COMMERCIAL`.
- `document_repo.get_document_unchecked(document_id)` already exists and is already used in the `else:` branch above (an existence-check read, not rights-gated) — this task reuses it to fetch the previous edition's own `Document` (for its `work_id`).

- [ ] **Step 1: Write the failing `identity.py` tests**

Add to `core/tests/pipeline/test_identity.py` (reusing the file's existing `_make_record` helper — extend it to accept an optional `edition` parameter with a default of `None`, since every existing call site omits it):

```python
def _make_record(raw_designation, raw_issuer, edition=None):
    return RawRecord(
        source_id=uuid.uuid4(),
        content_hash="sha256:identity-test",
        raw_designation=raw_designation,
        raw_issuer=raw_issuer,
        raw_title=None,
        edition=edition,
        full_text=None,
    )


def test_resolve_finds_the_same_edition_already_ingested(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-same-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2013-11-01")
    result = resolve(record, doc_repo)

    assert result.document_id == document.id
    assert result.is_new is False
    assert result.previous_edition_document_id is None


def test_resolve_reports_a_new_edition_of_a_known_designation(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-new-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    old_document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=old_document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2022-06-01")
    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id == old_document.id


def test_resolve_reports_new_document_with_no_previous_edition_for_a_first_appearance(
    db_session,
):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("DGUV Vorschrift 999", "DGUV", edition="2026-01-01")

    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/pipeline/test_identity.py -v`
Expected: the three new tests FAIL — `test_resolve_finds_the_same_edition_already_ingested` and the other two with `TypeError: IdentityResolution.__init__() got an unexpected keyword argument 'previous_edition_document_id'` (the field doesn't exist), or if you write the assertions before the field exists, `AttributeError: 'IdentityResolution' object has no attribute 'previous_edition_document_id'`. All pre-existing tests in this file still PASS (confirm this — Task 1/3 changes must not have broken `resolve()`'s current behavior for edition-less callers).

- [ ] **Step 3: Add `IdentityResolution.previous_edition_document_id` and rewrite `resolve()`**

In `core/src/normly_core/pipeline/domain.py`, add one field to `IdentityResolution`:

```python
@dataclass(frozen=True)
class IdentityResolution:
    document_id: uuid.UUID | None
    is_new: bool
    is_ambiguous: bool
    reason: str | None
    previous_edition_document_id: uuid.UUID | None = None
```

In `core/src/normly_core/pipeline/identity.py`, replace `resolve()` (lines 38-54):

```python
def resolve(record: RawRecord, document_repo: DocumentRepository) -> IdentityResolution:
    try:
        parse_designation(record.raw_designation)
    except UnparseableDesignationError:
        return IdentityResolution(
            document_id=None, is_new=False, is_ambiguous=True,
            reason="unparseable_designation",
        )

    if record.raw_issuer is not None:
        if record.edition is not None:
            exact = document_repo.find_by_designation(
                record.raw_issuer, record.raw_designation, edition=record.edition
            )
            if exact is not None:
                return IdentityResolution(
                    document_id=exact.id, is_new=False, is_ambiguous=False, reason=None
                )
            # Same designation, but not this exact edition -- check whether an
            # earlier edition exists at all, to distinguish "new edition of a
            # known Regelwerk" from "genuinely first appearance."
            previous = document_repo.find_by_designation(
                record.raw_issuer, record.raw_designation
            )
            return IdentityResolution(
                document_id=None, is_new=True, is_ambiguous=False, reason=None,
                previous_edition_document_id=previous.id if previous else None,
            )

        existing = document_repo.find_by_designation(record.raw_issuer, record.raw_designation)
        if existing is not None:
            return IdentityResolution(
                document_id=existing.id, is_new=False, is_ambiguous=False, reason=None
            )

    return IdentityResolution(document_id=None, is_new=True, is_ambiguous=False, reason=None)
```

(The `record.edition is None` branch is byte-for-byte the original function's behavior — confirming this stays a strict no-op for EUR-Lex/BAuA is the point of the regression tests in Step 1.)

- [ ] **Step 4: Run the `identity.py` tests to verify they pass**

Run: `.venv/bin/pytest tests/pipeline/test_identity.py -v`
Expected: all pass, including the 3 new tests and every pre-existing one.

- [ ] **Step 5: Write the failing end-to-end test**

Add to `core/tests/pipeline/test_end_to_end.py` (reuse the existing `_write_publication_pdf` helper from `test_dguv_adapter.py` via the same import pattern the just-merged sub-project's own end-to-end tests already use — check that file's existing `from test_dguv_adapter import ...` or `from pipeline.test_dguv_adapter import ...` and match whichever form actually resolves under this repo's pytest layout, confirmed in the prior sub-project to need the `pipeline.`-qualified form):

```python
def test_dguv_new_edition_is_recognised_shares_the_work_and_gets_a_replaces_edge(
    db_session, tmp_path
):
    from normly_core.graph.domain import EdgeType
    from normly_core.graph.postgres.repositories import PostgresEdgeRepository
    from pipeline.test_dguv_adapter import _write_publication_pdf

    dguv_source = _make_source(db_session, jurisdiction="DE")
    doc_repo = PostgresDocumentRepository(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1_2013.pdf", "DGUV Vorschrift 1",
        "vom 1. November 2013 Grundsätze der Prävention",
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
    old_document = doc_repo.find_by_designation(
        "DGUV", "DGUV Vorschrift 1", edition="2013-11-01"
    )
    assert old_document is not None
    (tmp_path / "dguv_vorschrift_1_2013.pdf").unlink()

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1_2022.pdf", "DGUV Vorschrift 1",
        "vom 1.6.2022 Grundsätze der Prävention",
    )
    run_adapter(DguvAdapter(directory=tmp_path, source_id=dguv_source.id), db_session)
    new_document = doc_repo.find_by_designation(
        "DGUV", "DGUV Vorschrift 1", edition="2022-06-01"
    )
    assert new_document is not None
    assert new_document.id != old_document.id

    assert new_document.work_id == old_document.work_id

    outgoing = edge_repo.list_edges_for_jurisdiction(new_document.id, "DE")
    assert any(
        e.edge_type == EdgeType.REPLACES and e.to_document_id == old_document.id
        for e in outgoing
    )
```

Before trusting `_make_source`'s exact signature above, read `test_end_to_end.py`'s own existing `_make_source(db_session, *, jurisdiction)` helper (already used throughout that file) and confirm it matches; it should, since this plan's authors read it directly this session.

- [ ] **Step 6: Run the end-to-end test to confirm it fails correctly**

Run: `.venv/bin/pytest tests/pipeline/test_end_to_end.py -v -k new_edition_is_recognised`
Expected: FAILS before Step 7's runner change lands — most likely on `assert new_document.id != old_document.id` (today's unmodified runner still merges the second ingestion into the first document, since `runner.py` itself hasn't been touched yet in this task).

- [ ] **Step 7: Wire the runner**

In `core/src/normly_core/pipeline/runner.py`, change the import line:

```python
from normly_core.graph.domain import Delivery
```

to:

```python
from normly_core.graph.domain import Delivery, EdgeType, Layer
```

Replace the `is_new` branch and the `add_designation` call (the full block shown in this task's Ground Truth section above) with:

```python
        if result.is_new:
            parsed = identity.parse_designation(record.raw_designation)
            if result.previous_edition_document_id is not None:
                # A new edition of an already-known designation: the edition
                # lineage IS the Work-linking signal here, more directly than
                # anything work_assignment.determine_work_assignment could
                # infer from raw_references -- reuse the predecessor's Work
                # outright and record the real REPLACES edge between the two
                # editions. This runs independently of, and in addition to,
                # any REPLACES reference the adapter's own Inkrafttreten-
                # section parsing may separately find for a differently-
                # designated predecessor; create_edge's own dedup logic
                # already covers the (rare) case where both mechanisms name
                # the same pair.
                previous_document = document_repo.get_document_unchecked(
                    result.previous_edition_document_id
                )
                document = document_repo.create_document(
                    origin_issuer=record.raw_issuer or "unknown",
                    origin_number=parsed.number,
                    edition=parsed.edition or record.edition or "",
                    part=None,
                    delivery_id=delivery.id,
                    work_id=previous_document.work_id,
                )
                delta.documents_created += 1
                layer = Layer.FREE if rule.may_export_free else Layer.COMMERCIAL
                edge_repo.create_edge(
                    from_document_id=document.id,
                    to_document_id=previous_document.id,
                    edge_type=EdgeType.REPLACES,
                    jurisdiction=None,
                    layer=layer,
                    delivery_id=delivery.id,
                )
            else:
                assignment = work_assignment.determine_work_assignment(record, document_repo)
                if assignment.is_ambiguous:
                    document = document_repo.create_document(
                        origin_issuer=record.raw_issuer or "unknown",
                        origin_number=parsed.number,
                        edition=parsed.edition or record.edition or "",
                        part=None,
                        delivery_id=delivery.id,
                        work_id=None,
                    )
                    delta.documents_created += 1
                    target_work_id = min(assignment.candidate_work_ids, key=str)
                    identity_repo.enqueue_work_merge_case(
                        delivery_id=delivery.id,
                        source_work_id=document.work_id,
                        target_work_id=target_work_id,
                        reason=assignment.reason,
                    )
                else:
                    document = document_repo.create_document(
                        origin_issuer=record.raw_issuer or "unknown",
                        origin_number=parsed.number,
                        edition=parsed.edition or record.edition or "",
                        part=None,
                        delivery_id=delivery.id,
                        work_id=assignment.work_id,
                    )
                    delta.documents_created += 1
        else:
            document = document_repo.get_document_unchecked(result.document_id)

        if record.raw_issuer is not None:
            document_repo.add_designation(
                document_id=document.id,
                issuer=record.raw_issuer,
                designation=record.raw_designation,
                language=language,
                edition=record.edition,
                is_primary=True,
                delivery_id=delivery.id,
            )
```

Two changes beyond the new `if result.previous_edition_document_id is not None:` branch, both applied consistently everywhere `edition=parsed.edition or ""` previously appeared: it becomes `edition=parsed.edition or record.edition or ""` (prefer a colon-embedded edition — EUR-Lex-style — over the adapter-supplied `record.edition`, DGUV-style, over empty string), and the previously-hardcoded `add_designation(..., edition=None, ...)` becomes `edition=record.edition` (passes through whatever the adapter parsed, `None` for EUR-Lex/BAuA/date-less DGUV publications, exactly preserving today's behavior for them).

- [ ] **Step 8: Run the end-to-end test, then the full suite**

Run: `.venv/bin/pytest tests/pipeline/test_end_to_end.py -v -k new_edition_is_recognised`
Expected: PASSES.

Run: `.venv/bin/pytest tests/pipeline/test_end_to_end.py -v`
Expected: all pass, including every pre-existing end-to-end test (in particular the ones from the just-merged sub-project asserting `documents_created` counts and REPLACES-edge behavior for EUR-Lex and for DGUV's Inkrafttreten-section detection — confirm none of their assertions assumed the old `edition=None`-always behavior in a way this task's `edition=record.edition` change would break; DGUV's Inkrafttreten-section tests don't set an issue date in their own fixture text, so `record.edition` should still come out `None` for them, but verify this directly rather than assuming it).

Run full suite: `.venv/bin/pytest tests -q`
Expected: all pass, no regressions anywhere (in particular EUR-Lex and BAuA tests, which never populate `record.edition` and must be completely unaffected).

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/pipeline/domain.py core/src/normly_core/pipeline/identity.py core/src/normly_core/pipeline/runner.py core/tests/pipeline/test_identity.py core/tests/pipeline/test_end_to_end.py
git commit -s -m "feat(core): recognise new DGUV editions, inherit their Work, link them with REPLACES"
```

---

## Model Selection Note (for subagent-driven-development execution)

This plan's four tasks are NOT independent, unlike the previous two sub-projects in this roadmap — they form a strict dependency chain for correctness (Task 2 before Task 3's DB-level tests can pass; Task 1 and Task 3 both before Task 4 can be written at all). **Do not parallelize; execute in the order 1, 2, 3, 4.**

- **Task 1** (DGUV date parsing): touches one file's regex/parsing logic plus a dataclass field addition, with exact code given — but the German-month-name mapping and the two-alternative regex require real attention to get right, not pure transcription. Standard model.
- **Task 2** (migration): small, mechanical, exact code given, one clear precedent to mirror (`0012_scope_segment_unique_to_delivery.py`) — but a wrong migration silently corrupts every other task's ability to run its own DB tests, so verify the precedent's exact shape rather than trusting this plan's recollection blindly. Standard model, not the cheapest tier, specifically because of this blast radius.
- **Task 3** (repository layer): a real behavior change to a two-call-site-shared method (`identity.py` and `references.py` both depend on it not regressing) — standard model.
- **Task 4** (integration): the most judgment-heavy task — touches `runner.py`'s central per-record dispatch, must correctly reason about interaction with the existing `work_assignment`/`_extract_predecessor_reference` machinery from the prior sub-project. Standard model at minimum; if the implementer's report shows any uncertainty about the interaction between the new `previous_edition_document_id` branch and the existing ambiguous-Work-signal branch, escalate the task reviewer to the most capable available model rather than accepting a shaky diff.

Task reviewers: standard model for all four, given the real cross-task coupling — each reviewer needs to trace beyond its own task's diff into the other tasks' already-committed code to verify integration correctness (e.g. Task 4's reviewer must re-confirm Task 3's `find_by_designation` ordering is actually deterministic, not just trust that Task 3 was reviewed once already). Final whole-branch review: most capable available model, per this roadmap's established pattern for every sub-project so far.

## Self-Review

**Spec coverage:** the spec's three "Ziel" items are each covered — item 1 (capture the issue date) by Task 1, item 2 (edition-aware resolve/find_by_designation) by Tasks 2-3-4, item 3 (Work inheritance + auto-REPLACES) by Task 4. The spec's Nicht-Ziele are respected by construction: no task touches `eur_lex.py`/`baua.py`; no backfill logic anywhere; `_extract_predecessor_reference` is untouched (Task 4's new runner branch is additive, confirmed by re-reading the full `process()` function — the Inkrafttreten-based path via `references.extract_references` still runs unconditionally later in the same function, regardless of which branch created `document`).

**Placeholder scan:** none found. The one gap from the first self-review pass — Task 3's exact test file and its fixture-building convention — was resolved by reading the actual file (`core/tests/graph/test_delivery_find_and_document_find.py`, confirmed to build every fixture inline with no shared setup helper) before finalizing; all three of Task 3's new tests now use that file's real, verified inline style directly, no "find it yourself" notes remain anywhere in the plan.

**Type consistency:** `RawRecord.edition: str | None`, `IdentityResolution.previous_edition_document_id: uuid.UUID | None`, and `find_by_designation(..., edition: str | None = None)` are used identically across every task that touches them. `EdgeType.REPLACES` and the `Layer.FREE if rule.may_export_free else Layer.COMMERCIAL` derivation in Task 4 match the exact convention already established in `references.py` (unchanged, verified this session) and the just-merged sub-project's own adapter code.
