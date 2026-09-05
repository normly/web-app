# CI/CD-Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Forgejo Actions pipeline (`.forgejo/workflows/ci.yml`) on the
STACKIT Git instance that runs all five packages' test suites on every push
and pull request, verified against a real pipeline run — not just written
and hoped to work.

**Architecture:** One workflow file, five independent jobs (one per
package: `accounts`, `api`, `chat`, `core`, `frontend`), each running in a
plain `python:3.12` or `node:20` container with shell (`run:`) steps only —
no GitHub-Actions-marketplace `uses:` steps, since those fetch from
github.com by default and this project may not run build steps outside
STACKIT infrastructure. Verification happens against the real STACKIT Git
instance via its REST API (Swagger-documented, confirmed reachable
unauthenticated for the schema itself) using the Personal Access Token
already stored in this machine's git credential store for the `stackit`
remote.

**Tech Stack:** Forgejo Actions (GitHub-Actions-compatible YAML syntax),
`python:3.12` / `node:20` container images, `curl` + the Forgejo REST API
for verification.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-02-ci-pipeline-design.md` —
  every task below implements a specific section of it.
- **No `uses:` steps anywhere in the workflow.** Every step is `run:` shell
  inside a `container:`-pinned image. This is the spec's central compliance
  decision (avoiding a US-hosted marketplace-action fetch at pipeline
  runtime) — do not add a `uses:` step "just this once," even for
  checkout; Forgejo Actions checks out the repo implicitly.
- Repo under test: **owner `jwokittel`, repo `normly-webapp`**, on the
  STACKIT Git instance `https://normly.git.onstackit.cloud`. Local git
  remote name: `stackit` (already configured, pushed once already —
  `git remote -v` will show it). REST API base:
  `https://normly.git.onstackit.cloud/api/v1`.
- **Authentication for API calls:** a Personal Access Token is already
  stored in this machine's git credential store
  (`git config credential.https://normly.git.onstackit.cloud.helper` is set
  to `store`, backing file typically `~/.git-credentials`) for HTTPS
  operations against the `stackit` remote. The same PAT works for the
  Forgejo REST API via an `Authorization: token <PAT>` header. **Never**
  print the token to stdout/stderr, a commit, a report file, or any log —
  extract it inline into the `curl` command (e.g. via command
  substitution reading `~/.git-credentials`) and use it only in the header.
  **Never run `git config` yourself** to set up or change this credential
  store — it is already configured; if for any reason it is missing or a
  `curl` call gets a 401, stop and report BLOCKED rather than trying to
  configure git credentials yourself.
- **Never `git push --force` to `stackit` or `origin`, never modify branch
  protection or repo settings via the API** — this plan's tasks only add
  files and push normal branches/commits. Repo-settings changes (push
  mirror, branch protection) are explicitly out of this plan's scope, see
  "After This Plan" at the end.
- Every commit needs a real DCO trailer: `Signed-off-by: normly <anonymous-jw@pm.me>`.
- Docker-in-Docker is available on the registered runner (confirmed by the
  project owner) — the four Python packages' test suites depend on it
  (`testcontainers[postgres]`) and this plan does not need to work around
  its absence.

---

### Task 1: Write and verify `.forgejo/workflows/ci.yml`

