# Image-Pipeline (TP2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die fünf Container-Images werden reproduzierbar in GitHub Actions gebaut, keyless mit cosign signiert und mit Versions-Tags nach `ghcr.io/normly/web-app/...` veröffentlicht; `docker compose up -d` zieht sie statt zu bauen.

**Architecture:** Ein uv-Workspace im Repo-Root mit einer `uv.lock` ersetzt die vier losen `pip install -e`-Umgebungen. `docker/python.Dockerfile` bekommt die Stufen `deps` (gelockte Fremdabhängigkeiten) → `weights` (Modellgewichte mit fester Revision) → `base` (beides plus `core`) → `api`/`chat`/`accounts`/`pipeline`. Eine `docker-bake.hcl` ist die Build-Definition für die CI; `compose.yaml` behält seine `build:`-Blöcke, zeigt aber auf die GHCR-Namen. Der Workflow `.github/workflows/images.yml` baut bei Push auf `main`, bei Tags `v*` und manuell, pusht mit Registry-Cache, erzeugt Provenance und SBOM und signiert jeden Digest.

**Tech Stack:** uv 0.12.23, Docker Buildx Bake (HCL), `python:3.12-slim` und `node:22-alpine` per Digest, `huggingface_hub.snapshot_download`, cosign v3 (keyless, Sigstore), GitHub Actions (`actions/checkout`, `docker/setup-buildx-action`, `docker/login-action`, `sigstore/cosign-installer`), Zensical für die Doku.

Spec: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`. Roadmap: `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`. Vorgänger-Plan (Dockerfile-Struktur, Compose-Profile): `docs/superpowers/plans/2026-10-04-tp1-containerisation.md`.

## Global Constraints

- Lizenzheader in jeder neuen Quelldatei: `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# Copyright (C) 2026 normly contributors` (Dockerfile, Compose, HCL, YAML, Shell, Python als `#`-Kommentar).
- Commits: Conventional Commits, Englisch, `git commit -s` (Signed-off-by des Menschen) plus Trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Kein Push auf `main`. **Jeder Push nach GitHub löst einen Workflow aus und wird vorher mit dem Nutzer abgestimmt.**
- Keine Secrets im Repo, auch nicht in `.env.example`, Workflows oder Tests. Signatur ohne eigenen Schlüssel (D1).
- Eine Version für alle fünf Images; der Git-Tag `vX.Y.Z` ist die einzige Quelle (D2). Erster Release-Tag `v0.1.0`.
- Image-Build nur bei Push auf `main`, Tags `v*` und `workflow_dispatch`, nie bei Pull Requests (D3).
- Nur `linux/amd64`.
- Modellrevisionen stehen ausschließlich als `ARG`-Vorgaben in `docker/python.Dockerfile` (eine Stelle). Werte, ermittelt 2026-10-08 über die Hugging-Face-API:
  - `intfloat/multilingual-e5-large` → `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` (main, 2026-04-02)
  - `docling-project/docling-layout-heron` → `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` (main, 2026-02-09)
  - `docling-project/docling-layout-heron-onnx` → `40bde044036bb181c130ddf6c51792187268748f` (main, 2026-03-31)
  - `docling-project/docling-models` → `fc0f2d45e2218ea24bce5045f58a389aed16dc23` (Tag v2.3.0, 2025-07-23)
- Basis-Image-Digests, ermittelt 2026-10-08 mit `docker buildx imagetools inspect`:
  - `python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f`
  - `node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402`
  - `ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21`
- Zur Laufzeit kontaktiert kein Container huggingface.co; die Images setzen `HF_HUB_OFFLINE=1`.
- Alle Container laufen als Nutzer `normly` (UID/GID 10001), wie in TP1.
- `docs/superpowers/`, `docs/adr/`, `docs/srs/`, CLAUDE.md bleiben Deutsch; `docs/guide/`, README, CONTRIBUTING sind Englisch.
- Der CI-Doku-Job erwartet exakt `3 issues found` beim Zensical-Build; neue Doku darf keine neuen Link-Issues erzeugen.
- Der bekannte rote `test-core`-Job (DGUV-Kaltstart-Download) ist nicht Teil dieses Plans und bleibt rot.

---

## Arbeitsweise

