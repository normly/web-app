# Zensical Documentation Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Zensical-built documentation site for normly-app, built
fresh against current `main`, replacing the stale unmerged mkdocs branch
`claude/normly-documentation-structure-3zs7i0` (which is content reference
only, never merged).

**Architecture:** A root-level `zensical.toml` with `docs_dir = "docs"`
points at the existing `docs/` folder, which already holds `docs/adr/` and
`docs/srs/` with current content — no copying. New site pages (home, guide,
concepts, code reference, glossary) are added under `docs/` alongside them.
Code reference pages use the mkdocstrings plugin, which imports
`core`/`api`/`accounts`/`chat` to read their docstrings. A new
`test-docs` CI job builds the site (not `--strict` — see Task 6 Step 3 for
why).

**Tech Stack:** Zensical (`pip install zensical`), mkdocstrings (bundled
Zensical plugin), Python 3.12 (matches other services' CI containers).

## Global Constraints

- No US services for build, operation, data, secrets, or deployment (CLAUDE.md
  wording at the time, non-negotiable). Concretely for this project: the built site must not load
  fonts from `fonts.googleapis.com` / `fonts.gstatic.com`.
- No GitHub as a contribution facade (ADR-019) — no new links to
  `github.com/sn4kez/normly-app` anywhere in the site content.
- Code, identifiers, and commits in English; documentation and UI in German
  (CLAUDE.md wording at the time, section "Language"). All new `docs/*.md` content in this plan was German at the time,
  matching the existing `docs/adr/`, `docs/srs/`, and old-branch content
  (the pages are shown in English below since the 2026-10 English migration;
  the `grep` checks still search for the original German strings).
- Commits need `Signed-off-by` (DCO) — use `git commit -s`.
- No direct push to `main` — this work should land via merge request once
  complete, per CLAUDE.md ("No direct push to `main`"). Ask the user
  before pushing/opening a merge request, per the standing "confirm before
  CI runs" rule — pushing triggers the STACKIT pipeline.
- New source files get the AGPL-3.0 license header where applicable; the
  files touched in this plan are all Markdown/TOML/YAML documentation and
  config, so no source license headers apply here.

---

### Task 1: Bootstrap Zensical project + Home page

**Files:**
- Create: `zensical.toml`
- Create: `docs/index.md`

**Interfaces:**
- Produces: `zensical.toml` with `[project]` table (`site_name`, `docs_dir`,
  `nav`) that later tasks extend by adding entries to `nav` and new
  `[project.plugins.*]` tables. Later tasks must not rename `site_name` or
  `docs_dir`.

- [ ] **Step 1: Create an isolated venv and install Zensical**

```bash
python3 -m venv .venv-docs
source .venv-docs/bin/activate
pip install zensical
pip show zensical
```

Expected: install succeeds; `pip show zensical` prints a `Version:` line —
note the exact version, it goes into the CI job in Task 7
(`pip install zensical==<version>`) so the build is reproducible.

If `pip install zensical` fails outright (package renamed/unpublished),
stop and re-check https://zensical.org/docs/get-started/ for the current
package name before continuing — do not substitute a guess.

- [ ] **Step 2: Write `zensical.toml`**

```toml
[project]
site_name = "normly"
site_description = "Standards knowledge, structured as a graph."
site_author = "normly contributors"
docs_dir = "docs"

nav = [
  { "Home" = "index.md" },
]
```

- [ ] **Step 3: Write `docs/index.md`**

```markdown
# normly

**AI-assisted standards and regulations, open to everyone.**

normly makes knowledge about standards and regulations as freely accessible
as legally possible — and builds on that an open, machine-readable
reference graph: which regulations reference each other, what replaced
what, and which legal requirement points to which standard.

!!! warning "Early development stage"
    This project is under construction. There is no runnable version yet
    and no stable API — this documentation site grows with the code.
    First runnable prototype: December 2026.

## Where to go next

- **[Guide](guide/getting-started.md)** — getting started for users and operators
- **[Concepts](concepts/norm-graph.md)** — the underlying principles
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

Note: this links to `guide/getting-started.md`, `concepts/norm-graph.md`,
`reference/core.md` which don't exist yet — that's expected, they land in
Tasks 2, 3, 5. Don't build with `--strict` yet (it would fail on these); a
plain build is enough for this task.

- [ ] **Step 4: Build and verify the Home page renders**

```bash
zensical build
ls site/index.html
grep -o 'KI-unterstützte Normen und Standards' site/index.html
```

Expected: `site/index.html` exists; the grep prints one match (confirms the
content actually made it into the rendered HTML, not just that the build
didn't crash).

- [ ] **Step 5: Verify no Google Fonts reference in the build output**

```bash
grep -rl "fonts.googleapis.com\|fonts.gstatic.com" site/ || echo "OK: no Google Fonts reference"
```

Expected: `OK: no Google Fonts reference`. If a match is found instead: the
default theme is pulling web fonts. Check `zensical.toml`'s theme
documentation (https://zensical.org/docs/setup/) for the current
font-disabling key (as of the mkdocs-material lineage this was
`theme.font: false` or an equivalent `[project.theme]` key), add it, rebuild,
and re-run this grep until it passes. Do not proceed to Step 6 until it
passes — this is a CLAUDE.md non-negotiable, not a style preference.

- [ ] **Step 6: Probe whether files outside `nav` still get built**

Zensical currently has no `exclude_docs`/`not_in_nav` equivalent (see
`docs/superpowers/specs/2026-09-11-zensical-documentation-site-design.md`).
`docs/superpowers/` already has real content and is never added to `nav` in
this plan — check what actually happens to it:

```bash
find site -path "*superpowers*"
```

Expected: either nothing (Zensical only builds pages reachable from `nav`)
or HTML files under `site/superpowers/...` (Zensical builds everything
under `docs_dir` regardless of `nav`). Either outcome is fine per the spec
— record which one it is in the Task 1 commit message so later readers
don't have to re-derive it. No action needed in this task either way.

- [ ] **Step 7: Commit**

```bash
git add zensical.toml docs/index.md
git commit -s -m "$(cat <<'EOF'
docs: bootstrap Zensical project with Home page

Fresh Zensical setup against current main (zensical.toml, native config
format), replacing the stale unmerged mkdocs branch
claude/normly-documentation-structure-3zs7i0. <note here whether Step 6
found superpowers/ built into site/ or not>.
EOF
)"
```

---

### Task 2: Guide section

**Files:**
- Create: `docs/guide/getting-started.md`
- Create: `docs/guide/self-hosting.md`
- Modify: `zensical.toml` (extend `nav`)

**Interfaces:**
- Consumes: `zensical.toml`'s `nav` array from Task 1.
- Produces: `nav` now has a `"Guide"` section; later tasks append their own
  sections after it, they don't reorder it.

- [ ] **Step 1: Write `docs/guide/getting-started.md`**

```markdown
# Getting Started