**Files:**
- Create: `.forgejo/workflows/ci.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a working CI pipeline on `stackit`'s `main` branch. Nothing
  downstream in this codebase consumes this file programmatically — it is
  the deliverable itself.

**Runner label — already discovered, use verbatim:** `stackit-docker`.
(Confirmed via `GET /repos/jwokittel/normly-webapp/actions/runners?visible=true`,
which returned one runner, `stackit-runner`, with labels
`stackit-busybox`, `stackit-corretto-21`, `stackit-docker`, `stackit-ubuntu-20`,
`stackit-ubuntu-22`, `stackit-alpine`, `stackit-alpine-bash` — `stackit-docker`
is the Docker-capable one the Python jobs need for `testcontainers`. Note:
that query reported the runner's `status` as `"offline"` — this may just
mean idle-between-jobs, or may mean the runner genuinely isn't picking up
work right now. If Step 4 below shows a run stuck in `"queued"` and never
progressing, this offline status is the likely cause — report BLOCKED
rather than guessing at a fix, since restarting/reconfiguring the runner
itself is infrastructure the project owner controls, not something in this
repo.)

- [ ] **Step 1: Write the workflow file**

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:

jobs:
  test-accounts:
    runs-on: stackit-docker
    container: python:3.12
    steps:
      - run: cd accounts && pip install -e .[dev] && pytest

  test-api:
    runs-on: stackit-docker
    container: python:3.12
    steps:
      - run: cd api && pip install -e .[dev] && pytest

  test-chat:
    runs-on: stackit-docker
    container: python:3.12
    steps:
      - run: cd chat && pip install -e .[dev] && pytest

  test-core:
    runs-on: stackit-docker
    container: python:3.12
    steps:
      - run: cd core && pip install -e .[dev] && pytest

  test-frontend:
    runs-on: stackit-docker
    container: node:20
    steps:
      - run: cd frontend && npm ci && npm test
```

- [ ] **Step 2: Commit to a test branch, not `main`**

```bash
git checkout -b ci/pipeline-smoke-test
git add .forgejo/workflows/ci.yml
git commit -m "ci: add Forgejo Actions pipeline for all five packages

Signed-off-by: normly <anonymous-jw@pm.me>"
```

- [ ] **Step 3: Push the branch to `stackit` and capture the trigger time**

```bash
date -u +%Y-%m-%dT%H:%M:%SZ   # note this timestamp
git push stackit ci/pipeline-smoke-test
```

The `push:` trigger (no branch filter) fires on this push — no PR needed to
trigger a run, though Step 6 below opens one anyway to prove the
`pull_request` trigger too.

- [ ] **Step 4: Poll for the triggered run**

```bash
curl -s -H "Authorization: token $(git credential fill <<< $'protocol=https\nhost=normly.git.onstackit.cloud\n' | awk -F= '/^password=/{print $2}')" \
  "https://normly.git.onstackit.cloud/api/v1/repos/jwokittel/normly-webapp/actions/runs?limit=5" \
  | python3 -m json.tool
```

Find the run whose `head_branch` is `ci/pipeline-smoke-test` and whose
`created_at`/`run_started_at` is at or after the timestamp from Step 3 (not
an older run). Note its `id` and `status`.

If `status` is `"queued"` or `"in_progress"`, wait 15 seconds and re-run
this query — repeat up to 20 times (5 minutes total). If it never leaves
`"queued"`, the runner (`stackit-runner`, reported `"offline"` when its
labels were checked, see above) may not be picking up jobs right now;
**stop and report BLOCKED** with the run's JSON, do not guess a different
label without evidence.

- [ ] **Step 5: Inspect the completed run**

```bash
curl -s -H "Authorization: token $(git credential fill <<< $'protocol=https\nhost=normly.git.onstackit.cloud\n' | awk -F= '/^password=/{print $2}')" \
  "https://normly.git.onstackit.cloud/api/v1/repos/jwokittel/normly-webapp/actions/runs/<RUN_ID>" \
  | python3 -m json.tool
```

(Replace `<RUN_ID>` with the id from Step 4.) Expected: `"status": "success"`
covering all five jobs. If any job's conclusion is `"failure"`, you have no
browser access to read logs via the Forgejo UI — instead call
`GET /repos/jwokittel/normly-webapp/actions/tasks` (same auth header
pattern) to list individual task runs, whose entries link to their logs.
More directly, diagnose from the failure category:

