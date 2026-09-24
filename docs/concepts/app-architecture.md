<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Copyright (C) 2026 normly contributors -->

# Application architecture

normly is a service-oriented application built around a PostgreSQL-backed
reference graph. Natural-language chat is implemented as a separate service
that chooses between two deliberately different execution paths:

- **Structural questions** are answered deterministically from document
  metadata and graph edges.
- **Synthesis questions** use dense vector retrieval over indexed text
  segments, followed by retrieval-augmented generation with a self-hosted
  language model.

The application does not currently use a general-purpose autonomous-agent
framework. The chat service performs explicit orchestration and calls a small
set of purpose-specific clients and repositories.

## System overview

```text
Browser
  |
  v
Next.js frontend / BFF
  |
  +--> accounts service       account/session validation
  +--> api service            public document and graph queries
  +--> chat service           chat orchestration and history
          |
          +--> PostgreSQL via normly-core repositories
          +--> local embedding model
          +--> Ollama / Llama 3.1
```

The browser communicates with frontend route handlers only. Backend service
URLs and raw authentication tokens are kept on the server side. The frontend
uses `httpOnly` cookies for the anonymous chat-session token and the optional
account-session token.

The main application packages are:

| Package | Responsibility |
|---|---|
| `frontend/` | Next.js App Router application and backend-for-frontend (BFF) |
| `chat/` | Chat endpoint, routing, retrieval, synthesis, and chat history |
| `api/` | Public read-only document, validity, and graph API |
| `accounts/` | Account and account-session management |
| `core/` | Domain model, PostgreSQL repositories, ingestion pipeline, and embeddings |

Database access follows the repository-only rule. Service code does not issue
ad-hoc SQL or access another service's ORM tables directly.

## A chat request from browser to response

The user-facing chat endpoint is exposed through the frontend route:

`frontend/src/app/api/chat/route.ts`

The backend chat endpoint is:

`POST /v1/chat`

The request flow is:

```text
1. Browser sends message, jurisdiction, language, and optional session state
   |
2. Next.js route reads httpOnly cookies
   |
3. Next.js forwards the request to chat/v1/chat
   |
4. chat resolves or creates the chat session
   |
5. chat classifies the question using rules, without an LLM call
   |
6. chat executes either the structural or synthesis path
   |
7. chat stores the user message, assistant message, and citations
   |
8. chat returns answer, answer type, citations, and session token
   |
9. Next.js refreshes the session cookie and returns the response to the browser
```

The chat router is implemented in
`chat/src/normly_chat/routers/chat.py`.

### Session resolution

Session handling is implemented in
`chat/src/normly_chat/session_resolution.py`. A chat session is identified by
an opaque random `session_token`, not a JWT. The token is only a lookup key in
the database.

The resolution rules are:

1. A missing or unknown chat token creates a new `chat_session`.
2. A known anonymous session is continued.
3. A valid account token can associate an existing anonymous session with an
   account while preserving its history.
4. If the existing session belongs to a different account, a new session is
   created instead of exposing or appending to another user's history.
5. An invalid or expired account token is treated as anonymous access; it does
   not make an otherwise valid chat request fail.

The optional account token is validated through an HTTP call to `accounts`.
The `chat` service does not access account tables directly.

Chat history is stored in three tables:

| Table | Purpose |
|---|---|
| `chat_session` | Session identity, jurisdiction, language, and optional account association |
| `chat_message` | User and assistant messages |
| `chat_message_citation` | Documents and segments supporting an assistant message |

The writes are performed by `PostgresChatRepository` in
`core/src/normly_core/graph/postgres/repositories.py`.

## Rule-based question routing

Question classification is implemented in
`chat/src/normly_chat/classify.py`. It is intentionally rule-based and does
not call an LLM for routing.

The classifier first looks for a standards or legal designation, such as:

- `DIN EN ISO 9001`
- `CEN EN 12345`
- `EU 2006/42/EC`

If a designation is present, trigger words determine whether the question is
structural:

- Validity terms such as `gültig`, `in Kraft`, `aktuell`, `valid`, or `in force`
  select the structural validity path.
- Reference terms such as `ersetzt`, `verweist`, `replaces`, or `references`
  select the structural reference path.
- A designation without either pattern, or a question without a designation,
  selects the synthesis path.

This routing keeps exact graph questions out of the language model path. It
also means that a general question containing a word such as "current" but no
specific document designation can still be answered through text retrieval.

