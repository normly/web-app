# Design: LLM Chat with Anonymous and Account-Bound Session History (v1)

**Date:** 2026-08-20 (session identity revised: 2026-08-21)
**Status:** approved
**Sub-project:** fifth of several for implementing the normly MVP (free core)

> **Addendum 2026-08-21:** This spec was originally approved with purely anonymous session identity,
> then deferred until the meanwhile completed accounts sub-project
> (fourth sub-project) provides real accounts. Now revised: section "Decided
> with the owner" item 1, Non-goals, Data model and Data flow add the optional
> account linking. The rest of the spec (architecture, RAG flow, LLM operation,
> rights gate questions) remains valid unchanged.

## Context

The first three sub-projects (data model & reference graph schema, ingestion pipeline,
backend API) built a populated reference graph with real data from EUR-Lex and DGUV as well as
a public, read-only HTTP API for deterministic graph queries. There is not yet
any way to ask questions in natural language — REQ-FUNC-001/002/003 and
REQ-INT-004 describe exactly that.

SRS chapter 3.1/3.2 attaches further, partly considerably larger requirements to "chat":
user-based document uploads (REQ-INT-002A/B/C), SSO (REQ-INT-003). That is too large for
one sub-project.

**Decided with the owner:**

1. Scope: a stateful chat endpoint incl. session history ("reopen",
   REQ-INT-002A), but without user uploads. Session identity primarily via an anonymous,
   client-held token — no account requirement, no login enforced (ADR-017/REQ-ACC-001;
   "histories" is on CLAUDE.md's exhaustive list of reasons for an account requirement, but is
   explicitly optional here, not mandatory). Since the revision of 2026-08-21, a `chat_session` can
   additionally be linked optionally to a real account from the accounts sub-project
   — see "Session identity and account linking" below.
2. LLM operation: self-hosted on STACKIT GPU infrastructure, no external US API provider —
   consistent with CLAUDE.md's "No US services for operations" and ADR-005's finding that
   LLM inference does "not run on serverless platforms anyway". Model: Llama 3.1 8B
   Instruct (REQ-INT-004's own example), inference server: Ollama (simpler to
   containerize than vLLM, sufficient for the current usage size; vLLM's
   throughput advantages would be premature here).
3. Classification of structural question vs. synthesis question: rule-based, no model call for the
   routing itself (ADR-008, "without token costs").
4. Architecture: a separate top-level package `chat/`, calls `api/` as an ordinary HTTP client for
   structural questions (like an external third-party system) — keeps `api/`'s already verified
   "read-only" property intact. Its own writing tables (`chat_session`,
   `chat_message`, `chat_message_citation`) in the existing `core` schema.
