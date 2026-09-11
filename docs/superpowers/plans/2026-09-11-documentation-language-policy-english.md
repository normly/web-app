# Documentation Language Policy Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct CLAUDE.md's documentation-language rule from German to
English (going forward only, not retroactive), record the decision as
ADR-020, and translate the still-unmerged Zensical documentation site
(branch `docs/zensical-documentation-site`, PR #30) into English before
it merges.

**Architecture:** Five tasks, all on the existing branch
`docs/zensical-documentation-site` (worktree already set up at
`/home/snake/Dokumente/Projekte/01_normly/normly-app/.worktrees/docs-zensical-documentation-site`,
already has a `.venv-docs/` with Zensical installed). No new branch, no
new worktree. Task 1 touches `CLAUDE.md` and `docs/adr/README.md`
(policy documents, no build involved). Tasks 2-5 translate the site's
`.md`/`.toml` content file by file, rebuilding and grep-verifying after
each.

**Tech Stack:** Same as the original site build — Zensical (already
installed in `.venv-docs/`), no new tooling.

## Global Constraints

- Not retroactive: `README.md`, `docs/adr/README.md`'s ADR-001 through
  ADR-019, `docs/srs/*.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `GOVERNANCE.md`, `TRADEMARK.md`, `CODE_OF_CONDUCT.md` are explicitly
  **not** touched by this plan — a separate, later project.
- `CLAUDE.md` stays German — only the "Sprache" section's stated rule
  changes, not the file's own language.
- ADR-020 is written in German — transitional, consistent with ADR-001
  through ADR-019 in the same file, until that file's own later
  migration.
- Domain-term exception carries over unchanged: German Normenwesen terms
  without an established English equivalent (e.g. `Normenausschuss`,
  `Trägerorganisation`) keep their German form even in English prose.
  Terms that *do* have an established English equivalent already used
  elsewhere in this same site (e.g. "reference graph") are translated,
  not kept as an exception — see Task 5's glossary translation for the
  concrete judgment call.
- Filenames, paths, and all link targets (including ADR/SRS anchors)
  stay exactly as they are — only prose and display text are translated.
  `docs/adr/README.md` and `docs/srs/*.md` are not translated by this
  plan, so links into them keep pointing at German anchor text; that's
  correct, not a bug.
- `docs/reference/*.md` (the four mkdocstrings stub pages) are already
  English — no task touches them.
- Commits need `Signed-off-by` (DCO) — `git commit -s`.
- No `--strict` build (unchanged from the original site plan — see
  `docs/superpowers/specs/2026-09-11-zensical-documentation-site-design.md`,
  "Warum kein `--strict`"). Plain `zensical build` must still exit 0 with
  exactly the same 3 known, out-of-scope warnings as before (from
  `docs/superpowers/specs/*.md`'s `[[wiki-link]]` convention) — translating
  content must not introduce new warnings.

---

### Task 1: CLAUDE.md rule correction + ADR-020

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/adr/README.md`

**Interfaces:**
- None — this task doesn't touch the Zensical site's build; Tasks 2-5 are
  independent of it (they don't need CLAUDE.md or ADR-020 to build the
  site, they just implement what those documents describe).

- [ ] **Step 1: Edit CLAUDE.md's "Sprache" section**

Find this section (near the end of the file):

```markdown
## Sprache

Code, Bezeichner und Commits auf Englisch. Fachbegriffe aus dem Normenwesen
behalten ihren deutschen Begriff, wo es keine etablierte Entsprechung gibt
(z. B. `Normenausschuss`). Dokumentation und Nutzeroberfläche auf Deutsch,
Mehrsprachigkeit vorgesehen.
```

Replace it with:

```markdown
## Sprache

Code, Bezeichner und Commits auf Englisch. **Dokumentation ebenfalls auf
Englisch** (`docs/`-Inhalte, Code-Referenz, Guides) — internationale
Reichweite hat Vorrang. Fachbegriffe aus dem Normenwesen behalten ihren
deutschen Begriff, wo es keine etablierte Entsprechung gibt (z. B.
`Normenausschuss`), unabhängig von der Sprache der umgebenden Doku. Diese
Datei (CLAUDE.md) bleibt auf Deutsch. Die App-eigene Sprachumschaltung
(Deutsch/Englisch für Endnutzer) ist davon unberührt. → ADR-020

Nicht rückwirkend: bestehender deutscher Content (README.md, docs/adr/,
docs/srs/, CONTRIBUTING.md, SECURITY.md, GOVERNANCE.md, TRADEMARK.md,
CODE_OF_CONDUCT.md) bleibt vorerst unverändert — Migration ist ein
eigenes, späteres Projekt.
```

- [ ] **Step 2: Add ADR-020 to `docs/adr/README.md`**

Find the end of the ADR-019 section — it currently reads (near the end of
the file, right before a `---` separator and `## Offene Punkte`):

```markdown
**Verworfen:** Beibehaltung von GitHub als reine, weiterhin manuell
gepflegte Beitragsfassade ohne Automatisierung (löst das
Pflegeaufwand-Problem nicht, verzögert die Entscheidung nur).

---

## Offene Punkte
```

Insert a new ADR-020 section between the `---` and `## Offene Punkte`, so
it reads:

```markdown
**Verworfen:** Beibehaltung von GitHub als reine, weiterhin manuell
gepflegte Beitragsfassade ohne Automatisierung (löst das
Pflegeaufwand-Problem nicht, verzögert die Entscheidung nur).

---

## ADR-020 — Dokumentation auf Englisch statt Deutsch

**Status:** beschlossen

**Entscheidung:** Neue Dokumentation (`docs/`-Inhalte, Code-Referenz,
Guides) wird ab sofort auf Englisch verfasst statt auf Deutsch. Nicht
rückwirkend — bestehender deutscher Content (README.md, `docs/adr/`,
`docs/srs/`, `CONTRIBUTING.md`, `SECURITY.md`, `GOVERNANCE.md`,
`TRADEMARK.md`, `CODE_OF_CONDUCT.md`) wird nicht migriert; das ist ein
eigenes, späteres Projekt.

**Begründung:** Englisch ist der De-facto-Standard für
Open-Source-Dokumentation. Er ermöglicht internationalen Beitragenden
Teilnahme, unabhängig vom deutschsprachigen Kernteam — passend zum
Open-Core-Modell (ADR-001) und dem Anspruch, dass der freie Kern von
außen mitgetragen werden kann. Die ursprüngliche Regel (Dokumentation auf
Deutsch) stand dem im Weg.

**Nicht betroffen:** Code, Bezeichner und Commits waren schon vorher
Englisch (unverändert). Die App-eigene Sprachumschaltung
(`LocaleProvider`, Deutsch/Englisch für Endnutzer) ist eine
Laufzeit-Funktion, keine Projektdokumentation, und bleibt unverändert.
Die Fachbegriffs-Ausnahme für Normenwesen-Begriffe ohne etablierte
englische Entsprechung (z. B. `Normenausschuss`) gilt unabhängig von der
Sprache weiter.

**Konsequenz:** CLAUDE.md's Abschnitt „Sprache" ist entsprechend
angepasst. Der bereits offene, noch nicht gemergte Merge Request für die
Zensical-Dokumentations-Site
(`docs/superpowers/plans/2026-09-11-zensical-documentation-site.md`)
wird vor dem Merge auf Englisch umgeschrieben, da er als „ab jetzt"
zählt.

---

## Offene Punkte
```

- [ ] **Step 3: Verify both files are well-formed**

```bash
grep -c "^## ADR-020" docs/adr/README.md
grep -c "ADR-020" CLAUDE.md
```

Expected: both commands print `1` (ADR-020 appears exactly once as a
heading in the ADR file, and CLAUDE.md references it exactly once via the
`→ ADR-020` pointer).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/adr/README.md
git commit -s -m "docs: correct documentation language policy to English (ADR-020)"
```

---

### Task 2: Translate `zensical.toml` nav/description + `docs/index.md`

**Files:**
- Modify: `zensical.toml`
- Modify: `docs/index.md`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: nothing later tasks depend on structurally — each later task
  edits its own `nav` entries' *files*, not the `nav` array itself. The
  `nav` array's German labels (`"Start"`, `"Architekturentscheidungen"`,
  `"Anforderungen (SRS)"`, `"Code-Referenz"`, `"Glossar"`) are fully
  replaced by this task; no later task touches `nav` again.

Work from: `/home/snake/Dokumente/Projekte/01_normly/normly-app/.worktrees/docs-zensical-documentation-site`

- [ ] **Step 1: Replace `zensical.toml`'s `site_description` and `nav`**

Current content to replace:

```toml
site_description = "Normen- und Regelwerkswissen, strukturiert als Graph."
```

```toml
nav = [
  { "Start" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/normen-graph.md",
    "concepts/lizenzmodell.md",
  ] },
  { "Architekturentscheidungen" = "adr/README.md" },
  { "Anforderungen (SRS)" = "srs/README.md" },
  { "Code-Referenz" = [
    "reference/core.md",
    "reference/api.md",
    "reference/accounts.md",
    "reference/chat.md",
  ] },
  { "Glossar" = "glossary.md" },
]
```

New content:

```toml
site_description = "Standards knowledge, structured as a graph."
```

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/normen-graph.md",
    "concepts/lizenzmodell.md",
  ] },
  { "Architecture decisions" = "adr/README.md" },
  { "Requirements (SRS)" = "srs/README.md" },
  { "Code reference" = [
    "reference/core.md",
    "reference/api.md",
    "reference/accounts.md",
    "reference/chat.md",
  ] },
  { "Glossary" = "glossary.md" },
]
```

The rest of `zensical.toml` (`site_name`, `site_author`, `docs_dir`,
`[project.theme]`, `[project.plugins.mkdocstrings...]`) is unchanged —
don't touch it.

- [ ] **Step 2: Replace `docs/index.md`**

Full replacement content:

```markdown
# normly

**AI-assisted standards and regulations, open to everyone.**

normly makes knowledge about standards and regulations as freely
accessible as legally possible — and builds on that an open,
machine-readable reference graph: which regulations reference each
other, what replaced what, and which legal requirement points to which
standard.

!!! warning "Early development stage"
    This project is under construction. There is no runnable version yet
    and no stable API — this documentation site grows with the code.
    First runnable prototype: December 2026.

## Where to go next

- **[Guide](guide/getting-started.md)** — getting started for users and
  operators
- **[Concepts](concepts/normen-graph.md)** — the underlying principles
  (graph first, license model)
- **[Architecture decisions](adr/README.md)** — why it's built the way
  it's built
- **[Requirements](srs/README.md)** — the 78 requirements (SRS/SDD)
- **[Code reference](reference/core.md)** — generated automatically from
  docstrings, for contributors

## Licenses

| Component | License |
|---|---|
| Core (server, application) | AGPL-3.0 |
| Client SDKs, API specification | Apache-2.0 |
| Data and reference graph | ODbL |

Details and rationale are in `README.md` and `GOVERNANCE.md` at the
repository root.
```

- [ ] **Step 3: Build and verify**

```bash
source .venv-docs/bin/activate
zensical build
grep -o "AI-assisted standards and regulations" site/index.html
grep -o ">Home<\|>Guide<\|>Concepts<\|>Architecture decisions<\|>Requirements (SRS)<\|>Code reference<\|>Glossary<" site/index.html | sort -u
```

Expected: the first grep prints one match. The second grep prints all 7
nav labels present in the built page (order doesn't matter for this
check, presence does) — if any are missing, the `nav` array wasn't saved
correctly.

- [ ] **Step 4: Commit**

```bash
git add zensical.toml docs/index.md
git commit -s -m "docs: translate site nav and Home page to English"
```

---

### Task 3: Translate the Guide section

**Files:**
- Modify: `docs/guide/getting-started.md`
- Modify: `docs/guide/self-hosting.md`

**Interfaces:**
- Consumes: nothing new from Task 2.

Work from: `/home/snake/Dokumente/Projekte/01_normly/normly-app/.worktrees/docs-zensical-documentation-site`

- [ ] **Step 1: Replace `docs/guide/getting-started.md`**

```markdown
# Getting Started

!!! warning "No runnable version yet"
    normly is in early development — there's no installable release yet.
    First runnable prototype: December 2026. This page fills in once
    that's ready.

If you want to contribute to the code, `CONTRIBUTING.md` at the
repository root is the right starting point, not this page.
```

- [ ] **Step 2: Replace `docs/guide/self-hosting.md`**

```markdown
# Self-Hosting

!!! warning "No runnable version yet"
    Delivery is planned per [ADR-010](../adr/README.md#adr-010-auslieferung-als-container-daten-getrennt-vom-image)
    as signed container images plus a Compose setup, with the knowledge
    base as an independently versioned dump. This page will describe the
    actual path once there's a first release that does it — speculation
    doesn't help anyone who actually wants to self-host.
```

Note: the ADR-010 link target is unchanged (`../adr/README.md#adr-010-...`)
— `docs/adr/README.md` isn't translated by this plan, so the anchor and
its surrounding German heading text stay exactly as they are. Only this
page's own prose and the link's visible text change.

- [ ] **Step 3: Build and verify**

```bash
source .venv-docs/bin/activate
zensical build
grep -o "No runnable version yet" site/guide/getting-started/index.html site/guide/self-hosting/index.html
grep -o 'href="[^"]*adr-010[^"]*"' site/guide/self-hosting/index.html
```

Expected: the first grep prints one match per file (two lines total). The
second grep prints the same href it always has
(`../../adr/#adr-010-auslieferung-als-container-daten-getrennt-vom-image`)
— confirms the anchor still resolves after the translation.

- [ ] **Step 4: Commit**

```bash
git add docs/guide
git commit -s -m "docs: translate Guide section to English"
```

---

### Task 4: Translate the Concepts section

**Files:**
- Modify: `docs/concepts/normen-graph.md`
- Modify: `docs/concepts/lizenzmodell.md`

**Interfaces:**
- Consumes: nothing new from Task 3.

Work from: `/home/snake/Dokumente/Projekte/01_normly/normly-app/.worktrees/docs-zensical-documentation-site`

Note: the filenames stay German (`normen-graph.md`, `lizenzmodell.md`) —
only the content and the display text of links pointing at them change.
Don't rename the files; other pages link to them by these exact paths.

- [ ] **Step 1: Replace `docs/concepts/normen-graph.md`**

```markdown
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
```

- [ ] **Step 2: Replace `docs/concepts/lizenzmodell.md`**

```markdown
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

Rationale for the license choice: [ADR-002](../adr/README.md#adr-002-lizenzmodell-agpl-30-apache-20-odbl).
Why the graph stays open despite licensing:
[ADR-007](../adr/README.md#adr-007-referenzgraph-bleibt-offen).

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
[ADR-012](../adr/README.md#adr-012-kein-scraping-kommerziell-verwerteter-katalogbestande).

Classification applies **per jurisdiction**, not globally — § 5 UrhG only
applies in Germany. Details: [ADR-011](../adr/README.md#adr-011-internationalisierung-von-beginn-an).

## Separate data storage per publisher

Licensed holdings (Category C) are stored separately per publisher, each
with its own data encryption key. This enables cryptographic deletion at
contract end — even in backups, where selective deletion is otherwise
practically infeasible. Details:
[ADR-014](../adr/README.md#adr-014-verschlusselung-kryptographisches-loschen-je-herausgeber).
```

Note: `§ 5 UrhG` and `§ 44b Abs. 3` are references to specific sections of
German copyright law (Urheberrechtsgesetz) — kept verbatim, not
translated, same as any other proper-noun legal citation.

- [ ] **Step 3: Build and verify**

```bash
source .venv-docs/bin/activate
zensical build
grep -o "Graph first, model only when needed" site/concepts/normen-graph/index.html
grep -o "License Model" site/concepts/lizenzmodell/index.html
for anchor in \
  adr-008-graph-first-anfrageverarbeitung \
  adr-006-postgresql-statt-neo4j-fur-den-referenzgraph \
  adr-002-lizenzmodell-agpl-30-apache-20-odbl \
  adr-007-referenzgraph-bleibt-offen \
  adr-012-kein-scraping-kommerziell-verwerteter-katalogbestande \
  adr-011-internationalisierung-von-beginn-an \
  adr-014-verschlusselung-kryptographisches-loschen-je-herausgeber \
; do
  grep -rl "id=\"$anchor\"" site/adr/ || echo "MISSING: $anchor"
done
```

Expected: the first two greps each print one match. The anchor loop
prints no `MISSING:` lines — these are the same seven anchors verified
when this content was first written in German (they point into
`docs/adr/README.md`, which this plan doesn't touch, so they cannot have
changed, but re-verify rather than assume).

- [ ] **Step 4: Commit**

```bash
git add docs/concepts
git commit -s -m "docs: translate Concepts section to English"
```

---

### Task 5: Translate the Glossary + final verification build

**Files:**
- Modify: `docs/glossary.md`

**Interfaces:**
- Consumes: nothing new from Task 4. This is the last translation task —
  after this, every page in the site is English except
  `docs/adr/README.md` and `docs/srs/*.md` (out of scope, unchanged, and
  still linked-to from translated pages, which is correct per this
  plan's design).

Work from: `/home/snake/Dokumente/Projekte/01_normly/normly-app/.worktrees/docs-zensical-documentation-site`

- [ ] **Step 1: Replace `docs/glossary.md`**

```markdown
# Glossary

Terms from the standards domain keep their German form where there's no
established English equivalent.

**Normenausschuss**
: The body responsible for the content of a standard and its upkeep.

**Reference graph**
: The machine-readable graph of regulations, legal texts, and the
  relationships between them (replacement, reference, adoption) —
  normly's central data asset.

**Work**
: A regulation as a language-independent node in the reference graph. DIN
  EN ISO 9001 and BS EN ISO 9001 are the same Work; national adoptions and
  translations are relationships or attributes, not separate Works. See
  the "Identifiers" section in `CLAUDE.md`.

**Trägerorganisation**
: Holds the brand, open data, and source code; responsible for the free
  core and relationships with publishers and the community. Separate from
  a future commercial entity — see
  [ADR-001](adr/README.md#adr-001-open-core-modell-statt-white-label-produkt).

**Normenausschuss vs. publisher**
: The publisher (e.g. DIN, VDI, DGUV) releases a standard; the
  Normenausschuss develops its content. For rights classification, the
  publisher is what counts.

**Category A–D**
: Rights classification per source, see
  [License Model](concepts/lizenzmodell.md#rechteklassifikation-nach-kategorie).
```

Judgment call worth understanding, not re-litigating: `Referenzgraph` (the
original German term) is translated here to "Reference graph", *not* kept
under the domain-term exception — unlike `Normenausschuss` and
`Trägerorganisation`, "reference graph" already has an established
English equivalent, the one already used consistently throughout
`index.md`, `normen-graph.md`, and `lizenzmodell.md` (translated in Tasks
2 and 4). Keeping the glossary entry itself in German would be
inconsistent with how the term is used everywhere else in the same site.
`Normenausschuss` and `Trägerorganisation` stay German because they don't
have that established English equivalent — they're specific German
institutional/legal concepts (a standards-committee body, and a specific
non-profit holding-entity structure discussed in ADR-001), not just
untranslated convenience.

- [ ] **Step 2: Full build and final verification**

```bash
source .venv-docs/bin/activate
zensical build
echo "exit code: $?"
```

Expected: exit code 0.

- [ ] **Step 3: Verify the warning count didn't change**

```bash
NO_COLOR=1 TERM=dumb zensical build 2>&1 | tail -3
```

Expected: `3 issues found` (the same known, out-of-scope
`docs/superpowers/specs/*.md` wiki-link warnings as before translation —
if the count differs, something in this plan's edits introduced a new
warning; find it with `NO_COLOR=1 TERM=dumb zensical build 2>&1 | grep -B3 "does not exist"` and
fix it before committing).

- [ ] **Step 4: Spot-check the glossary and full nav render in English**

```bash
grep -o "Normenausschuss\|Reference graph\|Trägerorganisation" site/glossary/index.html | sort -u
grep -o ">Home<\|>Guide<\|>Concepts<\|>Architecture decisions<\|>Requirements (SRS)<\|>Code reference<\|>Glossary<" site/glossary/index.html | sort -u
```

Expected: the first grep prints all three terms (confirms the glossary
page itself rendered, terms present). The second grep prints all 7 nav
labels (confirms the English nav from Task 2 is still intact on this,
the last page of the site).

- [ ] **Step 5: Commit**

```bash
git add docs/glossary.md
git commit -s -m "docs: translate Glossary to English"
```

---

## After all tasks

Push the updated branch to the `stackit` remote (`git push stackit
docs/zensical-documentation-site`) to update the existing PR #30 —
confirm with the user before pushing, per the standing "confirm before CI
runs" rule (this triggers the `test-docs` CI job again). Do not open a
second PR; this branch already has one open.