- Branch `feat/tp2-image-pipeline` von `main` (Stand nach Merge von PR #12, Commit `742a989` oder neuer), eigener Worktree.
- Lokal bauen und testen; Docker Engine mit Buildx ist vorhanden (`docker buildx version` → v0.37). Der erste lokale Build lädt rund 2,5 GB Modellgewichte und installiert Torch, Docling und Co. — 10 bis 20 Minuten, einmalig.
- Die Live-Verifikation (Task 8) läuft erst nach Merge des PR und braucht je Schritt das Ja des Nutzers.

---

## Dateistruktur

| Datei | Zweck | Task |
|---|---|---|
| `pyproject.toml` (neu, Root) | uv-Workspace-Anker, Quellen für `normly-core` und Torch-Index | 1 |
| `uv.lock` (neu) | Lock-Datei aller vier Python-Pakete | 1 |
| `api/pyproject.toml`, `chat/pyproject.toml`, `accounts/pyproject.toml` | Kommentar zur `normly-core`-Auflösung kürzen | 1 |
| `chat/tests/conftest.py` | Nachbardienste aus der gemeinsamen Umgebung starten | 1 |
| `CONTRIBUTING.md` | Abschnitt „Development setup" mit uv | 1 |
| `.github/workflows/ci.yml` | Python-Jobs auf `uv sync --frozen` | 2 |
| `docker/python.Dockerfile` | Stufen `deps`/`weights`/`base`, uv, Digest-Pins, Revisionen | 3 |
| `frontend/Dockerfile` | Digest-Pin | 3 |
| `core/src/normly_core/pipeline/docling_extraction.py`, `core/tests/pipeline/test_docling_offline.py` | Docstring/Skip-Text auf den neuen Modellbezug | 3 |
| `docker-bake.hcl` (neu) | Build-Definition der CI | 4 |
| `compose.yaml`, `.env.example` | GHCR-Image-Namen, `NORMLY_IMAGE_TAG` | 4 |
| `.github/workflows/images.yml` (neu) | Build, Push, Cache, Attestation, Signatur | 5 |
| `docs/adr/README.md` | ADR-023 | 6 |
| `docs/srs/03-anforderungen.md` | Verweise REQ-BUILD-001, REQ-DIST-004, REQ-GIT-005 | 6 |
| `docs/guide/self-hosting.md`, `docs/guide/releasing.md` (neu), `zensical.toml`, `README.md` | Pull-Weg, Signaturprüfung, Release-Ablauf | 7 |
| `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md` | TP2-Verweis | 7 |
| `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md` | Verifikationsergebnisse | 8 |

---

### Task 1: uv-Workspace und Lock-Datei

**Files:**
- Create: `pyproject.toml` (Repo-Root), `uv.lock`
- Modify: `api/pyproject.toml:7-15`, `chat/pyproject.toml:7-10`, `accounts/pyproject.toml:7-10`, `chat/tests/conftest.py:98-121`, `CONTRIBUTING.md` (vor `## Process`)

**Interfaces:**
- Produces: `uv.lock` im Root; `uv sync --frozen --all-packages --all-extras` richtet `.venv` im Root mit allen vier Paketen ein. Task 2 und Task 3 verlassen sich auf genau diese Lock-Datei und den Workspace-Namen `normly-core`, `normly-api`, `normly-chat`, `normly-accounts`.

- [ ] **Step 1: uv installieren und Version prüfen**

```bash
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Expected: `uv 0.12.23`

- [ ] **Step 2: Root-`pyproject.toml` anlegen**

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

- [ ] **Step 3: Lock-Datei erzeugen**

```bash
uv lock
ls -la uv.lock && grep -c '^\[\[package\]\]' uv.lock
grep -A3 'name = "torch"' uv.lock | head -8
```

Expected: `uv.lock` existiert, mehrere hundert Pakete; der `torch`-Eintrag zeigt `source = { registry = "https://download.pytorch.org/whl/cpu" }` und Wheel-Namen mit `+cpu`.

Falls `uv lock` an fehlenden Wheels für eine Plattform scheitert (Meldung „no wheels for platform …"), in das Root-`pyproject.toml` unter `[tool.uv]` ergänzen und erneut locken:

```toml
[tool.uv]
environments = ["sys_platform == 'linux'", "sys_platform == 'darwin'"]
```

- [ ] **Step 4: Gemeinsame Umgebung einrichten und alle Pakete importieren**

```bash
uv sync --frozen --all-packages --all-extras
.venv/bin/python -c "import normly_core, normly_api, normly_chat, normly_accounts, torch; print(torch.__version__, torch.cuda.is_available())"
```

Expected: Version mit Suffix `+cpu`, `False`.

- [ ] **Step 5: Kommentare in den drei Dienst-`pyproject.toml` kürzen**

In `api/pyproject.toml` den Kommentarblock über `"normly-core>=0.1.0,<0.2.0",` (Zeilen 7–14) ersetzen durch:

```toml
    # Same-repo sibling package. The uv workspace (root pyproject.toml,
    # [tool.uv.sources]) resolves it from ../core, never from an index: it
    # is not published to one, so any PyPI name match would be a typosquat.
    # The version constraint is a defensive floor matching core/pyproject.toml.
```

In `chat/pyproject.toml` und `accounts/pyproject.toml` den jeweils dreizeiligen Kommentar über `"normly-core>=0.1.0,<0.2.0",` ersetzen durch:

```toml
    # Same-repo sibling package, resolved by the uv workspace from ../core,
    # never from an index (see api/pyproject.toml for the full note).
```

- [ ] **Step 6: Chat-End-to-End-Fixtures auf die gemeinsame Umgebung umstellen**

In `chat/tests/conftest.py` oben `import sys` ergänzen (alphabetisch nach `import subprocess`). Dann in `api_process`:

```python
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "normly_api.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "api"), env=env,
    )
```

und in `accounts_process`:

```python
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "normly_accounts.main:app", "--port", str(port)],
        cwd=str(CHAT_DIR.parent / "accounts"), env=env,
    )
