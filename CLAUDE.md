# normly — Working instructions

Platform for knowledge of norms and standards. Open core: free core under
AGPL-3.0, commercial services kept separate from it.

Detailed context: `docs/adr/` (decisions with their rationale),
`docs/srs/` (requirements, entry point `docs/srs/README.md` with the
requirement index). This file contains only what applies to **every** task.

## Non-negotiable

These rules have legal or strategic reasons. In case of conflict with a
task: ask, do not work around them.

- **No US services for operations, user data, the norms knowledge base,
  secrets or production deployment.** These run exclusively on STACKIT,
  without exception. **Exception since ADR-021 (2026-09-14):** source code,
  CI/CD and the container registry of the free core live on GitHub
  (`github.com/normly/web-app`) — easier collaboration was the deciding
  reason. STACKIT Git (`jwokittel/normly-webapp`) is no longer used for
  this, is no longer intended for the knowledge base (ADR-025) and will be
  deleted; the knowledge base lives as a dump in STACKIT Object Storage.
  → ADR-021 (supersedes ADR-019)
- **No scraping of commercially exploited catalog collections** (DIN
  Media/Nautos and comparable ones). Obtain only by contract. Applies even
  when publicly accessible. → ADR-012
- **No personalized advertising**, no user profiles for advertising
  purposes. → ADR-009
- **No copyrighted full texts** in free exports or in the public
  repository.
- **No DRM, offline-protection or marking logic in the free core.**
  Exposed protection code is no protection. The core only provides
  interfaces. → ADR-015
- **The core must not depend on proprietary components.** It must be
  buildable, testable and runnable without them.
- **Language models only as open-weight models with an OSI license,
  operated on STACKIT.** No request reaches the model vendor; European
  origin is a preference, not a requirement. → ADR-022

## For every code change

- **License headers** in new source files: AGPL-3.0 (core), Apache-2.0
  (SDKs, API specification).
- **Commits** need `Signed-off-by` (DCO). Conventional Commits, SemVer.
- **No direct push to `main`** — merge request with review and a green
  pipeline.
- **No secrets in code**, not even in tests or examples.

## Working mode: when to align first, when to implement directly

These rules apply in every permission mode, including auto mode. Auto mode
only affects tool decisions (reading files, running commands), not the
question of whether a design is aligned first.

### First invoke the `brainstorming` skill and ask clarifying questions if at least one of these applies:
- a new component, page, route, table or service is created
- an interaction or a behavior changes for the user (flow, state, visibility, operation)
- more than two files are touched
- an interface, a data model or a migration is affected
- the requirement allows more than one sensible implementation

Implementation starts only after the design is confirmed. No edits before that.

### Implement directly, without brainstorming:
- bug fix with a clear cause
- purely visual change without a change in behavior (color, spacing, text, icon swap)
- changes to at most two files that allow exactly one implementation

When in doubt, the first list applies.

### Other skills
- Debugging always with `systematic-debugging`, not ad hoc.
- Before "done", always `verification-before-completion`.

## Architecture rules

- **Database access only through the repository layer.** No SQL or
  graph-specific queries in the domain logic — the storage technology must
  remain replaceable. → ADR-006
- **Carry lineage along.** Every derived artifact (section, segment,
  embedding, graph edge, export file) references its source delivery.
  Without this, the promised withdrawal cannot be honored. Cannot be
  established retroactively.
- **Graph first, model only when needed.** Structural questions
  (replacement, validity, references) are answered deterministically from
  the graph, without an LLM call. → ADR-008
- **Rights classification is the only gate.** No second check path, no
  distributed checks. Missing classification means "do not process", not
  "provisionally allowed".
- **Make processing steps idempotent.** Repetition produces no different
  result.
- **Licensed collections kept separate per publisher** — including a data key
  per publisher. Enables cryptographic deletion at the end of a contract,
  even in backups. Authorization check on every access. → ADR-014
- **Offline access only through the abstraction layer.** No direct storage
  access (IndexedDB, Keychain, Keystore) in the application logic —
  browser and native storage must remain interchangeable. → ADR-016