!!! warning "No runnable version yet"
    normly is in early development — there is no installable
    release yet. First runnable prototype: December 2026.
    This page will fill up once that point is reached.

If you want to contribute to the code, `CONTRIBUTING.md` at the
repository root is the right starting point, not this page.
```

(The old branch linked `CONTRIBUTING.md` to
`github.com/sn4kez/normly-app/blob/main/CONTRIBUTING.md` — dropped per
ADR-019, no new GitHub links. A plain-text reference is used instead of a
relative link because `CONTRIBUTING.md` lives outside `docs_dir` and a link
to it wouldn't resolve on the built site, only when browsing the raw repo.)

- [ ] **Step 2: Write `docs/guide/self-hosting.md`**

```markdown
# Self-Hosting

!!! warning "No runnable version yet"
    According to [ADR-010](
    ../adr/README.md#adr-010-shipping-as-a-container-data-separate-from-the-image)
    shipping is planned as signed
    container images plus a Compose setup, with the knowledge base as a
    separately versioned dump. This page describes the planned
    path only once there is a first release that actually
    does that — speculation helps no one who really wants to self-host.
```

- [ ] **Step 3: Extend `nav` in `zensical.toml`**

Replace the `nav` array with:

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
]
```

- [ ] **Step 4: Build and verify**

```bash
zensical build
grep -o 'Noch keine lauffähige Version' site/guide/getting-started/index.html
grep -o 'Noch keine lauffähige Version' site/guide/self-hosting/index.html
```

Expected: one match in each. (Path may be `site/guide/getting-started.html`
instead of the `.../index.html` directory form depending on
`use_directory_urls` — check `ls site/guide/` if the above path doesn't
exist and adjust.)

- [ ] **Step 5: Verify the ADR-010 anchor link resolves**

```bash
zensical build
grep -o 'id="adr-010-auslieferung-als-container-daten-getrennt-vom-image"' site/adr/*/index.html site/adr/*.html 2>/dev/null
```

Expected: one match (confirms the heading-derived anchor id in the built
`docs/adr/README.md` page actually matches what `self-hosting.md` links to
— a silently broken cross-reference here would only show up as a dead link
a reader clicks, `--strict` may or may not catch it depending on whether
Zensical validates anchor fragments, so check by hand). If no match, open
`site/adr/index.html` (or wherever it built) and grep for `id="adr-010` to
find the actual generated id, then fix the link in `self-hosting.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/guide zensical.toml
git commit -s -m "docs: add Guide section (getting-started, self-hosting)"
```

---

### Task 3: Concepts section

**Files:**
- Create: `docs/concepts/norm-graph.md`
- Create: `docs/concepts/license-model.md`
- Modify: `zensical.toml` (extend `nav`)

**Interfaces:**
- Consumes: `nav` array from Task 2.
- Produces: `nav` now has a `"Concepts"` section after `"Guide"`.

- [ ] **Step 1: Write `docs/concepts/norm-graph.md`**

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

Details and trade-offs: [ADR-008](../adr/README.md#adr-008-graph-first-query-processing).

## Data storage

The graph lives in PostgreSQL with pgvector — graph and embeddings in the
same database, the same transaction, the same backup, instead of two
systems that would need to be kept in sync. Database access goes
exclusively through the repository layer; the underlying storage
technology stays swappable.

Details: [ADR-006](../adr/README.md#adr-006-postgresql-instead-of-neo4j-for-the-reference-graph).

## Open and layered at once

The reference graph itself is open (ODbL) — layered into a free and a
commercial part, not withheld. What's free is described in
[License Model](license-model.md).
```

(Unchanged from the old branch — content still matches current ADR-006/-008.)

- [ ] **Step 2: Write `docs/concepts/license-model.md`**

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
separate program and unaffected — integrations are explicitly
welcome.

Rationale for the license choice: [ADR-002](../adr/README.md#adr-002-license-model-agpl-30-apache-20-odbl).
Why the graph stays open despite licensing:
[ADR-007](../adr/README.md#adr-007-reference-graph-stays-open).

## Rights classification by category

Every data source gets a category before it's processed
at all:

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

Licensed holdings (Category C) are stored separately per publisher, each
with its own data encryption key. This enables cryptographic deletion at
contract end — even in backups, where selective deletion is otherwise
practically infeasible. Details:
[ADR-014](../adr/README.md#adr-014-encryption-cryptographic-erasure-per-publisher).
```

(New paragraph "Separate data storage per publisher" added — the old
branch didn't cover ADR-014, but it's directly relevant to the license
model and was missing.)

- [ ] **Step 3: Extend `nav` in `zensical.toml`**

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/norm-graph.md",
    "concepts/license-model.md",
  ] },
]
```

- [ ] **Step 4: Build and verify all ADR anchors used so far resolve**

```bash
zensical build
for anchor in \
  adr-008-graph-first-anfrageverarbeitung \
  adr-006-postgresql-statt-neo4j-fur-den-referenzgraph \
  adr-002-lizenzmodell-agpl-30-apache-20-odbl \
  adr-007-referenzgraph-bleibt-offen \
  adr-012-kein-scraping-kommerziell-verwerteter-katalogbestande \
  adr-011-internationalisierung-von-beginn-an \
  adr-014-verschlusselung-kryptographisches-loschen-je-herausgeber \
  adr-010-auslieferung-als-container-daten-getrennt-vom-image \