```

- [ ] **Step 7: Alle vier Python-Testsuiten aus der gemeinsamen Umgebung laufen lassen**

```bash
(cd core && ../.venv/bin/pytest -q)
(cd api && ../.venv/bin/pytest -q)
(cd accounts && ../.venv/bin/pytest -q)
(cd chat && ../.venv/bin/pytest -q)
```

Expected: alle grün, einschließlich `chat/tests/test_structural_end_to_end.py` (vier Tests, starten api und accounts per `sys.executable -m uvicorn`). Docker muss laufen (testcontainers). `core` braucht lokal `libgl1` (bereits installiert, sonst `sudo apt-get install -y libgl1`).

- [ ] **Step 8: `CONTRIBUTING.md` um den Entwicklungsablauf ergänzen**

Vor `## Process` einfügen:

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
`uv.lock` with it — CI installs with `--frozen` and fails when the lock
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

### Task 2: Test-Pipeline auf die Lock-Datei umstellen

**Files:**
- Modify: `.github/workflows/ci.yml` (Jobs `test-accounts`, `test-api`, `test-chat`, `test-core`)

**Interfaces:**
- Consumes: `uv.lock`, Root-`pyproject.toml` aus Task 1.

- [ ] **Step 1: Die vier Python-Jobs umschreiben**

`ci.yml` komplett durch diese Fassung ersetzen (Frontend- und Docs-Job unverändert):

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
      # --frozen: fail when uv.lock does not match the pyproject.toml files,
      # so an outdated lock file is caught in every PR without its own job.
      - run: pip install "uv==${UV_VERSION}" && uv sync --frozen --all-packages --all-extras
      - run: cd accounts && ../.venv/bin/pytest

  test-api:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: pip install "uv==${UV_VERSION}" && uv sync --frozen --all-packages --all-extras
      - run: cd api && ../.venv/bin/pytest

  test-chat:
    runs-on: ubuntu-latest
    container: python:3.12
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - run: pip install "uv==${UV_VERSION}" && uv sync --frozen --all-packages --all-extras
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
      - run: pip install "uv==${UV_VERSION}" && uv sync --frozen --all-packages --all-extras
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

- [ ] **Step 2: Die CI-Schritte lokal in einem frischen Container nachstellen**

```bash
docker run --rm -v "$PWD":/src:ro python:3.12 sh -c '
  git clone -q /src /w && cd /w \
  && pip install -q "uv==0.12.23" && uv sync --frozen --all-packages --all-extras \
  && cd accounts && ../.venv/bin/pytest --co -q | tail -1'
```

Der Klon enthält nur Committetes (Task 1 ist committet) und lässt das lokale `.venv` unangetastet.

Expected: `uv sync --frozen` läuft ohne „lock file is out of date"; pytest sammelt die Tests (`N tests collected`; die Sammlung genügt, die volle Suite läuft im echten CI-Lauf).

- [ ] **Step 3: Workflow-Syntax prüfen**

```bash
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color
```

Expected: keine Ausgabe (keine Fehler).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -s -m "ci: install Python packages from uv.lock with --frozen

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Dockerfiles: gelockte Abhängigkeiten, gepinnte Gewichte, Digest-Pins

**Files:**
- Modify: `docker/python.Dockerfile` (vollständig neu), `frontend/Dockerfile:10,15,24`, `core/src/normly_core/pipeline/docling_extraction.py:6-17`, `core/tests/pipeline/test_docling_offline.py:19-28`

**Interfaces:**
- Consumes: `uv.lock`, Root-`pyproject.toml` (Task 1).
- Produces: Targets `api`, `chat`, `accounts`, `pipeline` in `docker/python.Dockerfile`, Build-Kontext Repo-Root; `frontend/Dockerfile` mit Kontext `frontend`. `ARG`-Namen `E5_REVISION`, `DOCLING_LAYOUT_REVISION`, `DOCLING_LAYOUT_ONNX_REVISION`, `DOCLING_MODELS_REVISION`. Task 4 referenziert genau diese Targets.

- [ ] **Step 1: `docker/python.Dockerfile` ersetzen**

```dockerfile
# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# One Dockerfile, four runtime targets (api, chat, accounts, pipeline) on a
# shared chain of stages, so BuildKit builds and pushes the heavy layers once:
#
#   deps     third-party dependencies, installed from uv.lock (--frozen)
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
    uv sync --frozen --no-dev --all-packages --no-install-workspace

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

- [ ] **Step 2: `frontend/Dockerfile` per Digest pinnen**

Nach dem Kopfkommentar (vor der ersten `FROM`-Zeile) einfügen:

```dockerfile
# Digest resolved 2026-10-08 (REQ-BUILD-001, ADR-023).
ARG NODE_IMAGE=node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402
```

und die drei Zeilen `FROM node:22-alpine AS deps|build|runtime` ersetzen durch `FROM ${NODE_IMAGE} AS deps`, `FROM ${NODE_IMAGE} AS build`, `FROM ${NODE_IMAGE} AS runtime`.

- [ ] **Step 3: Docstring und Skip-Text auf den neuen Modellbezug umstellen**

In `core/src/normly_core/pipeline/docling_extraction.py` die Zeilen 6–12 des Modul-Docstrings ersetzen durch:

```python
Production/CI requirement (STACKIT-only constraint -- no runtime access to
external model sources, see CLAUDE.md): the container image pre-fetches
Docling's layout and table-structure models at pinned revisions into
/opt/models/docling (docker/python.Dockerfile, stage `weights`, same folder
layout as `docling-tools models download layout tableformer -o <path>`)
and sets NORMLY_DOCLING_ARTIFACTS_PATH to that directory.
```

In `core/tests/pipeline/test_docling_offline.py` den `reason`-Text (Zeilen 21–27) ersetzen durch:

```python
        f"Set {_ARTIFACTS_PATH_ENV} to a directory populated with Docling's "
        "layout and tableformer models (locally: `docling-tools models "
        "download layout tableformer -o <path>`; in the image: "
        "/opt/models/docling) to run this test -- it proves extraction "
        "needs no network access once models are pre-fetched, matching the "
        "production deployment requirement (no runtime access to external "
        "model sources, CLAUDE.md's STACKIT-only constraint)."
