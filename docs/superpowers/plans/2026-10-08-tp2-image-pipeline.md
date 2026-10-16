# Image pipeline (TP2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The five container images are built reproducibly in GitHub Actions, signed keyless with cosign and published with version tags to `ghcr.io/normly/web-app/...`; `docker compose up -d` pulls them instead of building.

**Architecture:** A uv workspace in the repo root with one `uv.lock` replaces the four separate `pip install -e` environments. `docker/python.Dockerfile` gets the stages `deps` (locked third-party dependencies) → `weights` (model weights at a fixed revision) → `base` (both plus `core`) → `api`/`chat`/`accounts`/`pipeline`. A `docker-bake.hcl` is the build definition for the CI; `compose.yaml` keeps its `build:` blocks but points to the GHCR names. The workflow `.github/workflows/images.yml` builds on push to `main`, on tags `v*` and manually, pushes with a registry cache, generates provenance and SBOM and signs every digest.

**Tech Stack:** uv 0.12.23, Docker Buildx Bake (HCL), `python:3.12-slim` and `node:22-alpine` by digest, `huggingface_hub.snapshot_download`, cosign 2.x via cosign-installer@v3 (keyless, Sigstore), GitHub Actions (`actions/checkout`, `docker/setup-buildx-action`, `docker/login-action`, `sigstore/cosign-installer`), Zensical for the docs.

Spec: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`. Roadmap: `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`. Predecessor plan (Dockerfile structure, Compose profiles): `docs/superpowers/plans/2026-10-04-tp1-containerisation.md`.

## Global Constraints

- License header in every new source file: `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# Copyright (C) 2026 normly contributors` (Dockerfile, Compose, HCL, YAML, shell, Python as a `#` comment).
- Commits: Conventional Commits, English, `git commit -s` (Signed-off-by of the human) plus the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No push to `main`. **Every push to GitHub triggers a workflow and is agreed with the owner beforehand.**
- No secrets in the repo, not even in `.env.example`, workflows or tests. Signing without a key of our own (D1).
- One version for all five images; the Git tag `vX.Y.Z` is the single source (D2). First release tag `v0.1.0`.
- Image build only on push to `main`, tags `v*` and `workflow_dispatch`, never on pull requests (D3).
- Only `linux/amd64`.
- Model revisions are defined exclusively as `ARG` defaults in `docker/python.Dockerfile` (one place). Values, determined 2026-10-08 via the Hugging Face API:
  - `intfloat/multilingual-e5-large` → `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` (main, 2026-04-02)
  - `docling-project/docling-layout-heron` → `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` (main, 2026-02-09)
  - `docling-project/docling-layout-heron-onnx` → `40bde044036bb181c130ddf6c51792187268748f` (main, 2026-03-31)
  - `docling-project/docling-models` → `fc0f2d45e2218ea24bce5045f58a389aed16dc23` (tag v2.3.0, 2025-07-23)
- Base image digests, determined 2026-10-08 with `docker buildx imagetools inspect`:
  - `python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f`
  - `node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402`
  - `ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21`
- At runtime, no container contacts huggingface.co; the images set `HF_HUB_OFFLINE=1`.
- All containers run as the user `normly` (UID/GID 10001), as in TP1.
- `docs/superpowers/`, `docs/adr/`, `docs/srs/`, CLAUDE.md stay German; `docs/guide/`, README, CONTRIBUTING are English.
- The CI docs job expects exactly `3 issues found` from the Zensical build; new docs must not create new link issues.
- The known red `test-core` job (DGUV cold-start download) is not part of this plan and stays red.

---

## Way of working

