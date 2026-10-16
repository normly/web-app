# Design: CI/CD pipeline (test execution as a merge gate)

**Addendum 2026-09-05 (ADR-019):** The STACKIT→GitHub push mirror that
this spec describes below as a goal/architecture/activation step will
**not** be set up — GitHub is dropped as a target for any future
automation. The affected sections remain below to keep the basis for the
decision at the time traceable, but are to be read as superseded; see
ADR-019 for the rationale.

## Context

REQ-BUILD-002 requires STACKIT Pipelines (Forgejo Actions) as build/test
infrastructure, REQ-BUILD-003 requires automated quality assurance as a
merge precondition, REQ-GIT-004 requires a successful pipeline as a
condition for every merge request. So far the repository contains **no**
CI configuration — each of the five packages (`accounts`, `api`, `chat`, `core`,
Python; `frontend`, Next.js) has its own locally running test suite, but
nothing runs them automatically. Several earlier design documents
(`2026-08-30-docling-migration-design.md`, "Open items") already name this
as a gap: the only automated proof of the
"no runtime network access to model sources" requirement runs nowhere,
for lack of CI.

Chosen in consultation with the owner over two alternatives
(REQ-PIPE-007 identity resolution review interface; another
BAuA follow-up task) — as the most broadly load-bearing gap: it affects
every package and every future merge, not just a single source or
a single use case.

**Precondition, newly created during this design:** Until this
point, no reachable STACKIT Git/Forgejo instance existed for this
project — only the GitHub mirror (`origin`). During the brainstorming
session the owner created an organization and a repository
(`https://normly.git.onstackit.cloud/jwokittel/normly-webapp`,
set up locally as the remote `stackit`, HTTPS with a personal access token
via a credential helper — SSH on port 22 to this instance is not reachable
from the development environment, although SSH to GitHub and HTTPS to the
instance work; presumably the managed Forgejo offering provides no
public Git-over-SSH access, the official STACKIT docs only show
HTTPS clone examples). According to the owner, a runner for Forgejo Actions is
already registered. For details see the `reference_stackit_git` note.

**REQ-GIT-001/002 are therefore currently not fulfilled** — STACKIT Git is not
yet the primary platform (both remotes are currently pushed to independently by
hand, no automatic mirror in either direction). At the
owner's explicit request, this sub-project already catches up on the
central technical part of it here: an automated
push mirror from STACKIT Git (primary) to GitHub (contribution facade) after
every merge — the concrete acceptance criterion from REQ-GIT-002. What of it
is deliberately *not* done along with it is listed under Non-goals.

## Goal of this sub-project

- A Forgejo Actions pipeline (`.forgejo/workflows/ci.yml`) that runs the
  test suites of all five packages on every pull request against `main`
  and on every push.
- Each package as its own, independent job — its own status per package in
  the MR view; one failure does not block the feedback of the others.
- Verified live against the new STACKIT instance (test branch, real
  pipeline run) — not just YAML written "blind".
- Documented instructions for the one-time activation of branch protection on
  `main`, so that the pipeline actually becomes the merge gate (REQ-GIT-004).
- An automated push mirror from STACKIT Git to GitHub, so that
  STACKIT Git keeps the GitHub mirror up to date on its own after every merge
  to `main` (REQ-GIT-001/002) — no more manual double pushing as
  during this brainstorming session.

## Non-goals

- **No contribution facade automation and no DCO check on the
  GitHub side** (part of REQ-GIT-002, but not its mirror
  acceptance criterion). The path "external pull request on GitHub → lands
  checked in the STACKIT pipeline" (REQ-GIT-002 acceptance test, wording at the time) remains
  open — this sub-project only builds the *outgoing* mirroring
  STACKIT→GitHub, not the return path for incoming external contributions.
  A separate, later task.
- **No linting, no security scanning.** REQ-BUILD-003 requires both,
  but currently no package has a linter or scanning tool configured.
  Choosing tools and cleaning up existing violations are separate
  decisions that should not be made in passing while wiring up the pipeline
  (deliberately decided this way with the owner). Follow-up task.
- **No Playwright E2E tests in this pipeline.** They would need a
  running application including a database and browser binaries — a much
  heavier setup than the existing unit/integration tests. Only
  `npm test` (Vitest) runs for `frontend`.
- **No Docker image build, no shipping.** Not a single
  `Dockerfile` exists in the repository yet — REQ-DIST-004 (signed,
  versioned images) is a separate, downstream sub-project that
  first needs Dockerfiles per service.
- **No dependency caching in v1.** Marketplace actions such as
  `actions/cache@vX` fetch their own code from GitHub by default
  — the same category of risk as described below under "Architecture".
  Whether the STACKIT instance operates an Actions marketplace mirror
  was not checked. Until that is settled, every
  pipeline run remains a cold dependency install — correct, but slow
  (especially `core` with Docling/Torch, approx. 5.6 GB of installed
  dependencies). Optimization is a later, deliberately downstream
  task.