```

- [ ] **Step 4: Alle vier Python-Targets bauen**

```bash
for t in api chat accounts pipeline; do
  docker build -f docker/python.Dockerfile --target "$t" -t "normly-$t:tp2" . || exit 1
done
docker images 'normly-*:tp2'
```

Expected: vier Images; die Logs zeigen `uv sync --frozen` ohne Fehler und `snapshot_download` für vier Repos. Nur das erste Target lädt; die drei anderen treffen den Cache für `deps`, `weights` und `base`.

- [ ] **Step 5: Gewichte, Offline-Betrieb und Laufzeitimporte im Image prüfen**

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

Expected: beide Modellordner vorhanden, keine `pytorch_model.bin`, Ausgabe `1024`; UID `10001`, `HF_HUB_OFFLINE=1`.

Hinweis: `EmbeddingModel(model_name=MODEL_NAME, *, model_path=None)` liest bei `model_path=None` die Variable `NORMLY_EMBEDDING_MODEL_PATH` (`core/src/normly_core/pipeline/embeddings.py:35-47`); der Aufruf ohne Argumente ist korrekt. 1024 ist die Dimension von `multilingual-e5-large`.

- [ ] **Step 6: Docling-Offline-Test gegen die gepinnten Modelle im Image laufen lassen**

```bash
docker run --rm \
  -v "$PWD/core/tests:/app/core/tests:ro" \
  -e NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
  --user root \
  normly-pipeline:tp2 sh -c '
    uv pip install --no-deps pytest iniconfig pluggy packaging >/dev/null &&
    cd /app/core && python -m pytest -q --noconftest tests/pipeline/test_docling_offline.py'
```

`--noconftest`: `core/tests/conftest.py` importiert testcontainers (nicht im Image, nicht nötig — der Offline-Test nutzt keine Fixture daraus).

Expected: `1 passed`. Das beweist, dass Docling die unter der eigenen Ordnerkonvention abgelegten, gepinnten Modelle findet und keine Netzverbindung aufbaut. Scheitert der Test mit einem Download-Versuch, stimmt ein Ordnername nicht: `docker run --rm normly-pipeline:tp2 find /opt/models/docling -maxdepth 2` mit `docling-project--docling-layout-heron`, `docling-project--docling-layout-heron-onnx`, `docling-project--docling-models` vergleichen.

Falls `uv pip install --no-deps pytest …` weitere fehlende pytest-Abhängigkeiten meldet, diese dem Aufruf hinzufügen (die Liste stammt aus pytest 8).

- [ ] **Step 7: Frontend-Image bauen**

```bash
docker build -t normly-frontend:tp2 frontend
docker run --rm normly-frontend:tp2 node -e "console.log(process.version)"
```

Expected: Build erfolgreich, Node 22.

- [ ] **Step 8: Core-Testsuite lokal (Docstring-Änderung darf nichts brechen)**

```bash
(cd core && ../.venv/bin/pytest -q tests/pipeline/test_docling_offline.py)
```

Expected: `1 skipped` (Variable nicht gesetzt) — der Skip-Text wird angezeigt mit `-rs`.

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

### Task 4: Bake-Datei und Compose auf GHCR-Namen

**Files:**
- Create: `docker-bake.hcl`
- Modify: `compose.yaml:1-20,32-36,44-48,56-60,68-72,79-83,132-134,181-184`, `.env.example` (neuer Abschnitt nach `# --- Profiles`)

**Interfaces:**
- Consumes: Targets aus Task 3.
- Produces: Bake-Variablen `REGISTRY` (Standard `ghcr.io/normly/web-app`), `TAGS` (leerzeichengetrennt, Standard `local`), `CACHE_REF` (leer = kein Registry-Cache), `PUSH` (`"1"` = Attestationen an, sonst aus). Gruppe `default` mit den fünf Targets. Task 5 setzt genau diese Variablen.

- [ ] **Step 1: `docker-bake.hcl` anlegen**

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

- [ ] **Step 2: Bake-Definition prüfen, einmal lokal und einmal wie in der CI**

```bash
docker buildx bake --print | python3 -c "import sys,json; d=json.load(sys.stdin); print({k: v['tags'] for k, v in d['target'].items()})"
TAGS="0.1.0 0.1 latest sha-abc1234" CACHE_REF="ghcr.io/normly/web-app/cache" PUSH=1 \
  docker buildx bake --print | python3 -c "import sys,json; d=json.load(sys.stdin); t=d['target']['api']; print(t['tags'], t['cache-to'], t['attest'])"
```

Expected: erste Ausgabe fünf Targets mit `…:local`; zweite Ausgabe vier Tags für `api`, `cache-to` mit `mode=max`, zwei Attestationen.

