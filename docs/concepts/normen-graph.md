# Graph first, model only when needed

Queries are resolved against the reference graph first. A language model
is only invoked when synthesizing free text is actually needed — not for
structural questions.

**Why:** Questions like "what replaces standard X" or "which regulation
references standard Y" can be answered exactly from the graph —
deterministically, in milliseconds, at no token cost. A model call here
would be more expensive, slower, and more error-prone. Hallucinations are
especially costly for validity and replacement questions.

Details and trade-offs: [ADR-008](../adr/README.md#adr-008-graph-first-anfrageverarbeitung).

## Data storage

The graph lives in PostgreSQL with pgvector — graph and embeddings in the
same database, the same transaction, the same backup, instead of two
systems that would need to be kept in sync. Database access goes
exclusively through the repository layer; the underlying storage
technology stays swappable.

Details: [ADR-006](../adr/README.md#adr-006-postgresql-statt-neo4j-fur-den-referenzgraph).

## Open and layered at once

The reference graph itself is open (ODbL) — layered into a free and a
commercial part, not withheld. What's free is described in
[License Model](lizenzmodell.md).