; do
  grep -rl "id=\"$anchor\"" site/adr/ || echo "MISSING: $anchor"
done
```

Expected: no `MISSING:` lines. `adr-014-...` is the one anchor in this list
that wasn't already validated on the old branch (it's a new reference added
in Step 2) — if it's reported missing, open the built ADR page and grep for
`id="adr-014` to find the actual id Zensical generated, then fix the link
in `license-model.md`.

- [ ] **Step 5: Commit**

```bash
git add docs/concepts zensical.toml
git commit -s -m "docs: add Concepts section (normen-graph, lizenzmodell)"
```

---

### Task 4: Wire in existing ADR/SRS docs

**Files:**
- Modify: `zensical.toml` (extend `nav`)

**Interfaces:**
- Consumes: `nav` array from Task 3.
- Produces: `nav` now has `"Architecture decisions"` and
  `"Requirements (SRS)"` entries after `"Concepts"`.

No new content — `docs/adr/README.md` and `docs/srs/README.md` (plus
`docs/srs/01-*.md` through `docs/srs/06-*.md`, linked from
`docs/srs/README.md` itself) already exist and are current. This task only
adds nav entries, matching the old branch's structure (a single nav entry
per section, not one per SRS chapter file).

- [ ] **Step 1: Extend `nav` in `zensical.toml`**

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/norm-graph.md",
    "concepts/license-model.md",
  ] },
  { "Architecture decisions" = "adr/README.md" },
  { "Requirements (SRS)" = "srs/README.md" },
]
```

- [ ] **Step 2: Build and verify**

```bash
zensical build
grep -o 'ADR-001' site/adr/*/index.html site/adr/index.html 2>/dev/null | head -1
grep -o 'Requirement' site/srs/*/index.html site/srs/index.html 2>/dev/null | head -1
```

Expected: one match each (confirms both pages render with their real
content, not empty stubs).

- [ ] **Step 3: Commit**

```bash
git add zensical.toml
git commit -s -m "docs: link existing ADR and SRS docs into site nav"
```

---

### Task 5: Code reference (mkdocstrings)

**Files:**
- Create: `docs/reference/core.md`
- Create: `docs/reference/api.md`
- Create: `docs/reference/accounts.md`
- Create: `docs/reference/chat.md`
- Modify: `zensical.toml` (add mkdocstrings plugin config, extend `nav`)

**Interfaces:**
- Consumes: `nav` array from Task 4.
- Produces: `nav` now has a `"Code reference"` section; `zensical.toml` has
  `[project.plugins.mkdocstrings.handlers.python]` and
  `[project.plugins.mkdocstrings.handlers.python.options]` tables.

- [ ] **Step 1: Install the four packages into the docs venv**

```bash
source .venv-docs/bin/activate
python -c "import cv2" 2>/dev/null || sudo apt-get install -y --no-install-recommends libgl1
pip install -e core -e api -e accounts -e chat
```

`libgl1` is needed because importing `normly_core` pulls in Docling, which
needs it (see the `test-core` job in `.forgejo/workflows/ci.yml` and the
filterwarnings comment in `core/pyproject.toml`). Skip the apt-get line if
`libgl1` is already present.

Expected: all four `pip install -e` succeed. If installing `api`,
`accounts`, or `chat` fails trying to fetch `normly-core` from PyPI, `core`
wasn't installed first in this same environment — install order matters,
redo starting with `pip install -e core`.

- [ ] **Step 2: Write the four reference stub pages**

`docs/reference/core.md`:
```markdown
# normly-core

