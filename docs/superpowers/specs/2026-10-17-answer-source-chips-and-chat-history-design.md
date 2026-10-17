# Answer source chips and chat history — design

Date: 2026-10-17
Status: approved by the owner in brainstorming, 2026-10-17

## Background

The finding that started this work was a false positive: the
English-migration follow-ups listed `chat/structural.py` as answering only in
German. It does not — every phrase exists for `de` and `en`, the frontend
sends the UI locale, and tests cover both. Looking at the same code surfaced
three real defects instead:

1. **Structural answers show raw UUIDs.** `replaced_by`, `withdrawn_reference`
   and `to_document_id` are document ids, and `structural.py` interpolates
   them into the answer text: "DIN EN ISO 9001 has been replaced by:
   3f2a9c…".
2. **Citations do not show where an answer comes from.** Every chip reads
   "Source" and links to the publisher's document as a whole. Synthesis
   answers cite all five retrieved segments, whether the model used them or
   not.
3. **The chat history cannot be opened.** The sidebar lists sessions by
   timestamp, but no endpoint returns a session's messages. REQ-UI-005
   (reopen and continue a chat) is unmet. After a page reload, a new question
   silently lands in a session the user cannot see.

The owner's mockups from an earlier brainstorming session show the target:
chips per paragraph that name the norm and section, so the user sees at once
where an answer stands.

## Decomposition

The mockups describe more than one feature. Three sub-projects, each with its
own spec, plan and PR:

1. **Source chips and chat history** — this spec.
2. **Norm network** — an expandable view of a node's references with validity
   status, opened from the answer ("Open norm network · 4 references"). Uses
   the existing edge and validity endpoints.
3. **Dated and undated references** — extends the edge model with the cited
   edition, a dated flag and the citing section; then answer warnings ("a
   dated reference points to a withdrawn edition", "an undated reference has
   moved") and status lines in the network. Needs a migration and extractor
   changes.

Out of scope for all three: the audit-trail receipt ("Beleg"), harmonisation
status, change monitoring. The "in your holdings" idea from the mockup is
dropped entirely.

## Part 1a — source chips

### Chat backend (`chat/`)

**Synthesis answers.** The prompt numbers the context segments (`[1] …`,
`[2] …`) and asks the model to back each paragraph with markers such as `[1]`
or `[1][3]`. A parser:

1. splits the answer into paragraphs at blank lines;
2. collects the valid markers per paragraph — a marker is valid when it names
   one of the numbered segments;
3. drops invalid markers and strips all markers from the text.

The verbatim-overlap and faithfulness checks run on the stripped text. If the
model sets no valid marker at all, every retrieved segment becomes a citation
of the whole answer (`paragraph_index: null`), as today — an answer never
stands without a source.

**Structural answers.** Each sentence becomes one paragraph. It cites the
asked-about document and the sentence's target (successor, withdrawing
document, reference target). The text names the target by designation, never
by id. `ApiClient` gets a `get_document(id, jurisdiction)` method for this.

**Chip labels are resolved in the backend.** Each citation carries:

- `designation` — the document's primary designation;
- `section` — the leading section marker of the segment heading:
  `4.5.4 Performance Level` → `4.5.4`, `§ 1 Geltungsbereich` → `§ 1`;
  `null` when the heading starts with neither or the citation has no
  segment.

### Response format of `POST /v1/chat`

An extension; `answer` stays for compatibility.

```json
{
  "session_token": "…",
  "answer": "Paragraph one.\n\nParagraph two.",
  "answer_type": "synthesis",
  "paragraphs": ["Paragraph one.", "Paragraph two."],
  "citations": [
    {"document_id": "…", "segment_id": "…", "designation": "DIN EN ISO 13849-1",
     "section": "4.5.4", "paragraph_index": 0},
    {"document_id": "…", "segment_id": null, "designation": "DIN EN ISO 12100",
     "section": null, "paragraph_index": null}
  ]
}
```

`paragraph_index: null` means the citation belongs to the whole answer.
`answer` equals `paragraphs` joined by a blank line.

### Storage

- `chat_message_citation.paragraph_index` — new nullable integer column,
  Alembic migration.
- `chat_message.content` stores the stripped full text; paragraphs are
  recovered by splitting it at blank lines, which matches `paragraph_index`.
- Designation and section are **not** stored. They are derived from
  `document_id` and `segment_id` whenever an answer is shown, so a reopened
  chat reflects the current state of the knowledge base, not a stale label.
- `chat_session` and `chat_message_citation` are user tables
  (`core/src/normly_core/exchange/tables.py`); user tables are never part
  of a knowledge-base dump, so the new columns need no exchange change.
  They are personal data and appear in the account export (Art. 15 GDPR).

### Frontend

- `MessageList` renders an answer as paragraphs, each followed by its chips;
  chips with `paragraph_index: null` follow the last paragraph. Duplicate
  citations (same document and segment) within one paragraph collapse into
  one chip.
- A chip shows a document icon and "DIN EN ISO 13849-1 · 4.5.4", or only the
  designation when `section` is `null`. It links to
  `/documents/{id}#segment-{segment_id}`, or `/documents/{id}` without a
  segment, in the same tab. Style: a quiet outline pill as in the mockup.