- [ ] **Step 3: Lokal bauen und in den Docker-Daemon laden**

```bash
docker buildx bake --load
docker images 'ghcr.io/normly/web-app/*'
```

Expected: fünf Images mit Tag `local`; der Build trifft den Cache aus Task 3.

Falls `--load` mit „docker exporter does not currently support exporting manifest lists" abbricht, fehlt die `PUSH`-Bedingung an `attest` (lokal muss die Liste leer sein) — `docker buildx bake --print | grep -A2 attest` prüfen.

- [ ] **Step 4: `compose.yaml` auf die GHCR-Namen umstellen**

Kopfkommentar (Zeilen 4–10) ergänzen um zwei Zeilen vor `# Third-party image tags pinned`:

```yaml
# Images come from ghcr.io/normly/web-app (built and signed by
# .github/workflows/images.yml, defined in docker-bake.hcl); `up --build`
# builds the same targets locally under the same names.
```

Die fünf `image:`-Zeilen ersetzen:

| Service | neue `image:`-Zeile |
|---|---|
| `migrate` | `image: ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |
| `api` | `image: ghcr.io/normly/web-app/api:${NORMLY_IMAGE_TAG:-edge}` |
| `accounts` | `image: ghcr.io/normly/web-app/accounts:${NORMLY_IMAGE_TAG:-edge}` |
| `chat` | `image: ghcr.io/normly/web-app/chat:${NORMLY_IMAGE_TAG:-edge}` |
| `frontend` | `image: ghcr.io/normly/web-app/frontend:${NORMLY_IMAGE_TAG:-edge}` |
| `pipeline` | `image: ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |

- [ ] **Step 5: `.env.example` um `NORMLY_IMAGE_TAG` ergänzen**

Nach dem Abschnitt `# --- Profiles` (nach `COMPOSE_PROFILES=bundled`) einfügen:

```bash
# --- Images ---------------------------------------------------------------
# Which published image tag `docker compose up` pulls from ghcr.io/normly/web-app.
#   edge    newest commit on main (moves with every merge)
#   X.Y.Z   a release; X.Y follows the newest patch of that minor line
#   latest  the newest release
# `docker compose up --build` ignores this and builds locally instead.
NORMLY_IMAGE_TAG=edge
```

- [ ] **Step 6: Compose-Konfiguration prüfen und Stack mit den lokal gebauten Images starten**

```bash
docker compose config | grep -E "^\s+image: ghcr" | sort -u
cp -n .env.example .env   # nur, wenn noch keine .env existiert; Passwort setzen
NORMLY_IMAGE_TAG=local docker compose up -d
sleep 120 && NORMLY_IMAGE_TAG=local docker compose ps -a
curl -fsS http://localhost:3000/ -o /dev/null && echo frontend ok
NORMLY_IMAGE_TAG=local docker compose down
```

Expected: fünf GHCR-Namen mit `:edge`; mit `NORMLY_IMAGE_TAG=local` startet der Stack ohne Build aus den Bake-Images, `migrate` exit 0, api/accounts/chat/frontend `healthy`, Frontend antwortet. (Die bundled-Dienste Postgres, Ollama, Mailpit kommen wie in TP1 aus ihren Upstream-Images.)

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
- Consumes: Bake-Variablen `TAGS`, `CACHE_REF`, `PUSH` aus Task 4; Versionsfelder in `core/pyproject.toml`, `api/pyproject.toml`, `chat/pyproject.toml`, `accounts/pyproject.toml`, `frontend/package.json`.
- Produces: Images `ghcr.io/normly/web-app/{api,chat,accounts,pipeline,frontend}` mit den Tags aus der Spec, Signaturen, Attestationen, Cache unter `ghcr.io/normly/web-app/cache:<target>`.

- [ ] **Step 1: Workflow anlegen**

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

Hinweis zu den Action-Versionen: `actions/checkout@v4` wie in `ci.yml`; `docker/setup-buildx-action@v3`, `docker/login-action@v3`, `sigstore/cosign-installer@v3` sind die verbreiteten Major-Linien mit garantierter Existenz. Beim Implementieren mit `curl -s https://api.github.com/repos/<owner>/<repo>/releases/latest` prüfen, ob eine neuere Major-Linie existiert (am 2026-10-08: checkout v7, setup-buildx v4, login v4, cosign-installer v4), und auf die neueste heben, deren Major-Tag per `git ls-remote --tags https://github.com/<owner>/<repo> | grep -E 'refs/tags/v[0-9]+$'` nachweislich existiert. Im Kommentar vermerken, welche Version gewählt wurde.

- [ ] **Step 2: Syntax prüfen**

```bash
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color
```

Expected: keine Fehler. (`shellcheck`-Hinweise zu `$GITHUB_OUTPUT` sind keine Fehler.)

- [ ] **Step 3: Die Tag-Berechnung und die Versionsprüfung lokal nachstellen**

```bash
bash -c '
GITHUB_SHA=0123456789abcdef GITHUB_REF=refs/tags/v0.1.0 GITHUB_REF_NAME=v0.1.0
short="${GITHUB_SHA::7}"; version="${GITHUB_REF_NAME#v}"
echo "$version ${version%.*} latest sha-$short"'
for f in core api chat accounts; do python3 -c "import tomllib;print('$f', tomllib.load(open('$f/pyproject.toml','rb'))['project']['version'])"; done
python3 -c "import json;print('frontend', json.load(open('frontend/package.json'))['version'])"
```