Reference graph data model and repository layer. AGPL-3.0-or-later.

::: normly_core
```

`docs/reference/api.md`:
```markdown
# normly-api

Read-only HTTP API over the reference graph. AGPL-3.0-or-later.

::: normly_api
```

`docs/reference/accounts.md`:
```markdown
# normly-accounts

Account registration, login, and session service. AGPL-3.0-or-later.

::: normly_accounts
```

`docs/reference/chat.md`:
```markdown
# normly-chat

Natural-language chat over the reference graph. AGPL-3.0-or-later.

::: normly_chat
```

- [ ] **Step 3: Add mkdocstrings plugin config to `zensical.toml`**

Append:

```toml
[project.plugins.mkdocstrings.handlers.python]
paths = ["core/src", "api/src", "accounts/src", "chat/src"]

[project.plugins.mkdocstrings.handlers.python.options]
show_submodules = true
show_source = true
docstring_style = "google"
```

- [ ] **Step 4: Extend `nav`**

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/norm-graph.md",
    "concepts/license-model.md",
  ] },
  { "Architecture decisions" = "adr/README.md" },
  { "Requirements (SRS)" = "srs/README.md" },
  { "Code reference" = [
    "reference/core.md",
    "reference/api.md",
    "reference/accounts.md",
    "reference/chat.md",
  ] },
]
```