- The per-citation fetches of `/api/documents/{id}` for `retrieval_path` go
  away.

## Part 1a — segments endpoint and document page anchors

### Repository (`core/`)

`list_citable_segments_for_jurisdiction(document_id, jurisdiction)` returns
the segments of a document whose rights classification for the jurisdiction
has `may_process` and `may_cite_passages` set and is not revoked. It mirrors
the existing `list_segments_for_jurisdiction`, which gates on
`may_index_fulltext` for search. The gate stays in the rights classification,
inside the repository — no second check path.

`may_cite_passages` is deliberately stricter than `may_index_fulltext`:
EUR-Lex texts, for example, are indexable but not citable.

### API (`api/`)

`GET /v1/documents/{id}/segments?jurisdiction=…`, anonymous (free content,
ADR-017):

- **404** when the document is not visible in the jurisdiction — the same
  non-disclosure as `GET /v1/documents/{id}`;
- **200 with an empty list** when the document is visible but not citable;
- otherwise the segments ordered by `sequence_number`, each with `id`,
  `sequence_number`, `heading`, `text`.

### Frontend

- New BFF route `/api/documents/[id]/segments`.
- The document page gets a "Text" section below the references. Each segment
  shows its heading and text and carries the anchor `id="segment-<uuid>"`.
- Opened with `#segment-<uuid>`, the page scrolls to that segment and
  highlights it (border and background from the `primary` theme token,
  readable in dark mode).
- When the text is not citable, the section shows a notice ("The text of
  this document cannot be shown here.") with the link to the original
  source.
- All segments render unpaginated. DGUV and BAuA documents are small enough;
  very long documents are a later concern.

## Part 1b — chat history

### Opening a session

- New endpoint `GET /v1/chat/sessions/{id}/messages`, for the owning account
  only (404 otherwise). It returns the session token and the messages in
  order; assistant messages use the `POST /v1/chat` format (`paragraphs`,
  `citations` with `designation` and `section`), resolved against the
  session's jurisdiction and language.
- The BFF route sets the chat-session cookie from the returned token, so new
  questions append to the opened session.
- Clicking a session in the sidebar opens it; the active session is
  highlighted.
- On page load, when the cookie names a session, the page restores it.
- The sidebar reloads its list after every answer, so a new session appears
  at once.

### Session titles

- `chat_session.title` — new nullable text column, Alembic migration;
  included in the account export.
- **Fallback, computed on read, never stored:** the first user question,
  truncated to about 60 characters at a word boundary. A session without
  messages keeps showing its timestamp.
- **Model title:** `POST /v1/chat/sessions/{id}/title`, owning account only.
  The frontend calls it after the first answer of a new session, without
  waiting for it, and updates the sidebar with the result. When `title` is
  empty, the endpoint asks the language model for a title of three to six
  words in the session's language, stores it and returns it. When `title` is
  set, it returns it unchanged (idempotent). When the model call fails, it
  stores nothing and returns the fallback.
- A separate call rather than a background task: deterministic, testable, and
  it never slows the answer. The question reaches the model on STACKIT, the
  same path a synthesis answer takes (ADR-022).

## Error handling

- **Target or document cannot be resolved:** a document without a designation is labelled `origin_issuer origin_number`; a document `api/` does not return (error or 404) yields no chip. A structural sentence whose target designation is missing is
  left out; if no sentence remains, the existing fallback answer applies. No
  UUID ever appears in answer text.
- **Segment revoked or no longer citable:** the chip stays; the anchor finds
  no target and the page shows the "cannot be shown" notice.
- **Segment purged by a knowledge-base import:** `segment_id` is already set
  to `NULL` on purge (`DETACHED_REFERENCES`); the chip loses its section and
  links to the document page.
- **Document no longer available** in a reopened chat: the chip is dropped;
  the text stays.

## Requirements change

REQ-UI-003 says that for free content "the link leads to the original source
location". Chips now lead to the passage inside normly, which in turn links to
the original source. The same PR as this spec amends REQ-UI-003: every source
links to its location in normly (the document page, with the section where
permitted); the document page links free content to the original source and
paid content to the publisher's point of purchase. The rationale —
traceability, the publisher named as source — still holds.

REQ-UI-005 needs no change; part 1b fulfils it.

## Testing

- **Marker parser (unit):** valid and invalid markers, no markers, markers
  mid-sentence, paragraph splitting, overlap check on stripped text.
- **Structural answers:** designation instead of id in `de` and `en`,
  citations per sentence, unresolvable target.
- **API:** segments-endpoint gate — citable, only indexable, unclassified,
  revoked, unknown document.
- **Chat:** `POST /v1/chat` format; messages endpoint for own and foreign
  account; title endpoint — success, idempotence, model failure.
- **Migration and export:** the migration applies; `title` and `paragraph_index` appear in the account export.
- **Frontend (vitest):** chips per paragraph, anchor link, highlight on the
  document page, opening a session, title in the sidebar.
- **E2E (Playwright):** ask a question, click a chip, land on the highlighted
  section; open a session from the sidebar and continue it.
- **Measurement against the real model,** as for the semantic-search
  threshold: how often does the deployed model set valid markers? The result
  goes into the PR; it is not a merge criterion, because the fallback covers
  the bad case.