Expected: `0.1.0 0.1 latest sha-0123456`; alle fünf Versionsfelder `0.1.0`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/images.yml
git commit -s -m "ci: build, sign and publish container images to GHCR

Keyless cosign signatures, provenance and SBOM attestations, registry
layer cache; edge/sha tags on main, semver tags on v* (ADR-023).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: ADR-023 und SRS-Verweise

**Files:**
- Modify: `docs/adr/README.md` (neuer Eintrag vor `## Offene Punkte`, Zeile 804), `docs/srs/03-anforderungen.md:407-419` (REQ-BUILD-001), `:515` (REQ-DIST-004), `:771-781` (REQ-GIT-005)

- [ ] **Step 1: ADR-023 einfügen**

Vor `## Offene Punkte` (nach der `---`-Linie, die ADR-022 abschließt):

```markdown
## ADR-023 — Image-Pipeline: GHCR, keyless Signatur, eine Version, Lock-Datei

**Status:** beschlossen (2026-10-08)

**Entscheidung:**

1. **Veröffentlichung:** Die fünf Container-Images (`api`, `chat`,
   `accounts`, `pipeline`, `frontend`) werden in GitHub Actions gebaut
   und als öffentliche Pakete unter `ghcr.io/normly/web-app/` abgelegt
   (bestätigt ADR-021). Gebaut wird bei Push auf `main` (Tags `edge`,
   `sha-<kurz>`), bei Git-Tags `vX.Y.Z` (`X.Y.Z`, `X.Y`, `latest`) und
   manuell — nie bei Pull Requests.
2. **Signatur:** cosign keyless über GitHub-OIDC. Kein Schlüsselmaterial
   wird erzeugt oder verwahrt; das kurzlebige Zertifikat bindet die
   Signatur an Repository, Workflow und Commit. Dazu je Image
   SLSA-Provenance und SBOM aus BuildKit (REQ-GIT-005).
3. **Versionierung:** Eine Version für alle fünf Images; der annotierte
   Git-Tag `vX.Y.Z` ist die einzige Quelle. Die Versionsfelder der
   Pakete werden im Release-Commit auf denselben Wert gesetzt, der
   Workflow prüft die Übereinstimmung.
4. **Reproduzierbarkeit:** Die vier Python-Pakete bilden einen
   uv-Workspace mit einer `uv.lock`; Torch kommt ausschließlich aus dem
   CPU-Wheel-Index; Basis-Images sind per Digest, Modellgewichte (e5,
   Docling) per Commit gepinnt und liegen in einer eigenen Build-Stufe
   (REQ-BUILD-001).

**Begründung:** Der Vertrauensanker der keyless Signatur — die öffentliche
Sigstore-Infrastruktur (Fulcio, Rekor) — wird von der **Linux Foundation
betrieben, einer Non-Profit-Organisation.** Das unterscheidet ihn
qualitativ von den kommerziellen US-Diensten in der Build-Kette, die
ADR-021 für den freien Kern erlaubt, und wiegt leichter als
Schlüsselpflege, Rotation und Neusignierung bei Verlust. Die gemeinsame
Version bildet ab, was tatsächlich getestet wird: die Dienste nur in
Kombination, `api` und `chat` sogar aus einem Basis-Image; ein Rollback
ist damit ein Handgriff. Der Verzicht auf PR-Builds hält die Pipeline
schlank; ein kaputtes Dockerfile fällt nach dem Merge laut und ohne
Schaden auf (`edge` bleibt stehen, der Release-Tag schlägt fehl). Ohne
gepinnte Gewichte könnte derselbe Git-Tag andere Embeddings erzeugen als
der Datenstand, den TP4 importiert.

**Verworfen:** eigenes cosign-Schlüsselpaar (Schlüsselpflege, Ablage
außerhalb von GitHub, Neusignierung bei Verlust); Version je Paket
(getestete Kombination nicht mehr ablesbar, ein Tag je Paket je Release);
Image-Build bei Pull Requests (voller Build je PR, Pfadfilter übersieht
Codeänderungen); pip-tools (vier Lock-Dateien mit möglicher Drift, keine
saubere Index-Trennung für Torch).

**Konsequenz:** `docker compose up -d` zieht veröffentlichte Images,
`--build` bleibt der lokale Weg; `docs/guide/self-hosting.md` beschreibt
Bezug und Signaturprüfung, `docs/guide/releasing.md` den Release-Ablauf,
`CONTRIBUTING.md` die uv-Entwicklungsumgebung. REQ-BUILD-001,
REQ-DIST-004 und REQ-GIT-005 verweisen hierher. Die Signaturprüfung als
Pflichtschritt vor dem Start auf der VM folgt mit dem Rollout-Skript
(TP4). Details:
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`.

---