- [ ] **Step 5: Build and verify real docstrings were extracted**

```bash
zensical build
grep -o "WorkRepository" site/reference/core/index.html
grep -o "class Work" site/reference/core/index.html || grep -o "Work" site/reference/core/index.html
```

Expected: matches found — this proves mkdocstrings actually imported
`normly_core` and rendered a real symbol (`WorkRepository`, defined in
`core/src/normly_core/graph/domain.py`), not an empty or error page. If the
build fails here instead, it's almost always a missing runtime dependency
of one of the four packages inside `.venv-docs` — check the error for which
import failed.

- [ ] **Step 6: Commit**

```bash
git add docs/reference zensical.toml
git commit -s -m "docs: add mkdocstrings-generated code reference"
```

---

### Task 6: Glossary + full strict build

**Files:**
- Create: `docs/glossary.md`
- Modify: `zensical.toml` (extend `nav`, final version)

**Interfaces:**
- Consumes: `nav` array from Task 5.
- Produces: final `nav` — no later task extends it further.

- [ ] **Step 1: Write `docs/glossary.md`**

```markdown
# Glossary

Terms from the standards domain keep their German form where there's no
established English equivalent.

**Normenausschuss**
: The body responsible for the content of a standard and its upkeep.

**Reference graph**
: The machine-readable graph of standards, legal texts, and the
  relationships between them (replacement, reference, adoption) —
  normly's central data asset.

**Work**
: A standard as a language-independent node in the reference graph. DIN
  EN ISO 9001 and BS EN ISO 9001 are the same Work; national adoptions and
  translations are relationships and attributes, respectively, not
  separate Works. See the "Identifiers" section in `CLAUDE.md`.

**Trägerorganisation**
: Holds the brand, open data, and source code; responsible for the free
  core and relationships with publishers and the community. Separate from
  a future commercial entity — see
  [ADR-001](adr/README.md#adr-001-open-core-model-instead-of-a-white-label-product).

**Normenausschuss vs. publisher**
: The publisher (e.g. DIN, VDI, DGUV) releases a standard; the
  Normenausschuss develops its content. For rights classification, the
  publisher is what counts.

**Category A–D**
: Rights classification per source, see
  [License Model](concepts/license-model.md#rechteklassifikation-nach-kategorie).
```

(Adds a **Work** entry — new domain term introduced by the Normtracker work
since the old branch was written on 2026-08-27; matches
`core/src/normly_core/graph/domain.py`'s `Work` dataclass and CLAUDE.md's
"One standard = one node, language-independent" identifier rule.)

- [ ] **Step 2: Extend `nav`**