## Structural path: relational lookup and graph traversal

Structural answers are assembled by
`chat/src/normly_chat/structural.py`. The chat service calls the public `api`
service through the HTTP wrapper in
`chat/src/normly_chat/api_client.py`.

### Document lookup

First, the extracted issuer and designation are sent to:

```text
GET /v1/documents?issuer=<issuer>&designation=<designation>&jurisdiction=<jurisdiction>
```

The API implementation in `api/src/normly_api/routers/documents.py` performs
a relational lookup through `PostgresDocumentRepository.find_by_designation`.
It then applies the jurisdiction and rights gate. A document that is absent,
not classified for the jurisdiction, revoked, or otherwise not visible is
returned as `404` rather than disclosed.

This lookup is not a vector search. It is an exact designation lookup backed by
relational tables.

### Validity questions

For a validity question, chat calls:

```text
GET /v1/documents/{document_id}/validity?jurisdiction=<jurisdiction>
```

The API implementation in
`api/src/normly_api/routers/validity.py` checks incoming graph edges. This
direction matters because replacement and withdrawal edges point from a
successor or withdrawal notice to the document being replaced or withdrawn.

The result is derived deterministically:

- An incoming `REPLACES` edge means the document is replaced.
- An incoming `WITHDRAWN_BY` edge means it was withdrawn.
- If neither visible edge exists, the API reports it as valid.

The graph edge query is still a PostgreSQL relational query. The graph is
stored in tables; there is no separate graph database.

### Reference questions

For a reference question, chat calls both the validity endpoint and:

```text
GET /v1/documents/{document_id}/edges?jurisdiction=<jurisdiction>
```

The edge endpoint uses outgoing graph edges. The API implementation in
`api/src/normly_api/routers/edges.py` returns visible free-layer edges after
checking the source and target document rights.

The answer is then assembled from structured JSON. No LLM call is made for a
structural question.

### Structural path summary

```text
Designation in user text
  |
  v
Relational document lookup
  |
  +--> validity endpoint: incoming edge query
  |
  +--> reference endpoint: outgoing edge query
  |
  v
Deterministic response text and document citation
```

## Synthesis path: dense vector retrieval and generation

Synthesis answers are implemented in
`chat/src/normly_chat/synthesis.py`. This is the application's RAG path.

### Query embedding

The local embedding model is
`intfloat/multilingual-e5-large`, implemented by
`core/src/normly_core/pipeline/embeddings.py`.

The user's question is encoded with the E5 query prefix:

```text
query: <user question>
```

The model runs locally. It is loaded once when the chat service starts, not
for every request.

### Segment retrieval

The query vector is passed to:

`PostgresSegmentRepository.find_similar_segments_for_jurisdiction`

in `core/src/normly_core/graph/postgres/repositories.py`.

The repository query:

- Joins text segments to their stored embeddings.
- Restricts results to the requested jurisdiction.
- Requires `may_process = true`.
- Requires `may_index_fulltext = true`.
- Excludes revoked rights classifications.
- Restricts results to the requested embedding model.
- Filters out vectors beyond the configured cosine-distance threshold.
- Orders by cosine distance.
- Returns up to five segments.

The stored segment embeddings are 1024-dimensional `pgvector` values. The
database has HNSW indexes using cosine distance, created by migration `0031`.

The retrieval query is therefore a **dense semantic nearest-neighbor search**.
It is not a keyword search and it is not a graph traversal.

### Prompt construction and LLM calls

If no relevant segments are found, the service returns a fallback response and
does not call the LLM.

If segments are found, their text is placed into a constrained prompt. The
prompt instructs the model to:

- Answer only from the retrieved context.
- Paraphrase instead of reproducing the source verbatim.
- Answer in the requested language.

The prompt and answer are sent to the locally hosted Ollama service, normally
using `llama3.1:8b-instruct-q4_0`. The client is implemented in
`chat/src/normly_chat/ollama_client.py`.

### Output checks

The generated answer is checked in two stages:

1. A local verbatim-overlap check rejects an answer containing 15 or more
   consecutive words from the retrieved context.
2. If that check passes, a second Ollama call asks whether the answer is
   supported by the same context. A negative result causes a fallback.

These checks are safeguards, not independent fact verification. The
faithfulness check uses the same LLM service and the same retrieved context.

### Synthesis path summary