- **No automated branch protection configuration.** Activating it
  (pull request requirement, required status checks) is a one-time click in
  the Forgejo repo settings, not a recurring process — it is documented as
  instructions, not built as automation.

## Architecture

### Decision: no GitHub Actions marketplace actions

Forgejo Actions is largely GitHub Actions compatible (`uses: owner/repo@ref`
works syntactically identically) — which is exactly what makes it risky for the
"No US services for operations" requirement from CLAUDE.md: `uses: actions/checkout@v4`
fetches the referenced code from `github.com` at runtime by default,
unless the Forgejo instance operates its own Actions mirror/proxy.
Whether STACKIT's managed Forgejo offering does so was not checked for this
design (no login possible, no documentation on it
found). Instead of silently assuming it, this pipeline does without
`uses:` steps entirely: every job runs in a given
container image (`python:3.12` or `node:20`) and consists exclusively
of `run:` shell steps (`git checkout` is implicitly present in Forgejo Actions
anyway, no separate checkout step needed — to be verified
on the first real run, see Test concept). The only remaining
runtime network is PyPI/npm — already an accepted part of every
build today, no new category.

### Jobs

Five independent jobs in one file, `.forgejo/workflows/ci.yml`:

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:

jobs:
  test-accounts:
    runs-on: docker  # check the label against the real runner registration, see Open items
    container: python:3.12
    steps:
      - run: cd accounts && pip install -e .[dev] && pytest

  test-api:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd api && pip install -e .[dev] && pytest

  test-chat:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd chat && pip install -e .[dev] && pytest

  test-core:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd core && pip install -e .[dev] && pytest

  test-frontend:
    runs-on: docker
    container: node:20
    steps:
      - run: cd frontend && npm ci && npm test