```

- [ ] **Step 2: SRS-Verweise setzen**

REQ-BUILD-001 (Zeile 419, `**Weitere Informationen:** Gilt für Backend, Frontend und ML-Komponenten.`) ersetzen durch:

```markdown
**Weitere Informationen:** Gilt für Backend, Frontend und ML-Komponenten. Umsetzung seit ADR-023 (2026-10-08): uv-Workspace mit `uv.lock`, Basis-Images per Digest, Modellgewichte per Commit gepinnt; derselbe Git-Tag erzeugt dieselben Images.
```

REQ-DIST-004 (Zeile 515) am Ende ergänzen: ` Build, Signatur (cosign keyless) und Tagging der Images regelt ADR-023.`

REQ-GIT-005: `**Akzeptanzkriterium:** Signaturprüfung als Pflichtschritt in der Pipeline; Artefakte in der STACKIT Container Registry signiert abgelegt.` ersetzen durch:

```markdown
**Akzeptanzkriterium:** Signaturprüfung als Pflichtschritt vor dem Rollout; Artefakte signiert in der GitHub Container Registry abgelegt (ADR-021, ADR-023: cosign keyless, SLSA-Provenance und SBOM je Image).

**Stand (2026-10-08):** Signatur, Provenance und SBOM je Image sind mit ADR-023 umgesetzt. Die Prüfung als Pflichtschritt vor dem Start auf der Zielumgebung folgt mit dem Rollout-Skript (Deployment-Roadmap TP4).
```

- [ ] **Step 3: Doku-Build prüfen**

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12 sh -c '
  pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null
  zensical build 2>&1 | tail -5'
```

Expected: letzte Zeile `3 issues found`.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/README.md docs/srs/03-anforderungen.md
git commit -s -m "docs: record ADR-023 on image publishing, signing and reproducible builds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Betreiber- und Release-Dokumentation

**Files:**
- Modify: `docs/guide/self-hosting.md` (Requirements, Quick start, Known gaps; neuer Abschnitt), `zensical.toml:9-12`, `README.md:73-79`, `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md:230-243`
- Create: `docs/guide/releasing.md`

- [ ] **Step 1: `docs/guide/self-hosting.md` auf den Pull-Weg umstellen**

Im Abschnitt `## Requirements` den Punkt „About 20 GB of disk …" ersetzen durch:

```markdown
- About 20 GB of disk for images and models. Building the images yourself
  instead of pulling them needs about 45 GB more for Docker's build cache.
```

`## Quick start (everything bundled)` ersetzen durch:

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

Nach `## Configuration reference` (vor `## Ingesting documents`) einfügen:

````markdown
## Verifying image signatures

