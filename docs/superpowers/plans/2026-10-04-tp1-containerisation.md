# Containerisation (TP1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five container images and a Compose setup that starts normly with one invocation — locally/self-hosting with bundled Postgres, Ollama and Mailpit, in production on the STACKIT VM against PostgreSQL Flex and STACKIT AI Model Serving.

**Architecture:** One multi-stage Dockerfile `docker/python.Dockerfile` with a shared stage `base` (all `core` dependencies plus baked-in e5 weights) and four target stages `api`, `chat`, `accounts`, `pipeline`; BuildKit shares the `base` layers between the four builds. The frontend has its own multi-stage Dockerfile (Next.js `standalone`). `compose.yaml` at the repository root uses profiles (`bundled`, `edge`, `tools`) to control which services run; migrations run as the one-off service `migrate` before the app services. In the chat service, a provider selection (`NORMLY_LLM_PROVIDER`) replaces the hard-wired Ollama client.

**Tech Stack:** Docker 29 / Compose 2.40 (Ubuntu packages `docker.io`, `docker-compose-v2`), `python:3.12-slim`, `node:22-alpine`, `pgvector/pgvector:pg17`, `ollama/ollama`, `axllent/mailpit`, `caddy:2`, httpx, Alembic, pytest, vitest.

Spec: `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md`. Roadmap with the fundamental decisions E1–E8: `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

## Global Constraints

- License header in every new source file: `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# Copyright (C) 2026 normly contributors` (Dockerfiles, Compose, shell, Python; in YAML/Dockerfile as a `#` comment, in TypeScript as `//`).
- Commits: Conventional Commits, English, `git commit -s` (the human's Signed-off-by) plus the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No push to `main`.
- No secrets in the repo, not even in `.env.example` or tests. `.env` is git-ignored.
- `core` keeps Docling and sentence-transformers as mandatory dependencies (owner decision, do not split).
- The embedding weights `intfloat/multilingual-e5-large` are loaded into the stage `base` at build time; at runtime no container may contact huggingface.co.
- All containers run as the unprivileged user `normly` (UID/GID 10001).
- Base images pinned by tag (`python:3.12-slim`, `node:22-alpine`, `pgvector/pgvector:pg17`, `caddy:2`, `axllent/mailpit:v1`, `ollama/ollama` to the minor tag current at implementation time); digest pinning comes with TP2.
- Only the frontend (or Caddy) is reachable from outside; `api`, `chat`, `accounts` publish no ports.
- Production model `google/gemma-4-31B-it`; development/self-hosting model: smallest Gemma variant in the Ollama library (Task 8 checks the tag).
- `docs/superpowers/`, CLAUDE.md and `docs/adr/`, `docs/srs/` stay German; `docs/guide/` and READMEs are English (ADR-020).
- The CI docs job expects exactly `3 issues found` from the Zensical build; new docs must not produce new link issues.

---

## Working mode: building and testing on the STACKIT VM (E8)

The images are built **on the VM**, not locally. The working tree is mirrored over via rsync (no GitHub access needed on the VM). Access details:

- VM: `ssh ubuntu@213.17.23.196` (this machine's key is installed).
- The production `.env` is on the VM at `/opt/normly/.env` (permissions 600, contains secrets — **never print it, never copy it, never quote it in logs**).
- Working tree on the VM: `/opt/normly/src`.

Sync command (from the development machine, from the repository root; captured as a script in Task 3):

```bash
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.next' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'test-results' \
  --exclude '.worktrees' --exclude 'site' --exclude '.env' \
  ./ ubuntu@213.17.23.196:/opt/normly/src/
```

Build/run commands are always executed as `ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose ...'`. Unit tests (pytest, vitest) still run **locally** in the existing `.venv`s or with `npm test`.

Python packages locally: `core/.venv`, `api/.venv`, `chat/.venv`, `accounts/.venv` (each `bin/pytest`). After changes to `core`, `core` does not need to be reinstalled in the dependent venvs (editable installs).

---

## File Structure

**New:**
- `.dockerignore` — keep the build context of the Python images lean.
- `.env.example` — documented template of all variables, without secrets.
- `docker/python.Dockerfile` — stages `base`, `api`, `chat`, `accounts`, `pipeline`.
- `docker/caddy/Caddyfile` — TLS termination, `reverse_proxy frontend:3000`.
- `frontend/Dockerfile`, `frontend/.dockerignore` — Next.js standalone.
- `compose.yaml` — all services, profiles, healthchecks, volumes.
- `scripts/sync-to-vm.sh` — rsync mirroring of the working tree to the VM (development tool for E8).
- `core/src/normly_core/migrate.py` — `python -m normly_core.migrate`: Alembic `upgrade head` from `NORMLY_DATABASE_URL`.
- `core/tests/test_migrate.py`.
- `chat/src/normly_chat/llm_client.py` — `LlmClient` protocol, `OpenAiCompatibleClient`, `build_llm_client_from_env`.
- `chat/tests/test_llm_client.py`.

**Changed:**
- `.gitignore` — `.env`, `data/`.
- `chat/src/normly_chat/main.py`, `dependencies.py`, `routers/chat.py`, `synthesis.py` — switch to `LlmClient`.
- `chat/tests/conftest.py`, `test_chat_router.py`, `test_structural_end_to_end.py` — new variable names.
- `docs/adr/README.md` — ADR-022, open item struck.
- `CLAUDE.md` — sentence on model origin.
- `docs/srs/03-requirements.md` — REQ-DIST-001, chapter 3.5.9.
- `docs/guide/self-hosting.md`, `docs/guide/getting-started.md` — actual Compose path.
- `frontend/README.md` — note on running with Compose.

---

### Task 1: Repository hygiene for container builds

**Files:**
- Create: `.dockerignore`
- Create: `frontend/.dockerignore`
- Modify: `.gitignore`

**Interfaces:**
- Produces: build contexts without venvs, `node_modules`, tests and docs; `.env` can sit in the repository root without ever being committed.

- [ ] **Step 1: Create `.dockerignore` at the root**

```
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Build context for docker/python.Dockerfile (context = repository root).
.git
.github
.worktrees
.superpowers
**/.venv
**/__pycache__
**/*.pyc
**/.pytest_cache
**/*.egg-info
**/tests
frontend
docs
site
.venv-docs
.env
.env.*
!.env.example
data
```

- [ ] **Step 2: Create `frontend/.dockerignore`**

```
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
node_modules
.next
test-results
tests
playwright.config.ts
vitest.config.ts
tsconfig.tsbuildinfo
Dockerfile
.dockerignore
```

- [ ] **Step 3: Extend `.gitignore`**

Append to the end of `.gitignore`:

```
.env
.env.*
!.env.example
data/
```

- [ ] **Step 4: Check**

Run: `touch .env && git check-ignore -v .env && rm .env && git check-ignore -v .env.example; echo "exit=$?"`
Expected: the first line names `.gitignore:…:.env`; `.env.example` is **not** ignored (`exit=1` for the second call).

- [ ] **Step 5: Commit**

```bash
git add .dockerignore frontend/.dockerignore .gitignore
git commit -s -m "build: add dockerignore files and ignore local env files

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `python -m normly_core.migrate` — migrations from the environment

`alembic.ini` has an empty `sqlalchemy.url`; today only the tests set the URL programmatically (`core/tests/conftest.py:50-53`). The `migrate` service needs the same path as a command.

**Files:**
- Create: `core/src/normly_core/migrate.py`
- Create: `core/tests/test_migrate.py`

**Interfaces:**
- Produces: `normly_core.migrate.upgrade_to_head(database_url: str, core_dir: Path) -> None`; `normly_core.migrate.main(argv: list[str] | None = None) -> int`; environment variables `NORMLY_DATABASE_URL` (required) and `NORMLY_CORE_DIR` (default `/app/core`, directory with `alembic.ini` and `migrations/`). Exit 0 on success, 1 on missing configuration.

- [ ] **Step 1: Check fixture names in `core/tests/conftest.py`**

Run: `grep -n "def db_url\|def postgres_container\|CORE_DIR" core/tests/conftest.py`
Expected: fixture `db_url` (session-scoped, line 44) and `CORE_DIR = Path(__file__).parents[1]` (line 13) — both verified on 2026-10-04; the test below uses `db_url` and defines `CORE_DIR` itself.

- [ ] **Step 2: Write the failing test**

`core/tests/test_migrate.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

# core/tests has no __init__.py, so conftest constants are not importable;
# same definition as core/tests/conftest.py:13.
CORE_DIR = Path(__file__).resolve().parents[1]


def _alembic_head() -> str:
    cfg = Config(str(CORE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _run_migrate(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**os.environ, **env}, capture_output=True, text=True, timeout=300,
    )


def test_migrate_module_upgrades_to_head_and_is_idempotent(db_url):
    env = {"NORMLY_DATABASE_URL": db_url, "NORMLY_CORE_DIR": str(CORE_DIR)}

    first = _run_migrate(env)
    assert first.returncode == 0, first.stderr
    assert "migrations: at head" in first.stdout

    second = _run_migrate(env)
    assert second.returncode == 0, second.stderr

    engine = create_engine(db_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()
    assert version == _alembic_head()


def test_migrate_module_fails_without_database_url():
    env = {k: v for k, v in os.environ.items() if k != "NORMLY_DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**env, "NORMLY_CORE_DIR": str(CORE_DIR)}, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "NORMLY_DATABASE_URL" in result.stderr


def test_migrate_module_fails_when_core_dir_has_no_alembic_ini(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**os.environ, "NORMLY_DATABASE_URL": "postgresql+psycopg://x:y@localhost:1/z",
             "NORMLY_CORE_DIR": str(tmp_path)},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "alembic.ini" in result.stderr
```

- [ ] **Step 3: Run the test, confirm the failure**

Run: `cd core && .venv/bin/pytest tests/test_migrate.py -v`
Expected: FAIL — `No module named normly_core.migrate` (returncode 1, but without the expected messages).

- [ ] **Step 4: Implement the module**

`core/src/normly_core/migrate.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Run the Alembic migrations to head from environment configuration.

`alembic.ini` deliberately leaves `sqlalchemy.url` empty so no connection
string is ever committed; tests inject the URL programmatically
(core/tests/conftest.py). This module is the same injection as a command,
for the Compose `migrate` one-shot service and for operators:

    NORMLY_DATABASE_URL=postgresql+psycopg://... python -m normly_core.migrate

Idempotent: a second run against a migrated database is a no-op.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

DATABASE_URL_ENV_VAR = "NORMLY_DATABASE_URL"
#: Directory holding `alembic.ini` and `migrations/`; the container image
#: copies `core/` to /app/core, local runs point this at the checkout.
CORE_DIR_ENV_VAR = "NORMLY_CORE_DIR"
DEFAULT_CORE_DIR = Path("/app/core")


def upgrade_to_head(database_url: str, core_dir: Path) -> None:
    config = Config(str(core_dir / "alembic.ini"))
    config.set_main_option("script_location", str(core_dir / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def main(argv: list[str] | None = None) -> int:
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if not database_url:
        print(f"{DATABASE_URL_ENV_VAR} environment variable is required", file=sys.stderr)
        return 1
    core_dir = Path(os.environ.get(CORE_DIR_ENV_VAR, DEFAULT_CORE_DIR))
    if not (core_dir / "alembic.ini").is_file():
        print(
            f"no alembic.ini in {core_dir} (set {CORE_DIR_ENV_VAR} to the core/ directory)",
            file=sys.stderr,
        )
        return 1
    upgrade_to_head(database_url, core_dir)
    print("migrations: at head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests**

Run: `cd core && .venv/bin/pytest tests/test_migrate.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/migrate.py core/tests/test_migrate.py
git commit -s -m "feat(core): add python -m normly_core.migrate for env-driven alembic upgrade

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Python base stage with baked-in embedding weights, sync script, Docker on the VM

**Files:**
- Create: `docker/python.Dockerfile` (only stage `base` in this task)
- Create: `scripts/sync-to-vm.sh`

**Interfaces:**
- Produces: stage `base` with `normly-core` installed, `libgl1`, user `normly` (10001), `ENV NORMLY_EMBEDDING_MODEL_PATH=/opt/models/multilingual-e5-large`, weights under this path, `WORKDIR /app`, `core/` under `/app/core`. Later stages build with `FROM base AS <name>`.

- [ ] **Step 1: Install Docker and Compose on the VM**

Run:
```bash
ssh ubuntu@213.17.23.196 'sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 && sudo usermod -aG docker ubuntu && sudo systemctl enable --now docker'
ssh ubuntu@213.17.23.196 'docker --version && docker compose version && mkdir -p /opt/normly/src'
```
Expected: `Docker version 29.x`, `Docker Compose version v2.40.x`. The group change takes effect at the next SSH session (every `ssh` call is a new session).

- [ ] **Step 2: Create the sync script**

`scripts/sync-to-vm.sh`:

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Mirror the working tree to the STACKIT VM for building images there
# (roadmap decision E8). Never syncs .env or build artefacts.
#
# Usage: scripts/sync-to-vm.sh [user@host]   (default: ubuntu@213.17.23.196)
set -euo pipefail

TARGET="${1:-ubuntu@213.17.23.196}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.next' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'test-results' \
  --exclude '.worktrees' --exclude '.superpowers' --exclude 'site' \
  --exclude '.env' --exclude 'data' \
  "$REPO_ROOT/" "$TARGET:/opt/normly/src/"

echo "synced to $TARGET:/opt/normly/src"
```

Run: `chmod +x scripts/sync-to-vm.sh && scripts/sync-to-vm.sh`
Expected: `synced to ubuntu@213.17.23.196:/opt/normly/src`.

- [ ] **Step 3: Write stage `base`**

`docker/python.Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# One Dockerfile, five targets. `base` carries every core/ dependency plus
# the embedding weights; api/chat/accounts/pipeline add only their own
# package on top, so BuildKit shares the heavy layers between them.
# Build context: repository root.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    NORMLY_EMBEDDING_MODEL_PATH=/opt/models/multilingual-e5-large

# libgl1/libglib2.0-0: transitive runtime needs of docling -> opencv.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 normly \
    && useradd --uid 10001 --gid normly --create-home --shell /usr/sbin/nologin normly

WORKDIR /app

# 1) Dependencies only, read from core/pyproject.toml so the list never
#    drifts from the package metadata. Cached until pyproject.toml changes.
COPY core/pyproject.toml /tmp/core-pyproject.toml
RUN python - <<'PY' > /tmp/core-requirements.txt
import tomllib
with open("/tmp/core-pyproject.toml", "rb") as f:
    for dep in tomllib.load(f)["project"]["dependencies"]:
        print(dep)
PY
RUN pip install -r /tmp/core-requirements.txt

# 2) Embedding weights, fetched once at build time (the only moment
#    huggingface.co is contacted). Cached until the model name changes.
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("intfloat/multilingual-e5-large").save("/opt/models/multilingual-e5-large")
PY

# 3) The core package itself (code, alembic.ini, migrations). Changes here
#    only rebuild from this layer on.
COPY core /app/core
RUN pip install --no-deps /app/core \
    && chown -R normly:normly /opt/models /app
```

- [ ] **Step 4: Build and check on the VM**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && DOCKER_BUILDKIT=1 docker build -f docker/python.Dockerfile --target base -t normly-python-base:local . 2>&1 | tail -5'
ssh ubuntu@213.17.23.196 'docker image ls normly-python-base:local --format "{{.Size}}" && docker run --rm --network none normly-python-base:local python -c "
import os
from normly_core.pipeline.embeddings import EmbeddingModel
m = EmbeddingModel()
print(\"whoami\", os.getuid(), \"model path\", os.environ[\"NORMLY_EMBEDDING_MODEL_PATH\"])
print(\"dim\", len(m.embed_query(\"Test\")))
"'
```
Expected: the build finishes successfully (the first build takes 10–20 minutes because of Torch and 2.2 GB of weights); size in the range of 6–8 GB; the run with `--network none` prints `dim 1024` — this proves that the weights come from the image, not from the network. `whoami 0` is still fine here (USER comes in the target stages). If `embed_query` has a different name: `grep -n "def " core/src/normly_core/pipeline/embeddings.py` and use the matching method.

- [ ] **Step 5: Commit**

```bash
git add docker/python.Dockerfile scripts/sync-to-vm.sh
git commit -s -m "build: add shared python base image stage with baked-in embedding weights

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Target stages `api`, `chat`, `accounts`

**Files:**
- Modify: `docker/python.Dockerfile` (append)

**Interfaces:**
- Consumes: stage `base` from Task 3.
- Produces: images that start with `uvicorn normly_<svc>.main:app --host 0.0.0.0 --port 8000`, as user `normly`, port 8000. The images expect `NORMLY_DATABASE_URL` (all), `NORMLY_API_BASE_URL`/`NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_LLM_*` (chat), `NORMLY_SMTP_*`/`NORMLY_PUBLIC_BASE_URL`/`NORMLY_GOOGLE_*` (accounts, optional).

- [ ] **Step 1: Append the stages**

Append to `docker/python.Dockerfile`:

```dockerfile

# ---------------------------------------------------------------------------
FROM base AS api
COPY api /app/api
# normly-core is already installed from /app/core above, so pip resolves the
# `normly-core` requirement locally and never asks an index for it.
RUN pip install /app/api && chown -R normly:normly /app/api
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS chat
COPY chat /app/chat
RUN pip install /app/chat && chown -R normly:normly /app/chat
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_chat.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS accounts
COPY accounts /app/accounts
RUN pip install /app/accounts && chown -R normly:normly /app/accounts
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_accounts.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build and check that `normly-core` was not loaded from an index**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && for t in api chat accounts; do docker build -f docker/python.Dockerfile --target $t -t normly-$t:local --progress=plain . 2>&1 | tee /tmp/build-$t.log | tail -2; grep -i "downloading normly" /tmp/build-$t.log && echo "!! normly-core came from an index" || echo "ok: normly-core resolved locally ($t)"; done'
ssh ubuntu@213.17.23.196 'for t in api chat accounts; do docker run --rm --network none normly-$t:local python -c "import os, importlib; importlib.import_module(\"normly_$t.main\"); print(\"$t import ok, uid\", os.getuid())"; done'
```
Expected: three successful builds, each `ok: normly-core resolved locally`, import checks print `uid 10001`. The three builds may reuse the `base` layers (`CACHED` in the log for the base steps).

- [ ] **Step 3: Commit**

```bash
git add docker/python.Dockerfile
git commit -s -m "build: add api, chat and accounts image stages

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Target stage `pipeline` (migrations, ingestion, Docling models)

**Files:**
- Modify: `docker/python.Dockerfile` (append)

**Interfaces:**
- Consumes: stage `base`; `python -m normly_core.migrate` from Task 2.
- Produces: image with `ENTRYPOINT ["python", "-m", "normly_core.pipeline"]`, `ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling`, `ENV NORMLY_CORE_DIR=/app/core`; migrations via `--entrypoint python … -m normly_core.migrate`.

- [ ] **Step 1: Append the stage**

```dockerfile

# ---------------------------------------------------------------------------
FROM base AS pipeline
ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
    NORMLY_CORE_DIR=/app/core
# Docling's layout/tableformer models, fetched at build time only (see
# core/src/normly_core/pipeline/docling_extraction.py for why runtime
# downloads are not acceptable in production).
RUN docling-tools models download layout tableformer -o /opt/models/docling \
    && chown -R normly:normly /opt/models/docling
USER normly
ENTRYPOINT ["python", "-m", "normly_core.pipeline"]
```

- [ ] **Step 2: Build and check both entry points**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker build -f docker/python.Dockerfile --target pipeline -t normly-pipeline:local . 2>&1 | tail -2'
ssh ubuntu@213.17.23.196 'docker run --rm --network none normly-pipeline:local --help | head -5; docker run --rm --network none --entrypoint python normly-pipeline:local -m normly_core.migrate; echo "migrate exit=$?"; docker run --rm --network none normly-pipeline:local ingest dguv --directory /nonexistent; echo "ingest exit=$?"'
```
Expected: `--help` shows the subcommands `ingest`, `backfill-document-embeddings`, …; `migrate` ends with `exit=1` and the message `NORMLY_DATABASE_URL environment variable is required` (no URL set, intended); `ingest` ends with `exit=1` and the same message. No traceback output.

- [ ] **Step 3: Load the Docling models offline**

Run:
```bash
ssh ubuntu@213.17.23.196 'docker run --rm --network none --entrypoint python normly-pipeline:local -c "
import os
from normly_core.pipeline.docling_extraction import _get_converter
_get_converter(os.environ[\"NORMLY_DOCLING_ARTIFACTS_PATH\"])
print(\"docling converter built offline\")
"'
```
Expected: `docling converter built offline`. If the call fails because of missing models, read from the error message which model is missing and add it to the download list in Step 1 (e.g. `rapidocr` or `easyocr`, if OCR is enabled).

Known and **not** part of this task: with freshly loaded Docling models, the DGUV title detection returns `None` in two tests (see `docs/superpowers/specs/2026-09-02-ci-pipeline-design.md`, Open items). This concerns ingestion quality, not the container.

- [ ] **Step 4: Commit**

```bash
git add docker/python.Dockerfile
git commit -s -m "build: add pipeline image stage with docling models and migrate entrypoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Frontend image (Next.js standalone)

**Files:**
- Create: `frontend/Dockerfile`

**Interfaces:**
- Produces: image `normly-frontend:local`, port 3000, `node server.js`, user `normly`; reads `NORMLY_API_BASE_URL`, `NORMLY_ACCOUNTS_BASE_URL`, `NORMLY_CHAT_BASE_URL`, `NORMLY_PUBLIC_BASE_URL`, optionally `NORMLY_INSTANCE_NAME`, `NORMLY_BRAND_COLOR_HSL`, `NORMLY_LOGO_PATH` at runtime (`frontend/README.md`).

- [ ] **Step 1: Write the Dockerfile**

`frontend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Next.js `output: "standalone"` (next.config.ts): the runtime stage ships
# only server.js, the pruned node_modules Next traces, static assets and
# public/. Configuration is read per request from process.env, so one image
# serves any instance (ADR-010). Build context: frontend/.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -g 10001 normly && adduser -D -u 10001 -G normly normly
COPY --from=build --chown=normly:normly /app/.next/standalone ./
COPY --from=build --chown=normly:normly /app/.next/static ./.next/static
COPY --from=build --chown=normly:normly /app/public ./public
USER normly
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 2: Build and start**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src/frontend && docker build -t normly-frontend:local . 2>&1 | tail -2 && docker image ls normly-frontend:local --format "{{.Size}}"'
ssh ubuntu@213.17.23.196 'cid=$(docker run -d --rm -p 127.0.0.1:3100:3000 -e NORMLY_API_BASE_URL=http://api:8000 -e NORMLY_ACCOUNTS_BASE_URL=http://accounts:8000 -e NORMLY_CHAT_BASE_URL=http://chat:8000 -e NORMLY_PUBLIC_BASE_URL=http://localhost:3100 normly-frontend:local); sleep 4; curl -s -o /dev/null -w "frontend http=%{http_code}\n" http://127.0.0.1:3100/; curl -s http://127.0.0.1:3100/manifest.webmanifest | head -c 120; echo; docker exec $cid id -u; docker stop $cid >/dev/null'
```
Expected: build successful, size under 300 MB; `frontend http=200`; the manifest JSON is served (proves the `public/` copy); `id -u` = `10001`.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -s -m "build(frontend): add multi-stage Dockerfile for Next.js standalone output

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: LLM client selection in the chat service (`NORMLY_LLM_*`)

Today: `OllamaClient(base_url, model)` hard-wired in `chat/src/normly_chat/main.py:37-40`, variables `NORMLY_OLLAMA_BASE_URL`/`NORMLY_OLLAMA_MODEL`. Goal: protocol `LlmClient`, a second client for the OpenAI-compatible API of STACKIT AI Model Serving, selection via `NORMLY_LLM_PROVIDER`.

**Files:**
- Create: `chat/src/normly_chat/llm_client.py`
- Create: `chat/tests/test_llm_client.py`
- Modify: `chat/src/normly_chat/main.py:18,37-40`
- Modify: `chat/src/normly_chat/dependencies.py:13,35-36`
- Modify: `chat/src/normly_chat/routers/chat.py:21,23,39,63`
- Modify: `chat/src/normly_chat/synthesis.py:68-69,81,95,101`
- Modify: `chat/tests/conftest.py:86,132-135`, `chat/tests/test_chat_router.py:40`, `chat/tests/test_structural_end_to_end.py:143`

**Interfaces:**
- Produces: `normly_chat.llm_client.LlmClient` (Protocol with `chat(messages: list[dict]) -> str`), `OpenAiCompatibleClient(base_url: str, model: str, api_key: str, *, timeout: float = 120.0, transport: httpx.BaseTransport | None = None)`, `build_llm_client_from_env(environ: Mapping[str, str] = os.environ) -> LlmClient`; `app.state.llm_client`; `dependencies.get_llm_client`. Variables: `NORMLY_LLM_PROVIDER` (`ollama` | `openai-compatible`, default `ollama`), `NORMLY_LLM_BASE_URL` (required), `NORMLY_LLM_MODEL` (required), `NORMLY_LLM_API_KEY` (required only with `openai-compatible`).
- `OllamaClient` stays unchanged; `SynthesisAnswer.ollama_calls` keeps its name (public response field, no renaming in this task).

- [ ] **Step 1: Write the failing tests**

`chat/tests/test_llm_client.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json

import httpx
import pytest

from normly_chat.llm_client import OpenAiCompatibleClient, build_llm_client_from_env
from normly_chat.ollama_client import OllamaClient


def _transport(handler):
    return httpx.MockTransport(handler)


def test_openai_compatible_client_posts_chat_completions_and_returns_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "Antwort"}}],
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1/", "google/gemma-4-31B-it", "secret-token",
        transport=_transport(handler),
    )
    answer = client.chat([{"role": "user", "content": "Frage"}])

    assert answer == "Antwort"
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["body"]["model"] == "google/gemma-4-31B-it"
    assert seen["body"]["messages"] == [{"role": "user", "content": "Frage"}]
    assert seen["body"]["stream"] is False


def test_openai_compatible_client_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = OpenAiCompatibleClient("https://llm.example/v1", "m", "t", transport=_transport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.chat([{"role": "user", "content": "x"}])


def test_build_from_env_defaults_to_ollama():
    client = build_llm_client_from_env({
        "NORMLY_LLM_BASE_URL": "http://ollama:11434", "NORMLY_LLM_MODEL": "gemma3:4b",
    })
    assert isinstance(client, OllamaClient)


def test_build_from_env_selects_openai_compatible_with_api_key():
    client = build_llm_client_from_env({
        "NORMLY_LLM_PROVIDER": "openai-compatible",
        "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
        "NORMLY_LLM_MODEL": "google/gemma-4-31B-it",
        "NORMLY_LLM_API_KEY": "t",
    })
    assert isinstance(client, OpenAiCompatibleClient)


def test_build_from_env_requires_api_key_for_openai_compatible():
    with pytest.raises(KeyError, match="NORMLY_LLM_API_KEY"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "openai-compatible",
            "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
            "NORMLY_LLM_MODEL": "m",
        })


def test_build_from_env_rejects_unknown_provider():
    with pytest.raises(ValueError, match="NORMLY_LLM_PROVIDER"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "anthropic",
            "NORMLY_LLM_BASE_URL": "x", "NORMLY_LLM_MODEL": "m",
        })
```

- [ ] **Step 2: Confirm the failure**

Run: `cd chat && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: FAIL — `No module named normly_chat.llm_client`.

- [ ] **Step 3: Implement the module**

`chat/src/normly_chat/llm_client.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
LLM client selection.

Two providers behind one tiny interface: Ollama for local development and
self-hosting, and any OpenAI-compatible `/chat/completions` endpoint for
production -- concretely STACKIT AI Model Serving (ADR-022). Both are thin
httpx wrappers; no vendor SDK, same reasoning as OllamaClient.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol

import httpx

from normly_chat.ollama_client import OllamaClient

PROVIDER_ENV_VAR = "NORMLY_LLM_PROVIDER"
BASE_URL_ENV_VAR = "NORMLY_LLM_BASE_URL"
MODEL_ENV_VAR = "NORMLY_LLM_MODEL"
API_KEY_ENV_VAR = "NORMLY_LLM_API_KEY"

PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI_COMPATIBLE = "openai-compatible"


class LlmClient(Protocol):
    def chat(self, messages: list[dict]) -> str: ...


class OpenAiCompatibleClient:
    """POST {base_url}/chat/completions with a bearer token; returns the first choice."""

    def __init__(
        self, base_url: str, model: str, api_key: str, *,
        timeout: float = 120.0, transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    def chat(self, messages: list[dict]) -> str:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
            response = http.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "stream": False},
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def build_llm_client_from_env(environ: Mapping[str, str] = os.environ) -> LlmClient:
    provider = environ.get(PROVIDER_ENV_VAR, PROVIDER_OLLAMA)
    base_url = environ[BASE_URL_ENV_VAR]
    model = environ[MODEL_ENV_VAR]
    if provider == PROVIDER_OLLAMA:
        return OllamaClient(base_url=base_url, model=model)
    if provider == PROVIDER_OPENAI_COMPATIBLE:
        return OpenAiCompatibleClient(base_url, model, environ[API_KEY_ENV_VAR])
    raise ValueError(
        f"{PROVIDER_ENV_VAR} must be {PROVIDER_OLLAMA!r} or {PROVIDER_OPENAI_COMPATIBLE!r}, "
        f"got {provider!r}"
    )
```

- [ ] **Step 4: Run the tests**

Run: `cd chat && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: 6 passed.

- [ ] **Step 5: Switch the wiring**

`chat/src/normly_chat/main.py`: replace the import `from normly_chat.ollama_client import OllamaClient` with `from normly_chat.llm_client import build_llm_client_from_env`; replace the lines

```python
    app.state.ollama_client = OllamaClient(
        base_url=os.environ["NORMLY_OLLAMA_BASE_URL"],
        model=os.environ.get("NORMLY_OLLAMA_MODEL", "llama3.1:8b-instruct-q4_0"),
    )
```

with

```python
    app.state.llm_client = build_llm_client_from_env()
```

`chat/src/normly_chat/dependencies.py`: replace the import `OllamaClient` with `from normly_chat.llm_client import LlmClient`; rename the function:

```python
def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client
```

`chat/src/normly_chat/routers/chat.py`: in the import, `get_ollama_client` → `get_llm_client`; `from normly_chat.ollama_client import OllamaClient` → `from normly_chat.llm_client import LlmClient`; parameter `ollama_client: OllamaClient = Depends(get_ollama_client)` → `llm_client: LlmClient = Depends(get_llm_client)`; call `build_synthesis_answer(..., PostgresSegmentRepository(session), ollama_client,)` → `llm_client`.

`chat/src/normly_chat/synthesis.py`: parameter `ollama_client` in `_is_faithful` and `build_synthesis_answer` → `llm_client` (only the parameter name and its uses in lines 68–69, 81, 95, 101; the field `ollama_calls` stays).

- [ ] **Step 6: Switch the tests to the new variables**

In `chat/tests/conftest.py` (fixture `client`, line 86), replace:

```python
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("NORMLY_LLM_MODEL", "test-model")
```

In the same file (fixture `e2e_client`, lines 132–135), replace:

```python
    monkeypatch.setenv("NORMLY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", os.environ["NORMLY_TEST_OLLAMA_BASE_URL"])
    monkeypatch.setenv(
        "NORMLY_LLM_MODEL", os.environ.get("NORMLY_TEST_OLLAMA_MODEL", "gemma3:4b"),
    )
```

In `chat/tests/test_chat_router.py:40` and `chat/tests/test_structural_end_to_end.py:143`, replace the line `monkeypatch.setenv("NORMLY_OLLAMA_BASE_URL", …)` with the two lines `NORMLY_LLM_BASE_URL` (same value) and `NORMLY_LLM_MODEL` = `"test-model"`.

In `chat/tests/test_ollama_client.py:20`, replace the default `"llama3.1:8b-instruct-q4_0"` with `"gemma3:4b"` (test variables `NORMLY_TEST_OLLAMA_*` keep their names).

Run: `grep -rn "NORMLY_OLLAMA_\|get_ollama_client\|ollama_client" chat/src chat/tests | grep -v "^chat/src/normly_chat/ollama_client.py" | grep -v "_FakeOllamaClient\|ollama_calls"`
Expected: no matches in `chat/src`; in tests only `test_synthesis.py`, where `_FakeOllamaClient` is used as a keyword argument name — check there whether `build_synthesis_answer` is called positionally (yes, lines 42, 73, 99, 160); then no changes are needed.

- [ ] **Step 7: Full chat suite**

Run: `cd chat && .venv/bin/pytest -q`
Expected: all tests green (the Ollama-dependent ones stay `skipped` as long as `NORMLY_TEST_OLLAMA_BASE_URL` is not set).

- [ ] **Step 8: Commit**

```bash
git add chat/src/normly_chat/llm_client.py chat/tests/test_llm_client.py chat/src/normly_chat/main.py chat/src/normly_chat/dependencies.py chat/src/normly_chat/routers/chat.py chat/src/normly_chat/synthesis.py chat/tests/conftest.py chat/tests/test_chat_router.py chat/tests/test_structural_end_to_end.py chat/tests/test_ollama_client.py
git commit -s -m "feat(chat): select LLM provider via NORMLY_LLM_*, add OpenAI-compatible client

Adds a second thin httpx client for OpenAI-compatible chat/completions
endpoints (STACKIT AI Model Serving in production) behind a shared
LlmClient protocol. Replaces the hard-wired Ollama construction and the
NORMLY_OLLAMA_* variables; the Llama default model is dropped per the
model-provenance rule (ADR-022).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: `compose.yaml`, `.env.example`, Caddyfile

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `docker/caddy/Caddyfile`

**Interfaces:**
- Consumes: images/targets from Tasks 3–6; `python -m normly_core.migrate` (Task 2); `NORMLY_LLM_*` (Task 7).
- Produces: `docker compose up` starts the instance depending on `COMPOSE_PROFILES`. Profiles: `bundled` (postgres, ollama, ollama-pull, mailpit), `edge` (caddy), `tools` (pipeline, only via `run`). Internal hostnames: `postgres`, `ollama`, `mailpit`, `api`, `chat`, `accounts`, `frontend`, with ports 5432/11434/1025/8000/8000/8000/3000 respectively.

- [ ] **Step 1: Determine the Ollama model tag**

Run: `curl -s -o /dev/null -w "gemma4 %{http_code}\n" https://ollama.com/library/gemma4; curl -s -o /dev/null -w "gemma3 %{http_code}\n" https://ollama.com/library/gemma3`
Expected: if `gemma4 200`, the development model is the smallest variant on that page (read the tag from the page, e.g. `gemma4:<smallest>b`); otherwise `gemma3:4b`. Enter the chosen tag in `.env.example` (Step 3) and in `chat/tests/conftest.py`/`test_ollama_client.py` (Task 7, if it differs from `gemma3:4b`).

- [ ] **Step 2: Pin the image tags**

Run: `for i in ollama/ollama axllent/mailpit caddy pgvector/pgvector; do echo "== $i"; curl -s "https://hub.docker.com/v2/repositories/$( [[ $i == */* ]] && echo $i || echo library/$i )/tags?page_size=20&ordering=last_updated" | python3 -c "import sys,json; print(', '.join(t['name'] for t in json.load(sys.stdin)['results'][:12]))"; done`
Expected: tag lists. Choose: `pgvector/pgvector:pg17`, `caddy:2`, `axllent/mailpit:v1` (if no `v1` umbrella tag exists, the current `v1.x.y`), `ollama/ollama:<current minor tag, e.g. 0.13>` (not `latest`). Enter the chosen tags in Step 3.

- [ ] **Step 3: Write `compose.yaml`**

```yaml
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# One `docker compose up` starts a working normly instance (REQ-DIST-004).
# Profiles decide what is bundled:
#   bundled  postgres + ollama + mailpit  (self-hosting / development)
#   edge     caddy with automatic TLS     (production on a public host)
#   tools    pipeline (ingestion), run on demand with `docker compose run`
# Configuration comes from .env (copy .env.example). Secrets never live here.

name: normly

x-python-build: &python-build
  context: .
  dockerfile: docker/python.Dockerfile

x-backend-healthcheck: &backend-healthcheck
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=5)"]
  interval: 15s
  timeout: 10s
  retries: 20
  start_period: 90s   # api/chat load the embedding model at startup

services:
  postgres:
    image: pgvector/pgvector:pg17
    profiles: ["bundled"]
    environment:
      POSTGRES_DB: normly
      POSTGRES_USER: normly
      POSTGRES_PASSWORD: ${NORMLY_BUNDLED_POSTGRES_PASSWORD:?set NORMLY_BUNDLED_POSTGRES_PASSWORD in .env}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U normly -d normly"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped

  ollama:
    image: ollama/ollama:0.13        # pin per Task 8 Step 2
    profiles: ["bundled"]
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped

  ollama-pull:
    image: ollama/ollama:0.13        # same tag as `ollama`
    profiles: ["bundled"]
    depends_on:
      - ollama
    environment:
      OLLAMA_HOST: http://ollama:11434
    entrypoint: ["/bin/sh", "-c"]
    command: ["ollama pull \"$$NORMLY_LLM_MODEL\""]
    env_file: .env
    restart: "no"

  mailpit:
    image: axllent/mailpit:v1
    profiles: ["bundled"]
    ports:
      - "${NORMLY_MAILPIT_BIND:-127.0.0.1}:8025:8025"
    restart: unless-stopped

  migrate:
    build:
      <<: *python-build
      target: pipeline
    image: normly-pipeline:local
    entrypoint: ["python", "-m", "normly_core.migrate"]
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
        required: false            # absent when the bundled profile is off
    restart: "no"

  api:
    build:
      <<: *python-build
      target: api
    image: normly-api:local
    env_file: .env
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck: *backend-healthcheck
    restart: unless-stopped

  accounts:
    build:
      <<: *python-build
      target: accounts
    image: normly-accounts:local
    env_file: .env
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck: *backend-healthcheck
    restart: unless-stopped

  chat:
    build:
      <<: *python-build
      target: chat
    image: normly-chat:local
    env_file: .env
    environment:
      NORMLY_API_BASE_URL: http://api:8000
      NORMLY_ACCOUNTS_BASE_URL: http://accounts:8000
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck: *backend-healthcheck
    restart: unless-stopped

  frontend:
    build:
      context: frontend
    image: normly-frontend:local
    env_file: .env
    environment:
      NORMLY_API_BASE_URL: http://api:8000
      NORMLY_ACCOUNTS_BASE_URL: http://accounts:8000
      NORMLY_CHAT_BASE_URL: http://chat:8000
    ports:
      - "${NORMLY_FRONTEND_BIND:-127.0.0.1}:3000:3000"
    depends_on:
      api:
        condition: service_healthy
      accounts:
        condition: service_healthy
      chat:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO", "/dev/null", "http://127.0.0.1:3000/"]
      interval: 15s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  caddy:
    image: caddy:2
    profiles: ["edge"]
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      NORMLY_PUBLIC_HOST: ${NORMLY_PUBLIC_HOST:?set NORMLY_PUBLIC_HOST (e.g. app.example.org) for the edge profile}
    volumes:
      - ./docker/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - frontend
    restart: unless-stopped

  pipeline:
    build:
      <<: *python-build
      target: pipeline
    image: normly-pipeline:local
    profiles: ["tools"]
    env_file: .env
    volumes:
      - ./data:/data
    restart: "no"

volumes:
  postgres-data:
  ollama-data:
  caddy-data:
  caddy-config:
```

Notes on the file: `$$NORMLY_LLM_MODEL` (double dollar) makes Compose **not** substitute the variable itself but pass it through to the shell in the container, which gets it from `env_file`. `required: false` in `depends_on` needs Compose ≥ 2.20 (the VM has 2.40).

- [ ] **Step 4: Write `.env.example`**

```
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Copy to .env and adjust. Self-hosting defaults below start everything
# bundled (database, LLM, mail catcher) with `docker compose up`.
# Production on a public host: COMPOSE_PROFILES=edge, point
# NORMLY_DATABASE_URL at a managed PostgreSQL with pgvector, set the LLM
# provider to your OpenAI-compatible endpoint, set NORMLY_PUBLIC_HOST.
# Never commit .env.

# --- Profiles -------------------------------------------------------------
# bundled: postgres + ollama + mailpit | edge: caddy with TLS | both: "bundled,edge"
COMPOSE_PROFILES=bundled

# --- Database -------------------------------------------------------------
# Bundled postgres (profile bundled) uses this password; the URL must match.
NORMLY_BUNDLED_POSTGRES_PASSWORD=change-me
NORMLY_DATABASE_URL=postgresql+psycopg://normly:change-me@postgres:5432/normly
# Managed database instead (TLS enforced), e.g.:
# NORMLY_DATABASE_URL=postgresql+psycopg://user:password@host:5432/normly?sslmode=require

# --- LLM ------------------------------------------------------------------
# ollama (bundled, CPU, small model) or openai-compatible (hosted endpoint).
NORMLY_LLM_PROVIDER=ollama
NORMLY_LLM_BASE_URL=http://ollama:11434
NORMLY_LLM_MODEL=gemma3:4b
# openai-compatible example (STACKIT AI Model Serving):
# NORMLY_LLM_PROVIDER=openai-compatible
# NORMLY_LLM_BASE_URL=https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1
# NORMLY_LLM_MODEL=google/gemma-4-31B-it
# NORMLY_LLM_API_KEY=

# --- Frontend / public URL ------------------------------------------------
# URL users reach the instance at; used in e-mails and OAuth redirects.
NORMLY_PUBLIC_BASE_URL=http://localhost:3000
# Interface the frontend port is published on. 127.0.0.1 when caddy (edge)
# fronts it; 0.0.0.0 to reach it directly on a LAN/self-hosting box.
NORMLY_FRONTEND_BIND=0.0.0.0
# Hostname for the edge profile's TLS certificate (Let's Encrypt).
# NORMLY_PUBLIC_HOST=app.example.org
# Optional branding (see frontend/README.md)
# NORMLY_INSTANCE_NAME=normly
# NORMLY_BRAND_COLOR_HSL=222 89% 55%
# NORMLY_LOGO_PATH=

# --- Mail -----------------------------------------------------------------
# Bundled mail catcher (profile bundled): UI at http://localhost:8025
NORMLY_SMTP_HOST=mailpit
NORMLY_SMTP_PORT=1025
NORMLY_SMTP_FROM=noreply@normly.localhost
# Real relay (STARTTLS is used as soon as a username is set):
# NORMLY_SMTP_HOST=smtp.example.org
# NORMLY_SMTP_PORT=587
# NORMLY_SMTP_USERNAME=
# NORMLY_SMTP_PASSWORD=
# NORMLY_MAILPIT_BIND=127.0.0.1

# --- Google OAuth (optional) ----------------------------------------------
# NORMLY_GOOGLE_CLIENT_ID=
# NORMLY_GOOGLE_CLIENT_SECRET=
# Must be <NORMLY_PUBLIC_BASE_URL>/api/auth/google/callback (frontend/README.md)
# NORMLY_GOOGLE_REDIRECT_URI=
```

- [ ] **Step 5: Write the Caddyfile**

`docker/caddy/Caddyfile`:

```
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Edge profile: terminate TLS (automatic Let's Encrypt) and hand everything
# to the frontend, which is the only service meant to be reachable. The
# backends stay on the internal network.
{$NORMLY_PUBLIC_HOST} {
	encode zstd gzip
	reverse_proxy frontend:3000
}
```

- [ ] **Step 6: Syntax check locally**

Run: `cp .env.example .env && docker compose config --quiet && echo "compose config ok" && docker compose --profile edge config --quiet; echo "edge exit=$? (1 expected: NORMLY_PUBLIC_HOST unset)"; rm .env`
Expected: `compose config ok`; the second call fails with the `NORMLY_PUBLIC_HOST` message. Nothing is built or started locally.

- [ ] **Step 7: Commit**

```bash
git add compose.yaml .env.example docker/caddy/Caddyfile
git commit -s -m "build: add compose setup with bundled, edge and tools profiles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Verification on the VM — self-hosting path and production path

**Files:** no code change expected; errors are fixed in Tasks 3–8 and committed there afterwards.

**Interfaces:**
- Consumes: everything from Tasks 1–8; `/opt/normly/.env` (production values, created by the owner).

- [ ] **Step 1: Self-hosting path with bundled services (own Postgres, not Flex)**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && cp .env.example .env && sed -i "s/^NORMLY_FRONTEND_BIND=.*/NORMLY_FRONTEND_BIND=127.0.0.1/" .env && docker compose up -d --build 2>&1 | tail -15'
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && sleep 60 && docker compose ps --format "table {{.Service}}\t{{.Status}}" && docker compose logs migrate --no-log-prefix | tail -3'
```
Expected: `migrate` with `Exited (0)` and `migrations: at head`; `postgres`, `ollama`, `mailpit`, `api`, `accounts`, `chat`, `frontend` `Up … (healthy)`; `ollama-pull` `Exited (0)` after the download (can take a few minutes, `Up` until then).

- [ ] **Step 2: Functional probes (self-hosting)**

Run:
```bash
ssh ubuntu@213.17.23.196 'curl -s -o /dev/null -w "frontend %{http_code}\n" http://127.0.0.1:3000/; curl -s -o /dev/null -w "search page %{http_code}\n" http://127.0.0.1:3000/search; curl -s -X POST http://127.0.0.1:3000/api/auth/register -H "Content-Type: application/json" -d "{\"email\":\"smoke@example.org\",\"password\":\"Smoke-Test-Passw0rd!\"}" -o /dev/null -w "register %{http_code}\n"; sleep 2; curl -s http://127.0.0.1:8025/api/v1/messages | python3 -c "import sys,json; d=json.load(sys.stdin); print(\"mailpit messages:\", d.get(\"total\"))"'
```
Expected: `frontend 200`, `search page 200`, `register` 200/201/202 (depending on the route), `mailpit messages: 1` (the verification mail). If the registration endpoint has a different name: `ls frontend/src/app/api/auth` and adjust the path.

Chat probe (Ollama, CPU — can take 30–120 s):

Run:
```bash
ssh ubuntu@213.17.23.196 'curl -s -m 300 -X POST http://127.0.0.1:3000/api/chat -H "Content-Type: application/json" -d "{\"message\":\"Was regelt die DGUV Vorschrift 1?\",\"jurisdiction\":\"DE\",\"language\":\"de\"}" | head -c 400; echo'
```
Expected: JSON response with an `answer`/`text` field (with an empty database, the fallback answer — that is correct, there are no segments yet). No 5xx. If the request schema differs: `grep -n "class ChatRequest" -A8 chat/src/normly_chat/schemas.py`.

- [ ] **Step 3: Idempotency and offline behaviour**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose up -d 2>&1 | grep -ciE "recreat|creat" ; docker compose logs migrate --no-log-prefix | tail -1; docker exec normly-api-1 python -c "
import socket
try:
    socket.create_connection((\"huggingface.co\", 443), timeout=3); print(\"network reachable (fine) -\")
except Exception as e: print(\"no network:\", e)
"; docker compose logs api chat 2>&1 | grep -ci "huggingface" || true'
```
Expected: the second `up` creates/replaces **no** containers (counter 0, only "Running"); `migrate` still reports `at head`; `huggingface` does **not** occur in the logs of `api`/`chat` (counter 0) — the weights came from the image.

- [ ] **Step 4: Stop the self-hosting stack, prepare the production path**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose --profile bundled down -v && rm .env && ln -s /opt/normly/.env .env && ls -l .env'
ssh ubuntu@213.17.23.196 'grep -qE "^COMPOSE_PROFILES=" /opt/normly/.env || echo "COMPOSE_PROFILES=edge" >> /opt/normly/.env; grep -qE "^NORMLY_PUBLIC_HOST=" /opt/normly/.env || echo "NORMLY_PUBLIC_HOST=app.normly.ai" >> /opt/normly/.env; grep -qE "^NORMLY_FRONTEND_BIND=" /opt/normly/.env || echo "NORMLY_FRONTEND_BIND=127.0.0.1" >> /opt/normly/.env; grep -oE "^[A-Z_]+=" /opt/normly/.env | tr -d = | tr "\n" " "; echo'
```
Expected: symlink `.env -> /opt/normly/.env`; the variable list contains `NORMLY_DATABASE_URL NORMLY_LLM_PROVIDER NORMLY_LLM_BASE_URL NORMLY_LLM_MODEL NORMLY_LLM_API_KEY NORMLY_PUBLIC_BASE_URL COMPOSE_PROFILES NORMLY_PUBLIC_HOST NORMLY_FRONTEND_BIND`. **Never print values.**

- [ ] **Step 5: Start the production path**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose up -d 2>&1 | tail -10 && sleep 90 && docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}" && docker compose logs migrate --no-log-prefix | tail -2'
```
Expected: `migrate Exited (0)` with `at head` — this also verifies the Postgres Flex password; `api`, `accounts`, `chat`, `frontend` healthy; `caddy Up`; in the ports column only `caddy` with `0.0.0.0:80`/`443` and `frontend` with `127.0.0.1:3000`. No `postgres`, `ollama`, `mailpit`.

On a `migrate` error `password authentication failed`: the password in `/opt/normly/.env` does not match Postgres Flex — ask the owner to check it (do not change it yourself). On `could not connect`: check the ACL of the Flex instance (must contain `213.17.23.196/32`).

- [ ] **Step 6: TLS and end-to-end via the public address**

Run (from the development machine):
```bash
curl -sS -o /dev/null -w "https://app.normly.ai -> http=%{http_code} ssl=%{ssl_verify_result} issuer=%{certs}\n" https://app.normly.ai/ 2>/dev/null | cut -c1-80
curl -s -o /dev/null -w "http redirect %{http_code} -> %{redirect_url}\n" http://app.normly.ai/
curl -s -m 180 -X POST https://app.normly.ai/api/chat -H "Content-Type: application/json" -d '{"message":"Was regelt die DGUV Vorschrift 1?","jurisdiction":"DE","language":"de"}' | head -c 400; echo
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose logs chat --since 5m 2>&1 | grep -ciE "model-serving|chat/completions|200 OK" || true'
```
Expected: `http=200 ssl=0` (valid Let's Encrypt certificate); HTTP → 308/301 to `https://app.normly.ai/`; chat delivers an answer (with an empty database, the fallback answer) without 5xx; the chat logs show the call to Model Serving or no error. A real Gemma answer needs segments in the database — the data import is TP4; alternatively, run a mini ingestion via `docker compose run --rm pipeline ingest dguv --directory /data/raw/dguv` with a single PDF under `/opt/normly/src/data/raw/dguv/` and repeat the chat probe.

- [ ] **Step 7: Firewall evidence**

Run: `for p in 8000 3000 5432 11434 8025; do timeout 3 bash -c "cat < /dev/null > /dev/tcp/213.17.23.196/$p" 2>/dev/null && echo "port $p OPEN (!)" || echo "port $p closed"; done`
Expected: all five `closed`; only 22, 80, 443 are open.

- [ ] **Step 8: Record the findings**

If corrections to Dockerfiles, Compose or code were needed in Steps 1–7, they are committed in the respective files (Conventional Commit `fix(build): …`). Finally, append the results (image sizes, start-up times, peculiarities) as a section "Verification 2026-10-xx" to the end of the spec `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md` and commit:

```bash
git add docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md
git commit -s -m "docs: record TP1 verification results on the STACKIT VM

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Documentation — ADR-022, CLAUDE.md, SRS, self-hosting guide

**Files:**
- Modify: `docs/adr/README.md` (ADR-022 before `## Open items`, line 745; remove the open-items row "Public read access to STACKIT Container Registry" (wording at the time))
- Modify: `CLAUDE.md:33-35`
- Modify: `docs/srs/03-requirements.md` (REQ-DIST-001 "Further information"; section 3.5.9)
- Modify: `docs/guide/self-hosting.md`, `docs/guide/getting-started.md`
- Modify: `frontend/README.md` (note under "Environment variables")

- [ ] **Step 1: Insert ADR-022**

Insert directly before `## Open items` in `docs/adr/README.md`:

```markdown
## ADR-022 — Operating environment phase 1 and model-origin rule

**Status:** accepted (2026-09-23, amended 2026-10-03)

**Decision:**

1. **Target environment:** one STACKIT VM (`g1a.4d`) with Docker Compose, Caddy
   for TLS, PostgreSQL Flex (single instance, pgvector), Secrets Manager,
   later Object Storage. No SKE, no load balancer. Confirms ADR-005.
2. **LLM inference:** STACKIT AI Model Serving (OpenAI-compatible API,
   region eu01), initial model `google/gemma-4-31B-it`. Ollama remains for
   local development and self-hosting.
3. **Model-origin rule:** Language models used in production are
   open-weight models under an OSI-approved license, operated
   exclusively on STACKIT infrastructure; no request reaches the
   model vendor. European origin is a preference, not a requirement.
   Revisit: as soon as STACKIT offers a European model of suitable
   size, the switch will be examined.
4. **DNS:** the zone `normly.ai` is hosted entirely at STACKIT DNS
   (registrar remains Strato); no more Cloudflare. App at
   `app.normly.ai`.
5. **Mail sending:** SMTP from the existing Strato mail package
   (`noreply@normly.ai`), SPF and DKIM in the STACKIT zone.
6. **Environments:** initially only one production environment on STACKIT; the
   local Compose setup takes on the role of the staging environment.
   Deliberate, temporary deviation from REQ-DIST-001, to be lifted as soon as
   there are users whom a faulty deployment would hit.
7. **Images:** one shared Python base image with all
   `core` dependencies and baked-in embedding weights; no
   splitting of the dependencies.

**Rationale:** The VM with Compose is the cheapest environment and at the
same time the self-hosting artifact from ADR-010. AI Model Serving delivers
GPU inference per token without standing costs; the data goes to STACKIT, not
to the model vendor — weights are a file, not a service. The
origin rule closes the previously unregulated gap that the
default model (Llama, Meta license) was neither openly licensed nor
regulated; a European requirement would have left only a dedicated GPU VM,
since the STACKIT catalog lists no European chat model.
Cloudflare as DNS would have been a US service in the operations chain. The
domain's mail was already at Strato; a second provider would have meant an
MX change.

**Rejected:** Ollama on CPU in production (response times), dedicated GPU VM
(standing costs), European model origin as a requirement (no offering),
subzone delegation only for `app` (Cloudflare would remain authoritative), IONOS
as a second mail provider (MX conflict), splitting the
`core` dependencies into extras (owner decision in favor of
simplicity).

**Consequence:** CLAUDE.md gets a sentence on model origin; REQ-DIST-001
and chapter 3.5.9 of the SRS refer here; `docs/guide/self-hosting.md`
describes the Compose route. Follow-up work: load the embedding model only once
and downsize the VM to `g1a.2d` (TP1a), image pipeline (TP2),
obtaining secrets via AppRole (TP3), rollout/rollback/data version (TP4). Details:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

---

```

In addition, remove the row `| Public read access to STACKIT Container Registry | open | check in the portal |` (wording at the time) from the table under `## Open items` (moot because of ADR-021: the registry is GHCR).

- [ ] **Step 2: Extend CLAUDE.md**

After the item "The core must not depend on proprietary components." (lines 33–34), insert:

```markdown
- **Language models only as open-weight models with an OSI license,
  operated on STACKIT.** No request reaches the model vendor; European
  origin is a preference, not a requirement. → ADR-022
```

- [ ] **Step 3: Adjust the SRS**

In `docs/srs/03-requirements.md`, REQ-DIST-001, replace the line `**Further information:** Also applies to ML data and logs.` with:

```markdown
**Further information:** Also applies to ML data and logs. **Temporary deviation (ADR-022, 2026-09-23):** In Phase 1, only one production environment exists on STACKIT; the local Compose setup takes on the role of the staging environment. To be lifted as soon as there are users whom a faulty deployment would affect.
```

In section 3.5.9, replace the sentence `STACKIT Git (Forgejo) with STACKIT Pipelines is used as the source and build platform.` (wording at the time) with:

```markdown
Since ADR-021, source code, CI/CD and container registry of the free core reside on GitHub (REQ-GIT-001, REQ-BUILD-002). For language models, ADR-022 applies: exclusively open-weight models with an OSI-approved license, operated on STACKIT infrastructure; no request reaches the model vendor.
```

- [ ] **Step 4: Write the self-hosting guide**

Replace `docs/guide/self-hosting.md` completely:

````markdown
# Self-Hosting

normly ships as container images plus a Compose setup that starts a
working instance with one command ([ADR-010](../adr/README.md#adr-010-shipping-as-a-container-data-separate-from-the-image)).
The knowledge base is **not** part of the images; it arrives as a
separately versioned dump (import tooling follows in a later release, see
"Known gaps").

## Requirements

- Docker Engine 24+ with Compose v2.20+ (`docker compose version`).
- 16 GB RAM for the bundled setup (two services load a 2 GB embedding
  model; the bundled Ollama runs a small Gemma model on CPU).
- About 20 GB of disk for images and models on first start.
- A Linux host. The images are built for `linux/amd64`.

## Quick start (everything bundled)

```bash
git clone https://github.com/normly/web-app.git normly && cd normly
cp .env.example .env
# edit .env: set NORMLY_BUNDLED_POSTGRES_PASSWORD and the matching password
# inside NORMLY_DATABASE_URL
docker compose up -d --build
```

The first start builds the images (10–20 minutes: PyTorch, the embedding
weights and Docling models are fetched once at build time), pulls the
Ollama model, runs the database migrations and then brings up the four
services. Afterwards:

- App: <http://localhost:3000>
- Mail catcher (every e-mail the app sends): <http://localhost:8025>

Check `docker compose ps` — `migrate` and `ollama-pull` exit with code 0,
everything else reports `healthy`.

Running `docker compose up -d` again is safe: migrations are idempotent and
unchanged containers are left alone.

## What the profiles mean

`COMPOSE_PROFILES` in `.env` selects what is bundled:

| Profile   | Starts                                   | Use when                                   |
|-----------|------------------------------------------|--------------------------------------------|
| `bundled` | PostgreSQL (pgvector), Ollama, Mailpit   | you have no managed database or LLM        |
| `edge`    | Caddy with automatic Let's Encrypt TLS   | the host is public and has a DNS name      |
| `tools`   | nothing by itself                        | `docker compose run --rm pipeline …`       |

Both at once: `COMPOSE_PROFILES=bundled,edge`.

## Production-style setup

Point the instance at managed services instead of the bundled ones:

- `COMPOSE_PROFILES=edge`, `NORMLY_PUBLIC_HOST=app.example.org`,
  `NORMLY_PUBLIC_BASE_URL=https://app.example.org`,
  `NORMLY_FRONTEND_BIND=127.0.0.1` (Caddy is the only public entry point).
- `NORMLY_DATABASE_URL=postgresql+psycopg://…?sslmode=require` on a
  PostgreSQL 16+ with the `vector` extension available.
- LLM: `NORMLY_LLM_PROVIDER=openai-compatible` plus base URL, model and
  `NORMLY_LLM_API_KEY` of any OpenAI-compatible `/chat/completions`
  endpoint. Only open-weight models under an OSI-approved licence are used
  by the project itself ([ADR-022](../adr/README.md#adr-022-operating-environment-phase-1-and-model-origin-rule)).
- Mail: a real SMTP relay (`NORMLY_SMTP_*`; STARTTLS is used as soon as a
  username is set).

Ports 80 and 443 must be reachable from the internet for Let's Encrypt.

## Configuration reference

All variables are documented inline in `.env.example`. Frontend-specific
branding variables are described in `frontend/README.md`.

## Ingesting documents

```bash
mkdir -p data/raw/dguv   # put source PDFs here
docker compose run --rm pipeline ingest dguv --directory /data/raw/dguv
```

Sources: `eur-lex`, `dguv`, `baua`. Other maintenance commands:
`backfill-document-embeddings`, `cleanup-notifications`, `notify-watchers`.

## Known gaps

- No published images yet — `docker compose up --build` builds locally.
  Signed images on GHCR and a versioned knowledge-base dump are the next
  two deliverables of the deployment roadmap.
- No Helm chart. Kubernetes is not a target for the free core right now.
````

- [ ] **Step 5: Adjust the getting-started page and the frontend README**

Replace `docs/guide/getting-started.md` completely:

```markdown
# Getting Started

Want to run normly? See [Self-Hosting](self-hosting.md) — a Compose setup
starts a complete instance with one command.

Want to contribute? `CONTRIBUTING.md` at the repository root is the right
starting point. Each package (`core/`, `api/`, `chat/`, `accounts/`,
`frontend/`) has its own virtual environment and test suite; the CI
workflow in `.github/workflows/ci.yml` shows the exact commands.

The first public release with a published knowledge base is planned for
December 2026.
```

In `frontend/README.md`, insert directly under the heading `## Environment variables`:

```markdown
When running via the repository's `compose.yaml`, the three `*_BASE_URL`
variables are set by Compose to the internal service names; only the
optional branding variables and `NORMLY_PUBLIC_BASE_URL` come from `.env`.
```

- [ ] **Step 6: Check the docs build against the baseline**

Run:
```bash
docker run --rm -v "$PWD":/repo:ro -w /tmp python:3.12 bash -c 'cp -r /repo /work && cd /work && pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null 2>&1; zensical build 2>&1' | sed 's/\x1b\[[0-9;]*m//g' | grep -E "issues found|does not exist"
```
Expected: `3 issues found` (the three known wiki-link hits in `docs/superpowers/specs/`), no new `does not exist` lines. The ADR-022 anchor in `self-hosting.md` must be exactly `#adr-022-betriebsumgebung-phase-1-und-modellherkunftsregel` (umlauts become their base letters, special characters are dropped — cf. the existing anchors in `docs/srs/README.md`).

- [ ] **Step 7: Commit**

```bash
git add docs/adr/README.md CLAUDE.md docs/srs/03-requirements.md docs/guide/self-hosting.md docs/guide/getting-started.md frontend/README.md
git commit -s -m "docs: add ADR-022 (phase-1 operations, model provenance), self-hosting guide

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Overall check and PR

- [ ] **Step 1: All test suites locally**

Run:
```bash
(cd core && .venv/bin/pytest -q -x --ignore=tests/pipeline 2>&1 | tail -3)
(cd api && .venv/bin/pytest -q 2>&1 | tail -2)
(cd accounts && .venv/bin/pytest -q 2>&1 | tail -2)
(cd chat && .venv/bin/pytest -q --ignore=tests/test_structural_end_to_end.py 2>&1 | tail -2)
(cd frontend && npm test 2>&1 | tail -4)
```
Expected: all green (Ollama tests `skipped`). `core/tests/pipeline` is slow locally (Docling) and not touched by this sub-project; whoever has time lets it run along.

- [ ] **Step 2: License header and secrets scan**

Run:
```bash
for f in docker/python.Dockerfile docker/caddy/Caddyfile frontend/Dockerfile compose.yaml .env.example scripts/sync-to-vm.sh core/src/normly_core/migrate.py chat/src/normly_chat/llm_client.py core/tests/test_migrate.py chat/tests/test_llm_client.py .dockerignore frontend/.dockerignore; do grep -q "SPDX-License-Identifier: AGPL-3.0-or-later" "$f" && echo "ok  $f" || echo "MISSING header: $f"; done
git grep -nE "(sk-|Bearer [A-Za-z0-9]{20,}|postgresql\+psycopg://[^:]+:[^@c][^@]*@)" -- ':!docs/superpowers' ':!*.md' || echo "no credential-looking strings"
```
Expected: all `ok`; `no credential-looking strings` (the only URL with a password is `change-me` in `.env.example`).

- [ ] **Step 3: Branch state**

Run: `git status --short && git log --oneline main..HEAD`
Expected: working tree clean; commit list of Tasks 1–10 plus spec/plan commits.

- [ ] **Step 4: Push and PR — only after the owner's explicit approval** (triggers a CI run)

```bash
git push -u origin docs/tp1-containerisation-design
gh pr create --base main --title "feat: containerisation and compose setup (deployment TP1)" --body "$(cat <<'PRBODY'
## Summary

Sub-project 1 of the STACKIT deployment roadmap (`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`), design in `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md`.

- `docker/python.Dockerfile`: shared `base` stage (all core deps, baked-in multilingual-e5-large weights) plus `api`, `chat`, `accounts`, `pipeline` targets; `frontend/Dockerfile` for Next.js standalone. All run as UID 10001.
- `compose.yaml` with profiles `bundled` (postgres/pgvector, ollama, mailpit), `edge` (caddy + Let's Encrypt), `tools` (pipeline). One-shot `migrate` service runs Alembic before the apps start.
- `python -m normly_core.migrate`: env-driven, idempotent Alembic upgrade.
- chat: `NORMLY_LLM_PROVIDER` selects Ollama or an OpenAI-compatible endpoint (STACKIT AI Model Serving); `NORMLY_OLLAMA_*` removed, Llama default dropped.
- Docs: ADR-022 (phase-1 operations + model-provenance rule), CLAUDE.md sentence, SRS notes, real self-hosting guide.

Verified on the STACKIT VM: bundled self-hosting path and production path (Postgres Flex, Model Serving, TLS at app.normly.ai) — results recorded at the end of the design spec.

## Test plan

- [x] core/api/accounts/chat pytest suites, frontend vitest
- [x] `docker compose up` bundled and edge paths on the VM, idempotent second `up`
- [x] no runtime access to huggingface.co; only ports 22/80/443 open
- [ ] CI green (test-core stays known-red per the CI spec)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
PRBODY
)"
```

---

## Self-Review

**Spec coverage:** image structure (Tasks 3–6), Compose with profiles, migrate one-off service, healthchecks, only frontend/Caddy reachable (Task 8, checked in Task 9 Step 7), LLM client with provider selection and tests (Task 7), model weights in the image without runtime download (Task 3, checked in Task 9 Step 3), Docling models only in the pipeline image (Task 5), ingestion on the VM via `run` (Task 8 profile `tools`, guide in Task 10), documentation ADR-022/CLAUDE.md/SRS/self-hosting/frontend README (Task 10), verification of both paths including idempotency (Task 9). BFF verification from the spec: implicit in Task 8 — backends without `ports`, frontend route handlers use `getBackendUrls()` server-side (`frontend/src/lib/backend-urls.ts`); client components only call `/api/...`. Should a page in the browser try to reach `api:8000` in Task 9 Step 2, this shows up as a network error and is fixed there.

**Type consistency:** `build_llm_client_from_env`, `get_llm_client`, `app.state.llm_client`, `LlmClient`, `OpenAiCompatibleClient(base_url, model, api_key, *, timeout, transport)` are named identically in Tasks 7 and 8 (`.env.example`); `normly_core.migrate.main`/`upgrade_to_head` consistent in Task 2 and 5/8 (`python -m normly_core.migrate`); `NORMLY_CORE_DIR` default `/app/core` matches the `COPY core /app/core` in Task 3.

**Left open, deliberately:** exact Ollama and Mailpit tags (Task 8 Steps 1–2 determine them). Verified while writing: `EmbeddingModel.embed_query` exists, `db_url`/`CORE_DIR` in `core/tests/conftest.py`, frontend routes `/api/auth/register` and `/api/chat`, `ChatRequest` with `message`/`jurisdiction`/`language`.