```

(Illustrative — the exact syntax for the implicit checkout and the
`container:` keyword is verified against the instance on the first real run,
see Test concept; if Forgejo Actions deviates from the
GitHub Actions syntax here, the YAML is adjusted accordingly, without
touching the architecture decision "no marketplace actions".)

### STACKIT Git as the primary platform: push mirror to GitHub

REQ-GIT-002's acceptance criterion "automated push mirror after every
merge" (wording at the time) needs **no** Forgejo Actions job. Forgejo offers a
built-in repo feature for this: under Settings → Repository → Mirror Settings →
Push Mirror, a target repository (the GitHub URL) can be stored together with
credentials (a GitHub personal access token with write permission only on
this repo). Verified against the Forgejo documentation:
Forgejo then synchronizes automatically on every push to the
STACKIT repo, not just on a time interval — exactly the required
behavior, without any pipeline logic of our own. The token is held by Forgejo's
own credential management and appears nowhere in the repository or
in `ci.yml` — consistent with REQ-INST-003 ("Credentials and key material are held exclusively in the
STACKIT Secrets Manager").

In practice this means: from the setup of this mirror onwards, `main` on STACKIT Git
becomes the only place where merging actually has to happen —
from then on GitHub `main` is written exclusively via the mirror, never again
pushed by hand (the direct GitHub push during this session was a
deliberate, one-time exception before this mirror was set up, see
the conversation history, not the future normal case).

### Precondition: Docker-in-Docker on the runner

All four Python packages use `testcontainers[postgres]` — the tests
start a real Postgres container themselves. The registered runner
must therefore have access to a Docker daemon (confirmed by the
owner). Without it, every Python job fails at the first
`testcontainers` call — a clear, immediately visible error, not a
special case that this pipeline would have to handle separately.

## Components

| File | Change |
|---|---|
| `.forgejo/workflows/ci.yml` | **New.** Five jobs as described above. |

No further files — this pipeline only runs already
existing test commands, without changing existing code.

## Data flow

Push or pull request against `main` on the STACKIT instance → Forgejo
Actions triggers `ci.yml` → five jobs start in parallel on the registered
runner, each in its own container → each job installs its
package fresh (`pip install -e .[dev]` or `npm ci`) and runs its
test suite → success/failure of each job appears as its own status
check on the pull request.

## Error handling

- A failing package only blocks its own status check — the
  other four jobs run through independently (no `needs:` chaining
  between them, since the packages have no build-order dependency
  on one another that the pipeline would have to model).
- Missing Docker access on the runner shows up as an immediate,
  unambiguous `testcontainers` error in the four affected Python jobs —
  no separate handling needed; this is an infrastructure
  precondition error, not a pipeline logic error.

## Test concept

- After writing the `ci.yml`: push a test branch to the STACKIT instance,
  open a merge request against `main` there, observe the real
  pipeline run. That is the actual proof — not just
  that the YAML syntax looks plausible, but that it actually runs on the
  concrete runner (container start, implicit checkout,
  `testcontainers` Postgres start, all five test suites green).
- Deliberately only a smoke test run with unchanged code at first (all
  suites should be green, see the last known state: 250 passed, 1
  skipped in `core`, correspondingly for the other packages) — no
  artificial failure case needed to show that a red job turns the
  overall status red: that is standard Forgejo Actions behavior, not a
  self-built feature of this pipeline.

## Relation to requirements and ADRs

| Requirement | Relation |
|---|---|
| REQ-BUILD-002 | Pipeline runs on STACKIT Pipelines (Forgejo Actions), no US SaaS CI, no fetching of marketplace actions from GitHub at runtime. |
| REQ-BUILD-003 | Failed tests prevent the merge (after branch protection is activated) — the linting/security part is deliberately postponed as a follow-up task, see Non-goals. |
| REQ-GIT-004 | Only becomes *fulfillable* through this pipeline (technical precondition); the actual enforcement (merge blocking on red status) is the documented manual activation step below. |
| REQ-GIT-001 | Fulfilled — with this pipeline, STACKIT Git is the primary platform for build/test. |
| REQ-GIT-002 | **Dropped (ADR-019, 2026-09-05).** Push mirror will not be set up; no more GitHub as a contribution facade. Requirement in `docs/srs/03-requirements.md` marked as superseded accordingly. |
| REQ-INST-002, REQ-DIST-004 | Not affected — no deployment, no image build in this sub-project. |

## Activation steps after implementation (manual, one-time)

**Superseded by ADR-019 (2026-09-05):** Step 1 (push mirror) is dropped —
GitHub is no longer written to automatically. Only one
repo setting on STACKIT Git remains open:

1. **Branch protection for `main`** — pull request required, direct pushes
   prevented, **only the four green checks** (`test-accounts`, `test-api`,
   `test-chat`, `test-frontend`) marked as required checks. **`test-core`
   deliberately NOT as a required check** as long as the Docling cold-start
   malfunction documented further below is not fixed — see "Open items".
   Only then is REQ-GIT-004 actually enforced, not just technically
   possible. Should only be done after the pipeline (Test concept)
   demonstrably runs green (except for the accepted `test-core`) — otherwise
   our own first merge blocks itself.

## Open items / follow-up work

- **Exact runner label unclear.** `runs-on: docker` above is a
  placeholder — which label the registered runner actually carries
  becomes visible on the first real pipeline run (or the owner
  can look it up beforehand in the runner settings) and is corrected before the
  final commit.
- **Actions marketplace mirror status unclear.** If it turns out
  that the STACKIT instance does operate its own mirror/proxy for
  common actions, this decision (no `uses:`) can be deliberately relaxed in a
  later iteration — not in this pass,
  as it is unverified.
- ~~**External contribution intake via GitHub**~~ — **obsolete (ADR-019).**
  REQ-GIT-002 is dropped; no contribution facade on GitHub planned anymore.
- **Linting, security scanning, dependency caching, Docker image build,
  Playwright E2E** — all deliberately postponed, see Non-goals for each.
- **`test-core` turns red on every run and is deliberately accepted (not
  hidden, ignored or skipped).** Reason: Docling's DGUV/BAuA
  title detection (`raw_title` becomes `None` instead of the real title) is fragile
  with respect to a *fresh* HuggingFace model download — reproducible
  via `docker run python:3.12` with a completely fresh pip installation and
  no prebuilt model cache. Tests pass locally in this
  project's working copy only because this checkout has cached HF models from
  earlier work, so a real cold-start extraction is never
  actually exercised. Any truly fresh environment (new dev machine,
  rebuilt CI runner, fresh production container) will
  probably hit the same failure. The fix is a separate
  follow-up task (debug Docling model version sensitivity in `DguvAdapter` /
  `BauaAdapter`), not part of this CI sub-project. `test-core`
  is deliberately kept visible/red and is *not* marked as a required
  branch protection check until this has been investigated and fixed separately.
  **Addendum 2026-10-08: clarified and fixed.** The cause was not the
  model version but missing system fonts in the container: the
  fixture does not embed Helvetica, pdfium renders the page for the
  layout model with a fallback font, and the model classifies the
  title line as `page_header` (FURNITURE). `fonts-liberation` in the
  `test-core` job and in the Python image fixes it; proof and
  single-variable tests in the TP2 spec
  (`2026-10-08-tp2-image-pipeline-design.md`, follow-up work).
- **`tests/test_structural_end_to_end.py` in `chat` is excluded from CI
  (not faulty, but its fixture dependency is incompatible with CI).** These
  4 tests spawn sibling packages (`api`, `accounts`) via their local
  dev-only `.venv/bin/uvicorn` convention (see
  `chat/tests/conftest.py:98-121`), which does not exist in the fresh CI container
  (no per-package venvs are built there, only a fresh
  pip installation). Follow-up task: abstract the fixture setup to
  support CI-native alternatives (e.g. passing a TestClient instead of process
  spawning).
- **Fixed (2026-09-05, final whole-branch review):** `on: push:` had
  no branch filter — a push to a branch with an open pull request
  thereby triggered both a `push` and a `pull_request` run at the same time on
  the same shared runner (empirically confirmed as the cause of a
  `test-chat` failure through resource contention, not a real
  regression). Now `push: branches: [main]` — a feature branch
  only triggers the `pull_request` run. In addition, `timeout-minutes: 30`
  on every job, so that a hanging job does not block the entire runner capacity
  until the runner's default timeout.
