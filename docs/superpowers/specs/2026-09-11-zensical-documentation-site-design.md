# Design: Documentation site with Zensical

## Context

A working mkdocs + mkdocstrings + Material theme setup for the
code reference documentation already exists on the branch
`claude/normly-documentation-structure-3zs7i0` (commit `7f8a1ea`,
27.08.2026) — locally and on GitHub, but deliberately not merged. The branch
is about 27.9k lines behind current `main` (for example, it does not yet know
`frontend/tests/`) and, according to its own commit, was itself
incomplete (OpenAPI reference generation and the STACKIT/Forgejo
pipeline integration were missing).

In the meantime, the mkdocs-material team has announced [Zensical](https://zensical.org/)
as a successor project; Material for MkDocs has been in maintenance mode
since early 2026, and new feature work goes into Zensical. The
mkdocstrings author is part of the Zensical team; Zensical already supports
mkdocstrings. Zensical additionally has a compatibility layer
that reads existing `mkdocs.yml` configurations — but it is meant for the
migration of *existing* mkdocs projects. Since this is being built
from scratch, this project uses the native `zensical.toml` configuration instead of
the compatibility layer.

**Decision (already made, 01.09.2026):** The old branch is
not reactivated, merged or rebased. Instead, the
documentation site is built fresh against current `main` with Zensical.
The old branch serves only as a source of ideas and text.

`docs/adr/` and `docs/srs/` already hold current, maintained content
(one consolidated ADR document instead of numbered individual files as in the
old branch; the SRS chapters 01–06 individually). These do not need to be
rewritten, only hooked into the site navigation.

On the website (separate repo `normly-website`), the
"Documentation"/"API reference" links on the home page currently point to
placeholders — this project redeems these placeholders.

## Goal of this project

1. A static documentation site built with Zensical, with the same
   structure as the old branch: Home, Guide, Concepts, Architecture
   decisions, Requirements (SRS), code reference, glossary.
2. Guide and Concepts texts taken over from the old branch as the basis,
   but checked and corrected line by line against current `main` (README.md, CLAUDE.md,
   `docs/adr/README.md`).
3. `docs/adr/` and `docs/srs/` hooked into the nav unchanged.
4. Code reference generated via mkdocstrings from the docstrings of `core`, `api`,
   `accounts`, `chat` — one page per package, as in the old
   branch.
5. A new CI job (`test-docs` in `.forgejo/workflows/ci.yml`) that builds the
   site. **Addendum from the implementation:** `--strict` had to be
   dropped again — see "Why no `--strict`" further below.
6. A Dockerfile proposal marked as a draft and not wired into CI,
   as an appendix to this spec, for a later, standalone
   container/deployment sub-project.

## Non-goals

- **No container image, no registry push, no signing.** Currently no
  Dockerfile exists in the repo for any service — that would be
  infrastructure work that goes beyond this project and needs decisions of its own
  (base image, signing, versioning of the
  documentation state analogous to ADR-010). This project's CI job only builds
  and checks the site; it publishes nothing.
- **No multilingual support.** CLAUDE.md provides for it in the long term, but
  the site starts out monolingual German, like the old branch.
- **No OpenAPI reference rendering.** Was already follow-up work in the old branch
  and remains so.
- **No new ADR/SRS content.** Only linking of what exists.

## Architecture

A root-level `zensical.toml` with `docs_dir = "docs"`. This is deliberately
the same folder in which `docs/adr/` and `docs/srs/` already live — no
copying needed.

```
docs/
  index.md                    # new (basis: old branch, reviewed)
  guide/
    getting-started.md        # new (basis: old branch, reviewed)
    self-hosting.md           # new (basis: old branch, reviewed)
  concepts/
    norm-graph.md           # new (basis: old branch, reviewed)
    license-model.md           # new (basis: old branch, reviewed)
  reference/
    core.md                    # new, mkdocstrings stub: ::: normly_core
    api.md                     # new, mkdocstrings stub: ::: normly_api
    accounts.md                # new, mkdocstrings stub: ::: normly_accounts
    chat.md                    # new, mkdocstrings stub: ::: normly_chat
  glossary.md                 # new (basis: old branch, reviewed)
  adr/README.md               # already present, unchanged
  srs/*.md                    # already present, unchanged
  superpowers/                # already present, excluded from the nav
zensical.toml                 # new, root-level
```

`docs/superpowers/` (internal plans/specs, incl. this file) is not entered in
`nav`. Zensical currently has **no** exclude option (according to
its own compatibility list, `exclude_docs`, `not_in_nav` and
`draft_docs` are "not yet supported") — whether files not listed in `nav`
under `docs_dir` are built anyway and reachable under their path URL
is clarified in the first implementation task via a build probe.
If so: deliberately accepted, no workaround (e.g. narrowing `docs_dir` to a
subfolder and duplicating `adr/`/`srs/` there) — the entire
repository including `docs/superpowers/` is publicly viewable via STACKIT Git
anyway; an additional unlinked page on the documentation site
is no new data protection or confidentiality problem, only potentially
untidy. Becomes an issue only if it actually gets in the way.

### Code reference

One page per package with `show_submodules: true`, as in the old branch.
Following the known mkdocstrings Zensical format:

```toml
[project.plugins.mkdocstrings.handlers.python]
paths = ["core/src", "api/src", "accounts/src", "chat/src"]

[project.plugins.mkdocstrings.handlers.python.options]
show_submodules = true
show_source = true
docstring_style = "google"
```

No finer granularity (one page per module) — unnecessary complexity at the current
package size (YAGNI). Can be added later if
individual package pages become hard to navigate.

mkdocstrings' Python handler actually **imports** the modules in order to
extract docstrings (merely referencing the path is not enough). This
means all four packages must be installed at build time, together with
their runtime dependencies (SQLAlchemy, FastAPI, Docling,
sentence-transformers, …).

### Fonts: no Google Fonts

By default, the Material theme loads web fonts from Google Fonts — even
at build time a call to a US service, forbidden by CLAUDE.md ("No
US services for operations, **build**, data, secrets or deployment", wording at the time). The
exact theme key for switching this off is not verified at the time of this spec;
what is binding is the result, not the way there: the
built `site/` folder must contain **no** reference to `fonts.googleapis.com`
or `fonts.gstatic.com` (checked via grep, see the plan). Use a system
font stack — consistent with the frontend, which for the same
reason does not load Google Fonts either.

## Content in detail

| Page | Approach |
|---|---|
| `index.md` | Take over the text from the old branch, then check against `README.md`. **Must be corrected:** remove the GitHub link (`github.com/sn4kez/normly-app`) — ADR-019 freezes the GitHub facade, no new references to it. |
| `guide/getting-started.md` | Take over the text from the old branch, check against the current state. Stay honest: still no runnable version, no public access — keep the placeholder character where applicable. |
| `guide/self-hosting.md` | Take over the text from the old branch, check against the current Compose/deployment documentation (`ADR-010`). |
| `concepts/norm-graph.md` | Check against ADR-008 ("graph first") in `docs/adr/README.md`. |
| `concepts/license-model.md` | Check against ADR-002/-011/-014 and the current category table (A–D) from CLAUDE.md. |
| `glossary.md` | Take over the text from the old branch, check for new terms since 27.08. (e.g. Normtracker terms). |
| `adr/README.md`, `srs/*.md` | Unchanged, only enter them in `nav:`. |

## CI

A new job `test-docs` in `.forgejo/workflows/ci.yml`, analogous to the
existing jobs:

```yaml
test-docs:
  runs-on: stackit-docker
  container: python:3.12
  timeout-minutes: 30
  steps:
    - run: |
        # (checkout as in the other jobs)
    - run: apt-get update && apt-get install -y --no-install-recommends libgl1 && rm -rf /var/lib/apt/lists/*
    - run: pip install -e core -e api -e accounts -e chat zensical
    - run: zensical build
```

`libgl1` is needed because importing `normly_core` pulls in Docling
(see the `test-core` job).

The package name (`pip install zensical`) and command (`zensical build`) are
researched (see [zensical.org/docs/get-started](https://zensical.org/docs/get-started/)),
but not tested in this repo — the first implementation task
verifies this against the then-current Zensical version before the rest
of the project builds on it.

### Why no `--strict`

Originally planned, so that broken internal links and missing
docstring targets make the CI job fail instead of going unnoticed.
During implementation (Task 5/6) it turned out: `--strict` aborts with an
unhandled Python traceback as soon as any file under `docs_dir`
produces a warning — including files that are never in `nav` (according to its own
compatibility list, Zensical builds everything under `docs_dir` anyway, see
above). Two causes were found and assessed individually:

- **32 real, broken anchors in `docs/srs/README.md`** (German umlauts in the
  anchor fragment, which Zensical's slugification removes — e.g. the
  heading „…WCAG-Konformität" (i.e. WCAG conformance) produces the ID `...wcag-konformitat`, not
  `...wcag-konformität`). This was a real, pre-existing bug in the
  requirements index, independent of this project — fixed in a
  separate commit (`fix(srs): strip diacritics from requirement anchor
  links`), 32 targeted replacements, titles/text untouched.
- **3 unresolvable false alarms in `docs/superpowers/specs/*.md`** — these
  files use `[[repo/path.md]]` wikilink notation for loose cross-references
  between planning documents (the same convention as in the memory system),
  never intended as a real hyperlink. The target files exist; Zensical
  nevertheless tries to resolve `[[...]]` as a link and fails at the
  path resolution. Fixing that would mean changing a project-wide convention
  independent of this project — out of scope.

With the 32 real errors fixed, but the 3 false alarms still
present, `--strict` stays permanently red. Human decision: no
`--strict`; instead, targeted grep/anchor checks for the new pages
(already part of every single content task in the plan).

## Error handling

- A green `zensical build` (without `--strict`) in CI is the check that
  the site builds at all. The individual content tasks in the plan additionally run
  targeted checks (grep for expected content, anchor resolution against the
  actually built pages) — this covers broken links in new content
  without failing on the 3 pre-existing false alarms.
- No linting of prose content (spelling or similar) — out of
  scope.

## Appendix: Dockerfile draft (not part of this project)

An unverified proposal for a later, standalone
container/deployment sub-project. Not built, not tested, not wired into
CI — serves only as a starting point for this follow-up work.

```dockerfile
# DRAFT -- not verified, not wired into CI.
# Follow-up work: clarify base image choice, signing, versioning (ADR-010).

FROM python:3.12-slim AS build
WORKDIR /site
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 \
    && rm -rf /var/lib/apt/lists/*
COPY core api accounts chat docs zensical.toml .
RUN pip install --no-cache-dir -e core -e api -e accounts -e chat zensical \
    && zensical build --site-dir /site/dist

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY --from=build /site/dist /usr/share/nginx/html
```

DRAFT note: `--site-dir` does not exist in Zensical 0.0.60 —
set the output directory via `site_dir` in zensical.toml instead, or
move the default output after the build.

Open questions for the follow-up task: obtain the base image via a STACKIT-owned
mirror instead of Docker Hub (the nginxinc image lives on Docker Hub
— a US service, against CLAUDE.md), image signing, push target in the STACKIT
Container Registry, versioning of the documentation state.
