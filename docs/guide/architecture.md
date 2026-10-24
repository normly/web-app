# Architecture overview

normly is a set of focused services with a shared Python domain and persistence
package. The complete deployment topology is in [`compose.yaml`](https://github.com/normly/web-app/blob/develop/compose.yaml);
the source-to-delivery pipeline is shown in
[`normly_processing-chain.svg`](../normly_processing-chain.svg).

## Components

| Component | Responsibility | Start exploring |
|---|---|---|
| `core/` | Shared domain model, graph repositories, migrations, import/export, and source-processing pipeline | `core/src/normly_core/graph/`, `pipeline/`, `exchange/` |
| `api/` | HTTP endpoints for document, graph, and search operations | `api/src/normly_api/routers/` |
| `chat/` | Chat session flow, graph-first retrieval, and response synthesis | `chat/src/normly_chat/` |
| `accounts/` | Registration, authentication, sessions, profiles, and account features | `accounts/src/normly_accounts/routers/` |
| `frontend/` | Next.js application, page UI, and browser-facing backend routes | `frontend/src/app/` |

`deploy/`, `docker/`, `scripts/`, `.github/workflows/`, and `compose.yaml`
contain build, delivery, deployment, and operations code.

## Main data and request flows

```text
Sources
  → core processing pipeline (source adapters, extraction, rights checks,
    lineage, graph records and embeddings)
  → PostgreSQL / pgvector through core repositories

Browser → Next.js frontend
              ├─→ api      (document and graph access)
              ├─→ chat     (graph retrieval first; model synthesis if needed)
              └─→ accounts (identity and account operations)

chat → api      (document and graph retrieval over HTTP)
chat → accounts (session lookup over HTTP)
```

The services communicate over HTTP. The frontend has no database access.
Services do not issue SQL against the shared database themselves: persistence
is owned by `core` and accessed through its repository layer. PostgreSQL stores
the graph and embeddings together; the graph abstraction keeps the storage
technology replaceable. See [Graph first, model only when needed](../concepts/norm-graph.md)
and [ADR-006](../adr/README.md#adr-006-postgresql-instead-of-neo4j-for-the-reference-graph).

The repository-wide engineering and legal constraints are maintained in
[`AGENTS.md`](https://github.com/normly/web-app/blob/develop/AGENTS.md). For the rationale behind specific boundaries,
see the related [ADRs](../adr/README.md), especially
[ADR-008](../adr/README.md#adr-008-graph-first-query-processing) and
[ADR-021](../adr/README.md#adr-021-return-to-github-for-source-code-ci-and-registry).

For a task that changes component boundaries or data ownership, read the
[architecture skill](https://github.com/normly/web-app/blob/develop/.agents/skills/architecture/SKILL.md)
and the related requirements and ADRs before editing.