```toml
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/getting-started.md",
    "guide/self-hosting.md",
  ] },
  { "Concepts" = [
    "concepts/norm-graph.md",
    "concepts/license-model.md",
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

- [ ] **Step 3: Full build (not `--strict`)**

```bash
zensical build
echo "exit code: $?"
```

Expected: exit code 0. **`--strict` is deliberately not used** — a prior
run of this plan discovered `--strict` aborts on 3 pre-existing warnings in
`docs/superpowers/specs/2026-09-07-normtracker-document-detail-design.md`
and `docs/superpowers/specs/2026-09-07-normtracker-semantic-search-design.md`.
Those files use `[[repo/relative/path.md]]` wiki-link syntax (this
project's convention for informal cross-references between planning docs,
also used by the memory-writing skill), which Zensical tries and fails to
resolve as a real link. The target files exist; this isn't a broken link in
any meaningful sense, and fixing it would mean changing an unrelated
project-wide convention — out of scope here. (A related, *real* bug this
same investigation found — 32 broken anchor links in `docs/srs/README.md`
from unstripped German umlauts — was already fixed in a separate commit;
see `git log --oneline --grep="anchor links"` on this branch.) This is the
same reason Task 7's CI job below builds without `--strict` too.

- [ ] **Step 4: Re-run the Google Fonts and anchor checks from Tasks 1 and 3 against the final build**

```bash
grep -rl "fonts.googleapis.com\|fonts.gstatic.com" site/ || echo "OK: no Google Fonts reference"
grep -o "WorkRepository" site/reference/core/index.html
```

Expected: both checks still pass (regression check — a later task's
`nav`/config edits could theoretically have reintroduced a font reference or
broken the reference page).

- [ ] **Step 5: Commit**

```bash
git add docs/glossary.md zensical.toml
git commit -s -m "docs: add Glossary, complete site navigation"
```

---

### Task 7: CI job

**Files:**
- Modify: `.forgejo/workflows/ci.yml`

**Interfaces:**
- Consumes: the exact `zensical` version recorded in Task 1 Step 1.

- [ ] **Step 1: Add the `test-docs` job**

Add this job to `.forgejo/workflows/ci.yml`, following the same checkout
pattern as the existing jobs (`test-accounts`, `test-api`, `test-chat`,
`test-core`, `test-frontend` in that file):

```yaml
  test-docs:
    runs-on: stackit-docker
    container: python:3.12
    timeout-minutes: 30
    steps:
      - run: |
          (git --version >/dev/null 2>&1) || (apt-get update -qq && apt-get install -y -qq git)
          git init -q .
          git remote add origin "https://${GITHUB_TOKEN}@${GITHUB_SERVER_URL#https://}/${GITHUB_REPOSITORY}.git"
          git fetch -q --depth=1 origin "$GITHUB_SHA"
          git checkout -q FETCH_HEAD
      - run: apt-get update && apt-get install -y --no-install-recommends libgl1 && rm -rf /var/lib/apt/lists/*
      - run: pip install -e core -e api -e accounts -e chat "zensical==0.0.60" "mkdocstrings[python]"
      - run: zensical build
```

No `--strict` — see Task 6 Step 3 for why (3 pre-existing, unfixable-in-scope
wiki-link warnings in `docs/superpowers/specs/`).

`"mkdocstrings[python]"` is required in addition to `zensical` itself —
Task 5 discovered Task 1's original venv setup never installed it, and the
build fails outright ("mkdocstrings plugin is enabled, but mkdocstrings is
not installed") without it. This CI command already includes the fix;
don't drop it.

`0.0.60` was the latest release on PyPI as of 2026-09-11 (`pip index versions
zensical`) — Zensical is pre-1.0 and moves fast, so reconcile this against
whatever version Task 1 Step 1 actually installed (`pip show zensical`
there) and use that exact value instead if it differs; don't leave the job
unpinned either way, the other jobs in this file don't pin exact versions
but they also don't have a fast-moving pre-1.0 tool like Zensical as their
only content-generation step.

- [ ] **Step 2: Validate the YAML**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.forgejo/workflows/ci.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`, no exception.

- [ ] **Step 3: Re-run the exact CI commands locally to confirm they'd pass**

```bash
deactivate 2>/dev/null
rm -rf /tmp/normly-docs-ci-check && mkdir /tmp/normly-docs-ci-check
python3 -m venv /tmp/normly-docs-ci-check/venv
source /tmp/normly-docs-ci-check/venv/bin/activate
pip install -e core -e api -e accounts -e chat "zensical==0.0.60" "mkdocstrings[python]"  # match Task 1's actual version if different
zensical build
echo "exit code: $?"
deactivate
rm -rf /tmp/normly-docs-ci-check
```

Expected: exit code 0. This is the closest local approximation of what the
`stackit-docker` runner will do (a fresh environment, not the `.venv-docs`
used throughout this plan, which could be hiding a missing dependency that
happens to already be installed system-wide).

- [ ] **Step 4: Commit**

```bash
git add .forgejo/workflows/ci.yml
git commit -s -m "ci: add test-docs job building the Zensical site"
```

---

## After all tasks

This plan does not push to `main` or open a merge request — CLAUDE.md
forbids direct pushes to `main`, and pushing triggers the billed STACKIT
pipeline (confirm with the user first, per the standing project rule). Once
all 7 tasks are committed locally, stop and ask the user whether to push a
branch and open a merge request, or hold for further review.