- A `container:` or implicit-checkout syntax error (job fails immediately,
  before your `run:` step's own output ever appears) — this is the
  spec's flagged unverified assumption ("Illustrativ" in the design doc).
  Adjust the YAML to whatever the runner's Forgejo version actually
  expects (check the Forgejo version via
  `curl -s https://normly.git.onstackit.cloud/api/v1/version`, then compare
  against that version's Actions docs) and re-push the same branch (Step 3
  again, same branch name — this triggers a new run without opening a new
  PR).
- A real test failure inside a package (the job's `run:` step executed but
  `pytest`/`npm test` exited non-zero) — this is a **pre-existing test
  failure in that package**, not a pipeline bug. Do not modify the
  package's source or tests to force it green. **Stop and report
  DONE_WITH_CONCERNS**, naming exactly which package and the failure
  output, so the controller can decide whether to fix the underlying test
  or accept it as a known-broken baseline to fix separately.

Allow up to 3 push-and-recheck cycles for YAML/syntax issues (the first
category above). If still not green after 3 cycles, **stop and report
BLOCKED** with the last run's full JSON and the exact YAML you tried.

- [ ] **Step 6: Open a pull request to prove the `pull_request` trigger**

```bash
curl -s -X POST -H "Authorization: token $(git credential fill <<< $'protocol=https\nhost=normly.git.onstackit.cloud\n' | awk -F= '/^password=/{print $2}')" \
  -H "Content-Type: application/json" \
  -d '{"title":"ci: add Forgejo Actions pipeline","head":"ci/pipeline-smoke-test","base":"main"}' \
  "https://normly.git.onstackit.cloud/api/v1/repos/jwokittel/normly-webapp/pulls" \
  | python3 -m json.tool
```

Note the returned PR `number`. Repeat the polling from Step 4, this time
looking for a run with `"event": "pull_request"` referencing this PR — confirm
it also reaches `"status": "success"` across all five jobs (should reuse the
same, by-now-fixed YAML, so this is a confirmation, not expected to need
further fixes).

- [ ] **Step 7: Merge the verified workflow into `main`**

```bash
curl -s -X POST -H "Authorization: token $(git credential fill <<< $'protocol=https\nhost=normly.git.onstackit.cloud\n' | awk -F= '/^password=/{print $2}')" \
  "https://normly.git.onstackit.cloud/api/v1/repos/jwokittel/normly-webapp/pulls/<PR_NUMBER>/merge" \
  -H "Content-Type: application/json" \
  -d '{"Do":"merge"}'
```

(Replace `<PR_NUMBER>` with the number from Step 6.) Then update your local
`main` and this local checkout's own `main` to match:

```bash
git checkout main
git pull stackit main
```

- [ ] **Step 8: Confirm `main` itself is green**

Repeat Step 4/5's polling, this time for the run triggered by the merge
commit landing on `main` (event `"push"`, `head_branch` `"main"`). Confirm
`"status": "success"`.

---

## After This Plan (not part of it — manual, requires the project owner)

**Superseded 2026-09-05 (ADR-019):** the push-mirror step below is dropped —
GitHub is no longer an active target for anything going forward. The
existing `Sn4kez/normly-app` GitHub repo is left as-is (historical snapshot,
last synced by hand), but nothing should set up automated mirroring to it.
Only the branch-protection step remains:

1. **Branch protection on `main`**: after this plan's Task 1 is fully
   complete and merged — require pull requests, forbid direct pushes, mark
   only the four green checks (`test-accounts`, `test-api`, `test-chat`,
   `test-frontend`) as required. **Do NOT mark `test-core` as required** —
   it is deliberately, permanently red until the Docling cold-start
   title-extraction gap (see the design spec's "Offene Punkte") is fixed as
   its own follow-up task. Neither is a code change, so this
   isn't a plan task — an agentic worker cannot complete it (requires a
   logged-in browser session on `normly.git.onstackit.cloud`, and per this
   plan's Global Constraints, no task here touches repo settings or
   credentials via the API).
