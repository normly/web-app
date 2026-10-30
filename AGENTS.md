# normly — Repository instructions

normly is an open-core platform for knowledge about norms and standards. The
free core is licensed under AGPL-3.0; commercial services remain separate.

This file contains repository-wide constraints for contributors and coding
agents. Shared setup and test instructions are in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Coding agents can use the matching
task-specific skill under `.agents/skills/`:

- [Repository workflow](.agents/skills/repository-workflow/SKILL.md) — how to
  select and report checks for a task.
- [Specifications](.agents/skills/specifications/SKILL.md) — where requirements
  and decisions live, and how to change them consistently.
- [Architecture](.agents/skills/architecture/SKILL.md) — component boundaries
  and where to start tracing a change.

## Non-negotiable boundaries

These rules have legal or strategic reasons. If a task appears to conflict
with them, pause and ask rather than working around them.

- **No US services for operations, user data, the norms knowledge base,
  secrets, or production deployment.** These run exclusively on STACKIT.
  Since ADR-021, source code, CI/CD, and the free core's container registry
  live on GitHub (`github.com/normly/web-app`) for easier collaboration;
  STACKIT Git is no longer used. The knowledge base is a separately
  versioned dump in STACKIT Object Storage (ADR-025).
- **Do not scrape commercially exploited catalog collections** (DIN Media,
  Nautos, or comparable holdings). Obtain them only by contract. Public
  accessibility does not change this rule. → ADR-012
- **No personalized advertising** and no user profiles for advertising
  purposes. → ADR-009
- **Freely available content must remain usable without an account.** An
  account may only be required for the functions explicitly listed in
  [REQ-ACC-004](docs/srs/03-requirements.md#req-acc-004-functions-requiring-an-account).
- **No copyrighted full texts** in free exports or in the public repository.
- **No DRM, offline-protection, or marking logic in the free core.** The core
  may provide interfaces; protection components belong to the commercial
  layer. → ADR-015
- **The core must not depend on proprietary components.** It must remain
  buildable, testable, and runnable without them.
- **Language models must be open-weight models with an OSI-approved license,
  operated on STACKIT. User requests must not reach model vendors; European
  origin is a preference, not a requirement. → ADR-022
- **Production and CI must not access external model providers at runtime.**
  Required model artifacts must be pinned and bundled or pre-fetched during
  image or build preparation.
- **Every data source needs a source-register entry and legal category** before
  acquisition or processing. If no category and legal basis can be assigned,
  do not process it. Never use category D for commercially exploited catalogs.
  See [the license model](docs/concepts/license-model.md) for category details.

## Engineering invariants

- Database access goes only through the repository layer. Keep SQL and
  storage-specific queries out of domain logic so storage remains replaceable.
  → ADR-006
- Preserve source lineage for every derived artifact so a source can be
  withdrawn. Lineage cannot reliably be reconstructed later.
- Resolve structural questions (references, validity, replacements) from the
  graph first. Use a language model only when text synthesis is needed. → ADR-008
- Rights classification is the sole processing gate. Missing classification
  means do not process.
- Processing steps must be idempotent.
- Keep licensed collections isolated per publisher, including publisher-level
  data keys and authorization checks on every access. → ADR-014
- Application logic accesses offline storage only through its abstraction
  layer; do not use IndexedDB, Keychain, or Keystore directly in application
  logic. Keep browser and native storage interchangeable. → ADR-016
- **Services that trust forwarded headers must only be reachable through the
  configured trusted reverse proxy.** Direct public access would permit header
  spoofing.
- Encrypt everything persisted, including databases, object storage, indexes,
  logs, and backups. Store keys separately from data.

## Identifiers

Design identifiers for worldwide use from the start; retrofitting them is
costly.

- Use a globally collision-free scheme and keep publisher, number, edition,
  and part number separate.
- One standard is one language-independent graph node. National adoptions
  and translations are relationships or attributes, not separate documents.
- Classify rights per jurisdiction, not globally; German copyright law does
  not determine status in every jurisdiction. → ADR-011

## Working and contribution practices

- For a new component, page, route, table, or service; user-visible behavior
  changes; changes affecting more than two files, public interfaces, data
  models, or migrations; or requirements with multiple sensible
  implementations, agree on the design before implementation. A clear,
  isolated bug fix, behavior-preserving visual change, or change to at most
  two files with exactly one sensible implementation can be implemented
  directly.
- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for requirements, branches, PRs,
  commits, DCO, AI use, license headers, and security restrictions.
- Debug systematically. Run relevant checks before reporting completion and
  report any checks that could not be run; see the
  [repository-workflow skill](.agents/skills/repository-workflow/SKILL.md).
- LLM coding agents must consult the root [`review.md`](review.md) index and
  follow the applicable module review guide as part of testing a change.
  Treat those review-specific checks as additional to the shared contribution
  and CI checks; report any required validation that could not be completed.

See the [architecture overview](docs/guide/architecture.md) for component
responsibilities and data flows; use the relevant ADRs and SRS requirements
for authoritative technical decisions and behavior requirements.

## Documentation language

Write code, identifiers, commits, and repository documentation in English.
Keep standards-domain terms in German where no established English equivalent
exists (for example, `Normenausschuss` and `Trägerorganisation`). The app's
German/English language switch is unaffected. → ADR-020

Use the binding terminology in [`docs/glossary.md`](docs/glossary.md).

When process or rules change, keep the publicly read contributor and policy
documents aligned, including `CONTRIBUTING.md`, `SECURITY.md`, `GOVERNANCE.md`,
`TRADEMARK.md`, and `CODE_OF_CONDUCT.md`.

## When something is unclear

Use the linked skills, ADRs, and SRS to resolve questions. Record new
architecture decisions in `docs/adr/` and update affected requirements in
`docs/srs/`.