Every published image is signed keyless with [cosign](https://docs.sigstore.dev/)
from the `Images` workflow in `normly/web-app`, and ships a SLSA provenance
and an SBOM attestation ([ADR-023](../adr/README.md#adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei)).
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

Unter `## Known gaps` den Punkt „No published images yet …" (zwei Zeilen) ersetzen durch:

```markdown
- No versioned knowledge-base dump yet — ingestion runs locally with the
  `pipeline` image; the dump import is the next deliverable of the
  deployment roadmap.
```

- [ ] **Step 2: `docs/guide/releasing.md` anlegen**

````markdown
# Releasing

A release is one git tag that produces one version of all five images
([ADR-023](../adr/README.md#adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei)).
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

- [ ] **Step 3: Navigation, README und Roadmap-Spec**

In `zensical.toml` unter `"guide/self-hosting.md",` die Zeile `"guide/releasing.md",` einfügen.

In `README.md` den Absatz unter `## Where the code lives` am Ende ergänzen um:

```markdown
Container images are published to `ghcr.io/normly/web-app`, signed and
reproducible (ADR-023); see [docs/guide/self-hosting.md](docs/guide/self-hosting.md).
```

In `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md` unter `### TP2 — Image-Pipeline` nach dem Absatz `**Offen:** …` ergänzen:

```markdown
**Stand 2026-10-08:** Design in
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`
(Entscheidungen D1–D4: cosign keyless, eine Version je Tag, Build nur auf
`main`/Tags, vollständige Reproduzierbarkeit mit uv-Lock und gepinnten
Gewichten), umgesetzt nach `docs/superpowers/plans/2026-10-08-tp2-image-pipeline.md`.
```

- [ ] **Step 4: Doku-Build prüfen**

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12 sh -c '
  pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null
  zensical build 2>&1 | tail -5'
grep -rl "adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei" site/adr/ | head -1
```

Expected: `3 issues found`; der grep findet die gebaute ADR-Seite (der Anker existiert so, wie die Guides ihn verlinken; Zensical bildet Umlaute und Sonderzeichen so ab, wie die bestehenden Links auf `adr-022-betriebsumgebung-phase-1-und-modellherkunftsregel` zeigen). Zeigt der Build `4 issues found` oder mehr, ist ein Link in den neuen Seiten falsch — die Build-Ausgabe nennt ihn.

- [ ] **Step 5: Commit**

```bash
git add docs/guide/self-hosting.md docs/guide/releasing.md zensical.toml README.md docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md
git commit -s -m "docs: describe pulling, verifying and releasing the published images

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Live-Verifikation (nach PR und Merge, mit dem Nutzer)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md` (neuer Abschnitt `## Verifikation <Datum>` am Ende)

Dieser Task läuft nicht in einem Subagenten. Jeder Schritt, der einen Workflow auslöst, braucht vorher das ausdrückliche Ja des Nutzers.

- [ ] **Step 1: PR öffnen** (löst `CI` aus, nicht `Images`): Branch pushen, PR gegen `main` mit Verweis auf Spec und Plan. Erwartung: fünf grüne Jobs, `test-core` rot mit der bekannten DGUV-Signatur. Prüfen, dass `uv sync --frozen` in den Logs ohne „out of date" durchläuft.

- [ ] **Step 2: Merge durch den Nutzer.** Danach läuft `Images` zum ersten Mal auf `main`. Aus dem Lauf festhalten: Gesamtdauer, `df -h`-Ausgabe nach dem Aufräumen, Größe der fünf Images laut Summary, ob alle fünf Signaturen durchliefen.

- [ ] **Step 3: Pakete öffentlich stellen.** Nutzer stellt `api`, `chat`, `accounts`, `pipeline`, `frontend`, `cache` auf public. Anonyme Prüfung:

```bash
docker logout ghcr.io
docker manifest inspect ghcr.io/normly/web-app/api:edge | head -5
```

Expected: Manifest ohne Anmeldung lesbar.

- [ ] **Step 4: Signatur und Attestationen von außen prüfen**

```bash
curl -sSLo /tmp/cosign https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 && chmod +x /tmp/cosign
/tmp/cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/api:edge | head -3
docker buildx imagetools inspect ghcr.io/normly/web-app/api:edge --format '{{ json .SBOM }}' | head -c 300
```

Expected: `Verification for ghcr.io/normly/web-app/api:edge -- The following checks were performed …`; SBOM-JSON vorhanden.

- [ ] **Step 5: Pull-Weg ohne lokalen Build**

```bash
docker image rm $(docker images -q 'ghcr.io/normly/web-app/*') 2>/dev/null || true
docker compose pull && docker compose up -d
sleep 120 && docker compose ps -a && curl -fsS http://localhost:3000/ -o /dev/null && echo ok
docker compose down
```

Expected: Images kommen von GHCR (`Pulled`), Stack gesund.

- [ ] **Step 6: Release `v0.1.0`** (Nutzer-Ja): alle fünf Versionsfelder stehen bereits auf `0.1.0`.

```bash
git switch main && git pull
git tag -a v0.1.0 -m "normly 0.1.0" && git push origin v0.1.0
```

Expected: Lauf liefert `0.1.0`, `0.1`, `latest`, `sha-…`; Dauer deutlich unter Lauf 2 (Registry-Cache greift; Zahl notieren). `docker pull ghcr.io/normly/web-app/api:0.1.0` funktioniert.

- [ ] **Step 7: Negativprobe der Versionsprüfung** (Nutzer-Ja):

```bash
git tag v9.9.9 && git push origin v9.9.9
```

Expected: Lauf bricht im Schritt „Check that a release tag matches the package versions" ab, kein Build. Danach `git push origin :refs/tags/v9.9.9 && git tag -d v9.9.9`.

- [ ] **Step 8: Ergebnisse in die Spec schreiben und committen** (Abschnitt `## Verifikation 2026-MM-TT` mit den gemessenen Werten, Abweichungen und eventuellen Folgearbeiten; PR `docs: record TP2 verification results`).

---

## Self-Review

**Spec-Abdeckung:**

| Spec-Abschnitt | Task |
|---|---|
| D1 keyless Signatur, Verify-Aufruf | 5, 7 |
| D2 eine Version, Versionsprüfung, `v0.1.0` | 5 (Prüfung aller fünf Felder), 8 |
| D3 Auslöser nur main/Tags/manuell | 5 |
| D4 Lock-Datei, Torch-Index, gepinnte Gewichte in eigener Stufe | 1, 3 |
| Workflow: Berechtigungen, Plattenplatz, Bake, Cache, Attestationen, Summary | 4, 5 |
| Tagging-Tabelle | 5 |
| Öffentliche Pakete | 7 (releasing.md), 8 |
| Compose-Anbindung, `NORMLY_IMAGE_TAG` | 4 |
| uv-Workspace, Kommentare, Chat-E2E, `ci.yml`, CONTRIBUTING | 1, 2 |
| Dockerfile-Stufen, Digest-Pins, Docstring | 3 |
| ADR-023, SRS-Verweise | 6 |
| self-hosting.md, releasing.md, Navigation, README, Roadmap-Verweis | 7 |
| Verifikation 1–6 | 1–4 (lokal), 8 (live) |

**Abweichung von der Spec, bewusst:** Die Spec stellt in Aussicht, den CI-Ausschluss der Chat-End-to-End-Tests aufzuheben, falls sie grün laufen. Der Plan behält den Ausschluss: die Tests starten einen echten `api`-Prozess, der beim Start das e5-Modell lädt — in der CI ein 2-GB-Kaltstart-Download je Lauf, derselbe Mechanismus, der `test-core` rot hält. Der Kommentar in `ci.yml` nennt diesen Grund. Lokal laufen die Tests aus der gemeinsamen Umgebung (Task 1, Step 7).

**Typkonsistenz:** Bake-Variablen `REGISTRY`/`TAGS`/`CACHE_REF`/`PUSH` in Task 4 und 5 identisch; `ARG`-Namen in Task 3 nur dort verwendet; Image-Namen in Task 4, 5, 7 identisch; ADR-Anker `adr-023-image-pipeline-ghcr-keyless-signatur-eine-version-lock-datei` in Task 7 zweimal gleich und in Task 7 Step 4 gegen den Build geprüft.