- Branch `feat/tp2-image-pipeline` from `main` (state after the merge of PR #12, commit `742a989` or newer), its own worktree.
- Build and test locally; Docker Engine with Buildx is available (`docker buildx version` → v0.37). The first local build downloads about 2.5 GB of model weights and installs Torch, Docling and the like — 10 to 20 minutes, once.
- The live verification (Task 8) runs only after the PR is merged and needs the owner's yes for each step.

---

## File structure

| File | Purpose | Task |
|---|---|---|
| `pyproject.toml` (new, root) | uv workspace anchor, sources for `normly-core` and the Torch index | 1 |
| `uv.lock` (new) | lock file of all four Python packages | 1 |
| `api/pyproject.toml`, `chat/pyproject.toml`, `accounts/pyproject.toml` | shorten the comment on the `normly-core` resolution | 1 |
| `chat/tests/conftest.py` | start the sibling services from the shared environment | 1 |
| `CONTRIBUTING.md` | section "Development setup" with uv | 1 |
| `.github/workflows/ci.yml` | Python jobs on `uv sync --locked` | 2 |
| `docker/python.Dockerfile` | stages `deps`/`weights`/`base`, uv, digest pins, revisions | 3 |
| `frontend/Dockerfile` | digest pin | 3 |
| `core/src/normly_core/pipeline/docling_extraction.py`, `core/tests/pipeline/test_docling_offline.py` | docstring/skip text on the new model source | 3 |
| `docker-bake.hcl` (new) | build definition of the CI | 4 |
| `compose.yaml`, `.env.example` | GHCR image names, `NORMLY_IMAGE_TAG` | 4 |
| `.github/workflows/images.yml` (new) | build, push, cache, attestation, signing | 5 |
| `docs/adr/README.md` | ADR-023 | 6 |
| `docs/srs/03-requirements.md` | references REQ-BUILD-001, REQ-DIST-004, REQ-GIT-005 | 6 |
| `docs/guide/self-hosting.md`, `docs/guide/releasing.md` (new), `zensical.toml`, `README.md` | pull route, signature verification, release procedure | 7 |
| `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md` | TP2 reference | 7 |
| `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md` | verification results | 8 |

---

### Task 1: uv workspace and lock file

**Files:**
- Create: `pyproject.toml` (repo root), `uv.lock`
- Modify: `api/pyproject.toml:7-15`, `chat/pyproject.toml:7-10`, `accounts/pyproject.toml:7-10`, `chat/tests/conftest.py:98-121`, `CONTRIBUTING.md` (before `## Process`)

**Interfaces:**
- Produces: `uv.lock` in the root; `uv sync --locked --all-packages --all-extras` sets up `.venv` in the root with all four packages. Task 2 and Task 3 rely on exactly this lock file and the workspace names `normly-core`, `normly-api`, `normly-chat`, `normly-accounts`.

- [ ] **Step 1: Install uv and check the version**

```bash
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Expected: `uv 0.12.23`

- [ ] **Step 2: Create the root `pyproject.toml`**

```toml
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# uv workspace root. This file is not a package: it only ties the four
# Python packages together so that one `uv.lock` pins every dependency of
# all of them (REQ-BUILD-001, ADR-023). `normly-core` is resolved from the
# checkout, never from an index; torch and torchvision come only from the
# CPU wheel index (no CUDA builds, no other package may be served from it).

[tool.uv.workspace]
members = ["core", "api", "chat", "accounts"]

[tool.uv.sources]
normly-core = { workspace = true }
torch = { index = "pytorch-cpu" }
torchvision = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

- [ ] **Step 3: Generate the lock file**

```bash
uv lock
ls -la uv.lock && grep -c '^\[\[package\]\]' uv.lock
grep -A3 'name = "torch"' uv.lock | head -8
```

Expected: `uv.lock` exists, several hundred packages; the `torch` entry shows `source = { registry = "https://download.pytorch.org/whl/cpu" }` and wheel names with `+cpu`.

If `uv lock` fails because of missing wheels for a platform (message "no wheels for platform …"), add this to the root `pyproject.toml` under `[tool.uv]` and lock again:

```toml
[tool.uv]
environments = ["sys_platform == 'linux'", "sys_platform == 'darwin'"]
```

- [ ] **Step 4: Set up the shared environment and import all packages**

```bash
uv sync --locked --all-packages --all-extras
.venv/bin/python -c "import normly_core, normly_api, normly_chat, normly_accounts, torch; print(torch.__version__, torch.cuda.is_available())"
```

Expected: version with the suffix `+cpu`, `False`.

- [ ] **Step 5: Shorten the comments in the three service `pyproject.toml` files**

In `api/pyproject.toml`, replace the comment block above `"normly-core>=0.1.0,<0.2.0",` (lines 7–14) with:

```toml
    # Same-repo sibling package. The uv workspace (root pyproject.toml,
    # [tool.uv.sources]) resolves it from ../core, never from an index: it
    # is not published to one, so any PyPI name match would be a typosquat.
    # The version constraint is a defensive floor matching core/pyproject.toml.
```

In `chat/pyproject.toml` and `accounts/pyproject.toml`, replace the three-line comment above `"normly-core>=0.1.0,<0.2.0",` with:

```toml
    # Same-repo sibling package, resolved by the uv workspace from ../core,
    # never from an index (see api/pyproject.toml for the full note).
```

- [ ] **Step 6: Switch the chat end-to-end fixtures to the shared environment**

In `chat/tests/conftest.py`, add `import sys` at the top (alphabetically after `import subprocess`). Then in `api_process`:

```python
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "normly_api.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "api"), env=env,
    )
```

and in `accounts_process`:

```python
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "normly_accounts.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "accounts"), env=env,
    )
```

- [ ] **Step 7: Run all four Python test suites from the shared environment**

```bash
(cd core && ../.venv/bin/pytest -q)
(cd api && ../.venv/bin/pytest -q)
(cd accounts && ../.venv/bin/pytest -q)
(cd chat && ../.venv/bin/pytest -q)
```

Expected: all green, including `chat/tests/test_structural_end_to_end.py` (four tests, they start api and accounts via `sys.executable -m uvicorn`). Docker must be running (testcontainers). `core` needs `libgl1` locally (already installed, otherwise `sudo apt-get install -y libgl1`).

- [ ] **Step 8: Add the development workflow to `CONTRIBUTING.md`**

Insert before `## Process`:

```markdown
## Development setup

The four Python packages (`core`, `api`, `chat`, `accounts`) form one
[uv](https://docs.astral.sh/uv/) workspace with a single lock file
(`uv.lock`). One environment in the repository root serves all of them:

```bash
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
uv sync --all-packages --all-extras      # creates .venv with every package and dev extra
cd api && ../.venv/bin/pytest            # run one package's tests (needs Docker for testcontainers)
```

`uv sync` keeps `.venv` in step with `uv.lock`. Change a dependency in a
package's `pyproject.toml`, then run `uv lock` and commit the updated
`uv.lock` with it — CI installs with `--locked` and fails when the lock
file is out of date. The frontend uses `npm ci` with `package-lock.json`
as before.
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock api/pyproject.toml chat/pyproject.toml accounts/pyproject.toml chat/tests/conftest.py CONTRIBUTING.md
git commit -s -m "build: lock Python dependencies with a uv workspace

One uv.lock for core, api, chat and accounts; normly-core is resolved
from the checkout and torch/torchvision only from the CPU wheel index
(REQ-BUILD-001). Chat end-to-end fixtures start their sibling services
from the shared environment.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Switch the test pipeline to the lock file

**Files:**
- Modify: `.github/workflows/ci.yml` (jobs `test-accounts`, `test-api`, `test-chat`, `test-core`)

**Interfaces:**
- Consumes: `uv.lock`, root `pyproject.toml` from Task 1.

- [ ] **Step 1: Rewrite the four Python jobs**

Replace `ci.yml` completely with this version (frontend and docs jobs unchanged):

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

env:
  UV_VERSION: "0.12.23"

jobs:
  test-accounts:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      # --locked: fail when uv.lock does not match the pyproject.toml files,
      # so an outdated lock file is caught in every PR without its own job.
      - run: pip install "uv==${UV_VERSION}" && uv sync --locked --all-packages --all-extras
      - run: cd accounts && ../.venv/bin/pytest

  test-api:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: pip install "uv==${UV_VERSION}" && uv sync --locked --all-packages --all-extras
      - run: cd api && ../.venv/bin/pytest

  test-chat:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: pip install "uv==${UV_VERSION}" && uv sync --locked --all-packages --all-extras
      # Exclude tests/test_structural_end_to_end.py: those 4 tests start real
      # api and accounts processes, and api loads the embedding model at
      # startup -- a 2 GB cold download from huggingface.co on every CI run.
      # They run locally from the shared .venv (see CONTRIBUTING.md).
      - run: cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py

  test-core:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: apt-get update && apt-get install -y --no-install-recommends libgl1 && rm -rf /var/lib/apt/lists/*
      - run: pip install "uv==${UV_VERSION}" && uv sync --locked --all-packages --all-extras
      - run: cd core && ../.venv/bin/pytest

  test-frontend:
    runs-on: ubuntu-latest
    container: node:22
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: cd frontend && npm ci && npm test

  test-docs:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"
      # mkdocstrings-python defaults to force_inspection = False, so it parses
      # docstrings statically from the `paths` in zensical.toml -- it never
      # imports the normly_* packages. No editable installs, no libgl1 needed.
      - run: |
          set -euo pipefail
          zensical build 2>&1 | tee /tmp/build.log
          # Regression guard: fail if the accepted warning baseline (3 known
          # [[wiki-link]] false positives in docs/superpowers/specs/) changes.
          grep -q "^3 issues found" /tmp/build.log
```

- [ ] **Step 2: Reproduce the CI steps locally in a fresh container**

```bash
docker run --rm -v "$PWD":/src:ro python:3.12 sh -c '
  git clone -q /src /w && cd /w \
  && pip install -q "uv==0.12.23" && uv sync --locked --all-packages --all-extras \
  && cd accounts && ../.venv/bin/pytest --co -q | tail -1'
```

The clone contains only what is committed (Task 1 is committed) and leaves the local `.venv` untouched.

Expected: `uv sync --locked` runs without "lock file is out of date"; pytest collects the tests (`N tests collected`; the collection is enough, the full suite runs in the real CI run).

- [ ] **Step 3: Check the workflow syntax**

```bash
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color
```

Expected: no output (no errors).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -s -m "ci: install Python packages from uv.lock with --locked

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Dockerfiles: locked dependencies, pinned weights, digest pins

**Files:**
- Modify: `docker/python.Dockerfile` (completely new), `frontend/Dockerfile:10,15,24`, `core/src/normly_core/pipeline/docling_extraction.py:6-17`, `core/tests/pipeline/test_docling_offline.py:19-28`

**Interfaces:**
- Consumes: `uv.lock`, root `pyproject.toml` (Task 1).
- Produces: targets `api`, `chat`, `accounts`, `pipeline` in `docker/python.Dockerfile`, build context repo root; `frontend/Dockerfile` with context `frontend`. `ARG` names `E5_REVISION`, `DOCLING_LAYOUT_REVISION`, `DOCLING_LAYOUT_ONNX_REVISION`, `DOCLING_MODELS_REVISION`. Task 4 references exactly these targets.

- [ ] **Step 1: Replace `docker/python.Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# One Dockerfile, four runtime targets (api, chat, accounts, pipeline) on a
# shared chain of stages, so BuildKit builds and pushes the heavy layers once:
#
#   deps     third-party dependencies, installed from uv.lock (--locked)
#   weights  model weights at pinned revisions (the only stage that talks
#            to huggingface.co)
#   base     deps + weights + the core package
#   api/chat/accounts/pipeline  base + the service's own package
#
# Every input is pinned: base images by digest, Python packages by uv.lock,
# model weights by commit (REQ-BUILD-001, ADR-023). Build context: repo root.

# Digests resolved 2026-10-08.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21

FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON=/usr/local/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

# libgl1/libglib2.0-0: transitive runtime needs of docling -> opencv.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 normly \
    && useradd --uid 10001 --gid normly --create-home --shell /usr/sbin/nologin normly

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Only the workspace metadata: this layer is rebuilt when a dependency
# changes, not when application code does. --no-install-workspace leaves
# the four normly packages out; each stage below adds its own.
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY api/pyproject.toml api/
COPY chat/pyproject.toml chat/
COPY accounts/pyproject.toml accounts/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --all-packages --no-install-workspace

# ---------------------------------------------------------------------------
FROM deps AS weights

# Model revisions: the single place they are defined. Commit SHAs resolved
# 2026-10-08 from the Hugging Face API (what `main` resp. tag v2.3.0
# pointed to that day). Change deliberately, in a commit of its own, and
# re-embed the knowledge base afterwards (embeddings depend on e5).
ARG E5_REVISION=3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3
ARG DOCLING_LAYOUT_REVISION=8f39ad3c0b4c58e9c2d2c84a38465abf757272d8
ARG DOCLING_LAYOUT_ONNX_REVISION=40bde044036bb181c130ddf6c51792187268748f
ARG DOCLING_MODELS_REVISION=fc0f2d45e2218ea24bce5045f58a389aed16dc23

ENV HF_HUB_DISABLE_TELEMETRY=1

# Docling resolves pre-fetched models under NORMLY_DOCLING_ARTIFACTS_PATH in
# the folder layout its own `docling-tools models download` produces:
# <artifacts>/<repo_id with "/" replaced by "--">. We reproduce that layout
# with snapshot_download so revisions can be pinned (the CLI cannot).
RUN --mount=type=cache,target=/tmp/hf \
    HF_HOME=/tmp/hf python - <<'PY' \
    && find /opt/models -type d -name .cache -prune -exec rm -rf {} + \
    && chown -R normly:normly /opt/models
import os
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="intfloat/multilingual-e5-large",
    revision=os.environ["E5_REVISION"],
    local_dir="/opt/models/multilingual-e5-large",
    # safetensors only: no ONNX/OpenVINO exports, no duplicate .bin weights.
    ignore_patterns=["onnx/*", "openvino/*", "pytorch_model.bin", ".eval_results/*", "*.md"],
)
for repo_id, revision in [
    ("docling-project/docling-layout-heron", os.environ["DOCLING_LAYOUT_REVISION"]),
    ("docling-project/docling-layout-heron-onnx", os.environ["DOCLING_LAYOUT_ONNX_REVISION"]),
    ("docling-project/docling-models", os.environ["DOCLING_MODELS_REVISION"]),
]:
    snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir="/opt/models/docling/" + repo_id.replace("/", "--"),
    )
PY

# ---------------------------------------------------------------------------
FROM deps AS base

COPY --from=weights --chown=normly:normly /opt/models /opt/models

# HF_HUB_OFFLINE: at runtime no container may contact huggingface.co; with
# the weights baked in, any attempt is a bug and now fails loudly.
ENV NORMLY_EMBEDDING_MODEL_PATH=/opt/models/multilingual-e5-large \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_OFFLINE=1

# The core package itself (code, alembic.ini, migrations). Dependencies are
# already in the environment, so --no-deps installs only the package.
COPY core /app/core
RUN uv pip install --no-deps /app/core \
    && chown -R normly:normly /app

# ---------------------------------------------------------------------------
FROM base AS api
COPY api /app/api
RUN uv pip install --no-deps /app/api && chown -R normly:normly /app/api
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS chat
COPY chat /app/chat
RUN uv pip install --no-deps /app/chat && chown -R normly:normly /app/chat
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_chat.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS accounts
COPY accounts /app/accounts
RUN uv pip install --no-deps /app/accounts && chown -R normly:normly /app/accounts
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_accounts.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS pipeline
ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
    NORMLY_CORE_DIR=/app/core
USER normly
ENTRYPOINT ["python", "-m", "normly_core.pipeline"]
```

- [ ] **Step 2: Pin `frontend/Dockerfile` by digest**

Insert after the header comment (before the first `FROM` line):

```dockerfile
# Digest resolved 2026-10-08 (REQ-BUILD-001, ADR-023).
ARG NODE_IMAGE=node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402
```

and replace the three lines `FROM node:22-alpine AS deps|build|runtime` with `FROM ${NODE_IMAGE} AS deps`, `FROM ${NODE_IMAGE} AS build`, `FROM ${NODE_IMAGE} AS runtime`.

- [ ] **Step 3: Switch the docstring and the skip text to the new model source**

In `core/src/normly_core/pipeline/docling_extraction.py`, replace lines 6–12 of the module docstring with:

```python
Production/CI requirement (STACKIT-only constraint -- no runtime access to
external model sources, see CLAUDE.md): the container image pre-fetches
Docling's layout and table-structure models at pinned revisions into
/opt/models/docling (docker/python.Dockerfile, stage `weights`, same folder
layout as `docling-tools models download layout tableformer -o <path>`)
and sets NORMLY_DOCLING_ARTIFACTS_PATH to that directory.
```

In `core/tests/pipeline/test_docling_offline.py`, replace the `reason` text (lines 21–27) with:

```python
        f"Set {_ARTIFACTS_PATH_ENV} to a directory populated with Docling's "
        "layout and tableformer models (locally: `docling-tools models "
        "download layout tableformer -o <path>`; in the image: "
        "/opt/models/docling) to run this test -- it proves extraction "
        "needs no network access once models are pre-fetched, matching the "
        "production deployment requirement (no runtime access to external "
        "model sources, CLAUDE.md's STACKIT-only constraint)."
```

- [ ] **Step 4: Build all four Python targets**

```bash
for t in api chat accounts pipeline; do
  docker build -f docker/python.Dockerfile --target "$t" -t "normly-$t:tp2" . || exit 1
done
docker images 'normly-*:tp2'
```

Expected: four images; the logs show `uv sync --locked` without errors and `snapshot_download` for four repos. Only the first target downloads; the other three hit the cache for `deps`, `weights` and `base`.

- [ ] **Step 5: Check weights, offline operation and runtime imports in the image**

```bash
docker run --rm normly-api:tp2 sh -c '
  ls /opt/models/multilingual-e5-large /opt/models/docling &&
  test ! -e /opt/models/multilingual-e5-large/pytorch_model.bin &&
  python -c "
from normly_core.pipeline.embeddings import EmbeddingModel
m = EmbeddingModel()
v = m.embed_query(\"Prüfung der Schutzmaßnahmen\")
print(len(v))"'
docker run --rm normly-api:tp2 sh -c 'id -u && env | grep -E "HF_HUB_OFFLINE|NORMLY_EMBEDDING_MODEL_PATH"'
```

Expected: both model folders present, no `pytorch_model.bin`, output `1024`; UID `10001`, `HF_HUB_OFFLINE=1`.

Note: with `model_path=None`, `EmbeddingModel(model_name=MODEL_NAME, *, model_path=None)` reads the variable `NORMLY_EMBEDDING_MODEL_PATH` (`core/src/normly_core/pipeline/embeddings.py:35-47`); the call without arguments is correct. 1024 is the dimension of `multilingual-e5-large`.

- [ ] **Step 6: Run the Docling offline test against the pinned models in the image**

```bash
docker run --rm \
  -v "$PWD/core/tests:/app/core/tests:ro" \
  -e NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
  --user root \
  normly-pipeline:tp2 sh -c '
    uv pip install --no-deps pytest iniconfig pluggy packaging >/dev/null &&
    cd /app/core && python -m pytest -q --noconftest tests/pipeline/test_docling_offline.py'
```

`--noconftest`: `core/tests/conftest.py` imports testcontainers (not in the image, not needed — the offline test uses no fixture from it).

Expected: `1 passed`. This proves that Docling finds the pinned models stored under its own folder convention and opens no network connection. If the test fails with a download attempt, a folder name is wrong: compare `docker run --rm normly-pipeline:tp2 find /opt/models/docling -maxdepth 2` with `docling-project--docling-layout-heron`, `docling-project--docling-layout-heron-onnx`, `docling-project--docling-models`.

If `uv pip install --no-deps pytest …` reports further missing pytest dependencies, add them to the call (the list comes from pytest 8).

- [ ] **Step 7: Build the frontend image**

```bash
docker build -t normly-frontend:tp2 frontend
docker run --rm normly-frontend:tp2 node -e "console.log(process.version)"
```

Expected: build successful, Node 22.

- [ ] **Step 8: Core test suite locally (the docstring change must not break anything)**

```bash
(cd core && ../.venv/bin/pytest -q tests/pipeline/test_docling_offline.py)
```

Expected: `1 skipped` (variable not set) — the skip text is shown with `-rs`.

- [ ] **Step 9: Commit**

```bash
git add docker/python.Dockerfile frontend/Dockerfile core/src/normly_core/pipeline/docling_extraction.py core/tests/pipeline/test_docling_offline.py
git commit -s -m "build: pin base images, dependencies and model weights in the Dockerfiles

deps/weights/base stages: dependencies from uv.lock, model weights fetched
at fixed commits in a stage of their own, base images by digest, HF offline
at runtime (REQ-BUILD-001).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Bake file and Compose on GHCR names

**Files:**
- Create: `docker-bake.hcl`
- Modify: `compose.yaml:1-20,32-36,44-48,56-60,68-72,79-83,132-134,181-184`, `.env.example` (new section after `# --- Profiles`)

**Interfaces:**
- Consumes: targets from Task 3.
- Produces: bake variables `REGISTRY` (default `ghcr.io/normly/web-app`), `TAGS` (space-separated, default `local`), `CACHE_REF` (empty = no registry cache), `PUSH` (`"1"` = attestations on, otherwise off). Group `default` with the five targets. Task 5 sets exactly these variables.

- [ ] **Step 1: Create `docker-bake.hcl`**

```hcl
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Build definition for the image pipeline (.github/workflows/images.yml).
# One `docker buildx bake` builds all five images in a single BuildKit
# session, so the four Python targets share their deps/weights/base layers.
# compose.yaml keeps its own build: blocks for `docker compose up --build`;
# both point at the same Dockerfiles and targets.
#
# Variables (all optional locally):
#   REGISTRY   image name prefix
#   TAGS       space-separated tags applied to every image
#   CACHE_REF  registry cache prefix; empty disables the registry cache
#   PUSH       "1" when pushing: enables provenance + SBOM attestations
#              (the local docker exporter cannot store them)

variable "REGISTRY" { default = "ghcr.io/normly/web-app" }
variable "TAGS" { default = "local" }
variable "CACHE_REF" { default = "" }
variable "PUSH" { default = "0" }

function "tags" {
  params = [name]
  result = [for t in split(" ", TAGS) : "${REGISTRY}/${name}:${t}"]
}

function "cache_from" {
  params = [name]
  result = CACHE_REF == "" ? [] : ["type=registry,ref=${CACHE_REF}:${name}"]
}

function "cache_to" {
  params = [name]
  result = CACHE_REF == "" ? [] : ["type=registry,ref=${CACHE_REF}:${name},mode=max"]
}

group "default" {
  targets = ["api", "chat", "accounts", "pipeline", "frontend"]
}

target "_common" {
  platforms = ["linux/amd64"]
  attest = PUSH == "1" ? ["type=provenance,mode=max", "type=sbom"] : []
}

target "_python" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "docker/python.Dockerfile"
}

target "api" {
  inherits   = ["_python"]
  target     = "api"
  tags       = tags("api")
  cache-from = cache_from("api")
  cache-to   = cache_to("api")
}

target "chat" {
  inherits   = ["_python"]
  target     = "chat"
  tags       = tags("chat")
  cache-from = cache_from("chat")
  cache-to   = cache_to("chat")
}

target "accounts" {
  inherits   = ["_python"]
  target     = "accounts"
  tags       = tags("accounts")
  cache-from = cache_from("accounts")
  cache-to   = cache_to("accounts")
}

target "pipeline" {
  inherits   = ["_python"]
  target     = "pipeline"
  tags       = tags("pipeline")
  cache-from = cache_from("pipeline")
  cache-to   = cache_to("pipeline")
}

target "frontend" {
  inherits   = ["_common"]
  context    = "frontend"
  dockerfile = "Dockerfile"
  tags       = tags("frontend")
  cache-from = cache_from("frontend")
  cache-to   = cache_to("frontend")
}
```

- [ ] **Step 2: Check the bake definition, once locally and once as in the CI**

```bash
docker buildx bake --print | python3 -c "import sys,json; d=json.load(sys.stdin); print({k: v['tags'] for k, v in d['target'].items()})"
TAGS="0.1.0 0.1 latest sha-abc1234" CACHE_REF="ghcr.io/normly/web-app/cache" PUSH=1 \
  docker buildx bake --print | python3 -c "import sys,json; d=json.load(sys.stdin); t=d['target']['api']; print(t['tags'], t['cache-to'], t['attest'])"
```

Expected: first output five targets with `…:local`; second output four tags for `api`, `cache-to` with `mode=max`, two attestations.

- [ ] **Step 3: Build locally and load into the Docker daemon**

```bash
docker buildx bake --load
docker images 'ghcr.io/normly/web-app/*'
```

Expected: five images with the tag `local`; the build hits the cache from Task 3.

If `--load` aborts with "docker exporter does not currently support exporting manifest lists", the `PUSH` condition on `attest` is missing (locally the list must be empty) — check `docker buildx bake --print | grep -A2 attest`.

- [ ] **Step 4: Switch `compose.yaml` to the GHCR names**

Extend the header comment (lines 4–10) by two lines before `# Third-party image tags pinned`:

```yaml
# Images come from ghcr.io/normly/web-app (built and signed by
# .github/workflows/images.yml, defined in docker-bake.hcl); `up --build`
# builds the same targets locally under the same names.
```

Replace the five `image:` lines:

| Service | new `image:` line |
|---|---|
| `migrate` | `image: ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |
| `api` | `image: ghcr.io/normly/web-app/api:${NORMLY_IMAGE_TAG:-edge}` |
| `accounts` | `image: ghcr.io/normly/web-app/accounts:${NORMLY_IMAGE_TAG:-edge}` |
| `chat` | `image: ghcr.io/normly/web-app/chat:${NORMLY_IMAGE_TAG:-edge}` |
| `frontend` | `image: ghcr.io/normly/web-app/frontend:${NORMLY_IMAGE_TAG:-edge}` |
| `pipeline` | `image: ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |

- [ ] **Step 5: Add `NORMLY_IMAGE_TAG` to `.env.example`**

Insert after the section `# --- Profiles` (after `COMPOSE_PROFILES=bundled`):

```bash
# --- Images ---------------------------------------------------------------
# Which published image tag `docker compose up` pulls from ghcr.io/normly/web-app.
#   edge    newest commit on main (moves with every merge)
#   X.Y.Z   a release; X.Y follows the newest patch of that minor line
#   latest  the newest release
# `docker compose up --build` ignores this and builds locally instead.
NORMLY_IMAGE_TAG=edge
```

- [ ] **Step 6: Check the Compose configuration and start the stack with the locally built images**

```bash
docker compose config | grep -E "^\s+image: ghcr" | sort -u
cp -n .env.example .env   # only if no .env exists yet; set the password
NORMLY_IMAGE_TAG=local docker compose up -d
sleep 120 && NORMLY_IMAGE_TAG=local docker compose ps -a
curl -fsS http://localhost:3000/ -o /dev/null && echo frontend ok
NORMLY_IMAGE_TAG=local docker compose down
```

Expected: five GHCR names with `:edge`; with `NORMLY_IMAGE_TAG=local` the stack starts without a build from the bake images, `migrate` exit 0, api/accounts/chat/frontend `healthy`, the frontend responds. (The bundled services Postgres, Ollama, Mailpit come from their upstream images as in TP1.)

- [ ] **Step 7: Commit**

```bash
git add docker-bake.hcl compose.yaml .env.example
git commit -s -m "build: add bake definition and point compose at ghcr.io images

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Workflow `images.yml`

**Files:**
- Create: `.github/workflows/images.yml`

**Interfaces:**
- Consumes: bake variables `TAGS`, `CACHE_REF`, `PUSH` from Task 4; version fields in `core/pyproject.toml`, `api/pyproject.toml`, `chat/pyproject.toml`, `accounts/pyproject.toml`, `frontend/package.json`.
- Produces: images `ghcr.io/normly/web-app/{api,chat,accounts,pipeline,frontend}` with the tags from the spec, signatures, attestations, cache under `ghcr.io/normly/web-app/cache:<target>`.

- [ ] **Step 1: Create the workflow**

```yaml
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Builds, signs and publishes the five container images (ADR-023).
#   push to main   -> edge, sha-<short>
#   tag vX.Y.Z     -> X.Y.Z, X.Y, latest, sha-<short>
# Pull requests never build images (D3 in the TP2 spec). Signing is keyless
# (cosign + GitHub OIDC); no key material exists anywhere.
name: Images

on:
  push:
    branches: [main]
    tags: ["v*"]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io/normly/web-app
  CACHE_REF: ghcr.io/normly/web-app/cache
  COSIGN_YES: "true"

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    permissions:
      contents: read
      packages: write   # push images and cache to GHCR
      id-token: write   # keyless signing: OIDC token for Sigstore
    steps:
      - uses: actions/checkout@v4

      - name: Check that a release tag matches the package versions
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          set -euo pipefail
          version="${GITHUB_REF_NAME#v}"
          fail=0
          for f in core api chat accounts; do
            v=$(python3 -c "import tomllib;print(tomllib.load(open('$f/pyproject.toml','rb'))['project']['version'])")
            [ "$v" = "$version" ] || { echo "::error::$f/pyproject.toml is $v, tag is $version"; fail=1; }
          done
          v=$(python3 -c "import json;print(json.load(open('frontend/package.json'))['version'])")
          [ "$v" = "$version" ] || { echo "::error::frontend/package.json is $v, tag is $version"; fail=1; }
          exit $fail

      - name: Compute tags
        id: tags
        run: |
          set -euo pipefail
          short="${GITHUB_SHA::7}"
          if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
            version="${GITHUB_REF_NAME#v}"
            tags="$version ${version%.*} latest sha-$short"
          else
            tags="edge sha-$short"
          fi
          echo "tags=$tags" >> "$GITHUB_OUTPUT"
          echo "Tags: $tags"

      - name: Free disk space on the runner
        # ~14 GB free by default; the Python base layer alone is ~5 GB and
        # the registry cache export needs room too.
        run: |
          sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL
          sudo docker image prune -af >/dev/null
          df -h / | tail -1

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        env:
          TAGS: ${{ steps.tags.outputs.tags }}
          PUSH: "1"
        run: docker buildx bake --push --metadata-file /tmp/bake-meta.json

      - uses: sigstore/cosign-installer@v3

      - name: Sign every image by digest
        run: |
          set -euo pipefail
          for t in api chat accounts pipeline frontend; do
            digest=$(jq -r --arg t "$t" '.[$t]["containerimage.digest"]' /tmp/bake-meta.json)
            [ -n "$digest" ] && [ "$digest" != "null" ] || { echo "::error::no digest for $t"; exit 1; }
            cosign sign "${REGISTRY}/${t}@${digest}"
            echo "${t} ${digest}" >> /tmp/digests.txt
          done

      - name: Summary
        run: |
          {
            echo "## Images"
            echo
            echo "Tags: \`${{ steps.tags.outputs.tags }}\`"
            echo
            echo "| Image | Digest |"
            echo "|---|---|"
            while read -r t d; do echo "| \`${REGISTRY}/${t}\` | \`${d}\` |"; done < /tmp/digests.txt
            echo
            echo "Verify: \`cosign verify --certificate-identity-regexp '^https://github\\.com/normly/web-app/\\.github/workflows/images\\.yml@refs/' --certificate-oidc-issuer https://token.actions.githubusercontent.com ${REGISTRY}/api@<digest>\`"
          } >> "$GITHUB_STEP_SUMMARY"
```

Note on the action versions: `actions/checkout@v4` as in `ci.yml`; `docker/setup-buildx-action@v3`, `docker/login-action@v3`, `sigstore/cosign-installer@v3` are the widespread major lines that are guaranteed to exist. When implementing, check with `curl -s https://api.github.com/repos/<owner>/<repo>/releases/latest` whether a newer major line exists (on 2026-10-08: checkout v7, setup-buildx v4, login v4, cosign-installer v4), and raise to the newest one whose major tag demonstrably exists according to `git ls-remote --tags https://github.com/<owner>/<repo> | grep -E 'refs/tags/v[0-9]+$'`. Note in the comment which version was chosen.

- [ ] **Step 2: Check the syntax**

```bash
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color
```

Expected: no errors. (`shellcheck` hints about `$GITHUB_OUTPUT` are not errors.)

- [ ] **Step 3: Reproduce the tag computation and the version check locally**

```bash
bash -c '
GITHUB_SHA=0123456789abcdef GITHUB_REF=refs/tags/v0.1.0 GITHUB_REF_NAME=v0.1.0
short="${GITHUB_SHA::7}"; version="${GITHUB_REF_NAME#v}"
echo "$version ${version%.*} latest sha-$short"'
for f in core api chat accounts; do python3 -c "import tomllib;print('$f', tomllib.load(open('$f/pyproject.toml','rb'))['project']['version'])"; done
python3 -c "import json;print('frontend', json.load(open('frontend/package.json'))['version'])"
```

Expected: `0.1.0 0.1 latest sha-0123456`; all five version fields `0.1.0`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/images.yml
git commit -s -m "ci: build, sign and publish container images to GHCR

Keyless cosign signatures, provenance and SBOM attestations, registry
layer cache; edge/sha tags on main, semver tags on v* (ADR-023).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: ADR-023 and SRS references

**Files:**
- Modify: `docs/adr/README.md` (new entry before `## Open items`, line 804), `docs/srs/03-requirements.md:407-419` (REQ-BUILD-001), `:515` (REQ-DIST-004), `:771-781` (REQ-GIT-005)

- [ ] **Step 1: Insert ADR-023**

Before `## Open items` (after the `---` line that closes ADR-022):

```markdown
## ADR-023 — Image pipeline: GHCR, keyless signing, one version, lock file

**Status:** accepted (2026-10-08)

**Decision:**

1. **Publication:** The five container images (`api`, `chat`,
   `accounts`, `pipeline`, `frontend`) are built in GitHub Actions
   and stored as public packages under `ghcr.io/normly/web-app/`
   (confirms ADR-021). Builds run on push to `main` (tags `edge`,
   `sha-<short>`), on Git tags `vX.Y.Z` (`X.Y.Z`, `X.Y`, `latest`) and
   manually — never on pull requests.
2. **Signing:** cosign keyless via GitHub OIDC. No key material
   is generated or kept; the short-lived certificate binds the
   signature to repository, workflow and commit. In addition, per image,
   SLSA provenance and SBOM from BuildKit (REQ-GIT-005).
3. **Versioning:** One version for all five images; the annotated
   Git tag `vX.Y.Z` is the single source. The version fields of the
   packages are set to the same value in the release commit; the
   workflow checks that they match.
4. **Reproducibility:** The four Python packages form a
   uv workspace with one `uv.lock`; Torch comes exclusively from the
   CPU wheel index; base images are pinned by digest, model weights (e5,
   Docling) by commit, and sit in a build stage of their own
   (REQ-BUILD-001).

**Rationale:** The trust anchor of the keyless signature — the public
Sigstore infrastructure (Fulcio, Rekor) — is **operated by the Linux
Foundation, a non-profit organization.** This distinguishes it
qualitatively from the commercial US services in the build chain that
ADR-021 permits for the free core, and is a lighter burden than
key management, rotation and re-signing on loss. The shared
version reflects what is actually tested: the services only in
combination, `api` and `chat` even from one base image; a rollback
is thus a single step. Doing without PR builds keeps the pipeline
lean; a broken Dockerfile shows up loudly and without harm after the merge
(`edge` stays where it is, the release tag fails). Without
pinned weights, the same Git tag could produce different embeddings than
the data version that TP4 imports.

**Rejected:** own cosign key pair (key management, storage
outside GitHub, re-signing on loss); version per package
(tested combination no longer readable, one tag per package per release);
image build on pull requests (full build per PR, path filter misses
code changes); pip-tools (four lock files with possible drift, no
clean index separation for Torch).

**Consequence:** `docker compose up -d` pulls published images,
`--build` remains the local route; `docs/guide/self-hosting.md` describes
obtaining the images and verifying the signatures, `docs/guide/releasing.md` the release procedure,
`CONTRIBUTING.md` the uv development environment. REQ-BUILD-001,
REQ-DIST-004 and REQ-GIT-005 refer here. Signature verification as a
mandatory step before start on the VM follows with the rollout script
(TP4). Details:
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`.

---

```

- [ ] **Step 2: Set the SRS references**

Replace REQ-BUILD-001 (line 419, `**Further information:** Applies to backend, frontend and ML components.`) with (wording at the time):

```markdown
**Further information:** Applies to backend, frontend and ML components. Implementation since ADR-023 (2026-10-08): uv workspace with `uv.lock`, base images pinned by digest, model weights pinned by commit; the same Git tag produces the same images.
```

At the end of REQ-DIST-004 (line 515), add: ` Build, signing (cosign keyless) and tagging of the images are governed by ADR-023.`

REQ-GIT-005: replace `**Acceptance criteria:** Signature verification as a mandatory step in the pipeline; artifacts stored signed in the STACKIT Container Registry.` (wording at the time) with the following (the second sentence of the "As of" paragraph is the wording at the time):

```markdown
**Acceptance criteria:** Signature verification as a mandatory step before rollout; artifacts stored signed in the GitHub Container Registry (ADR-021, ADR-023: cosign keyless, SLSA provenance and SBOM per image).

**As of (2026-10-08):** Signature, provenance and SBOM per image are implemented with ADR-023. The verification as a mandatory step before the start on the target environment follows with the rollout script (deployment roadmap TP4).
```

- [ ] **Step 3: Check the docs build**

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12 sh -c '
  pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null
  zensical build 2>&1 | tail -5'
```

Expected: last line `3 issues found`.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/README.md docs/srs/03-requirements.md
git commit -s -m "docs: record ADR-023 on image publishing, signing and reproducible builds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Operator and release documentation

**Files:**
- Modify: `docs/guide/self-hosting.md` (Requirements, Quick start, Known gaps; new section), `zensical.toml:9-12`, `README.md:73-79`, `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md:230-243`
- Create: `docs/guide/releasing.md`

- [ ] **Step 1: Switch `docs/guide/self-hosting.md` to the pull route**

In the section `## Requirements`, replace the item "About 20 GB of disk …" with:

```markdown
- About 20 GB of disk for images and models. Building the images yourself
  instead of pulling them needs about 45 GB more for Docker's build cache.
```

Replace `## Quick start (everything bundled)` with:

````markdown
## Quick start (everything bundled)

```bash
git clone https://github.com/normly/web-app.git normly && cd normly
cp .env.example .env
# edit .env: set NORMLY_BUNDLED_POSTGRES_PASSWORD and the matching password
# inside NORMLY_DATABASE_URL
docker compose up -d
```

The first start pulls the five normly images from
`ghcr.io/normly/web-app` (about 5 GB; PyTorch, the embedding weights and
Docling's models are inside), pulls the Ollama model, runs the database
migrations and then brings up the four services. `NORMLY_IMAGE_TAG` in
`.env` selects which published tag you follow: `edge` (newest commit on
`main`, the default), a release such as `0.1.0`, its minor line `0.1`, or
`latest` (newest release). To update, change the tag if you want, then
`docker compose pull && docker compose up -d`.

To build the images from source instead — for example on a modified
checkout — run `docker compose up -d --build`; this takes 10–20 minutes
and needs the extra disk space listed above.
````

Insert after `## Configuration reference` (before `## Ingesting documents`):

````markdown
## Verifying image signatures

Every published image is signed keyless with [cosign](https://docs.sigstore.dev/)
from the `Images` workflow in `normly/web-app`, and ships a SLSA provenance
and an SBOM attestation ([ADR-023](../adr/README.md#adr-023-image-pipeline-ghcr-keyless-signing-one-version-lock-file)).
To check an image before running it:

```bash
cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/api:0.1.0
```

A valid signature prints the certificate subject (the workflow) and the
commit it was built from. Provenance and SBOM are visible with
`docker buildx imagetools inspect ghcr.io/normly/web-app/api:0.1.0 --format '{{ json .Provenance }}'`
(and `.SBOM`).
````

Under `## Known gaps`, replace the item "No published images yet …" (two lines) with:

```markdown
- No versioned knowledge-base dump yet — ingestion runs locally with the
  `pipeline` image; the dump import is the next deliverable of the
  deployment roadmap.
```

- [ ] **Step 2: Create `docs/guide/releasing.md`**

````markdown
# Releasing

A release is one git tag that produces one version of all five images
([ADR-023](../adr/README.md#adr-023-image-pipeline-ghcr-keyless-signing-one-version-lock-file)).
Images are built, signed and published by the `Images` workflow
(`.github/workflows/images.yml`); nobody builds release images by hand.

## What gets published

| Trigger | Tags on every image |
|---|---|
| merge to `main` | `edge`, `sha-<short commit>` |
| tag `vX.Y.Z` | `X.Y.Z`, `X.Y`, `latest`, `sha-<short commit>` |

Images: `ghcr.io/normly/web-app/{api,chat,accounts,pipeline,frontend}`.
`latest` always means the newest release, never `edge`.

## Cutting a release

1. Set the same version in all five places and commit it on a branch:
   `core/pyproject.toml`, `api/pyproject.toml`, `chat/pyproject.toml`,
   `accounts/pyproject.toml` (`[project] version`) and
   `frontend/package.json` (then `cd frontend && npm install --package-lock-only`
   so `package-lock.json` follows). The workflow refuses a tag whose
   version differs from any of them.
2. Merge that branch to `main` through a pull request as usual.
3. Tag the merge commit and push the tag:

   ```bash
   git switch main && git pull
   git tag -a v0.2.0 -m "normly 0.2.0"
   git push origin v0.2.0
   ```

4. Watch the `Images` run. Its summary lists every image digest and the
   `cosign verify` command. A failed run publishes nothing for that tag;
   fix on `main`, delete the tag locally and remotely, and tag again.

## First publish only

GHCR packages are created private. After the very first successful run,
open each of the six packages (`api`, `chat`, `accounts`, `pipeline`,
`frontend`, `cache`) under the organisation's *Packages*, and set its
visibility to **public** — otherwise `docker compose pull` fails for
anonymous users and the storage counts against the plan's quota.

## Changing model weights

The embedding model and Docling's models are fetched at build time at
fixed commits (`ARG … _REVISION` in `docker/python.Dockerfile`). To move
to a newer revision: look up the commit on huggingface.co, change the
`ARG` default in a commit of its own, and plan a re-embedding of the
knowledge base — vectors from different e5 revisions are not comparable.

## Updating dependencies

Python: `uv lock --upgrade` (or `uv lock --upgrade-package <name>`), run
the test suites, commit `uv.lock`. Base images: refresh the digests in
`docker/python.Dockerfile` and `frontend/Dockerfile` with
`docker buildx imagetools inspect <image>:<tag>`. Frontend: `npm update`
in `frontend/` and commit `package-lock.json`.
````

- [ ] **Step 3: Navigation, README and roadmap spec**

In `zensical.toml`, insert the line `"guide/releasing.md",` below `"guide/self-hosting.md",`.

In `README.md`, extend the paragraph under `## Where the code lives` at the end with:

```markdown
Container images are published to `ghcr.io/normly/web-app`, signed and
reproducible (ADR-023); see [docs/guide/self-hosting.md](docs/guide/self-hosting.md).
```

In `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`, under `### TP2 — Image pipeline`, add after the paragraph `**Open:** …`:

```markdown
**As of 2026-10-08:** design in
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`
(decisions D1–D4: cosign keyless, one version per tag, build only on
`main`/tags, full reproducibility with uv lock and pinned
weights), implemented according to `docs/superpowers/plans/2026-10-08-tp2-image-pipeline.md`.
```

- [ ] **Step 4: Check the docs build**

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12 sh -c '
  pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null
  zensical build 2>&1 | tail -5'
grep -rl "adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei" site/adr/ | head -1
```

Expected: `3 issues found`; the grep finds the built ADR page (the anchor exists as the guides linked to it at the time; Zensical maps umlauts and special characters the way the existing links to `adr-022-betriebsumgebung-phase-1-und-modellherkunftsregel` show). If the build shows `4 issues found` or more, a link in the new pages is wrong — the build output names it.

- [ ] **Step 5: Commit**

```bash
git add docs/guide/self-hosting.md docs/guide/releasing.md zensical.toml README.md docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md
git commit -s -m "docs: describe pulling, verifying and releasing the published images

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Live verification (after PR and merge, with the owner)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md` (new section `## Verification <date>` at the end)

This task does not run in a subagent. Every step that triggers a workflow needs the owner's explicit yes beforehand.

- [ ] **Step 1: Open the PR** (triggers `CI`, not `Images`): push the branch, PR against `main` with a reference to spec and plan. Expectation: five green jobs, `test-core` red with the known DGUV signature. Check that `uv sync --locked` runs through in the logs without "out of date".

- [ ] **Step 2: Merge by the owner.** Afterwards `Images` runs on `main` for the first time. Record from the run: total duration, `df -h` output after the cleanup, size of the five images according to the summary, whether all five signatures went through.

- [ ] **Step 3: Make the packages public.** The owner sets `api`, `chat`, `accounts`, `pipeline`, `frontend`, `cache` to public. Anonymous check:

```bash
docker logout ghcr.io
docker manifest inspect ghcr.io/normly/web-app/api:edge | head -5
```

Expected: manifest readable without sign-in.

- [ ] **Step 4: Check signature and attestations from outside**

```bash
curl -sSLo /tmp/cosign https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 && chmod +x /tmp/cosign
/tmp/cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/api:edge | head -3
docker buildx imagetools inspect ghcr.io/normly/web-app/api:edge --format '{{ json .SBOM }}' | head -c 300
```

Expected: `Verification for ghcr.io/normly/web-app/api:edge -- The following checks were performed …`; SBOM JSON present.

- [ ] **Step 5: Pull route without a local build**

```bash
docker image rm $(docker images -q 'ghcr.io/normly/web-app/*') 2>/dev/null || true
docker compose pull && docker compose up -d
sleep 120 && docker compose ps -a && curl -fsS http://localhost:3000/ -o /dev/null && echo ok
docker compose down
```

Expected: images come from GHCR (`Pulled`), stack healthy.

- [ ] **Step 6: Release `v0.1.0`** (owner's yes): all five version fields are already at `0.1.0`.

```bash
git switch main && git pull
git tag -a v0.1.0 -m "normly 0.1.0" && git push origin v0.1.0
```

Expected: the run delivers `0.1.0`, `0.1`, `latest`, `sha-…`; duration well below run 2 (registry cache takes effect; note the number). `docker pull ghcr.io/normly/web-app/api:0.1.0` works.

- [ ] **Step 7: Negative test of the version check** (owner's yes):

```bash
git tag v9.9.9 && git push origin v9.9.9
```

Expected: the run aborts in the step "Check that a release tag matches the package versions", no build. Afterwards `git push origin :refs/tags/v9.9.9 && git tag -d v9.9.9`.

- [ ] **Step 8: Write the results into the spec and commit** (section `## Verification 2026-MM-DD` with the measured values, deviations and any follow-up work; PR `docs: record TP2 verification results`).

---

## Self-Review

**Correction after the full review (2026-10-08):** `uv sync --frozen` does not check the lock file; replaced everywhere by `--locked`.

**Spec coverage:**

| Spec section | Task |
|---|---|
| D1 keyless signing, verify call | 5, 7 |
| D2 one version, version check, `v0.1.0` | 5 (check of all five fields), 8 |
| D3 triggers only main/tags/manual | 5 |
| D4 lock file, Torch index, pinned weights in a stage of their own | 1, 3 |
| Workflow: permissions, disk space, bake, cache, attestations, summary | 4, 5 |
| Tagging table | 5 |
| Public packages | 7 (releasing.md), 8 |
| Compose integration, `NORMLY_IMAGE_TAG` | 4 |
| uv workspace, comments, chat E2E, `ci.yml`, CONTRIBUTING | 1, 2 |
| Dockerfile stages, digest pins, docstring | 3 |
| ADR-023, SRS references | 6 |
| self-hosting.md, releasing.md, navigation, README, roadmap reference | 7 |
| Verification 1–6 | 1–4 (local), 8 (live) |

**Deliberate deviation from the spec:** The spec holds out the prospect of lifting the CI exclusion of the chat end-to-end tests if they run green. The plan keeps the exclusion: the tests start a real `api` process that loads the e5 model at startup — in the CI a 2 GB cold-start download per run, the same mechanism that keeps `test-core` red. The comment in `ci.yml` names this reason. Locally, the tests run from the shared environment (Task 1, Step 7).

**Type consistency:** bake variables `REGISTRY`/`TAGS`/`CACHE_REF`/`PUSH` identical in Task 4 and 5; `ARG` names used only in Task 3; image names identical in Task 4, 5, 7; ADR anchor `adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei` (anchor at the time; the two Task 7 links were later pointed to `adr-023-image-pipeline-ghcr-keyless-signing-one-version-lock-file` when the ADRs were translated) the same twice in Task 7 and checked against the build in Task 7 Step 4.
