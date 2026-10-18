# Answer Source Chips and Chat History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat answers show per-paragraph source chips ("DIN EN ISO 13849-1 · 4.5.4") that open the cited passage on the document page, structural answers name documents instead of raw ids, and chat sessions can be reopened, continued and carry a title.

**Architecture:** `chat/` asks the model for `[n]` markers, parses them into paragraphs with citations, and resolves chip labels (designation via `api/`, section from the segment heading) on every read. `api/` gains a citable-segments endpoint gated by `may_cite_passages`; the document page renders segments with `#segment-<id>` anchors. `chat/` gains session-messages and session-title endpoints; the frontend opens sessions from the sidebar and restores the active one on load.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest + testcontainers (pgvector/pg16); Next.js 16 (App Router, BFF route handlers), React 19, vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-17-answer-source-chips-and-chat-history-design.md`

## Global Constraints

- Everything committed is English: code, comments, tests, commits, docs. User-facing strings exist in `de` and `en`.
- New source files carry the AGPL-3.0 header used throughout (`# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors`; `//` in TypeScript).
- Commits: Conventional Commits, `git commit -s` (DCO, the human's identity from git config), and the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subagents never add a `Signed-off-by` of their own.
- Database access only through the repository layer (`core/src/normly_core/graph/postgres/repositories.py`); the rights classification is the only gate and lives in repository queries.
- No UUID ever appears in user-facing answer text.
- Free content needs no account (ADR-017): the segments endpoint is anonymous; chat history endpoints are account-only.
- Language model calls only through the existing `LlmClient` (ADR-022).
- Python tests: `cd <service> && ../.venv/bin/pytest …` (Docker must run for testcontainers). Frontend: `cd frontend && npx vitest run …`.
- `chat/tests/test_structural_end_to_end.py` is excluded in CI (it starts a real `api/` with the embedding model); run it locally where the task says so.
- Do not push and do not open a PR; the owner decides when CI runs.

## Corrections to the spec, applied in Task 1

Reading the code while planning surfaced three spec details that need fixing:

1. **Section numbers:** DGUV headings read `§ 1 Geltungsbereich`, so the section pattern must accept `§ 1` as well as `4.5.4`.
2. **Exchange format:** `chat_session` and `chat_message_citation` are `USER_TABLES` in `core/src/normly_core/exchange/tables.py`, which only groups tables; user tables are never part of a knowledge-base dump. The new columns need no exchange change and no exchange test. They do belong in the personal-data export (Art. 15 GDPR), which Task 10 covers.
3. **Label fallback:** when a document has no designation, the label is `origin_issuer origin_number` from the document response; a chip is dropped only when the document cannot be fetched at all.

## File Structure

**core/**
- Create `core/migrations/versions/0038_chat_titles_and_paragraph_citations.py` — `chat_session.title`, `chat_message_citation.paragraph_index`.
- Modify `core/src/normly_core/graph/postgres/orm.py` — the two columns.
- Modify `core/src/normly_core/graph/domain.py` — `ChatSession.title`, `ChatMessageCitation.paragraph_index`, new `ChatRepository` and `SegmentRepository` methods.
- Modify `core/src/normly_core/graph/postgres/repositories.py` — implementations.
- Modify `core/tests/graph/test_architecture.py` — exempt `ChatRepository.get_session_for_account`.
- Tests: `core/tests/graph/test_chat_repository.py`, `core/tests/graph/test_segment_repository.py`.

**api/**
- Create `api/src/normly_api/routers/segments.py` — `GET /v1/documents/{id}/segments`.
- Modify `api/src/normly_api/schemas.py` (`SegmentResponse`), `api/src/normly_api/main.py` (router).
- Tests: create `api/tests/test_segments.py`; modify `api/tests/test_openapi_and_end_to_end.py`.

**chat/**
- Create `chat/src/normly_chat/markers.py` — numbered context, marker parsing, paragraph splitting.
- Create `chat/src/normly_chat/citation_labels.py` — section from heading, document label, `CitationResolver`.
- Create `chat/src/normly_chat/titles.py` — fallback title, model title.
- Modify `chat/src/normly_chat/api_client.py` (`get_document`), `synthesis.py`, `structural.py`, `schemas.py`, `routers/chat.py`, `routers/sessions.py`.
- Tests: create `chat/tests/test_markers.py`, `chat/tests/test_citation_labels.py`, `chat/tests/test_titles.py`; modify `test_synthesis.py`, `test_structural.py`, `test_chat_router.py`, `test_sessions_router.py`, `test_structural_end_to_end.py`, `test_api_client.py`.

**accounts/**
- Modify `accounts/src/normly_accounts/schemas.py`, `accounts/src/normly_accounts/routers/account_management.py`; test `accounts/tests/test_account_export.py`.

**frontend/**
- Create `frontend/src/lib/chat-answer.ts` — API → view conversion for answers.
- Create BFF routes: `src/app/api/documents/[id]/segments/route.ts`, `src/app/api/chat/sessions/[id]/messages/route.ts`, `src/app/api/chat/sessions/[id]/title/route.ts`, `src/app/api/chat/current/route.ts`.
- Modify `src/components/chat/citation-chip.tsx`, `message-list.tsx`, `chat-shell.tsx`, `chat-history-sidebar.tsx`, `src/app/home-page-content.tsx`, `src/app/documents/[id]/document-detail-content.tsx`, `src/lib/i18n/de.json`, `src/lib/i18n/en.json`.
- Tests: create `tests/unit/chat-answer.test.ts`, `tests/unit/chat-history-routes.test.ts`, `tests/unit/document-segments-route.test.ts`; modify `message-list.test.tsx`, `home-page-content.test.tsx`, `chat-history-sidebar.test.tsx`, `document-detail-page.test.tsx`, `tests/e2e/chat-and-history.spec.ts`.

---

### Task 1: Chat storage — titles, paragraph citations, session lookup

**Files:**
- Modify: `docs/superpowers/specs/2026-10-17-answer-source-chips-and-chat-history-design.md` (the three corrections above)
- Create: `core/migrations/versions/0038_chat_titles_and_paragraph_citations.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`ChatSessionORM`, `ChatMessageCitationORM`)
- Modify: `core/src/normly_core/graph/domain.py` (`ChatSession`, `ChatMessageCitation`, `ChatRepository`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_chat_session_to_domain`, `_chat_message_citation_to_domain`, `PostgresChatRepository`)
- Modify: `core/tests/graph/test_architecture.py`
- Test: `core/tests/graph/test_chat_repository.py`

**Interfaces:**
- Produces:
  - `ChatSession.title: str | None` (last field, default `None`)
  - `ChatMessageCitation.paragraph_index: int | None` (last field, default `None`)
  - `PostgresChatRepository.add_citation(*, message_id, document_id, segment_id, paragraph_index: int | None = None) -> ChatMessageCitation`
  - `PostgresChatRepository.get_session_for_account(session_id: uuid.UUID, account_id: uuid.UUID) -> ChatSession | None`
  - `PostgresChatRepository.set_session_title(session_id: uuid.UUID, title: str) -> None`
  - `PostgresChatRepository.first_user_messages_for_sessions(session_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]`
  - `list_messages_for_session` orders a user message before an assistant message with the same `created_at`.

- [ ] **Step 1: Apply the spec corrections**

In the spec, make these edits:

- Under "Chip labels are resolved in the backend", replace the `section` bullet with:

```markdown
- `section` — the leading section marker of the segment heading:
  `4.5.4 Performance Level` → `4.5.4`, `§ 1 Geltungsbereich` → `§ 1`;
  `null` when the heading starts with neither or the citation has no
  segment.
```

- Under "Storage", replace the last bullet (starting "`chat_message_citation` is a user table") with:

```markdown
- `chat_session` and `chat_message_citation` are user tables
  (`core/src/normly_core/exchange/tables.py`); user tables are never part
  of a knowledge-base dump, so the new columns need no exchange change.
  They are personal data and appear in the account export (Art. 15 GDPR).
```

- Under "Session titles", replace "carried through the exchange format like `paragraph_index`" with "included in the account export".
- Under "Error handling", replace the first bullet's first sentence with: "**Target or document cannot be resolved:** a document without a designation is labelled `origin_issuer origin_number`; a document `api/` does not return (error or 404) yields no chip."
- Under "Testing", replace the "Migration and exchange" bullet with: "**Migration and export:** the migration applies; `title` and `paragraph_index` appear in the account export."

- [ ] **Step 2: Write the failing repository tests**

Append to `core/tests/graph/test_chat_repository.py`:

```python
def _account(db_session, email):
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def test_a_new_session_has_no_title_and_set_session_title_stores_one(db_session):
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-title", jurisdiction="DE", language="de", created_at=_now(),
    )
    assert session.title is None

    repo.set_session_title(session.id, "Schutzbrillen beim Schweißen")

    assert repo.get_session_by_token("tok-title").title == "Schutzbrillen beim Schweißen"


def test_get_session_for_account_returns_only_the_owners_session(db_session):
    owner = _account(db_session, "owner-lookup@example.de")
    other = _account(db_session, "other-lookup@example.de")
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-owned", jurisdiction="DE", language="de", created_at=_now(),
        account_id=owner.id,
    )

    assert repo.get_session_for_account(session.id, owner.id).id == session.id
    assert repo.get_session_for_account(session.id, other.id) is None


def test_first_user_messages_for_sessions_returns_the_earliest_question_per_session(db_session):
    repo = PostgresChatRepository(db_session)
    first = repo.create_session(
        session_token="tok-first-a", jurisdiction="DE", language="de", created_at=_now(),
    )
    second = repo.create_session(
        session_token="tok-first-b", jurisdiction="DE", language="de", created_at=_now(),
    )
    empty = repo.create_session(
        session_token="tok-first-c", jurisdiction="DE", language="de", created_at=_now(),
    )
    t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc)
    repo.create_message(
        session_id=first.id, role=ChatMessageRole.USER, content="Spätere Frage",
        answer_type=None, created_at=t1,
    )
    repo.create_message(
        session_id=first.id, role=ChatMessageRole.USER, content="Erste Frage",
        answer_type=None, created_at=t0,
    )
    repo.create_message(
        session_id=second.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.FALLBACK, created_at=t0,
    )
    repo.create_message(
        session_id=second.id, role=ChatMessageRole.USER, content="Frage B",
        answer_type=None, created_at=t1,
    )

    result = repo.first_user_messages_for_sessions([first.id, second.id, empty.id])

    assert result == {first.id: "Erste Frage", second.id: "Frage B"}
    assert repo.first_user_messages_for_sessions([]) == {}


def test_a_user_message_sorts_before_its_answer_when_both_share_a_timestamp(db_session):
    # routers/chat.py stores question and answer with the same `now`.
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-tie", jurisdiction="DE", language="de", created_at=_now(),
    )
    same = _now()
    answer = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.FALLBACK, created_at=same,
    )
    question = repo.create_message(
        session_id=session.id, role=ChatMessageRole.USER, content="Frage",
        answer_type=None, created_at=same,
    )

    assert [m.id for m in repo.list_messages_for_session(session.id)] == [question.id, answer.id]


def test_add_citation_stores_the_paragraph_index(db_session):
    from datetime import date

    from normly_core.graph.domain import LegalBasisCategory
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/p",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:paragraph-index", ingested_at=_now(),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="2", edition="2021", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-pi", jurisdiction="DE", language="de", created_at=_now(),
    )
    message = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="A\n\nB",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=_now(),
    )

    with_index = repo.add_citation(
        message_id=message.id, document_id=document.id, segment_id=None, paragraph_index=1,
    )
    without_index = repo.add_citation(
        message_id=message.id, document_id=document.id, segment_id=None,
    )

    assert with_index.paragraph_index == 1
    assert without_index.paragraph_index is None
    stored = repo.citations_for_messages([message.id])[message.id]
    assert sorted(c.paragraph_index is None for c in stored) == [False, True]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_chat_repository.py -v`
Expected: the five new tests FAIL (`AttributeError: 'ChatSession' object has no attribute 'title'`, missing methods, unexpected keyword `paragraph_index`, order assertion).

- [ ] **Step 4: Write the migration**

Create `core/migrations/versions/0038_chat_titles_and_paragraph_citations.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add chat_session.title and chat_message_citation.paragraph_index

title holds the model-generated session title; NULL means none was generated
and the reader falls back to the first question. paragraph_index ties a
citation to one paragraph of its answer; NULL means the whole answer (the
fallback when the model set no source markers, and every citation written
before this revision).

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_session", sa.Column("title", sa.String(), nullable=True))
    op.add_column(
        "chat_message_citation", sa.Column("paragraph_index", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_message_citation", "paragraph_index")
    op.drop_column("chat_session", "title")
```

- [ ] **Step 5: Add the ORM columns**

In `core/src/normly_core/graph/postgres/orm.py`, in `ChatSessionORM` after `language: Mapped[str]`:

```python
    title: Mapped[str | None] = mapped_column(nullable=True)
```

In `ChatMessageCitationORM` after the `segment_id` column:

```python
    paragraph_index: Mapped[int | None] = mapped_column(nullable=True)
```

- [ ] **Step 6: Extend the domain**

In `core/src/normly_core/graph/domain.py`:

`ChatSession` — add as the last field:

```python
    title: str | None = None
```

`ChatMessageCitation` — add as the last field:

```python
    paragraph_index: int | None = None
```

In `ChatRepository`, after `get_session_by_token`:

```python
    def get_session_for_account(
        self, session_id: uuid.UUID, account_id: uuid.UUID
    ) -> ChatSession | None:
        """The session only if it belongs to account_id; None for unknown and foreign ids alike."""
        ...

    def set_session_title(self, session_id: uuid.UUID, title: str) -> None: ...

    def first_user_messages_for_sessions(
        self, session_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """The earliest user message per session; sessions without one are absent."""
        ...
```

Change the `add_citation` signature in the Protocol to:

```python
    def add_citation(
        self, *, message_id: uuid.UUID, document_id: uuid.UUID,
        segment_id: uuid.UUID | None, paragraph_index: int | None = None,
    ) -> ChatMessageCitation: ...
```

- [ ] **Step 7: Implement the repository changes**

In `core/src/normly_core/graph/postgres/repositories.py`:

`_chat_session_to_domain`:

```python
def _chat_session_to_domain(orm: ChatSessionORM) -> ChatSession:
    return ChatSession(
        id=orm.id, session_token=orm.session_token, account_id=orm.account_id,
        jurisdiction=orm.jurisdiction, language=orm.language, created_at=orm.created_at,
        title=orm.title,
    )
```

`_chat_message_citation_to_domain`:

```python
def _chat_message_citation_to_domain(orm: ChatMessageCitationORM) -> ChatMessageCitation:
    return ChatMessageCitation(
        id=orm.id, message_id=orm.message_id, document_id=orm.document_id,
        segment_id=orm.segment_id, paragraph_index=orm.paragraph_index,
    )
```

In `PostgresChatRepository`, after `get_session_by_token`:

```python
    def get_session_for_account(
        self, session_id: uuid.UUID, account_id: uuid.UUID
    ) -> ChatSession | None:
        # Scoped by account_id in the WHERE clause, like delete_chat_session:
        # a foreign id answers exactly like an unknown one.
        orm = self._session.execute(
            select(ChatSessionORM).where(
                ChatSessionORM.id == session_id, ChatSessionORM.account_id == account_id,
            )
        ).scalar_one_or_none()
        return _chat_session_to_domain(orm) if orm else None

    def set_session_title(self, session_id: uuid.UUID, title: str) -> None:
        self._session.execute(
            sa.update(ChatSessionORM).where(ChatSessionORM.id == session_id).values(title=title)
        )
        self._session.flush()

    def first_user_messages_for_sessions(
        self, session_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not session_ids:
            return {}
        rows = self._session.execute(
            select(ChatMessageORM.session_id, ChatMessageORM.content)
            .where(
                ChatMessageORM.session_id.in_(session_ids),
                ChatMessageORM.role == ChatMessageRole.USER,
            )
            .order_by(ChatMessageORM.session_id, ChatMessageORM.created_at)
        ).all()
        first: dict[uuid.UUID, str] = {}
        for session_id, content in rows:
            first.setdefault(session_id, content)
        return first
```

Replace `list_messages_for_session`:

```python
    def list_messages_for_session(self, session_id: uuid.UUID) -> list[ChatMessage]:
        # routers/chat.py stores a question and its answer with the same
        # timestamp, so created_at alone leaves their order to the database.
        # The question always comes first.
        rows = self._session.execute(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(
                ChatMessageORM.created_at,
                sa.case((ChatMessageORM.role == ChatMessageRole.USER, 0), else_=1),
            )
        ).scalars()
        return [_chat_message_to_domain(row) for row in rows]
```

Replace `add_citation`:

```python
    def add_citation(
        self, *, message_id: uuid.UUID, document_id: uuid.UUID,
        segment_id: uuid.UUID | None, paragraph_index: int | None = None,
    ) -> ChatMessageCitation:
        orm = ChatMessageCitationORM(
            id=uuid.uuid4(), message_id=message_id, document_id=document_id,
            segment_id=segment_id, paragraph_index=paragraph_index,
        )
        self._session.add(orm)
        self._session.flush()
        return _chat_message_citation_to_domain(orm)
```

If `ChatMessageRole` is not yet imported in `repositories.py`, add it to the existing `from normly_core.graph.domain import (...)` block.

- [ ] **Step 8: Exempt the new account-scoped read**

In `core/tests/graph/test_architecture.py`, inside `JURISDICTION_EXEMPT_READS`, after `"ChatRepository.list_messages_for_session",` add:

```python
    "ChatRepository.get_session_for_account",
```

- [ ] **Step 9: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_chat_repository.py tests/graph/test_architecture.py tests/test_migrate.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add docs/superpowers/specs/2026-10-17-answer-source-chips-and-chat-history-design.md \
  core/migrations/versions/0038_chat_titles_and_paragraph_citations.py \
  core/src/normly_core/graph core/tests/graph/test_chat_repository.py \
  core/tests/graph/test_architecture.py
git commit -s -m "feat(core): store chat session titles and paragraph citations" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Citable segments and segment headings in the repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (`SegmentRepository`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`PostgresSegmentRepository`)
- Test: `core/tests/graph/test_segment_repository.py`

**Interfaces:**
- Produces:
  - `PostgresSegmentRepository.list_citable_segments_for_jurisdiction(document_id: uuid.UUID, jurisdiction: str) -> list[Segment]` — gate: `may_process AND may_index_fulltext AND may_cite_passages AND revoked_at IS NULL`, ordered by `sequence_number`.
  - `PostgresSegmentRepository.list_segment_headings_for_jurisdiction(segment_ids: list[uuid.UUID], jurisdiction: str) -> dict[uuid.UUID, str | None]` — gate: same as `list_segments_for_jurisdiction` (`may_process AND may_index_fulltext AND revoked_at IS NULL`); absent ids are not visible.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/graph/test_segment_repository.py`:

```python
def _seeded_document(db_session, *, content_hash, may_cite_passages, may_index_fulltext=True):
    from datetime import datetime, timezone

    from normly_core.graph.postgres.repositories import PostgresDeliveryRepository

    source = _make_source(db_session, jurisdiction="DE")
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=content_hash, edition="2020", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction="DE", may_process=True,
        may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
        may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="test",
        delivery_id=delivery.id,
    )
    repo = PostgresSegmentRepository(db_session)
    second, _ = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=2,
        heading="§ 2 Pflichten", text="Zweiter Text", language="de",
    )
    first, _ = repo.add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 1 Geltungsbereich", text="Erster Text", language="de",
    )
    return document, delivery, first, second


def test_citable_segments_are_listed_in_sequence_order(db_session):
    document, _, first, second = _seeded_document(
        db_session, content_hash="sha256:citable-1", may_cite_passages=True,
    )

    segments = PostgresSegmentRepository(db_session).list_citable_segments_for_jurisdiction(
        document.id, "DE",
    )

    assert [s.id for s in segments] == [first.id, second.id]


def test_indexable_but_not_citable_segments_are_not_listed(db_session):
    document, _, _, _ = _seeded_document(
        db_session, content_hash="sha256:citable-2", may_cite_passages=False,
    )

    repo = PostgresSegmentRepository(db_session)
    assert repo.list_citable_segments_for_jurisdiction(document.id, "DE") == []
    assert len(repo.list_segments_for_jurisdiction(document.id, "DE")) == 2


def test_citable_segments_respect_jurisdiction_and_revocation(db_session):
    from normly_core.graph.postgres.repositories import PostgresDeliveryRepository

    document, delivery, _, _ = _seeded_document(
        db_session, content_hash="sha256:citable-3", may_cite_passages=True,
    )
    repo = PostgresSegmentRepository(db_session)
    assert repo.list_citable_segments_for_jurisdiction(document.id, "AT") == []

    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    assert repo.list_citable_segments_for_jurisdiction(document.id, "DE") == []


def test_segment_headings_are_returned_for_visible_segments_only(db_session):
    visible_doc, _, first, second = _seeded_document(
        db_session, content_hash="sha256:headings-1", may_cite_passages=False,
    )
    hidden_doc, _, hidden, _ = _seeded_document(
        db_session, content_hash="sha256:headings-2", may_cite_passages=True,
        may_index_fulltext=False,
    )

    headings = PostgresSegmentRepository(db_session).list_segment_headings_for_jurisdiction(
        [first.id, second.id, hidden.id], "DE",
    )

    assert headings == {first.id: "§ 1 Geltungsbereich", second.id: "§ 2 Pflichten"}
    assert PostgresSegmentRepository(db_session).list_segment_headings_for_jurisdiction(
        [], "DE",
    ) == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_segment_repository.py -v`
Expected: the four new tests FAIL with `AttributeError` (methods missing).

- [ ] **Step 3: Extend the Protocol**

In `core/src/normly_core/graph/domain.py`, in `SegmentRepository` after `list_segments_for_jurisdiction`:

```python
    def list_citable_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]:
        """Segments whose text may be shown to a reader (may_cite_passages)."""
        ...

    def list_segment_headings_for_jurisdiction(
        self, segment_ids: list[uuid.UUID], jurisdiction: str
    ) -> dict[uuid.UUID, str | None]:
        """Headings of the visible segments among segment_ids; others are absent."""
        ...
```

- [ ] **Step 4: Implement**

In `PostgresSegmentRepository`, after `list_segments_for_jurisdiction`:

```python
    def list_citable_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]:
        # Showing a passage to a reader is a stricter question than indexing
        # it for search: EUR-Lex texts, for example, are indexable but not
        # citable. may_index_fulltext stays in the gate because segments only
        # exist where indexing was permitted when they were written.
        rows = self._session.execute(
            select(SegmentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == SegmentORM.document_id,
            )
            .where(
                SegmentORM.document_id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.may_cite_passages.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(SegmentORM.sequence_number)
        ).scalars()
        return [_segment_to_domain(row) for row in rows]

    def list_segment_headings_for_jurisdiction(
        self, segment_ids: list[uuid.UUID], jurisdiction: str
    ) -> dict[uuid.UUID, str | None]:
        # Same read gate as list_segments_for_jurisdiction: chat citations
        # point at segments that synthesis read under exactly this gate.
        if not segment_ids:
            return {}
        rows = self._session.execute(
            select(SegmentORM.id, SegmentORM.heading)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == SegmentORM.document_id,
            )
            .where(
                SegmentORM.id.in_(segment_ids),
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).all()
        return {segment_id: heading for segment_id, heading in rows}
```

- [ ] **Step 5: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_segment_repository.py tests/graph/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph core/tests/graph/test_segment_repository.py
git commit -s -m "feat(core): list citable segments and segment headings" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `GET /v1/documents/{id}/segments`

**Files:**
- Create: `api/src/normly_api/routers/segments.py`
- Modify: `api/src/normly_api/schemas.py`, `api/src/normly_api/main.py`
- Test: create `api/tests/test_segments.py`; modify `api/tests/test_openapi_and_end_to_end.py`

**Interfaces:**
- Consumes: `PostgresSegmentRepository.list_citable_segments_for_jurisdiction` (Task 2).
- Produces: `GET /v1/documents/{document_id}/segments?jurisdiction=XX` → 200 `[{"id", "sequence_number", "heading", "text"}]`; 404 `{"detail": "document not found"}`.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_segments.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _seed(db_session, *, content_hash, may_cite_passages=True, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=content_hash, edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=may_cite_passages, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 1 Geltungsbereich", text="Diese Vorschrift gilt für Unternehmer.",
        language="de",
    )
    return document, delivery, segment


def test_citable_segments_are_returned(client, db_session):
    document, _, segment = _seed(db_session, content_hash="sha256:api-segments-1")

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json() == [{
        "id": str(segment.id), "sequence_number": 1, "heading": "§ 1 Geltungsbereich",
        "text": "Diese Vorschrift gilt für Unternehmer.",
    }]


def test_a_visible_but_not_citable_document_returns_an_empty_list(client, db_session):
    document, _, _ = _seed(
        db_session, content_hash="sha256:api-segments-2", may_cite_passages=False,
    )

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json() == []


def test_a_document_not_visible_in_the_jurisdiction_is_404(client, db_session):
    document, _, _ = _seed(
        db_session, content_hash="sha256:api-segments-3", jurisdiction="FR",
    )

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 404


def test_an_unknown_document_is_404(client):
    response = client.get(f"/v1/documents/{uuid.uuid4()}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 404


def test_a_revoked_delivery_hides_the_document(client, db_session):
    document, delivery, _ = _seed(db_session, content_hash="sha256:api-segments-4")
    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    # Revocation removes the only classification, so the document itself is
    # no longer visible -- the same 404 as an unclassified document.
    assert response.status_code == 404
```

In `api/tests/test_openapi_and_end_to_end.py`:
- add `"/v1/documents/{document_id}/segments",` to the expected `paths` set (after `/rights`);
- add `"/v1/documents/{document_id}/segments",` to the tuple of paths that must declare a 404.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && ../.venv/bin/pytest tests/test_segments.py tests/test_openapi_and_end_to_end.py -v`
Expected: FAIL — 404 for the first two tests (route missing), path set mismatch.

- [ ] **Step 3: Add the schema**

In `api/src/normly_api/schemas.py`, after `TitleResponse`:

```python
class SegmentResponse(BaseModel):
    id: uuid.UUID
    sequence_number: int
    heading: str | None
    text: str
```

- [ ] **Step 4: Add the router**

Create `api/src/normly_api/routers/segments.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresSegmentRepository,
)

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import SegmentResponse

segments_router = APIRouter(prefix="/v1/documents", tags=["segments"])


@segments_router.get(
    "/{document_id}/segments",
    response_model=list[SegmentResponse],
    responses=NOT_FOUND_RESPONSE,
)
def list_segments(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> list[SegmentResponse]:
    # Same non-disclosure as GET /v1/documents/{id}: a document that is not
    # visible in this jurisdiction is a 404, whether it exists or not.
    if PostgresDocumentRepository(session).get_document_for_jurisdiction(
        document_id, jurisdiction
    ) is None:
        raise HTTPException(status_code=404, detail="document not found")

    # A visible document whose text may not be shown answers with an empty
    # list; the caller reads the reason from GET /v1/documents/{id}/rights.
    segments = PostgresSegmentRepository(session).list_citable_segments_for_jurisdiction(
        document_id, jurisdiction
    )
    return [
        SegmentResponse(
            id=s.id, sequence_number=s.sequence_number, heading=s.heading, text=s.text,
        )
        for s in segments
    ]
```

- [ ] **Step 5: Register the router**

In `api/src/normly_api/main.py`, import it next to the other routers:

```python
from normly_api.routers.segments import segments_router
```

and after the `rights_router` block:

```python
    app.include_router(
        segments_router, responses=COMMON_ERROR_RESPONSES,
        dependencies=[Depends(enforce_rate_limit)],
    )
```

- [ ] **Step 6: Run the tests**

Run: `cd api && ../.venv/bin/pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add api/src/normly_api api/tests/test_segments.py api/tests/test_openapi_and_end_to_end.py
git commit -s -m "feat(api): serve citable segments of a document" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Citation labels in `chat/`

**Files:**
- Modify: `chat/src/normly_chat/api_client.py`
- Create: `chat/src/normly_chat/citation_labels.py`
- Test: create `chat/tests/test_citation_labels.py`; modify `chat/tests/test_api_client.py`

**Interfaces:**
- Consumes: `list_segment_headings_for_jurisdiction` (Task 2); `GET /v1/documents/{id}` of `api/`.
- Produces:
  - `ApiClient.get_document(document_id: uuid.UUID, jurisdiction: str) -> dict | None`
  - `section_from_heading(heading: str | None) -> str | None`
  - `document_label(document: dict) -> str`
  - `CitationResolver(api_client, segment_repo, jurisdiction: str)` with `.label(document_id: uuid.UUID) -> str | None` and `.resolve(citations: list[dict]) -> list[dict]`. Input citation dicts have keys `document_id: uuid.UUID`, `segment_id: uuid.UUID | None`, `paragraph_index: int | None`; output adds `designation: str`, `section: str | None` and drops citations whose document cannot be fetched.

- [ ] **Step 1: Write the failing tests**

Look at how `chat/tests/test_api_client.py` stubs HTTP for `get_validity` and add the same kind of test for `get_document` (200 returns the JSON body, 404 returns `None`, URL is `{base}/v1/documents/{id}` with `jurisdiction` as query parameter). Copy the structure of the existing `get_validity` tests in that file exactly, changing only the method and path.

Create `chat/tests/test_citation_labels.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import pytest

from normly_chat.citation_labels import CitationResolver, document_label, section_from_heading


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("4.5.4 Performance Level", "4.5.4"),
        ("4.5.4. Performance Level", "4.5.4"),
        ("5 Anforderungen", "5"),
        ("§ 1 Geltungsbereich", "§ 1"),
        ("§ 12a Übergangsvorschrift", "§ 12a"),
        ("Anhang A", None),
        ("Vorwort", None),
        ("", None),
        (None, None),
    ],
)
def test_section_from_heading(heading, expected):
    assert section_from_heading(heading) == expected


def test_document_label_prefers_the_primary_designation():
    document = {
        "origin_issuer": "ISO", "origin_number": "13849-1",
        "designations": [
            {"designation": "BS EN ISO 13849-1", "is_primary": False},
            {"designation": "DIN EN ISO 13849-1", "is_primary": True},
        ],
    }
    assert document_label(document) == "DIN EN ISO 13849-1"


def test_document_label_falls_back_to_any_designation_then_to_the_origin():
    assert document_label({
        "origin_issuer": "ISO", "origin_number": "1",
        "designations": [{"designation": "EN 1", "is_primary": False}],
    }) == "EN 1"
    assert document_label(
        {"origin_issuer": "ISO", "origin_number": "9001", "designations": []}
    ) == "ISO 9001"


class _FakeApiClient:
    def __init__(self, documents):
        self._documents = documents
        self.calls = []

    def get_document(self, document_id, jurisdiction):
        self.calls.append((document_id, jurisdiction))
        return self._documents.get(document_id)


class _FakeSegmentRepo:
    def __init__(self, headings):
        self._headings = headings
        self.calls = []

    def list_segment_headings_for_jurisdiction(self, segment_ids, jurisdiction):
        self.calls.append((list(segment_ids), jurisdiction))
        return {s: self._headings[s] for s in segment_ids if s in self._headings}


def test_resolve_adds_labels_fetches_each_document_once_and_drops_unknown_documents():
    known, unknown = uuid.uuid4(), uuid.uuid4()
    segment = uuid.uuid4()
    api_client = _FakeApiClient({
        known: {
            "origin_issuer": "DGUV", "origin_number": "Vorschrift 1",
            "designations": [{"designation": "DGUV Vorschrift 1", "is_primary": True}],
        },
    })
    segment_repo = _FakeSegmentRepo({segment: "§ 2 Pflichten des Unternehmers"})
    resolver = CitationResolver(api_client, segment_repo, "DE")

    resolved = resolver.resolve([
        {"document_id": known, "segment_id": segment, "paragraph_index": 0},
        {"document_id": known, "segment_id": None, "paragraph_index": None},
        {"document_id": unknown, "segment_id": None, "paragraph_index": 1},
    ])

    assert resolved == [
        {"document_id": known, "segment_id": segment, "paragraph_index": 0,
         "designation": "DGUV Vorschrift 1", "section": "§ 2"},
        {"document_id": known, "segment_id": None, "paragraph_index": None,
         "designation": "DGUV Vorschrift 1", "section": None},
    ]
    assert api_client.calls == [(known, "DE"), (unknown, "DE")]
    assert segment_repo.calls == [([segment], "DE")]


def test_resolve_without_segments_does_not_query_headings():
    document_id = uuid.uuid4()
    segment_repo = _FakeSegmentRepo({})
    resolver = CitationResolver(
        _FakeApiClient({document_id: {
            "origin_issuer": "ISO", "origin_number": "1", "designations": [],
        }}),
        segment_repo, "DE",
    )

    resolver.resolve([{"document_id": document_id, "segment_id": None, "paragraph_index": 0}])

    assert segment_repo.calls == []


def test_label_returns_none_for_an_unknown_document():
    resolver = CitationResolver(_FakeApiClient({}), _FakeSegmentRepo({}), "DE")
    assert resolver.label(uuid.uuid4()) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_citation_labels.py tests/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: normly_chat.citation_labels` and `AttributeError: get_document`.

- [ ] **Step 3: Add `ApiClient.get_document`**

In `chat/src/normly_chat/api_client.py`, after `search_document`:

```python
    def get_document(self, document_id: uuid.UUID, jurisdiction: str) -> dict | None:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
            response = http.get(
                f"{self._base_url}/v1/documents/{document_id}",
                params={"jurisdiction": jurisdiction},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Create `citation_labels.py`**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Labels for citation chips: which norm, which section.

Labels are derived on every read, never stored, so a reopened chat shows the
current state of the knowledge base instead of a stale snapshot.
"""

from __future__ import annotations

import re
import uuid

# "4.5.4 Performance Level" -> "4.5.4", "§ 1 Geltungsbereich" -> "§ 1".
# A trailing dot after a number ("4.5.4. Title") is not part of the section.
_SECTION_PATTERN = re.compile(r"^\s*(§\s*\d+[a-z]?|\d+(?:\.\d+)*)\.?(?=\s|$)")


def section_from_heading(heading: str | None) -> str | None:
    if not heading:
        return None
    match = _SECTION_PATTERN.match(heading)
    return match.group(1) if match else None


def document_label(document: dict) -> str:
    designations = document.get("designations") or []
    for designation in designations:
        if designation.get("is_primary"):
            return designation["designation"]
    if designations:
        return designations[0]["designation"]
    return f"{document['origin_issuer']} {document['origin_number']}"


class CitationResolver:
    """
    Resolves chip labels for one jurisdiction, fetching each document from
    api/ at most once. A document api/ does not return (not visible, retired)
    yields no label, and its citations are dropped.
    """

    def __init__(self, api_client, segment_repo, jurisdiction: str):
        self._api_client = api_client
        self._segment_repo = segment_repo
        self._jurisdiction = jurisdiction
        self._documents: dict[uuid.UUID, dict | None] = {}

    def label(self, document_id: uuid.UUID) -> str | None:
        if document_id not in self._documents:
            self._documents[document_id] = self._api_client.get_document(
                document_id, self._jurisdiction
            )
        document = self._documents[document_id]
        return document_label(document) if document is not None else None

    def resolve(self, citations: list[dict]) -> list[dict]:
        segment_ids = [c["segment_id"] for c in citations if c.get("segment_id") is not None]
        headings = (
            self._segment_repo.list_segment_headings_for_jurisdiction(
                segment_ids, self._jurisdiction
            )
            if segment_ids else {}
        )
        resolved = []
        for citation in citations:
            label = self.label(citation["document_id"])
            if label is None:
                continue
            resolved.append({
                **citation,
                "designation": label,
                "section": section_from_heading(headings.get(citation.get("segment_id"))),
            })
        return resolved
```

- [ ] **Step 5: Run the tests**

Run: `cd chat && ../.venv/bin/pytest tests/test_citation_labels.py tests/test_api_client.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add chat/src/normly_chat/api_client.py chat/src/normly_chat/citation_labels.py \
  chat/tests/test_citation_labels.py chat/tests/test_api_client.py
git commit -s -m "feat(chat): resolve citation chip labels" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Source-marker parser

**Files:**
- Create: `chat/src/normly_chat/markers.py`
- Test: create `chat/tests/test_markers.py`

**Interfaces:**
- Produces:
  - `number_context(texts: list[str]) -> str` — `"[1] a\n\n[2] b"`.
  - `split_paragraphs(text: str) -> list[str]` — split at blank lines, stripped, empty blocks dropped.
  - `MarkedParagraph(text: str, sources: list[int])` — frozen dataclass; `sources` are 0-based indexes into the context list, in first-seen order, without duplicates.
  - `parse_marked_answer(answer: str, source_count: int) -> list[MarkedParagraph]`.

- [ ] **Step 1: Write the failing tests**

Create `chat/tests/test_markers.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.markers import (
    MarkedParagraph,
    number_context,
    parse_marked_answer,
    split_paragraphs,
)


def test_number_context_numbers_from_one():
    assert number_context(["Erster.", "Zweiter."]) == "[1] Erster.\n\n[2] Zweiter."


def test_split_paragraphs_splits_at_blank_lines_and_drops_empty_blocks():
    assert split_paragraphs("A\nweiter\n\n  \n\nB\n") == ["A\nweiter", "B"]
    assert split_paragraphs("") == []


def test_markers_are_collected_per_paragraph_and_stripped():
    answer = "Schutzbrillen sind Pflicht [1].\n\nDas gilt auch für Helfer [2][3]."

    assert parse_marked_answer(answer, 3) == [
        MarkedParagraph("Schutzbrillen sind Pflicht.", [0]),
        MarkedParagraph("Das gilt auch für Helfer.", [1, 2]),
    ]


def test_comma_lists_and_mid_sentence_markers_are_understood():
    answer = "Laut Vorschrift [1, 2] gilt das, siehe auch [2]."

    assert parse_marked_answer(answer, 2) == [
        MarkedParagraph("Laut Vorschrift gilt das, siehe auch.", [0, 1]),
    ]


def test_markers_outside_the_source_range_are_dropped():
    assert parse_marked_answer("Text [0] und [7] und [2].", 2) == [
        MarkedParagraph("Text und und.", [1]),
    ]


def test_an_answer_without_markers_keeps_its_paragraphs_with_no_sources():
    assert parse_marked_answer("Eins.\n\nZwei.", 3) == [
        MarkedParagraph("Eins.", []),
        MarkedParagraph("Zwei.", []),
    ]


def test_a_marker_only_block_attaches_to_the_previous_paragraph():
    assert parse_marked_answer("Eins.\n\n[2]", 2) == [MarkedParagraph("Eins.", [1])]


def test_a_leading_marker_only_block_is_dropped():
    assert parse_marked_answer("[1]\n\nEins.", 2) == [MarkedParagraph("Eins.", [])]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_markers.py -v`
Expected: FAIL with `ModuleNotFoundError: normly_chat.markers`.

- [ ] **Step 3: Implement**

Create `chat/src/normly_chat/markers.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Source markers in synthesis answers.

The model sees the context passages numbered ([1], [2], ...) and backs each
paragraph with the numbers it relies on. This module numbers the context and
turns a marked answer into clean paragraphs with their sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "[1]", "[1][3]", "[1, 3]"; the whitespace in front goes with the marker so
# "Pflicht [1]." becomes "Pflicht.".
_MARKER = re.compile(r"\s*\[(\d+(?:\s*,\s*\d+)*)\]")
_BLANK_LINE = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class MarkedParagraph:
    text: str
    sources: list[int] = field(default_factory=list)


def number_context(texts: list[str]) -> str:
    return "\n\n".join(f"[{number}] {text}" for number, text in enumerate(texts, start=1))


def split_paragraphs(text: str) -> list[str]:
    return [block.strip() for block in _BLANK_LINE.split(text.strip()) if block.strip()]


def parse_marked_answer(answer: str, source_count: int) -> list[MarkedParagraph]:
    paragraphs: list[MarkedParagraph] = []
    for block in split_paragraphs(answer):
        sources: list[int] = []
        for match in _MARKER.finditer(block):
            for number in match.group(1).split(","):
                index = int(number) - 1
                if 0 <= index < source_count and index not in sources:
                    sources.append(index)
        text = _MARKER.sub("", block).strip()
        if text:
            paragraphs.append(MarkedParagraph(text, sources))
        elif paragraphs:
            # A line holding only markers backs the paragraph above it.
            previous = paragraphs[-1]
            merged = previous.sources + [s for s in sources if s not in previous.sources]
            paragraphs[-1] = MarkedParagraph(previous.text, merged)
    return paragraphs
```

- [ ] **Step 4: Run the tests**

Run: `cd chat && ../.venv/bin/pytest tests/test_markers.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/markers.py chat/tests/test_markers.py
git commit -s -m "feat(chat): parse source markers in synthesis answers" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Synthesis answers with paragraph citations

**Files:**
- Modify: `chat/src/normly_chat/synthesis.py`
- Test: `chat/tests/test_synthesis.py`

**Interfaces:**
- Consumes: `number_context`, `parse_marked_answer` (Task 5).
- Produces: `SynthesisAnswer(paragraphs: list[str], citations: list[dict], is_fallback: bool, ollama_calls: int)` with a read-only property `text` (`"\n\n".join(paragraphs)`). Citation dicts: `{"document_id", "segment_id", "paragraph_index"}`.

- [ ] **Step 1: Update existing tests and add new ones**

In `chat/tests/test_synthesis.py`, every existing assertion of the form

```python
assert result.citations == [{"document_id": X, "segment_id": Y}]
```

gains `"paragraph_index": None` in each dict (those answers carry no markers, so the whole-answer fallback applies). Then append:

```python
def _two_call_llm(answer):
    class _Llm:
        def __init__(self):
            self.calls = 0
            self.messages = []

        def chat(self, messages):
            self.calls += 1
            self.messages.append(messages)
            return answer if self.calls == 1 else "ja"

    return _Llm()


def test_markers_become_paragraph_citations_and_are_stripped():
    first = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")
    second = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Helfer tragen ebenfalls Schutzbrillen.")
    llm = _two_call_llm(
        "Beim Schweißen muss eine Schutzbrille getragen werden [1].\n\n"
        "Auch helfende Personen brauchen eine [2]."
    )

    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([first, second]), llm,
    )

    assert result.is_fallback is False
    assert result.paragraphs == [
        "Beim Schweißen muss eine Schutzbrille getragen werden.",
        "Auch helfende Personen brauchen eine.",
    ]
    assert result.text == "\n\n".join(result.paragraphs)
    assert result.citations == [
        {"document_id": first.document_id, "segment_id": first.id, "paragraph_index": 0},
        {"document_id": second.document_id, "segment_id": second.id, "paragraph_index": 1},
    ]
    system_prompt = llm.messages[0][0]["content"]
    assert "[1] Schutzbrillen sind beim Schweißen Pflicht." in system_prompt
    assert "[2] Helfer tragen ebenfalls Schutzbrillen." in system_prompt
    # The faithfulness check sees the stripped answer, not the markers.
    assert "[1]" not in llm.messages[1][1]["content"]


def test_an_answer_without_valid_markers_cites_every_segment_for_the_whole_answer():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")
    llm = _two_call_llm("Beim Schweißen muss eine Schutzbrille getragen werden [9].")

    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert result.paragraphs == ["Beim Schweißen muss eine Schutzbrille getragen werden."]
    assert result.citations == [
        {"document_id": segment.document_id, "segment_id": segment.id, "paragraph_index": None},
    ]


def test_the_english_prompt_asks_for_markers_in_english():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Goggles are mandatory when welding.")
    llm = _two_call_llm("Wear goggles when welding [1].")

    build_synthesis_answer(
        "What protection?", "DE", "en", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert "for example [1] or [2][3]" in llm.messages[0][0]["content"]


def test_an_answer_of_only_markers_is_a_fallback():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Text.")
    llm = _two_call_llm("[1]")

    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert result.is_fallback is True
    assert result.paragraphs == ["Dazu finde ich in den verfügbaren Quellen keine ausreichende Grundlage."]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_synthesis.py -v`
Expected: the new tests and the updated assertions FAIL (`paragraphs` missing, no `paragraph_index`).

- [ ] **Step 3: Rewrite the synthesis module**

In `chat/src/normly_chat/synthesis.py`:

Add the import:

```python
from normly_chat.markers import number_context, parse_marked_answer
```

Replace `SynthesisAnswer` and `_fallback`:

```python
@dataclass(frozen=True)
class SynthesisAnswer:
    paragraphs: list[str]
    citations: list[dict] = field(default_factory=list)
    is_fallback: bool = False
    ollama_calls: int = 0

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


def _fallback(language: str, ollama_calls: int = 0) -> SynthesisAnswer:
    return SynthesisAnswer(
        paragraphs=[_FALLBACK_TEXT[language]], citations=[], is_fallback=True,
        ollama_calls=ollama_calls,
    )
```

Replace `_SYSTEM_PROMPT`:

```python
_SYSTEM_PROMPT = {
    "de": (
        "Du beantwortest Fragen ausschließlich auf Grundlage der folgenden nummerierten "
        "Kontextabschnitte. Paraphrasiere, gib den Kontext nicht wortwörtlich wieder. "
        "Antworte auf Deutsch. Trenne Absätze durch eine Leerzeile und belege jeden Absatz "
        "mit den Nummern der Abschnitte, auf die er sich stützt, zum Beispiel [1] oder [2][3]."
    ),
    "en": (
        "You answer questions using only the following numbered context passages. "
        "Paraphrase, do not reproduce the context verbatim. Answer in English. "
        "Separate paragraphs with a blank line and back every paragraph with the numbers "
        "of the passages it relies on, for example [1] or [2][3]."
    ),
}
```

Replace the body of `build_synthesis_answer` from `context = ...` to the end:

```python
    # The checks compare against the plain passages; only the model sees the
    # numbers it needs to set markers.
    context = "\n\n".join(segment.text for segment in segments)
    numbered_context = number_context([segment.text for segment in segments])
    messages = [
        {"role": "system", "content": f"{_SYSTEM_PROMPT[language]}\n\nKontext:\n{numbered_context}"},
        {"role": "user", "content": message},
    ]
    raw_answer = llm_client.chat(messages)
    ollama_calls = 1

    paragraphs = parse_marked_answer(raw_answer, len(segments))
    if not paragraphs:
        return _fallback(language, ollama_calls=ollama_calls)
    answer_text = "\n\n".join(paragraph.text for paragraph in paragraphs)

    if _has_verbatim_overlap(answer_text, context):
        return _fallback(language, ollama_calls=ollama_calls)

    if not _is_faithful(answer_text, context, llm_client):
        ollama_calls += 1
        return _fallback(language, ollama_calls=ollama_calls)
    ollama_calls += 1

    if any(paragraph.sources for paragraph in paragraphs):
        citations = [
            {
                "document_id": segments[source].document_id,
                "segment_id": segments[source].id,
                "paragraph_index": index,
            }
            for index, paragraph in enumerate(paragraphs)
            for source in paragraph.sources
        ]
    else:
        # No usable marker at all: the answer still never stands without a
        # source, so every passage it was built from backs the whole answer.
        citations = [
            {"document_id": segment.document_id, "segment_id": segment.id, "paragraph_index": None}
            for segment in segments
        ]
    return SynthesisAnswer(
        paragraphs=[paragraph.text for paragraph in paragraphs],
        citations=citations, ollama_calls=ollama_calls,
    )
```

- [ ] **Step 4: Run the tests**

Run: `cd chat && ../.venv/bin/pytest tests/test_synthesis.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/synthesis.py chat/tests/test_synthesis.py
git commit -s -m "feat(chat): cite synthesis sources per paragraph" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Structural answers name documents and cite per sentence

**Files:**
- Modify: `chat/src/normly_chat/structural.py`
- Test: `chat/tests/test_structural.py`, `chat/tests/test_structural_end_to_end.py`

**Interfaces:**
- Consumes: `CitationResolver.label` (Task 4).
- Produces: `build_structural_answer(question_type, message, jurisdiction, language, api_client, labels: CitationResolver) -> StructuralAnswer`; `StructuralAnswer(paragraphs: list[str], citations: list[dict], is_fallback: bool)` with property `text`. Each paragraph cites the asked-about document and its targets, all with `segment_id: None` and the paragraph's index.

- [ ] **Step 1: Rewrite the unit tests**

In `chat/tests/test_structural.py`:

Extend `_FakeApiClient` with documents and a `get_document` method, and add a helper that builds a resolver:

```python
from normly_chat.citation_labels import CitationResolver


class _FakeApiClient:
    def __init__(self, *, document=None, validity=None, edges=None, documents=None):
        self._document = document
        self._validity = validity
        self._edges = edges
        self._documents = documents or {}
        self.calls = []

    def search_document(self, issuer, designation, jurisdiction):
        self.calls.append(("search_document", issuer, designation, jurisdiction))
        return self._document

    def get_validity(self, document_id, jurisdiction):
        self.calls.append(("get_validity", document_id, jurisdiction))
        return self._validity

    def get_edges(self, document_id, jurisdiction):
        self.calls.append(("get_edges", document_id, jurisdiction))
        return self._edges

    def get_document(self, document_id, jurisdiction):
        return self._documents.get(document_id)


class _NoSegments:
    def list_segment_headings_for_jurisdiction(self, segment_ids, jurisdiction):
        return {}


def _answer(question_type, message, language, api_client):
    labels = CitationResolver(api_client, _NoSegments(), "DE")
    return build_structural_answer(question_type, message, "DE", language, api_client, labels)


def _doc(designation):
    return {
        "origin_issuer": "X", "origin_number": "0",
        "designations": [{"designation": designation, "is_primary": True}],
    }
```

Change every existing call `build_structural_answer(QT, msg, "DE", lang, api_client)` to `_answer(QT, msg, lang, api_client)`. Change every existing citation expectation `{"document_id": D, "segment_id": None}` for the validity question to `{"document_id": D, "segment_id": None, "paragraph_index": 0}`.

Replace the existing reference-question tests (the ones that assert raw target ids in `result.text`) with these:

```python
SOURCE = "22222222-2222-2222-2222-222222222222"
TARGET = "33333333-3333-3333-3333-333333333333"
SUCCESSOR = "44444444-4444-4444-4444-444444444444"
WITHDRAWER = "55555555-5555-5555-5555-555555555555"


def test_a_reference_names_the_target_and_cites_both_documents():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=[{"edge_type": "references", "from_document_id": SOURCE,
                "to_document_id": TARGET, "jurisdiction": "DE", "layer": "free"}],
        documents={uuid.UUID(TARGET): _doc("DIN EN ISO 12100")},
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "Worauf verweist DIN EN ISO 9001?", "de", api_client,
    )

    assert result.paragraphs == ["DIN EN ISO 9001 verweist auf: DIN EN ISO 12100."]
    assert result.citations == [
        {"document_id": uuid.UUID(SOURCE), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(TARGET), "segment_id": None, "paragraph_index": 0},
    ]


def test_successor_and_withdrawal_are_named_in_english():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "replaced", "replaced_by": [SUCCESSOR],
                  "withdrawn_reference": WITHDRAWER},
        edges=[],
        documents={
            uuid.UUID(SUCCESSOR): _doc("DIN EN ISO 9001:2015"),
            uuid.UUID(WITHDRAWER): _doc("DIN-Mitteilungen 2015-09"),
        },
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "What replaces DIN EN ISO 9001?", "en", api_client,
    )

    assert result.paragraphs == [
        "DIN EN ISO 9001 has been replaced by: DIN EN ISO 9001:2015.",
        "DIN EN ISO 9001 has been withdrawn by: DIN-Mitteilungen 2015-09.",
    ]
    assert result.citations == [
        {"document_id": uuid.UUID(SOURCE), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(SUCCESSOR), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(SOURCE), "segment_id": None, "paragraph_index": 1},
        {"document_id": uuid.UUID(WITHDRAWER), "segment_id": None, "paragraph_index": 1},
    ]


def test_an_unresolvable_target_drops_its_sentence_and_never_shows_an_id():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=[
            {"edge_type": "references", "from_document_id": SOURCE,
             "to_document_id": TARGET, "jurisdiction": "DE", "layer": "free"},
            {"edge_type": "based_on_law", "from_document_id": SOURCE,
             "to_document_id": SUCCESSOR, "jurisdiction": "DE", "layer": "free"},
        ],
        documents={uuid.UUID(SUCCESSOR): _doc("ArbSchG")},
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "Worauf verweist DIN EN ISO 9001?", "de", api_client,
    )

    assert result.paragraphs == ["DIN EN ISO 9001 beruht auf: ArbSchG."]
    assert TARGET not in result.text


def test_only_unresolvable_targets_give_the_fallback():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "replaced", "replaced_by": [SUCCESSOR], "withdrawn_reference": None},
        edges=[],
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "de", api_client,
    )

    assert result.is_fallback is True
    assert result.citations == []
```

Keep every other existing test (fallback paths, status phrases in both languages), adapted only by the call and citation changes described above.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_structural.py -v`
Expected: FAIL — `build_structural_answer()` takes 5 positional arguments, `paragraphs` missing.

- [ ] **Step 3: Rewrite `structural.py` below the phrase tables**

Replace everything from `@dataclass(frozen=True)\nclass StructuralAnswer` to the end of the file with:

```python
@dataclass(frozen=True)
class StructuralAnswer:
    paragraphs: list[str]
    citations: list[dict] = field(default_factory=list)
    is_fallback: bool = False

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


def _fallback(language: str) -> StructuralAnswer:
    return StructuralAnswer(paragraphs=[_FALLBACK_TEXT[language]], citations=[], is_fallback=True)


def _labelled(labels: CitationResolver, document_ids: list[uuid.UUID]) -> list[tuple[uuid.UUID, str]]:
    # A target api/ does not return is left out entirely: its id must never
    # reach the answer text.
    pairs = []
    for document_id in document_ids:
        label = labels.label(document_id)
        if label is not None:
            pairs.append((document_id, label))
    return pairs


def build_structural_answer(
    question_type: QuestionType, message: str, jurisdiction: str, language: str, api_client,
    labels: CitationResolver,
) -> StructuralAnswer:
    found = extract_designation(message)
    if found is None:
        return _fallback(language)
    issuer, designation = found

    document = api_client.search_document(issuer, designation, jurisdiction)
    if document is None:
        return _fallback(language)

    # The API speaks JSON, so ids arrive as strings; the citation schemas
    # declare uuid.UUID, so the conversion belongs here.
    document_id = uuid.UUID(document["id"])

    paragraphs: list[str] = []
    citations: list[dict] = []

    def add(sentence: str, target_ids: list[uuid.UUID]) -> None:
        # Each sentence is one paragraph and cites the asked-about document
        # together with the documents the sentence names.
        index = len(paragraphs)
        paragraphs.append(sentence)
        citations.extend(
            {"document_id": cited, "segment_id": None, "paragraph_index": index}
            for cited in [document_id, *target_ids]
        )

    if question_type == QuestionType.STRUCTURAL_VALIDITY:
        validity = api_client.get_validity(document_id, jurisdiction)
        if validity is None:
            return _fallback(language)
        status = validity.get("status")
        phrase = _STATUS_PHRASE[language].get(status, _UNKNOWN_STATUS_PHRASE[language])
        add(f"{designation} {phrase}.", [])
        return StructuralAnswer(paragraphs=paragraphs, citations=citations)

    # A replacement question ("Was ersetzt DIN EN ISO 9001?") asks about the
    # OLD document, but REPLACES/WITHDRAWN_BY edges point FROM the successor TO
    # it -- so the outgoing-edge listing get_edges() returns is empty for
    # exactly the document the question names. The validity endpoint already
    # resolves that direction correctly (it queries incoming edges), so its
    # replaced_by / withdrawn_reference fields are the direction-safe source
    # for this question shape. Outgoing edges (genuine REFERENCES-style ones)
    # point the same way the question does and are still reported alongside.
    validity = api_client.get_validity(document_id, jurisdiction)
    edges = api_client.get_edges(document_id, jurisdiction)

    if validity is not None:
        successors = _labelled(
            labels, [uuid.UUID(str(target)) for target in validity.get("replaced_by") or []]
        )
        if successors:
            add(
                _REPLACED_BY_SENTENCE[language].format(
                    designation=designation,
                    targets=", ".join(label for _, label in successors),
                ),
                [target for target, _ in successors],
            )
        withdrawn_reference = validity.get("withdrawn_reference")
        if withdrawn_reference:
            withdrawing = _labelled(labels, [uuid.UUID(str(withdrawn_reference))])
            if withdrawing:
                target, label = withdrawing[0]
                add(
                    _WITHDRAWN_BY_SENTENCE[language].format(
                        designation=designation, reference=label,
                    ),
                    [target],
                )

    for edge in edges or []:
        resolved = _labelled(labels, [uuid.UUID(str(edge["to_document_id"]))])
        if not resolved:
            continue
        target, label = resolved[0]
        phrase = _EDGE_PHRASE[language].get(edge.get("edge_type"), _UNKNOWN_EDGE_PHRASE[language])
        add(f"{designation} {phrase}: {label}.", [target])

    if not paragraphs:
        return _fallback(language)
    return StructuralAnswer(paragraphs=paragraphs, citations=citations)
```

Add the import at the top:

```python
from normly_chat.citation_labels import CitationResolver
```

- [ ] **Step 4: Update the structural end-to-end tests**

In `chat/tests/test_structural_end_to_end.py`, the successor document has no designation, so its label is its origin `ISO 9001`. Update:

- `test_a_replacement_question_about_the_superseded_document_is_not_a_fallback`: replace `assert str(successor.id) in body["answer"]` with

```python
    assert "ISO 9001." in body["answer"]
    assert str(successor.id) not in body["answer"]
```

and the citation assertion with

```python
    assert [c["document_id"] for c in body["citations"]] == [str(superseded.id), str(successor.id)]
    assert {c["designation"] for c in body["citations"]} == {"DIN EN ISO 9001", "ISO 9001"}
```

- `test_an_english_replacement_question_answers_in_english`: replace the `answer` assertion with

```python
    assert body["answer"] == "DIN EN ISO 9001 has been replaced by: ISO 9001."
    assert body["paragraphs"] == [body["answer"]]
```

(These two tests need Task 8 for the `designation` and `paragraphs` fields; they run in Task 8, Step 5.)

- [ ] **Step 5: Keep the router working with the new signature**

In `chat/src/normly_chat/routers/chat.py`, add the import

```python
from normly_chat.citation_labels import CitationResolver
```

and change the structural call to pass a resolver (Task 8 reworks this block further):

```python
    else:
        labels = CitationResolver(
            api_client, PostgresSegmentRepository(session), payload.jurisdiction,
        )
        result = build_structural_answer(
            question_type, payload.message, payload.jurisdiction, payload.language, api_client,
            labels,
        )
```

The router still builds `CitationResponse(document_id=…, segment_id=…)` from the citation dicts and ignores `paragraph_index`, which is fine until Task 8.

- [ ] **Step 6: Run the chat suite**

Run: `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py -v`
Expected: all PASS. (The two end-to-end tests updated in Step 4 need Task 8's response fields and run there.)

- [ ] **Step 7: Commit**

```bash
git add chat/src/normly_chat/structural.py chat/src/normly_chat/routers/chat.py \
  chat/tests/test_structural.py chat/tests/test_structural_end_to_end.py
git commit -s -m "fix(chat): name structural answer targets instead of showing ids" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `POST /v1/chat` returns paragraphs and labelled citations

**Files:**
- Modify: `chat/src/normly_chat/schemas.py`, `chat/src/normly_chat/routers/chat.py`
- Test: `chat/tests/test_chat_router.py`

**Interfaces:**
- Consumes: `CitationResolver` (Task 4), new answer shapes (Tasks 6, 7), `add_citation(paragraph_index=…)` (Task 1).
- Produces:
  - `CitationResponse(document_id: UUID, segment_id: UUID | None, designation: str, section: str | None, paragraph_index: int | None)`
  - `ChatResponse(session_id: UUID | None, session_token: str | None, answer: str, answer_type, paragraphs: list[str], citations: list[CitationResponse])`

- [ ] **Step 1: Write the failing tests**

Append to `chat/tests/test_chat_router.py`:

```python
class _OneDocumentApiClient:
    """A validity question about one known, valid document."""

    DOCUMENT_ID = "66666666-6666-6666-6666-666666666666"

    def search_document(self, issuer, designation, jurisdiction):
        return {"id": self.DOCUMENT_ID}

    def get_validity(self, document_id, jurisdiction):
        return {"status": "valid", "replaced_by": [], "withdrawn_reference": None}

    def get_edges(self, document_id, jurisdiction):
        return []

    def get_document(self, document_id, jurisdiction):
        return {
            "origin_issuer": "ISO", "origin_number": "9001",
            "designations": [{"designation": "DIN EN ISO 9001", "is_primary": True}],
        }


def test_the_answer_carries_paragraphs_and_labelled_citations(client):
    client.app.dependency_overrides[get_api_client] = lambda: _OneDocumentApiClient()

    response = client.post("/v1/chat", json=_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] is None
    assert body["answer"] == "DIN EN ISO 9001 ist noch gültig."
    assert body["paragraphs"] == ["DIN EN ISO 9001 ist noch gültig."]
    assert body["citations"] == [{
        "document_id": _OneDocumentApiClient.DOCUMENT_ID, "segment_id": None,
        "designation": "DIN EN ISO 9001", "section": None, "paragraph_index": 0,
    }]


def test_a_stored_answer_keeps_its_paragraph_index_and_returns_the_session_id(client, db_session):
    from normly_chat.accounts_client import ChatAccountIdentity
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(
        email="chat-paragraph@example.de", password_hash=None,
    )
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(identity)
    # The document must exist for the citation's foreign key.
    from datetime import date, datetime, timezone

    from normly_core.graph.domain import LegalBasisCategory
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DIN", retrieval_path="https://example.de/router",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:router-paragraph",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    class _KnownDocumentApiClient(_OneDocumentApiClient):
        DOCUMENT_ID = str(document.id)

    client.app.dependency_overrides[get_api_client] = lambda: _KnownDocumentApiClient()

    response = client.post("/v1/chat", json=_BODY, headers={"Authorization": "Bearer valid"})

    body = response.json()
    session_id = body["session_id"]
    assert session_id is not None
    chat_repo = PostgresChatRepository(db_session)
    chat_session = chat_repo.get_session_by_token(body["session_token"])
    assert str(chat_session.id) == session_id
    answer = chat_repo.list_messages_for_session(chat_session.id)[1]
    [citation] = chat_repo.citations_for_messages([answer.id])[answer.id]
    assert citation.paragraph_index == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_chat_router.py -v`
Expected: FAIL (old signature in the router, missing fields).

- [ ] **Step 3: Update the schemas**

In `chat/src/normly_chat/schemas.py`, replace `CitationResponse` and `ChatResponse`:

```python
class CitationResponse(BaseModel):
    document_id: uuid.UUID
    segment_id: uuid.UUID | None
    designation: str
    section: str | None
    # None: the citation backs the whole answer rather than one paragraph.
    paragraph_index: int | None


class ChatResponse(BaseModel):
    session_id: uuid.UUID | None
    session_token: str | None
    # The paragraphs joined by a blank line; kept for clients that render
    # plain text.
    answer: str
    answer_type: Literal["structural", "synthesis", "fallback"]
    paragraphs: list[str]
    citations: list[CitationResponse]
```

- [ ] **Step 4: Update the router**

In `chat/src/normly_chat/routers/chat.py` (the `CitationResolver` import exists since Task 7), replace the code from `question_type = classify(payload.message)` to the end of the function with:

```python
    labels = CitationResolver(api_client, PostgresSegmentRepository(session), payload.jurisdiction)
    question_type = classify(payload.message)
    if question_type == QuestionType.SYNTHESIS:
        result = build_synthesis_answer(
            payload.message, payload.jurisdiction, payload.language, embedding_model,
            PostgresSegmentRepository(session), llm_client,
        )
    else:
        result = build_structural_answer(
            question_type, payload.message, payload.jurisdiction, payload.language, api_client,
            labels,
        )
    citations = labels.resolve(result.citations)

    answer_type = (
        ChatAnswerType.FALLBACK if result.is_fallback
        else ChatAnswerType.SYNTHESIS if question_type == QuestionType.SYNTHESIS
        else ChatAnswerType.STRUCTURAL
    )

    if chat_session is not None:
        now = datetime.now(timezone.utc)
        chat_repo.create_message(
            session_id=chat_session.id, role=ChatMessageRole.USER, content=payload.message,
            answer_type=None, created_at=now,
        )
        answer_message = chat_repo.create_message(
            session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content=result.text,
            answer_type=answer_type, created_at=now,
        )
        for citation in citations:
            chat_repo.add_citation(
                message_id=answer_message.id, document_id=citation["document_id"],
                segment_id=citation["segment_id"], paragraph_index=citation["paragraph_index"],
            )
        # Committed before the response leaves: the frontend reloads the
        # session list as soon as the answer arrives, and the dependency's own
        # commit would only run after that.
        session.commit()

    return ChatResponse(
        session_id=chat_session.id if chat_session is not None else None,
        session_token=chat_session.session_token if chat_session is not None else None,
        answer=result.text,
        answer_type=answer_type.value,
        paragraphs=result.paragraphs,
        citations=[CitationResponse(**citation) for citation in citations],
    )
```

- [ ] **Step 5: Run the chat suite**

Run: `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py -v`
Expected: all PASS.

Then, locally (needs the embedding model download on first run): `cd chat && ../.venv/bin/pytest tests/test_structural_end_to_end.py -v`
Expected: 4 PASS. If the model cannot be downloaded here, say so in the task report instead of skipping silently.

- [ ] **Step 6: Commit**

```bash
git add chat/src/normly_chat/schemas.py chat/src/normly_chat/routers/chat.py \
  chat/tests/test_chat_router.py
git commit -s -m "feat(chat): return answer paragraphs with labelled citations" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Session titles and session messages endpoints

**Files:**
- Create: `chat/src/normly_chat/titles.py`
- Modify: `chat/src/normly_chat/schemas.py`, `chat/src/normly_chat/routers/sessions.py`
- Test: create `chat/tests/test_titles.py`; modify `chat/tests/test_sessions_router.py`

**Interfaces:**
- Consumes: Task 1 repository methods, `CitationResolver` (Task 4), `split_paragraphs` (Task 5), `CitationResponse` (Task 8).
- Produces:
  - `fallback_title(question: str) -> str`; `generate_title(llm_client, question: str, language: str) -> str | None`
  - `GET /v1/chat/sessions` items gain `title: str | None`.
  - `GET /v1/chat/sessions/{id}/messages` → `ChatSessionMessagesResponse(session_id, session_token, title, messages: list[ChatMessageResponse])`, `ChatMessageResponse(role, content, answer_type, paragraphs, citations, created_at)`; 401 without account, 404 for unknown/foreign ids.
  - `POST /v1/chat/sessions/{id}/title` → `{"title": str}`; 401/404 as above; 404 also when the session has no question.

- [ ] **Step 1: Write the failing title tests**

Create `chat/tests/test_titles.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import httpx

from normly_chat.titles import fallback_title, generate_title


def test_a_short_question_is_its_own_fallback_title():
    assert fallback_title("  Ist DIN EN ISO 9001\n noch gültig?  ") == "Ist DIN EN ISO 9001 noch gültig?"


def test_a_long_question_is_cut_at_a_word_boundary():
    question = (
        "Welche Anforderungen stellt DIN EN ISO 13849-1 an die Bewertung "
        "des Performance Level einer Sicherheitsfunktion?"
    )
    title = fallback_title(question)
    assert title == "Welche Anforderungen stellt DIN EN ISO 13849-1 an die…"
    assert len(title) <= 61


class _Llm:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        if self._error:
            raise self._error
        return self._response


def test_generate_title_cleans_the_model_output():
    llm = _Llm('„Performance Level bewerten“.\nZweite Zeile')
    assert generate_title(llm, "Frage", "de") == "Performance Level bewerten"
    assert "drei bis sechs Wörtern" in llm.messages[0]["content"]
    assert llm.messages[1] == {"role": "user", "content": "Frage"}


def test_generate_title_uses_the_session_language():
    llm = _Llm("Welding goggles")
    assert generate_title(llm, "Question", "en") == "Welding goggles"
    assert "three to six words" in llm.messages[0]["content"]


def test_generate_title_returns_none_on_failure_or_empty_output():
    assert generate_title(_Llm(error=httpx.ConnectError("down")), "Frage", "de") is None
    assert generate_title(_Llm(error=KeyError("choices")), "Frage", "de") is None
    assert generate_title(_Llm("   "), "Frage", "de") is None


def test_generate_title_caps_an_overlong_answer():
    title = generate_title(_Llm(" ".join(["Wort"] * 30)), "Frage", "de")
    assert len(title.split()) == 8
```

- [ ] **Step 2: Run to verify failure**

Run: `cd chat && ../.venv/bin/pytest tests/test_titles.py -v`
Expected: FAIL with `ModuleNotFoundError: normly_chat.titles`.

- [ ] **Step 3: Implement `titles.py`**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Chat session titles: a short model summary of the first question, with the
truncated question itself as the fallback.
"""

from __future__ import annotations

import httpx

_FALLBACK_MAX_CHARS = 60
_MAX_TITLE_WORDS = 8
_QUOTES = "\"'„“”‚‘’«»"

_TITLE_PROMPT = {
    "de": (
        "Fasse die folgende Frage als Titel mit drei bis sechs Wörtern zusammen. "
        "Antworte nur mit dem Titel, ohne Anführungszeichen und ohne Punkt am Ende."
    ),
    "en": (
        "Summarise the following question as a title of three to six words. "
        "Answer with the title only, without quotation marks and without a final full stop."
    ),
}


def fallback_title(question: str) -> str:
    text = " ".join(question.split())
    if len(text) <= _FALLBACK_MAX_CHARS:
        return text
    cut = text[:_FALLBACK_MAX_CHARS]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(" ,.;:") + "…"


def generate_title(llm_client, question: str, language: str) -> str | None:
    prompt = _TITLE_PROMPT.get(language, _TITLE_PROMPT["en"])
    try:
        raw = llm_client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ])
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        # The title is a convenience: a failed model call must not fail the
        # request, the caller falls back to the truncated question.
        return None
    lines = (raw or "").strip().splitlines()
    if not lines:
        return None
    title = lines[0].strip().strip(_QUOTES).rstrip(".").strip().strip(_QUOTES).strip()
    words = title.split()
    if not words:
        return None
    return " ".join(words[:_MAX_TITLE_WORDS])
```

- [ ] **Step 4: Run the title tests**

Run: `cd chat && ../.venv/bin/pytest tests/test_titles.py -v`
Expected: all PASS.

- [ ] **Step 5: Write the failing router tests**

Append to `chat/tests/test_sessions_router.py`:

```python
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from normly_core.graph.domain import ChatAnswerType, ChatMessageRole, LegalBasisCategory


def _app_for(client, identity, *, api_client=None, llm_client=None):
    from normly_chat.dependencies import (
        get_accounts_client, get_api_client, get_llm_client, get_session,
    )
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = client.app.dependency_overrides[get_session]
    app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)
    if api_client is not None:
        app.dependency_overrides[get_api_client] = lambda: api_client
    if llm_client is not None:
        app.dependency_overrides[get_llm_client] = lambda: llm_client
    return app


def _owned_session(db_session, email, *, language="de"):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)
    chat_repo = PostgresChatRepository(db_session)
    chat_session = chat_repo.create_session(
        session_token=f"tok-{email}", jurisdiction="DE", language=language,
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    identity = ChatAccountIdentity(account_id=account.id, email=email)
    return chat_repo, chat_session, identity


def _document(db_session, number):
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/sessions",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=f"sha256:sessions-{number}",
        ingested_at=datetime.now(timezone.utc),
    )
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=number, edition="2020", part=None,
        delivery_id=delivery.id,
    )


class _LabelApiClient:
    def __init__(self, known_ids):
        self._known = set(known_ids)

    def get_document(self, document_id, jurisdiction):
        if document_id not in self._known:
            return None
        return {
            "origin_issuer": "DGUV", "origin_number": "1",
            "designations": [{"designation": "DGUV Vorschrift 1", "is_primary": True}],
        }


class _TitleLlm:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self._error:
            raise self._error
        return self._response


def test_messages_endpoint_returns_paragraphs_and_resolved_citations(client, db_session):
    chat_repo, chat_session, identity = _owned_session(db_session, "messages@example.de")
    known = _document(db_session, "known")
    gone = _document(db_session, "gone")
    now = datetime.now(timezone.utc)
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Was gilt?",
        answer_type=None, created_at=now,
    )
    answer = chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content="Eins.\n\nZwei.",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=now,
    )
    chat_repo.add_citation(
        message_id=answer.id, document_id=known.id, segment_id=None, paragraph_index=1,
    )
    chat_repo.add_citation(
        message_id=answer.id, document_id=gone.id, segment_id=None, paragraph_index=0,
    )
    app = _app_for(client, identity, api_client=_LabelApiClient({known.id}))

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/v1/chat/sessions/{chat_session.id}/messages",
            headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(chat_session.id)
    assert body["session_token"] == chat_session.session_token
    assert body["title"] == "Was gilt?"
    question, reply = body["messages"]
    assert question["role"] == "user"
    assert question["paragraphs"] == ["Was gilt?"]
    assert reply["paragraphs"] == ["Eins.", "Zwei."]
    assert reply["answer_type"] == "synthesis"
    assert reply["citations"] == [{
        "document_id": str(known.id), "segment_id": None,
        "designation": "DGUV Vorschrift 1", "section": None, "paragraph_index": 1,
    }]


def test_messages_endpoint_hides_foreign_sessions(client, db_session):
    _, chat_session, _ = _owned_session(db_session, "owner-msg@example.de")
    _, _, stranger = _owned_session(db_session, "stranger-msg@example.de")
    app = _app_for(client, stranger, api_client=_LabelApiClient(set()))

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/v1/chat/sessions/{chat_session.id}/messages",
            headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 404


def test_messages_endpoint_requires_an_account(client):
    response = client.get(f"/v1/chat/sessions/{uuid.uuid4()}/messages")
    assert response.status_code == 401


def test_session_list_shows_the_stored_or_fallback_title(client, db_session):
    chat_repo, titled, identity = _owned_session(db_session, "titles-list@example.de")
    untitled = chat_repo.create_session(
        session_token="tok-untitled", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=identity.account_id,
    )
    empty = chat_repo.create_session(
        session_token="tok-empty", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=identity.account_id,
    )
    chat_repo.set_session_title(titled.id, "Gespeicherter Titel")
    chat_repo.create_message(
        session_id=untitled.id, role=ChatMessageRole.USER, content="Erste Frage hier",
        answer_type=None, created_at=datetime.now(timezone.utc),
    )
    app = _app_for(client, identity)

    with TestClient(app) as test_client:
        body = test_client.get("/v1/chat/sessions", headers={"Authorization": "Bearer t"}).json()

    titles = {item["id"]: item["title"] for item in body}
    assert titles == {
        str(titled.id): "Gespeicherter Titel",
        str(untitled.id): "Erste Frage hier",
        str(empty.id): None,
    }


def test_title_endpoint_generates_stores_and_then_reuses_the_title(client, db_session):
    chat_repo, chat_session, identity = _owned_session(db_session, "title-gen@example.de")
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Brauche ich eine Schutzbrille?",
        answer_type=None, created_at=datetime.now(timezone.utc),
    )
    llm = _TitleLlm("Schutzbrille beim Schweißen")
    app = _app_for(client, identity, llm_client=llm)

    with TestClient(app) as test_client:
        first = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )
        second = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert first.json() == {"title": "Schutzbrille beim Schweißen"}
    assert second.json() == {"title": "Schutzbrille beim Schweißen"}
    assert llm.calls == 1
    assert chat_repo.get_session_by_token(chat_session.session_token).title == (
        "Schutzbrille beim Schweißen"
    )


def test_title_endpoint_falls_back_without_storing_when_the_model_fails(client, db_session):
    import httpx

    chat_repo, chat_session, identity = _owned_session(db_session, "title-fail@example.de")
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Kurze Frage",
        answer_type=None, created_at=datetime.now(timezone.utc),
    )
    app = _app_for(client, identity, llm_client=_TitleLlm(error=httpx.ConnectError("down")))

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    assert response.json() == {"title": "Kurze Frage"}
    assert chat_repo.get_session_by_token(chat_session.session_token).title is None


def test_title_endpoint_is_404_for_foreign_or_empty_sessions(client, db_session):
    _, chat_session, owner = _owned_session(db_session, "title-owner@example.de")
    _, _, stranger = _owned_session(db_session, "title-stranger@example.de")

    with TestClient(_app_for(client, stranger, llm_client=_TitleLlm("x"))) as test_client:
        foreign = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )
    with TestClient(_app_for(client, owner, llm_client=_TitleLlm("x"))) as test_client:
        empty = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert foreign.status_code == 404
    assert empty.status_code == 404
```

- [ ] **Step 6: Run to verify failure**

Run: `cd chat && ../.venv/bin/pytest tests/test_sessions_router.py -v`
Expected: the new tests FAIL (405/404 for missing routes, missing `title`).

- [ ] **Step 7: Add the schemas**

In `chat/src/normly_chat/schemas.py`, add `title: str | None` to `ChatSessionSummary` (after `language`), and add:

```python
class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    answer_type: Literal["structural", "synthesis", "fallback"] | None
    paragraphs: list[str]
    citations: list[CitationResponse]
    created_at: datetime


class ChatSessionMessagesResponse(BaseModel):
    session_id: uuid.UUID
    # The frontend sets its chat cookie from this, so that new questions
    # continue the reopened session.
    session_token: str
    title: str | None
    messages: list[ChatMessageResponse]


class ChatSessionTitleResponse(BaseModel):
    title: str
```

- [ ] **Step 8: Implement the endpoints**

In `chat/src/normly_chat/routers/sessions.py`, replace the imports block with:

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from normly_core.graph.domain import ChatMessage, ChatMessageCitation, ChatMessageRole
from normly_core.graph.postgres.repositories import (
    PostgresChatRepository,
    PostgresSegmentRepository,
)

from normly_chat.accounts_client import AccountsClient
from normly_chat.api_client import ApiClient
from normly_chat.citation_labels import CitationResolver
from normly_chat.dependencies import (
    get_accounts_client, get_api_client, get_llm_client, get_session,
)
from normly_chat.llm_client import LlmClient
from normly_chat.markers import split_paragraphs
from normly_chat.schemas import (
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionSummary,
    ChatSessionTitleResponse,
    CitationResponse,
    DeletedSessionsResponse,
)
from normly_chat.titles import fallback_title, generate_title
```

Add helpers after `_require_account`:

```python
def _display_title(stored: str | None, first_question: str | None) -> str | None:
    if stored:
        return stored
    return fallback_title(first_question) if first_question else None


def _owned_session_or_404(chat_repo, session_id: uuid.UUID, account_id: uuid.UUID):
    chat_session = chat_repo.get_session_for_account(session_id, account_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    return chat_session


def _message_response(
    message: ChatMessage, citations: list[ChatMessageCitation], labels: CitationResolver,
) -> ChatMessageResponse:
    if message.role == ChatMessageRole.USER:
        return ChatMessageResponse(
            role="user", content=message.content, answer_type=None,
            paragraphs=[message.content], citations=[], created_at=message.created_at,
        )
    paragraphs = split_paragraphs(message.content)
    raw = [
        {
            "document_id": c.document_id, "segment_id": c.segment_id,
            # An index without a matching paragraph backs the whole answer.
            "paragraph_index": (
                c.paragraph_index
                if c.paragraph_index is not None and c.paragraph_index < len(paragraphs)
                else None
            ),
        }
        for c in citations
    ]
    return ChatMessageResponse(
        role="assistant", content=message.content,
        answer_type=message.answer_type.value if message.answer_type else None,
        paragraphs=paragraphs,
        citations=[CitationResponse(**c) for c in labels.resolve(raw)],
        created_at=message.created_at,
    )
```

Replace the body of `list_sessions` after `sessions = ...`:

```python
    first_questions = chat_repo.first_user_messages_for_sessions([s.id for s in sessions])
    return [
        ChatSessionSummary(
            id=s.id, session_token=s.session_token, jurisdiction=s.jurisdiction,
            language=s.language, title=_display_title(s.title, first_questions.get(s.id)),
            created_at=s.created_at,
        )
        for s in sessions
    ]
```

Add the two endpoints after `list_sessions`:

```python
@sessions_router.get(
    "/sessions/{session_id}/messages", response_model=ChatSessionMessagesResponse,
)
def get_session_messages(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    api_client: ApiClient = Depends(get_api_client),
) -> ChatSessionMessagesResponse:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    chat_session = _owned_session_or_404(chat_repo, session_id, account_id)

    messages = chat_repo.list_messages_for_session(chat_session.id)
    citations_by_message = chat_repo.citations_for_messages([m.id for m in messages])
    # Labels are resolved against the session's own jurisdiction, so a chat
    # reads the same whatever jurisdiction the UI shows right now.
    labels = CitationResolver(
        api_client, PostgresSegmentRepository(session), chat_session.jurisdiction,
    )
    first_question = next(
        (m.content for m in messages if m.role == ChatMessageRole.USER), None,
    )
    return ChatSessionMessagesResponse(
        session_id=chat_session.id, session_token=chat_session.session_token,
        title=_display_title(chat_session.title, first_question),
        messages=[
            _message_response(m, citations_by_message.get(m.id, []), labels) for m in messages
        ],
    )


@sessions_router.post(
    "/sessions/{session_id}/title", response_model=ChatSessionTitleResponse,
)
def create_session_title(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    llm_client: LlmClient = Depends(get_llm_client),
) -> ChatSessionTitleResponse:
    account_id = _require_account(authorization, accounts_client)
    chat_repo = PostgresChatRepository(session)
    chat_session = _owned_session_or_404(chat_repo, session_id, account_id)
    if chat_session.title:
        return ChatSessionTitleResponse(title=chat_session.title)

    first_question = chat_repo.first_user_messages_for_sessions([chat_session.id]).get(
        chat_session.id
    )
    if first_question is None:
        raise HTTPException(status_code=404, detail="chat session has no question yet")

    title = generate_title(llm_client, first_question, chat_session.language)
    if title is None:
        # Nothing stored: a later call may still get a model title.
        return ChatSessionTitleResponse(title=fallback_title(first_question))
    chat_repo.set_session_title(chat_session.id, title)
    session.commit()
    return ChatSessionTitleResponse(title=title)
```

- [ ] **Step 9: Run the chat suite**

Run: `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add chat/src/normly_chat/titles.py chat/src/normly_chat/schemas.py \
  chat/src/normly_chat/routers/sessions.py chat/tests/test_titles.py \
  chat/tests/test_sessions_router.py
git commit -s -m "feat(chat): reopen chat sessions and give them titles" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Account export includes titles and paragraph indexes

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py`, `accounts/src/normly_accounts/routers/account_management.py`
- Test: `accounts/tests/test_account_export.py`

**Interfaces:**
- Consumes: `ChatSession.title`, `ChatMessageCitation.paragraph_index` (Task 1).
- Produces: `ExportChatSession.title: str | None`, `ExportCitation.paragraph_index: int | None`.

- [ ] **Step 1: Update and add tests**

In `accounts/tests/test_account_export.py`:

- In `test_export_citations_name_the_document_readably`, pass `paragraph_index=0` to `add_citation` and add `"paragraph_index": 0` to the expected citation dict.
- Append:

```python
def test_export_includes_the_session_title(client, db_session):
    headers = _register(client, email="titleexport@example.de")
    chat_session, _ = _chat_with_message(db_session, _account_id(client, headers), token="t-title")
    PostgresChatRepository(db_session).set_session_title(chat_session.id, "Schutzbrillen")
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert body["chat_sessions"][0]["title"] == "Schutzbrillen"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd accounts && ../.venv/bin/pytest tests/test_account_export.py -v`
Expected: FAIL (missing keys).

- [ ] **Step 3: Implement**

In `accounts/src/normly_accounts/schemas.py`: add `paragraph_index: int | None` to `ExportCitation` (after `segment_id`), and `title: str | None` to `ExportChatSession` (after `language`).

In `accounts/src/normly_accounts/routers/account_management.py`, in the export: pass `title=chat_session.title` to `ExportChatSession(...)` and `paragraph_index=c.paragraph_index` to `ExportCitation(...)`.

- [ ] **Step 4: Run the accounts suite**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add accounts/src/normly_accounts accounts/tests/test_account_export.py
git commit -s -m "feat(accounts): export chat titles and paragraph citations" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: BFF routes for segments, session messages, titles, current session

**Files:**
- Create: `frontend/src/app/api/documents/[id]/segments/route.ts`
- Create: `frontend/src/app/api/chat/sessions/[id]/messages/route.ts`
- Create: `frontend/src/app/api/chat/sessions/[id]/title/route.ts`
- Create: `frontend/src/app/api/chat/current/route.ts`
- Test: create `frontend/tests/unit/document-segments-route.test.ts`, `frontend/tests/unit/chat-history-routes.test.ts`

**Interfaces:**
- Consumes: the `api/` and `chat/` endpoints from Tasks 3 and 9.
- Produces (browser-facing):
  - `GET /api/documents/[id]/segments?jurisdiction=XX` → backend body and status.
  - `GET /api/chat/sessions/[id]/messages` → backend body **without** `session_token`; on 200 sets the `normly_session` cookie to that token. 401 without account cookie.
  - `POST /api/chat/sessions/[id]/title` → backend body and status. 401 without account cookie.
  - `GET /api/chat/current` → 200 with the messages body (no token) of the session the `normly_session` cookie names; 204 when there is no account cookie, no chat cookie, or no matching session.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/unit/document-segments-route.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/segments/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/segments", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to api/ with the jurisdiction and passes status and body through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([{ id: "s1" }]), { status: 200 }));

    const response = await GET(
      new NextRequest("http://localhost/api/documents/doc-1/segments?jurisdiction=AT"),
      { params: Promise.resolve({ id: "doc-1" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ id: "s1" }]);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/doc-1/segments?jurisdiction=AT");
  });

  it("passes a 404 through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "document not found" }), { status: 404 }));

    const response = await GET(
      new NextRequest("http://localhost/api/documents/doc-1/segments"),
      { params: Promise.resolve({ id: "doc-1" }) },
    );

    expect(response.status).toBe(404);
  });
});
```

Create `frontend/tests/unit/chat-history-routes.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET as getMessages } from "@/app/api/chat/sessions/[id]/messages/route";
import { POST as postTitle } from "@/app/api/chat/sessions/[id]/title/route";
import { GET as getCurrent } from "@/app/api/chat/current/route";

const originalFetch = global.fetch;

function request(url: string, cookie?: string, method = "GET"): NextRequest {
  return new NextRequest(url, { method, headers: cookie ? { cookie } : {} });
}

const MESSAGES_BODY = {
  session_id: "sess-1",
  session_token: "chat-tok-1",
  title: "Titel",
  messages: [],
};

describe("GET /api/chat/sessions/[id]/messages", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account token, strips the session token and sets the chat cookie", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(MESSAGES_BODY), { status: 200 }));

    const response = await getMessages(
      request("http://localhost/api/chat/sessions/sess-1/messages", "normly_account_session=acct"),
      { params: Promise.resolve({ id: "sess-1" }) },
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.session_token).toBeUndefined();
    expect(body.title).toBe("Titel");
    expect(response.cookies.get("normly_session")?.value).toBe("chat-tok-1");
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions/sess-1/messages");
    expect(init.headers.Authorization).toBe("Bearer acct");
  });

  it("answers 401 without an account cookie and does not call the backend", async () => {
    global.fetch = vi.fn();
    const response = await getMessages(request("http://localhost/api/chat/sessions/x/messages"), {
      params: Promise.resolve({ id: "x" }),
    });
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("passes a 404 through without touching the cookie", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "nope" }), { status: 404 }));
    const response = await getMessages(
      request("http://localhost/api/chat/sessions/x/messages", "normly_account_session=acct"),
      { params: Promise.resolve({ id: "x" }) },
    );
    expect(response.status).toBe(404);
    expect(response.cookies.get("normly_session")).toBeUndefined();
  });
});

describe("POST /api/chat/sessions/[id]/title", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies the title request with the account token", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ title: "T" }), { status: 200 }));

    const response = await postTitle(
      request("http://localhost/api/chat/sessions/sess-1/title", "normly_account_session=acct", "POST"),
      { params: Promise.resolve({ id: "sess-1" }) },
    );

    expect(await response.json()).toEqual({ title: "T" });
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions/sess-1/title");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer acct");
  });

  it("answers 401 without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await postTitle(request("http://localhost/api/chat/sessions/x/title", undefined, "POST"), {
      params: Promise.resolve({ id: "x" }),
    });
    expect(response.status).toBe(401);
  });
});

describe("GET /api/chat/current", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("restores the session the chat cookie names", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "http://chat.internal/v1/chat/sessions") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              { id: "other", session_token: "chat-tok-0" },
              { id: "sess-1", session_token: "chat-tok-1" },
            ]),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(MESSAGES_BODY), { status: 200 }));
    });

    const response = await getCurrent(
      request("http://localhost/api/chat/current", "normly_account_session=acct; normly_session=chat-tok-1"),
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.session_id).toBe("sess-1");
    expect(body.session_token).toBeUndefined();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map(([u]) => u);
    expect(urls).toEqual([
      "http://chat.internal/v1/chat/sessions",
      "http://chat.internal/v1/chat/sessions/sess-1/messages",
    ]);
  });

  it("answers 204 when a cookie is missing or no session matches", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    expect((await getCurrent(request("http://localhost/api/chat/current"))).status).toBe(204);
    expect(
      (await getCurrent(request("http://localhost/api/chat/current", "normly_account_session=acct"))).status,
    ).toBe(204);
    expect(
      (
        await getCurrent(
          request("http://localhost/api/chat/current", "normly_account_session=acct; normly_session=gone"),
        )
      ).status,
    ).toBe(204);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run tests/unit/document-segments-route.test.ts tests/unit/chat-history-routes.test.ts`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the routes**

`frontend/src/app/api/documents/[id]/segments/route.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { rateLimitHeaders } from "@/lib/rate-limit-headers";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(id)}/segments` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
    { headers: rateLimitHeaders(request) },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

`frontend/src/app/api/chat/sessions/[id]/messages/route.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies, readSessionCookies } from "@/lib/session-cookies";

// Opening a session makes it the active one: the chat cookie is pointed at
// it, so the next /api/chat POST continues this conversation. The token
// itself stays server-side, like every other chat token.
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "account session required" }, { status: 401 });
  }
  const { id } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(id)}/messages`,
    { headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json().catch(() => ({}));
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  const { session_token: chatSessionToken, ...rest } = body;
  const response = NextResponse.json(rest);
  applySessionCookies(response, { chatSessionToken });
  return response;
}
```

`frontend/src/app/api/chat/sessions/[id]/title/route.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "account session required" }, { status: 401 });
  }
  const { id } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(id)}/title`,
    { method: "POST", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(body, { status: backendResponse.status });
}
```

`frontend/src/app/api/chat/current/route.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

// The chat cookie is httpOnly, so the page cannot tell which session is
// active. This route answers that on page load: the session list carries
// each session's token, the cookie names one of them.
export async function GET(request: NextRequest): Promise<NextResponse> {
  const { chatSessionToken, accountSessionToken } = readSessionCookies(request);
  if (!chatSessionToken || !accountSessionToken) {
    return new NextResponse(null, { status: 204 });
  }
  const headers = { Authorization: `Bearer ${accountSessionToken}` };
  const listResponse = await fetch(`${getBackendUrls().chat}/v1/chat/sessions`, { headers });
  if (!listResponse.ok) {
    return new NextResponse(null, { status: 204 });
  }
  const sessions: { id: string; session_token: string }[] = await listResponse.json();
  const active = sessions.find((session) => session.session_token === chatSessionToken);
  if (!active) {
    return new NextResponse(null, { status: 204 });
  }
  const messagesResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(active.id)}/messages`,
    { headers },
  );
  if (!messagesResponse.ok) {
    return new NextResponse(null, { status: 204 });
  }
  const { session_token: _token, ...body } = await messagesResponse.json();
  return NextResponse.json(body);
}
```

If ESLint flags `_token` as unused, use `delete` on a copied object instead:

```ts
  const body = await messagesResponse.json();
  delete body.session_token;
  return NextResponse.json(body);
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run tests/unit/document-segments-route.test.ts tests/unit/chat-history-routes.test.ts`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/api frontend/tests/unit/document-segments-route.test.ts \
  frontend/tests/unit/chat-history-routes.test.ts
git commit -s -m "feat(frontend): add BFF routes for segments and chat history" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Source chips per paragraph

**Files:**
- Create: `frontend/src/lib/chat-answer.ts`
- Modify: `frontend/src/components/chat/citation-chip.tsx`, `frontend/src/components/chat/message-list.tsx`, `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Test: create `frontend/tests/unit/chat-answer.test.ts`; modify `frontend/tests/unit/message-list.test.tsx`

**Interfaces:**
- Produces (`@/lib/chat-answer`):

```ts
export interface ApiCitation { document_id: string; segment_id: string | null; designation: string; section: string | null; paragraph_index: number | null }
export interface ApiChatMessage { role: "user" | "assistant"; content: string; paragraphs: string[]; citations: ApiCitation[] }
export interface CitationView { documentId: string; segmentId: string | null; designation: string; section: string | null }
export interface AnswerParagraph { text: string; citations: CitationView[] }
export interface ChatMessageView { role: "user" | "assistant"; content: string; paragraphs?: AnswerParagraph[]; answerCitations?: CitationView[] }
export function assistantMessageView(content: string, paragraphs: string[], citations: ApiCitation[]): ChatMessageView
export function messageViews(messages: ApiChatMessage[]): ChatMessageView[]
export function citationHref(citation: CitationView): string
export function citationLabel(citation: CitationView): string
```

- `message-list.tsx` re-exports `ChatMessageView`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/unit/chat-answer.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import {
  assistantMessageView,
  citationHref,
  citationLabel,
  messageViews,
  type ApiCitation,
} from "@/lib/chat-answer";

const cite = (overrides: Partial<ApiCitation>): ApiCitation => ({
  document_id: "doc-1",
  segment_id: null,
  designation: "DIN EN ISO 12100",
  section: null,
  paragraph_index: null,
  ...overrides,
});

describe("assistantMessageView", () => {
  it("groups citations by paragraph, dedupes them and keeps whole-answer citations apart", () => {
    const view = assistantMessageView("A\n\nB", ["A", "B"], [
      cite({ segment_id: "s1", section: "5.4", paragraph_index: 0 }),
      cite({ segment_id: "s1", section: "5.4", paragraph_index: 0 }),
      cite({ document_id: "doc-2", designation: "DGUV Vorschrift 1", paragraph_index: 1 }),
      cite({ document_id: "doc-3", designation: "ISO 9001" }),
    ]);

    expect(view.paragraphs).toEqual([
      { text: "A", citations: [{ documentId: "doc-1", segmentId: "s1", designation: "DIN EN ISO 12100", section: "5.4" }] },
      { text: "B", citations: [{ documentId: "doc-2", segmentId: null, designation: "DGUV Vorschrift 1", section: null }] },
    ]);
    expect(view.answerCitations).toEqual([
      { documentId: "doc-3", segmentId: null, designation: "ISO 9001", section: null },
    ]);
  });
});

describe("messageViews", () => {
  it("maps user and assistant messages", () => {
    const views = messageViews([
      { role: "user", content: "Frage", paragraphs: ["Frage"], citations: [] },
      { role: "assistant", content: "Antwort", paragraphs: ["Antwort"], citations: [] },
    ]);
    expect(views[0]).toEqual({ role: "user", content: "Frage" });
    expect(views[1].paragraphs).toEqual([{ text: "Antwort", citations: [] }]);
  });
});

describe("citationHref and citationLabel", () => {
  it("links to the segment anchor when there is a segment", () => {
    const withSegment = { documentId: "d", segmentId: "s", designation: "DIN EN ISO 13849-1", section: "4.5.4" };
    expect(citationHref(withSegment)).toBe("/documents/d#segment-s");
    expect(citationLabel(withSegment)).toBe("DIN EN ISO 13849-1 · 4.5.4");
  });

  it("links to the document and shows only the designation otherwise", () => {
    const plain = { documentId: "d", segmentId: null, designation: "ISO 9001", section: null };
    expect(citationHref(plain)).toBe("/documents/d");
    expect(citationLabel(plain)).toBe("ISO 9001");
  });
});
```

In `frontend/tests/unit/message-list.test.tsx`, replace the first test ("renders user and assistant messages with a citation link") and the third ("renders an assistant message without a citation link when resolution failed") with:

```tsx
  it("renders paragraphs with their chips and whole-answer chips after them", () => {
    const messages: ChatMessageView[] = [
      { role: "user", content: "Was gilt beim Schweißen?" },
      {
        role: "assistant",
        content: "Erster Absatz.\n\nZweiter Absatz.",
        paragraphs: [
          {
            text: "Erster Absatz.",
            citations: [{ documentId: "d1", segmentId: "s1", designation: "DGUV Vorschrift 1", section: "§ 2" }],
          },
          { text: "Zweiter Absatz.", citations: [] },
        ],
        answerCitations: [{ documentId: "d2", segmentId: null, designation: "ISO 9001", section: null }],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );

    expect(screen.getByText("Was gilt beim Schweißen?")).toBeInTheDocument();
    expect(screen.getByText("Erster Absatz.")).toBeInTheDocument();
    expect(screen.getByText("Zweiter Absatz.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DGUV Vorschrift 1 · § 2" })).toHaveAttribute(
      "href",
      "/documents/d1#segment-s1",
    );
    expect(screen.getByRole("link", { name: "ISO 9001" })).toHaveAttribute("href", "/documents/d2");
  });

  it("renders an assistant message without chips when it has no citations", () => {
    const messages: ChatMessageView[] = [
      {
        role: "assistant",
        content: "Fallback-Antwort ohne Quelle.",
        paragraphs: [{ text: "Fallback-Antwort ohne Quelle.", citations: [] }],
        answerCitations: [],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Fallback-Antwort ohne Quelle.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
```

Leave the loading and copy-button tests as they are; if a copy-button test builds an assistant message without `paragraphs`, it keeps working because `MessageList` falls back to `content`.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run tests/unit/chat-answer.test.ts tests/unit/message-list.test.tsx`
Expected: FAIL — module `@/lib/chat-answer` missing, links not found.

- [ ] **Step 3: Create `src/lib/chat-answer.ts`**

```ts
// frontend/src/lib/chat-answer.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// Turns chat/'s answer format (paragraphs + citations with a paragraph
// index) into what MessageList renders. Shared by fresh answers and
// reopened sessions, so both look the same.

export interface ApiCitation {
  document_id: string;
  segment_id: string | null;
  designation: string;
  section: string | null;
  // null: the citation backs the whole answer, not one paragraph.
  paragraph_index: number | null;
}

export interface ApiChatMessage {
  role: "user" | "assistant";
  content: string;
  paragraphs: string[];
  citations: ApiCitation[];
}

export interface CitationView {
  documentId: string;
  segmentId: string | null;
  designation: string;
  section: string | null;
}

export interface AnswerParagraph {
  text: string;
  citations: CitationView[];
}

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  paragraphs?: AnswerParagraph[];
  answerCitations?: CitationView[];
}

function toView(citation: ApiCitation): CitationView {
  return {
    documentId: citation.document_id,
    segmentId: citation.segment_id,
    designation: citation.designation,
    section: citation.section,
  };
}

function dedupe(citations: CitationView[]): CitationView[] {
  const seen = new Set<string>();
  return citations.filter((citation) => {
    const key = `${citation.documentId}:${citation.segmentId ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function assistantMessageView(
  content: string,
  paragraphs: string[],
  citations: ApiCitation[],
): ChatMessageView {
  return {
    role: "assistant",
    content,
    paragraphs: paragraphs.map((text, index) => ({
      text,
      citations: dedupe(citations.filter((c) => c.paragraph_index === index).map(toView)),
    })),
    answerCitations: dedupe(citations.filter((c) => c.paragraph_index === null).map(toView)),
  };
}

export function messageViews(messages: ApiChatMessage[]): ChatMessageView[] {
  return messages.map((message) =>
    message.role === "user"
      ? { role: "user", content: message.content }
      : assistantMessageView(message.content, message.paragraphs, message.citations),
  );
}

export function citationHref(citation: CitationView): string {
  return citation.segmentId
    ? `/documents/${citation.documentId}#segment-${citation.segmentId}`
    : `/documents/${citation.documentId}`;
}

export function citationLabel(citation: CitationView): string {
  return citation.section ? `${citation.designation} · ${citation.section}` : citation.designation;
}
```

- [ ] **Step 4: Rewrite the chip**

Replace `frontend/src/components/chat/citation-chip.tsx`:

```tsx
// frontend/src/components/chat/citation-chip.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { FileText } from "lucide-react";
import { citationHref, citationLabel, type CitationView } from "@/lib/chat-answer";

export type { CitationView };

// Names the norm and section, so the reader sees where an answer stands
// without opening anything; the link opens the passage on the document page
// (REQ-UI-003).
export function CitationChip({ citation }: { citation: CitationView }) {
  return (
    <Link
      href={citationHref(citation)}
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-foreground hover:bg-muted"
    >
      <FileText className="size-3 text-muted-foreground" aria-hidden="true" />
      {citationLabel(citation)}
    </Link>
  );
}
```

- [ ] **Step 5: Render paragraphs in `MessageList`**

In `frontend/src/components/chat/message-list.tsx`:

Replace the `ChatMessageView` interface and the `CitationChip` import with:

```tsx
import { CitationChip } from "@/components/chat/citation-chip";
import type { CitationView, ChatMessageView } from "@/lib/chat-answer";

export type { ChatMessageView };

function ChipRow({ citations }: { citations: CitationView[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {citations.map((citation) => (
        <CitationChip key={`${citation.documentId}:${citation.segmentId ?? ""}`} citation={citation} />
      ))}
    </div>
  );
}
```

Replace the assistant branch (`<div key={index} className="flex flex-col gap-2"> … </div>`) with:

```tsx
          <div key={index} className="flex flex-col gap-3">
            {(message.paragraphs ?? [{ text: message.content, citations: [] }]).map(
              (paragraph, paragraphIndex) => (
                <div key={paragraphIndex} className="flex flex-col gap-1.5">
                  <p className="whitespace-pre-wrap text-sm text-foreground">{paragraph.text}</p>
                  <ChipRow citations={paragraph.citations} />
                </div>
              ),
            )}
            <ChipRow citations={message.answerCitations ?? []} />
            <CopyButton content={message.content} />
          </div>
```

- [ ] **Step 6: Remove the unused translation**

Delete the `"citationSource"` entry from the `chat` object in both `frontend/src/lib/i18n/de.json` and `frontend/src/lib/i18n/en.json`.

- [ ] **Step 7: Run the tests and the type check**

Run: `cd frontend && npx vitest run tests/unit/chat-answer.test.ts tests/unit/message-list.test.tsx && npx tsc --noEmit`
Expected: tests PASS. `tsc` reports errors only in `home-page-content.tsx` (it still builds the old citation shape) — Task 13 fixes them. Any other error must be fixed here.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/chat-answer.ts frontend/src/components/chat \
  frontend/src/lib/i18n frontend/tests/unit/chat-answer.test.ts \
  frontend/tests/unit/message-list.test.tsx
git commit -s -m "feat(frontend): show source chips per answer paragraph" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Open, restore and title chat sessions in the UI

**Files:**
- Modify: `frontend/src/app/home-page-content.tsx`, `frontend/src/components/chat/chat-shell.tsx`, `frontend/src/components/chat/chat-history-sidebar.tsx`
- Test: `frontend/tests/unit/home-page-content.test.tsx`, `frontend/tests/unit/chat-history-sidebar.test.tsx`

**Interfaces:**
- Consumes: BFF routes (Task 11), `assistantMessageView`, `messageViews`, `ApiCitation`, `ApiChatMessage` (Task 12), `ChatResponse.session_id` (Task 8).
- Produces:
  - `ChatShell` props: `onNewChat: () => void; activeSessionId?: string | null; onOpenSession?: (id: string) => void; onSessionsDeleted?: (deletedId: string | null) => void; sessionsVersion?: number; children`.
  - `ChatHistorySidebar` props: the same minus `children`. `onSessionsDeleted(null)` means "all deleted".

- [ ] **Step 1: Write the failing tests**

In `frontend/tests/unit/home-page-content.test.tsx`, in both existing tests' `fetch` mocks, add as the first branch:

```ts
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
```

and change the mocked `/api/chat` answer bodies to the new format, e.g.

```ts
JSON.stringify({ session_id: null, answer: "Answer", answer_type: "fallback", paragraphs: ["Answer"], citations: [] })
```

Then append inside the `describe`:

```tsx
  it("restores the active session on load", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/current") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-1",
              title: "Titel",
              messages: [
                { role: "user", content: "Alte Frage", paragraphs: ["Alte Frage"], citations: [] },
                {
                  role: "assistant",
                  content: "Alte Antwort",
                  paragraphs: ["Alte Antwort"],
                  citations: [
                    { document_id: "d1", segment_id: null, designation: "DGUV Vorschrift 1", section: null, paragraph_index: 0 },
                  ],
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByText("Alte Frage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DGUV Vorschrift 1" })).toHaveAttribute("href", "/documents/d1");
  });

  it("opens a session from the sidebar", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              { id: "sess-9", session_token: "x", jurisdiction: "DE", language: "de", title: "Schutzbrillen", created_at: new Date().toISOString() },
            ]),
            { status: 200 },
          ),
        );
      }
      if (url === "/api/chat/sessions/sess-9/messages") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-9",
              title: "Schutzbrillen",
              messages: [{ role: "user", content: "Brauche ich eine Schutzbrille?", paragraphs: ["Brauche ich eine Schutzbrille?"], citations: [] }],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 404 }));
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Schutzbrillen" }));

    expect(await screen.findByText("Brauche ich eine Schutzbrille?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schutzbrillen" })).toHaveAttribute("aria-current", "true");
  });

  it("asks for a title after the first answer of a new session and reloads the list", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string) => {
      calls.push(url);
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/chat/sessions/sess-new/title") {
        return Promise.resolve(new Response(JSON.stringify({ title: "Neu" }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ session_id: "sess-new", answer: "A", answer_type: "fallback", paragraphs: ["A"], citations: [] }),
          { status: 200 },
        ),
      );
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), { target: { value: "Frage" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));

    await waitFor(() => expect(calls).toContain("/api/chat/sessions/sess-new/title"));
    // Initial load plus at least one reload after the answer. React may batch
    // the answer's and the title's refresh into one render, so the exact
    // count is not asserted.
    await waitFor(() =>
      expect(calls.filter((u) => u === "/api/chat/sessions").length).toBeGreaterThanOrEqual(2),
    );
  });
```

In `frontend/tests/unit/chat-history-sidebar.test.tsx`:
- Rewrite the comment above `expect(screen.queryByRole("link")).not.toBeInTheDocument();` to say that sessions open through buttons, never links, so the session token cannot end up in an `href`.
- Append:

```tsx
  it("shows the title when there is one and opens the session on click", async () => {
    const onOpenSession = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: "s1", session_token: "t1", jurisdiction: "DE", language: "de", title: "Schutzbrillen", created_at: new Date().toISOString() },
        ]),
        { status: 200 },
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <SidebarProvider>
          <ChatHistorySidebar onNewChat={vi.fn()} onOpenSession={onOpenSession} activeSessionId="s1" />
        </SidebarProvider>
      </LocaleProvider>,
    );

    const button = await screen.findByRole("button", { name: "Schutzbrillen" });
    expect(button).toHaveAttribute("aria-current", "true");
    fireEvent.click(button);
    expect(onOpenSession).toHaveBeenCalledWith("s1");
  });

  it("reports the deleted session id", async () => {
    const onSessionsDeleted = vi.fn();
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify([
            { id: "s1", session_token: "t1", jurisdiction: "DE", language: "de", title: "Eins", created_at: new Date().toISOString() },
          ]),
          { status: 200 },
        ),
      );
    });
    render(
      <LocaleProvider initialLocale="de">
        <SidebarProvider>
          <ChatHistorySidebar onNewChat={vi.fn()} onSessionsDeleted={onSessionsDeleted} />
        </SidebarProvider>
      </LocaleProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Verlauf löschen" }));
    fireEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() => expect(onSessionsDeleted).toHaveBeenCalledWith("s1"));
  });
```

(`"Verlauf löschen"` and `"Endgültig löschen"` are the current German strings of `history.deleteButton` and `history.confirmDeleteButton`.)

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run tests/unit/home-page-content.test.tsx tests/unit/chat-history-sidebar.test.tsx`
Expected: the new tests FAIL.

- [ ] **Step 3: Update `ChatHistorySidebar`**

In `frontend/src/components/chat/chat-history-sidebar.tsx`:

- Add `SidebarMenuButton` to the `@/components/ui/sidebar` import.
- Add `title: string | null;` to `ChatSessionSummary`.
- Change the component signature and the list effect:

```tsx
export function ChatHistorySidebar({
  onNewChat,
  activeSessionId = null,
  onOpenSession = () => {},
  onSessionsDeleted = () => {},
  sessionsVersion = 0,
}: {
  onNewChat: () => void;
  activeSessionId?: string | null;
  onOpenSession?: (sessionId: string) => void;
  onSessionsDeleted?: (deletedId: string | null) => void;
  sessionsVersion?: number;
}) {
```

and give the `fetch("/api/chat/sessions")` effect the dependency list `[sessionsVersion]` instead of `[]`.

- In `confirmDelete`, after `setDeleteTarget(null);` add:

```tsx
      onSessionsDeleted(target.kind === "all" ? null : target.id);
```

- Replace the row markup inside `<SidebarMenuItem key={session.id}>` (the comment and the `<div className="flex h-8 …">` with its `<span>`) with:

```tsx
                    <div className="flex items-center gap-1">
                      <SidebarMenuButton
                        isActive={session.id === activeSessionId}
                        aria-current={session.id === activeSessionId ? "true" : undefined}
                        onClick={() => onOpenSession(session.id)}
                        className="min-w-0 flex-1"
                      >
                        <span className="truncate">
                          {session.title ?? new Date(session.created_at).toLocaleString(locale)}
                        </span>
                      </SidebarMenuButton>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        aria-label={t("history.deleteButton")}
                        onClick={() => openDeleteDialog({ kind: "one", id: session.id })}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
```

- [ ] **Step 4: Pass the props through `ChatShell`**

In `frontend/src/components/chat/chat-shell.tsx`, extend the props:

```tsx
export function ChatShell({
  onNewChat,
  activeSessionId = null,
  onOpenSession,
  onSessionsDeleted,
  sessionsVersion = 0,
  children,
}: {
  onNewChat: () => void;
  activeSessionId?: string | null;
  onOpenSession?: (sessionId: string) => void;
  onSessionsDeleted?: (deletedId: string | null) => void;
  sessionsVersion?: number;
  children: React.ReactNode;
}) {
```

and render the sidebar as:

```tsx
        <ChatHistorySidebar
          onNewChat={onNewChat}
          activeSessionId={activeSessionId}
          onOpenSession={onOpenSession}
          onSessionsDeleted={onSessionsDeleted}
          sessionsVersion={sessionsVersion}
        />
```

- [ ] **Step 5: Rewrite `HomePageContent`**

Replace the imports, the `ChatApiResponse` interface and the component body in `frontend/src/app/home-page-content.tsx` (keep the file header comment):

```tsx
"use client";

import * as React from "react";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatShell } from "@/components/chat/chat-shell";
import { useTranslation } from "@/lib/i18n/provider";
import { useJurisdiction } from "@/lib/jurisdiction/provider";
import {
  assistantMessageView,
  messageViews,
  type ApiChatMessage,
  type ApiCitation,
  type ChatMessageView,
} from "@/lib/chat-answer";

interface ChatApiResponse {
  session_id: string | null;
  answer: string;
  answer_type: "structural" | "synthesis" | "fallback";
  paragraphs: string[];
  citations: ApiCitation[];
}

interface SessionMessagesResponse {
  session_id: string;
  title: string | null;
  messages: ApiChatMessage[];
}

export function HomePageContent() {
  const { t, locale } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [messages, setMessages] = React.useState<ChatMessageView[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  // Bumped whenever the sidebar's session list may have changed.
  const [sessionsVersion, setSessionsVersion] = React.useState(0);
  const refreshSessions = () => setSessionsVersion((version) => version + 1);

  const showSession = (body: SessionMessagesResponse) => {
    setActiveSessionId(body.session_id);
    setMessages(messageViews(body.messages));
  };

  // After a reload the chat cookie still names a session; show it instead of
  // an empty chat that new questions would silently continue.
  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/current")
      .then(async (response) => {
        if (cancelled || response.status !== 200) return;
        showSession(await response.json());
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const openSession = async (sessionId: string) => {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages`);
    if (!response.ok) return;
    showSession(await response.json());
  };

  const startNewChat = () => {
    setMessages([]);
    setActiveSessionId(null);
  };

  const handleSessionsDeleted = async (deletedId: string | null) => {
    if (activeSessionId === null) return;
    if (deletedId !== null && deletedId !== activeSessionId) return;
    await fetch("/api/chat/new-session", { method: "POST" });
    startNewChat();
  };

  const sendMessage = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jurisdiction, language: locale, message }),
      });
      const body: ChatApiResponse = await response.json();
      setMessages((prev) => [...prev, assistantMessageView(body.answer, body.paragraphs, body.citations)]);
      if (body.session_id) {
        const isNewSession = activeSessionId === null;
        setActiveSessionId(body.session_id);
        refreshSessions();
        if (isNewSession) {
          // Not awaited: the title is a convenience and must never delay
          // the answer. The endpoint is idempotent.
          fetch(`/api/chat/sessions/${body.session_id}/title`, { method: "POST" })
            .then((titleResponse) => {
              if (titleResponse.ok) refreshSessions();
            })
            .catch(() => {});
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ChatShell
      onNewChat={startNewChat}
      activeSessionId={activeSessionId}
      onOpenSession={openSession}
      onSessionsDeleted={handleSessionsDeleted}
      sessionsVersion={sessionsVersion}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-4">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={sendMessage} disabled={isLoading} />
        <p className="text-center text-xs text-muted-foreground">{t("chat.aiDisclaimer")}</p>
      </div>
    </ChatShell>
  );
}
```

- [ ] **Step 6: Run the frontend suite and the type check**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: all tests PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/home-page-content.tsx frontend/src/components/chat \
  frontend/tests/unit/home-page-content.test.tsx frontend/tests/unit/chat-history-sidebar.test.tsx
git commit -s -m "feat(frontend): reopen, restore and title chat sessions" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Document page shows the text with segment anchors

**Files:**
- Modify: `frontend/src/app/documents/[id]/document-detail-content.tsx`, `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/document-detail-page.test.tsx`

**Interfaces:**
- Consumes: `GET /api/documents/[id]/segments` (Task 11).
- Produces: segments render as `<section id="segment-<uuid>">`; the one named by `location.hash` gets `aria-current="true"` and the highlight classes.

- [ ] **Step 1: Add the translations**

In `de.json`, inside `documentDetail`:

```json
    "textHeading": "Text",
    "textNotShown": "Der Text dieses Dokuments kann hier nicht angezeigt werden.",
    "textOriginalSource": "Zur Originalquelle"
```

In `en.json`, inside `documentDetail`:

```json
    "textHeading": "Text",
    "textNotShown": "The text of this document cannot be shown here.",
    "textOriginalSource": "Open the original source"
```

- [ ] **Step 2: Write the failing tests**

In `frontend/tests/unit/document-detail-page.test.tsx`, extend `mockFetch`'s `overrides` with `segments?: object[]; segmentsStatus?: number;` and add this branch **before** the plain `/api/documents/${DOCUMENT_ID}` branch (the more specific URL must match first):

```ts
    if (url.includes(`/api/documents/${DOCUMENT_ID}/segments`)) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides.segments ?? []), { status: overrides.segmentsStatus ?? 200 }),
      );
    }
```

Append tests:

```tsx
describe("DocumentDetailContent text section", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    window.location.hash = "";
  });

  const SEGMENTS = [
    { id: "seg-1", sequence_number: 1, heading: "§ 1 Geltungsbereich", text: "Gilt für alle." },
    { id: "seg-2", sequence_number: 2, heading: "§ 2 Pflichten", text: "Der Unternehmer muss." },
  ];

  it("renders each segment with its anchor", async () => {
    mockFetch({ segments: SEGMENTS });
    renderDetail(DOCUMENT_ID);

    expect(await screen.findByText("§ 1 Geltungsbereich")).toBeInTheDocument();
    expect(document.getElementById("segment-seg-2")).toHaveTextContent("Der Unternehmer muss.");
  });

  it("highlights the segment named in the URL hash", async () => {
    window.location.hash = "#segment-seg-2";
    mockFetch({ segments: SEGMENTS });
    renderDetail(DOCUMENT_ID);

    await screen.findByText("§ 2 Pflichten");
    await waitFor(() =>
      expect(document.getElementById("segment-seg-2")).toHaveAttribute("aria-current", "true"),
    );
    expect(document.getElementById("segment-seg-1")).not.toHaveAttribute("aria-current");
  });

  it("explains when the text cannot be shown and links the original source", async () => {
    mockFetch({ segments: [] });
    renderDetail(DOCUMENT_ID);

    expect(
      await screen.findByText(/Der Text dieses Dokuments kann hier nicht angezeigt werden\./),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zur Originalquelle" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^https?:\/\//),
    );
  });

  it("hides the text section when the segments request fails", async () => {
    mockFetch({ segmentsStatus: 503 });
    renderDetail(DOCUMENT_ID);

    await screen.findByRole("heading", { level: 2 });
    expect(screen.queryByText("Text")).not.toBeInTheDocument();
  });
});
```

If the existing `mockFetch` serves the document body from a URL check that would also match `/segments`, the branch order above handles it; verify by running the existing tests in this file.

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: the new tests FAIL.

- [ ] **Step 4: Implement**

In `frontend/src/app/documents/[id]/document-detail-content.tsx`:

- Import `cn`: `import { cn } from "@/lib/utils";`
- Add the type after `RightsClassification`:

```tsx
interface SegmentView {
  id: string;
  sequence_number: number;
  heading: string | null;
  text: string;
}
```

- Add state next to the others:

```tsx
  const [segments, setSegments] = React.useState<SegmentView[] | null>(null);
  const [highlightedSegmentId, setHighlightedSegmentId] = React.useState<string | null>(null);
```

- In `load()`, add `fetch(\`/api/documents/${documentId}/segments${query}\`)` as a sixth entry of `Promise.all` (destructure it as `segmentsResponse`), and after `setRights(...)`:

```tsx
      setSegments(segmentsResponse.ok ? await segmentsResponse.json() : null);
```

- Add an effect after the load effect:

```tsx
  // A citation chip links to /documents/{id}#segment-{id}. The segments
  // arrive after the first render, so the browser's own jump to the anchor
  // finds nothing; this scrolls once they exist and marks the target.
  React.useEffect(() => {
    if (!segments || segments.length === 0) return;
    const prefix = "#segment-";
    if (!window.location.hash.startsWith(prefix)) return;
    const segmentId = decodeURIComponent(window.location.hash.slice(prefix.length));
    const element = document.getElementById(`segment-${segmentId}`);
    if (!element) return;
    setHighlightedSegmentId(segmentId);
    element.scrollIntoView?.({ block: "start" });
  }, [segments]);
```

- In the left column, after the references block (`{edges.length > 0 && ( … )}`), add:

```tsx
          {segments !== null && (
            <div>
              <h3 className="font-medium">{t("documentDetail.textHeading")}</h3>
              {segments.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("documentDetail.textNotShown")}{" "}
                  <a
                    href={documentDetail.source.retrieval_path}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                  >
                    {t("documentDetail.textOriginalSource")}
                  </a>
                </p>
              ) : (
                <div className="mt-2 flex flex-col gap-3" data-testid="segment-list">
                  {segments.map((segment) => {
                    const isHighlighted = segment.id === highlightedSegmentId;
                    return (
                      <section
                        key={segment.id}
                        id={`segment-${segment.id}`}
                        aria-current={isHighlighted ? "true" : undefined}
                        className={cn(
                          "scroll-mt-20 rounded-md border p-3",
                          isHighlighted && "border-primary bg-primary/10",
                        )}
                      >
                        {segment.heading && <h4 className="text-sm font-medium">{segment.heading}</h4>}
                        <p className="mt-1 whitespace-pre-wrap text-sm">{segment.text}</p>
                      </section>
                    );
                  })}
                </div>
              )}
            </div>
          )}
```

- [ ] **Step 5: Run the frontend suite and the type check**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/documents frontend/src/lib/i18n \
  frontend/tests/unit/document-detail-page.test.tsx
git commit -s -m "feat(frontend): show document text with citable segment anchors" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: End-to-end check, live verification and marker measurement

**Files:**
- Modify: `frontend/tests/e2e/chat-and-history.spec.ts`

**Interfaces:**
- Consumes: everything above, running as the local Compose stack (the setup the existing Playwright specs use; Playwright is not part of CI).

- [ ] **Step 1: Add the E2E test**

Append inside the `test.describe` block of `frontend/tests/e2e/chat-and-history.spec.ts`:

```ts
  test("a chat can be reopened from the sidebar and is restored after a reload", async ({ page }) => {
    await page.goto("/signup");
    const email = `e2e-reopen-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    // An unknown designation answers structurally with a fallback: no model
    // and no knowledge-base data needed.
    const question = "Ist DIN EN ISO 99999 noch gültig?";
    await page.getByPlaceholder("Frage stellen…").fill(question);
    await page.getByRole("button", { name: "Senden" }).click();
    await expect(page.getByText(question).first()).toBeVisible();

    await page.reload();
    await expect(page.getByRole("log").getByText(question)).toBeVisible();

    await page.getByRole("button", { name: "Neuer Chat" }).click();
    await expect(page.getByRole("log").getByText(question)).toHaveCount(0);

    // The title is the model's summary or, without a model, the question.
    await page.locator('[data-sidebar="menu-button"]').first().click();
    await expect(page.getByRole("log").getByText(question)).toBeVisible();
  });
```

- [ ] **Step 2: Run the E2E suite against the local stack**

Start the stack the way the existing Playwright specs expect (see `frontend/playwright.config.ts` and `docs/guide/self-hosting.md`), rebuilt from this branch, with migrations applied. Then:

Run: `cd frontend && npx playwright test tests/e2e/chat-and-history.spec.ts`
Expected: all PASS. If the stack cannot be started here, report that explicitly; do not mark the step done.

- [ ] **Step 3: Verify the chips live**

With the local stack and knowledge-base data (DGUV/BAuA) loaded and the local model (`gemma4:e4b` via Ollama) configured, as a signed-in user:

1. Ask a synthesis question the data covers (e.g. "Welche Pflichten hat der Unternehmer nach DGUV Vorschrift 1?"). Expect paragraphs with chips such as "DGUV Vorschrift 1 · § 2".
2. Click a chip. Expect the document page, scrolled to the segment, highlighted.
3. Ask "Was ersetzt <designation of a replaced document in the data>?". Expect the successor named by designation, two chips, no UUID anywhere.
4. Switch the UI to English and repeat step 1 in English. Expect English text and the same chip format.
5. Reload. Expect the conversation restored; the sidebar shows a title.

Record what you saw (screenshots or a short log) for the PR description.

- [ ] **Step 4: Measure marker reliability**

Write a throwaway script in the session scratchpad (not in the repository) that sends 10 synthesis questions covered by the local data to `POST http://localhost:3000/api/chat` (anonymous is fine) and counts, among non-fallback synthesis answers, how many have at least one citation with a non-null `paragraph_index`. Record "N of M answers carried valid markers" with the model name for the PR description. This number is informational, not a merge criterion.

- [ ] **Step 5: Run every suite once more**

Run:

```bash
cd core && ../.venv/bin/pytest -q
cd ../api && ../.venv/bin/pytest -q
cd ../chat && ../.venv/bin/pytest -q --ignore=tests/test_structural_end_to_end.py
cd ../accounts && ../.venv/bin/pytest -q
cd ../frontend && npx vitest run && npx tsc --noEmit && npm run build
```

Expected: everything green.

- [ ] **Step 6: Commit**

```bash
git add frontend/tests/e2e/chat-and-history.spec.ts
git commit -s -m "test(frontend): cover reopening and restoring chat sessions end to end" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