```text
User question
  |
  v
multilingual-e5-large: embed query
  |
  v
pgvector cosine nearest-neighbor search over segments
  |
  v
Top five rights-visible segments
  |
  v
Ollama / Llama 3.1 synthesis
  |
  v
Verbatim-overlap check
  |
  v
Faithfulness check through a second Ollama call
  |
  v
Answer with segment and document citations
```

## Exactly which search types are used?

The current implementation can be summarized as follows:

| Question type | Lookup type | LLM used? |
|---|---|---|
| Structural validity | Exact relational document lookup plus incoming graph-edge query | No |
| Structural reference | Exact relational document lookup plus outgoing graph-edge query | No |
| Synthesis | Dense vector search over segment embeddings using pgvector cosine distance | Yes |

The chat path currently does **not** use:

- Sparse vector retrieval.
- BM25 ranking.
- PostgreSQL full-text search for chat retrieval.
- Hybrid dense-plus-sparse retrieval.
- A separate graph database.
- Multi-hop graph traversal for synthesis questions.
- An autonomous agent that chooses arbitrary tools.

The wider application does have other search functionality. For example,
document/work search can combine exact text candidates with document-level
semantic candidates. That is separate from the chat synthesis query, which
currently searches segment embeddings directly.

## Ingestion and index creation

Chat retrieval depends on artifacts created by the core ingestion pipeline.
The main orchestration is in
`core/src/normly_core/pipeline/runner.py`.

For each source record, the pipeline:

1. Applies rights classification before creating derived artifacts.
2. Resolves the document identity.
3. Creates or updates the document and its designations and titles.
4. Extracts references and creates graph edges.
5. Stores rights classifications for each jurisdiction.
6. Extracts full-text sections when `may_index_fulltext` allows it.
7. Stores each section as a segment.
8. Embeds each segment with the E5 passage prefix:
   `passage: <segment text>`.
9. Stores the segment embedding in PostgreSQL.

The segment embeddings used by chat are stored in the `embedding` table. The
pipeline also creates document-level embeddings in `document_embedding`; those
are used by broader catalogue/work search and are not the primary retrieval
index for chat synthesis.

The same rights model is applied at ingestion and retrieval time. A document
may have been indexed previously but become unavailable later if its rights
classification is revoked or no longer permits full-text indexing. The chat
repository checks the current rights state before returning a segment.

## Data and citation lineage

Every synthesis result cites the retrieved document and segment IDs. Every
structural result cites the identified document. These citations are stored in
`chat_message_citation` alongside the assistant message.

The underlying derived artifacts also retain delivery lineage. Segments,
embeddings, and graph edges reference the delivery that produced them. This
allows rights revocation and source withdrawal to remove or hide derived
artifacts consistently.

## Failure and fallback behavior

The chat service prefers an explicit fallback over an unsupported answer:

| Situation | Behavior |
|---|---|
| Missing message or jurisdiction | `400` response |
| No structural document | Fallback answer |
| No visible structural validity or edge result | Fallback answer |
| No relevant synthesis segments | Fallback without an LLM call |
| Verbatim overlap detected | Fallback after one LLM call |
| Faithfulness check fails | Fallback after the second LLM call |
| Ollama unavailable | Service error, without leaking internal details |
| Database or dependent service unavailable | Service error, without leaking internal details |

This design makes the distinction between lookup and generation explicit:
structural facts come from deterministic database-backed queries, while free
text is generated only after semantic retrieval has produced context.

## Relevant implementation locations

| Concern | Location |
|---|---|
| Frontend chat proxy | `frontend/src/app/api/chat/route.ts` |
| Chat request orchestration | `chat/src/normly_chat/routers/chat.py` |
| Session resolution | `chat/src/normly_chat/session_resolution.py` |
| Rule-based classification | `chat/src/normly_chat/classify.py` |
| Structural answers | `chat/src/normly_chat/structural.py` |
| Synthesis/RAG answers | `chat/src/normly_chat/synthesis.py` |
| API service client | `chat/src/normly_chat/api_client.py` |
| Ollama client | `chat/src/normly_chat/ollama_client.py` |
| Document API | `api/src/normly_api/routers/documents.py` |
| Validity API | `api/src/normly_api/routers/validity.py` |
| Edge API | `api/src/normly_api/routers/edges.py` |
| Segment vector retrieval | `core/src/normly_core/graph/postgres/repositories.py` |
| Embedding model | `core/src/normly_core/pipeline/embeddings.py` |
| Ingestion orchestration | `core/src/normly_core/pipeline/runner.py` |