- **Everything persisted is encrypted:** database, object storage, indexes,
  logs, backups. Keys never next to the data.

## New data sources

Every source needs a register entry with a category:

| | Category | Basis |
|---|---|---|
| A | Official works, legal texts | § 5 UrhG (German Copyright Act) or similar |
| B | Freely licensed standards | License of the publisher |
| C | Obtained by contract | Contract reference |
| D | Other publicly accessible | Case-by-case review + § 44b Abs. 3 (German Copyright Act, rights reservation for text and data mining) |

No category assignable → do not acquire. Never category D for commercially
exploited catalogs.

## Technical framework

- **Data storage:** PostgreSQL (Flex) with pgvector — graph and embeddings
  in one database. No Neo4j. → ADR-006
- **Shipping:** signed container images plus a runnable Compose setup.
  The knowledge base is **not** in the image but exists as an
  independently versioned dump. Code and data versioned separately.
  → ADR-010
- **Registry:** GitHub Container Registry (GHCR) in the repository
  `normly/web-app`, primary for the free core. → ADR-021
- **CI:** GitHub Actions in the repository `normly/web-app`. Porting
  `.forgejo/workflows/ci.yml` is still pending as follow-up work. → ADR-021
- **Frontend:** Next.js with `standalone` output, at the same time an
  installable PWA. No platform-specific primitives — everything must run in
  the container behind any reverse proxy.
- **Mobile:** The PWA is the only mobile access until phase 2. A native app
  comes only once licensed offline full texts are offered and belongs to the
  commercial layer. Not tied to a language model of its own. → ADR-016
- **Commercial layer does not mean paid access.** The native app is free of
  charge; free content in it is accessible without an account. Fees only
  for licensed full texts and their protected offline use.
- **No account requirement for free content.** Search, reference graph and
  free standards work without signing in. Account only for: higher quotas,
  histories, uploads, licensed content, offline use, paid services — this
  list is exhaustive. → ADR-017
- **SSO is optional**, never a prerequisite for free content. → REQ-INT-003
- **Quota counting on the server side**, never via cookies or browser
  storage. Same infrastructure as the rate limiting from REQ-SEC-004.

## Identifiers

Designed for worldwide use from the start — rebuilding after the fact is
the most expensive legacy burden.

- Globally collision-free scheme, publisher / number / edition / part
  number kept separate.
- **One standard = one node, language-independent.** DIN EN ISO 9001 and
  BS EN ISO 9001 are the same document; national adoptions and
  translations are relationships and attributes, respectively.
- **License classification per jurisdiction**, not global. § 5 UrhG
  applies only in Germany. → ADR-011

## Language

Everything in this repository is in English: code, identifiers, commits,
documentation (`docs/`, code reference, guides), ADRs, the SRS, specs and
plans under `docs/superpowers/`, root files, and this file. International
reach takes priority. Terms from the standards domain keep their German
form where there is no established English equivalent (e.g.
`Normenausschuss`, `Trägerorganisation`), regardless of the language of
the surrounding text. The app's own language switch (German/English for
end users) is unaffected. → ADR-020 (addendum pending in the ADR
translation; the decision is recorded in
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`)

Terminology is binding and defined in `docs/glossary.md`: *Norm* is
"norm", *Regelwerk* is "standards" (the broader term, which includes
norms); "norms and standards" names both together.

Migration in progress (2026-10-15): `docs/adr/`, `docs/srs/` and
`docs/superpowers/` are still being translated, see
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`. Until
then they remain German; new text in them is written in English.

## Other repository files

`CONTRIBUTING.md` (DCO process), `SECURITY.md` (reporting channel),
`GOVERNANCE.md` (roles and decision paths), `TRADEMARK.md` (trademark
use), `CODE_OF_CONDUCT.md`. When the process or the rules change, update
these files too — they are publicly visible and are read.

## When something is unclear

In case of conflict between this file and a task: ask. The rules above
have legal or strategic reasons that need not be apparent from a single
task. New architecture decisions get their own entry in `docs/adr/`.