5. A simple verbatim-overlap check (REQ-FUNC-002's "Plagiarism check without matches") is
   part of this sub-project, not follow-up work.
6. In addition to the verbatim-overlap check, a limited faithfulness check by
   self-assessment: a second, targeted Ollama call evaluates, after the actual
   synthesis answer, whether its statements are covered by the cited segments (see
   Data flow). This is explicitly not a complete fact check against an external
   source of truth (remains a non-goal), but an additional, heuristic
   error brake based on the same model.

## Goal of this sub-project

A chat endpoint that takes user questions in natural language, answers structural questions
deterministically from the graph (no model call), answers synthesis questions via
retrieval-augmented generation against real DGUV full text with a self-hosted LLM
— paraphrased, with citations, with plagiarism protection — and delivers an explanatory
fallback answer when there is no basis. The session can be continued without an account via an anonymous
token.

## Non-goals

- **User uploads, isolation, expiry** (REQ-INT-002A/B/C, the upload part) — a separate,
  later sub-project. Only the session history from REQ-INT-002A is implemented here, not
  the document upload capability itself.
- **Authentication logic of its own in `chat/`.** `chat/` only checks a supplied
  account token with `accounts/` (HTTP call, like `api/`) — no login of its own, no
  session management of its own for accounts. Whether an account token is sent at all
  is left entirely to the client; anonymous sessions work unchanged without
  any contact with `accounts/`.
- **Rate limiting/quota** (REQ-SEC-004, server-side quota counting) — as in the
  backend API sub-project, a separate infrastructure decision, not part of this sub-project.
- **Verification against an external source of truth.** REQ-FUNC-001 is aimed at through
  context-bound prompting (answer only from retrieved segments) plus the
  faithfulness check described in "Decided with the owner" item 6 —
  both are heuristics based on the same model, no guarantee. A robust,
  fundamentally reliable fact check (e.g. against a curated knowledge base or
  with a dedicated, independent verification model) remains a separate, larger
  research topic and is not part of the scope here.
- **Production deployment/scaling of the inference server** (SKE, GPU provisioning,
  load balancing) — analogous to the previous sub-projects, a later
  deployment decision.
- **Languages beyond German/English.** `language` is `"de"`/`"en"` from the start
  (see Architecture) — further languages are follow-up work, no translation service for
  arbitrary target languages in this sub-project.

## Architecture

### Package structure

Three approaches were weighed:

1. **A separate `chat/` directory, calls `api/` as an HTTP client for structural questions.**
2. Add chat endpoints directly to `api/` — rejected: breaks the already verified
   invariant "API is read-only", mixes two different protection needs
   (public, anonymous read API vs. session-bound, writing chat history).
3. Chat logic directly in `core/` instead of a separate service — rejected: `core/` is
   library + CLI, not a web service; would pull FastAPI/LLM client dependencies into every
   `core` installation, the same argument as against approach 2 in the backend API design.

**Decided: approach 1.**

```
chat/
  pyproject.toml        # own package, depends on normly_core
  src/normly_chat/
    main.py              # FastAPI app, mounts /v1/chat
    dependencies.py       # DB session, HTTP client for api/, Ollama client
    schemas.py             # Pydantic request/response models
    classify.py             # rule-based structural-vs-synthesis detection
    structural.py            # builds answers from api/ calls (no LLM)
    synthesis.py              # RAG retrieval + Ollama call + paraphrasing prompt
                               # + verbatim-overlap check + faithfulness check
  tests/
```

`chat/` talks to `api/` exclusively via its public HTTP interface — like
an external third-party system, no direct Python import of the `api` routers. This is deliberate
dogfooding of our own public API.

### Data model (new tables in the existing `core` schema)

| Table | Columns | Purpose |
|---|---|---|
| `chat_session` | `id` (PK), `session_token` (unique, opaque), `account_id` (FK to `account`, **nullable**), `jurisdiction`, `language` (`de`/`en`), `created_at` | Session identity — anonymous (`account_id IS NULL`) or account-linked |
| `chat_message` | `id` (PK), `session_id` (FK), `role` (`user`/`assistant`), `content`, `answer_type` (`structural`/`synthesis`/`fallback`), `created_at` | Chat history |
| `chat_message_citation` | `message_id` (FK), `document_id` (FK), `segment_id` (FK, nullable) | Lineage of the answer — which document/segment supports the answer |

`session_token` is a random, sufficiently long opaque string (no JWT needed — no
embedded claims, only a lookup key). The client receives it with the first
request and sends it along with follow-up requests; a missing or unknown token starts
a new session, not an error.

`account_id` is `NULL` for purely anonymous sessions and stays so for the entire lifetime
of the session as long as no valid account token is sent — see below. An account can
have several `chat_session` rows (one device/browser = one session, as before); there
is no automatic merging of several device histories into one session.

### Session identity and account linking

`POST /v1/chat` optionally accepts an `Authorization: Bearer <accounts-session-token>`
header. `chat/` verifies a supplied account token exclusively via an
HTTP call against `accounts/` (`GET /v1/accounts/session`) — the same "service as
HTTP client" principle as with `api/`, no direct access to `accounts` tables. Three
cases:

1. **No or invalid account token.** Behavior unchanged from the original spec: purely
   anonymous session via `session_token`, no contact with `accounts/`.
2. **Valid account token, `chat_session` not yet linked** (`account_id IS NULL`).
   The session is now linked to the account ID (`UPDATE chat_session SET account_id =
   ...`), the previous message history is fully preserved and from this
   point on is also visible from other devices linked to the same account (via
   a future "list sessions" capability, not part of the scope here — see Open
   items).
3. **Valid account token, `chat_session` already bound to a DIFFERENT account ID.**
   Protection against a change of device/user: instead of reusing the other person's session, a
   new `chat_session` is created for this account and a new `session_token`
   is returned (as with the very first request). Prevents one
   person's messages from ending up in another's history just because both used the same device with a
   reused `session_token`.

An expired/unknown account token is treated like "no token" (case 1) — no
error, no detail leak, consistent with `accounts/`'s own handling of `/session`.

`language` is an explicit client parameter (`"de"` or `"en"`), not an automatically
detected one — the same pattern as `jurisdiction`: deterministic, no additional
detection service/model needed. It controls (a) which text templates `structural.py` uses for
structural answers (b) the language instruction in the synthesis prompt to the LLM. The
similarity search itself is independent of it: `multilingual-e5-large` is cross-lingual
— an English question also finds German DGUV segments, and the LLM then still phrases the answer
in English. `chat/`'s answer (paraphrased) is thus linguistically independent
of the source language of the cited segments.

Repository access follows the same pattern as everywhere in the project: `ChatRepository` (or similar) in
`core/src/normly_core/graph/postgres/repositories.py`, Protocol in `domain.py`,
Alembic migration for the three tables.

### New repository capability: similarity search

`SegmentRepository.find_similar_segments_for_jurisdiction(query_vector: list[float],
jurisdiction: str, limit: int = 5) -> list[Segment]` — pgvector similarity search
(`ORDER BY embedding.vector <=> :query_vector LIMIT :limit`), with the same
rights gate conditions as the existing `list_segments_for_jurisdiction`
(`may_process`, `may_index_fulltext`, `revoked_at IS NULL`) — only with
distance ordering instead of completeness. No second check path: the same
rights classification logic, only a different ordering/limit.

`EmbeddingModel` (from the ingestion pipeline, `core/src/normly_core/pipeline/embeddings.py`)
gets a new method `embed_query(text: str) -> list[float]` (prefix `"query: "` instead of
`"passage: "`, the e5 convention for search queries vs. index content) — the existing `embed()`
stays unchanged, no breaking change for the ingestion pipeline.

## Data flow

`POST /v1/chat` — `{session_token: str | None, jurisdiction: str, language: Literal["de", "en"], message: str}`,
optional header `Authorization: Bearer <accounts-session-token>`

```
No/unknown session_token? -> create a new chat_session, return a new token

Authorization header present?
    -> GET /v1/accounts/session at accounts/ (HTTP call)
    invalid/expired? -> treat like "no header", continue as before
    valid, chat_session.account_id still NULL?
        -> set chat_session.account_id, history is kept
    valid, chat_session.account_id already a DIFFERENT account ID?
        -> create a new chat_session for this account, return a new session_token
    valid, chat_session.account_id == this account ID?
        -> nothing to do, continue as before

classify message (classify.py, rule-based, no model call):
    patterns like "ersetzt", "gültig", "Verweis auf" + a recognizable designation in the text
    -> STRUCTURAL QUESTION
    otherwise -> SYNTHESIS QUESTION

STRUCTURAL QUESTION:
    extract the designation from the text (regex/heuristic)
    -> HTTP call against api/: GET /v1/documents (search), then, depending on the detected
       question type, GET .../validity or GET .../edges
    -> deterministic answer sentence, assembled as text from the
       structured JSON response — NO model call
    -> citation: the found document itself
    -> document not found (404 from api/)? -> fallback answer

SYNTHESIS QUESTION:
    EmbeddingModel.embed_query(message)
    -> SegmentRepository.find_similar_segments_for_jurisdiction(vector, jurisdiction, limit)
    no match? -> fallback answer (canned text, no model call)
    matches present?
        -> prompt: system instruction "only paraphrase, answer only from the context,
           no full-text reproduction, answer in {language}" (REQ-FUNC-001/002) +
           segment texts + question
        -> Ollama call (Llama 3.1 8B Instruct)
        -> verbatim-overlap check of the answer against the cited segment texts (cheap,
           no model call; first, so that a clear hit no longer needs a second,
           more expensive model call)
           (15+ consecutive words overlapping? -> discard the answer, fallback
           instead, incident logged)
        -> otherwise: faithfulness check (second, targeted Ollama call: "sind die
           Aussagen dieser Antwort durch den folgenden Kontext gedeckt? ja/nein + Begründung",
           i.e. are the statements of this answer backed by the following context? yes/no + reasoning; context = the same cited segments)
           "nein"? -> discard the answer, fallback instead, incident logged
        -> otherwise: answer + citations (the segments/documents used)

store chat_message (user question) + chat_message (answer) + chat_message_citation(s)
-> Response: {session_token, answer, answer_type, citations}
```

No LLM call for structural questions and for any fallback case that is already
known before generation (no match, no document) — only an actually attempted synthesis calls the
model, twice in the success case (generation + faithfulness check), only once on a
verbatim-overlap hit (ADR-008's "Double gain": lower costs and higher
reliability exactly where errors would be most expensive — the second call is deliberately only
the exception, not the rule, more expensive than the ADR originally envisaged, but still limited to the
one case where it matters).

## Error handling

| Case | Behavior |
|---|---|
| Missing/empty `message` or `jurisdiction` | 400 |
| Unknown/missing `session_token` | No error — a new session is created |
| Missing/invalid/expired account token in the `Authorization` header | No error — treated like "no account token", chat continues to work anonymously |
| Structural question, but document not found in `api/` (404) | Fallback answer, no chat error |
| Synthesis question without relevant segments | Fallback answer, no model call |
| LLM answer contains 15+ consecutive words from a cited source segment | Answer discarded, fallback answer instead, incident logged |
| Faithfulness check rates the answer as not covered by the context | Answer discarded, fallback answer instead, incident logged |
| Ollama unreachable | 503, no detail leak |
| Database or `api/`/`accounts/` connection down | 503, no detail leak |

## Test concept

- Real Ollama with the real Llama 3.1 8B Instruct in the tests (no mocking of the model) —
  consistent with the project style so far (real embedding model in the
  ingestion pipeline, real Postgres everywhere). The available 24 GB GPU is sufficient for this.
- `api/` and `accounts/` run as real processes in the tests, `chat/` really calls them
  over HTTP — no mocking, exactly as an external third-party system would use them.
- Classification (`classify.py`) tested in isolation and without model/DB — pure
  function logic, fast.
- Structural question path: end-to-end against real DGUV/EUR-Lex test data, additionally checks that
  no Ollama call takes place (counter/spy on the Ollama client).
- Synthesis question path: end-to-end with real DGUV segments, checks citations, the
  verbatim-overlap check and the faithfulness check — each positively (a normal paraphrase
  or a covered statement is let through) and negatively (a test prompt that deliberately
  repeats full text forces the fallback via the verbatim check; a test prompt that deliberately
  inserts claims foreign to the context forces the fallback
  via the faithfulness check). Also checks that the faithfulness check is NOT called anymore on a clear
  verbatim hit (counter/spy on the Ollama client, the second
  call does not happen).
- Rights classification asymmetry: the same question returns exclusively the fallback for a jurisdiction without
  classification (no segments visible) — analogous to the
  existing pattern from the previous sub-projects.
- Bilingualism: the same synthesis question once with `language="de"`, once with
  `language="en"` against the same (German) DGUV segments — checks that the
  similarity search finds the same segments in both cases (cross-lingual
  embedding model) and that the answer is actually phrased in the requested language
  each time.
- Session continuation: two requests with the same `session_token` end up in the same
  `chat_session`, with the complete `chat_message` history in the correct order.
- Account linking: an anonymous session with existing history, followed by a request
  with the same `session_token` plus a valid account token — checks that `account_id` is set
  AND the previous history is preserved. A second test with an invalid/expired
  account token checks that the session stays anonymous (no error). A third test checks the
  account-switch protection: `chat_session` already bound to account A, request with a valid token
  for account B — must create a new `chat_session` with a new `session_token` without
  touching account A's session.

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| REQ-FUNC-001 | Synthesis answers exclusively from retrieved segments visible in the jurisdiction (prompt binding); structural answers exclusively from the graph; additionally a faithfulness check as a post-check |
| REQ-FUNC-002 | Paraphrasing instruction in the prompt + verbatim-overlap check as a post-check |
| REQ-FUNC-003 | Fallback answer for every case without a robust basis (no match, no document, suspected plagiarism, uncovered statement) |
| REQ-INT-002A (history part only) | `chat_session`/`chat_message` allow "reopen chat" via the `session_token`, without an account — optionally additionally via a linked account |
| REQ-INT-004 | Ollama as an interchangeable inference layer behind `synthesis.py`; model change without changes to `chat/`'s public interface |
| REQ-GRAPH-003 | Rule-based classification before any model call, structural questions deterministically via `api/` |
| ADR-005 | Self-hosted LLM (Ollama/Llama 3.1) instead of an external US API |
| ADR-008 | No model call for routing, structural questions or fallback cases |
| ADR-017 / REQ-ACC-001 | Anonymous `session_token` stays the normal case — chat works without login; account linking is purely optional, never a prerequisite |

## Open items / follow-up work

- **User uploads** (REQ-INT-002A/B/C, the upload part) — a separate, later sub-project.
- **"List sessions" for an account.** An account can have several `chat_session` rows
  (one per device/browser that was linked), but this sub-project delivers no
  endpoint that shows a signed-in user all of their sessions or lets them switch
  between them — only the linking itself. Separate follow-up work.
- **Rate limiting/quota** (REQ-SEC-004) — a separate infrastructure decision, as in the
  backend API sub-project.
- **Session expiry/cleanup.** `chat_session`/`chat_message` currently have no
  automatic deletion period. REQ-INT-002C (default 7 days) applies explicitly to uploads, not to
  chat history — whether an analogous period makes sense for chat sessions is not
  decided here.
- **Two-model strategy** (ADR-008 mentions "a small model for routing, a large one only for complex
  syntheses") — for the start, one model plus rule-based routing is enough; a
  second, smaller model for fuzzier classification cases is not observably needed with the current
  collection.
- **Robust fact check against an external source of truth** (curated knowledge base,
  independent verification model) — see Non-goals, a separate, larger research topic.
  The model-based faithfulness check from this sub-project is a heuristic, not a
  guarantee; its actual hit rate (false positives/negatives) is only observable after
  production operation with real questions and could make a later calibration
  necessary.
- **Production deployment of the inference server** (GPU provisioning on STACKIT,
  scaling, SKE connection) — a later deployment decision, analogous to the previous
  sub-projects.
- **Several simultaneous chat requests/queue at Ollama.** With a single GPU
  and Ollama's default operation, parallelism is limited — unproblematic for the current usage size,
  to be checked with a growing collection (see also the vLLM alternative from the
  architecture discussion).
