# License Model

normly follows an open-core model — the dividing line runs along
**content**, not the access path.

| Component | License |
|---|---|
| Core (server, application) | AGPL-3.0 |
| Client SDKs, API specification | Apache-2.0 |
| Data and reference graph | ODbL |

The AGPL applies when someone modifies and operates the server itself. A
third-party system that talks to a normly instance over the HTTP API is a
separate program and unaffected — integrations are explicitly welcome.

Rationale for the license choice: [ADR-002](../adr/README.md#adr-002-license-model-agpl-30-apache-20-odbl).
Why the graph stays open despite licensing:
[ADR-007](../adr/README.md#adr-007-reference-graph-stays-open).

## Rights classification by category

Every data source gets a category before it's processed at all:

| | Category | Basis |
|---|---|---|
| A | Official works, legal texts | § 5 UrhG or similar |
| B | Freely licensed regulations | Publisher's license |
| C | Contractually acquired | Contract reference |
| D | Other publicly accessible | Case-by-case review + § 44b Abs. 3 |

No assignable category means: not ingested. Category D is never used for
commercially exploited catalogs (DIN Media/Nautos and similar) — see
[ADR-012](../adr/README.md#adr-012-no-scraping-of-commercially-exploited-catalog-collections).

Classification applies **per jurisdiction**, not globally — § 5 UrhG only
applies in Germany. Details: [ADR-011](../adr/README.md#adr-011-internationalization-from-the-start).

## Separate data storage per publisher

Licensed collections (Category C) are stored separately per publisher, each
with its own data encryption key. This enables cryptographic erasure at
contract end — even in backups, where selective deletion is otherwise
practically infeasible. Details:
[ADR-014](../adr/README.md#adr-014-encryption-cryptographic-erasure-per-publisher).
