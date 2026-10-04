# Containerisierung (TP1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fünf Container-Images und ein Compose-Setup, das normly mit einem Aufruf startet — lokal/Self-Hosting mit gebündeltem Postgres, Ollama und Mailpit, in Produktion auf der STACKIT-VM gegen PostgreSQL Flex und STACKIT AI Model Serving.

**Architecture:** Ein Multi-Stage-Dockerfile `docker/python.Dockerfile` mit einer gemeinsamen Stage `base` (alle `core`-Abhängigkeiten plus eingebackene e5-Gewichte) und vier Ziel-Stages `api`, `chat`, `accounts`, `pipeline`; BuildKit teilt die `base`-Schichten zwischen den vier Builds. Das Frontend ist ein eigenes Multi-Stage-Dockerfile (Next.js `standalone`). `compose.yaml` an der Repository-Wurzel steuert über Profile (`bundled`, `edge`, `tools`), welche Dienste mitlaufen; Migrationen laufen als Einmal-Dienst `migrate` vor den App-Diensten. Im Chat-Dienst ersetzt eine Provider-Auswahl (`NORMLY_LLM_PROVIDER`) den fest verdrahteten Ollama-Client.

**Tech Stack:** Docker 29 / Compose 2.40 (Ubuntu-Pakete `docker.io`, `docker-compose-v2`), `python:3.12-slim`, `node:22-alpine`, `pgvector/pgvector:pg17`, `ollama/ollama`, `axllent/mailpit`, `caddy:2`, httpx, Alembic, pytest, vitest.

Spec: `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md`. Roadmap mit den Grundsatzentscheidungen E1–E8: `docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

## Global Constraints

- Lizenzheader in jeder neuen Quelldatei: `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# Copyright (C) 2026 normly contributors` (Dockerfiles, Compose, Shell, Python; in YAML/Dockerfile als `#`-Kommentar, in TypeScript als `//`).
- Commits: Conventional Commits, Englisch, `git commit -s` (Signed-off-by des Menschen) plus Trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Kein Push auf `main`.
- Keine Secrets im Repo, auch nicht in `.env.example` oder Tests. `.env` ist git-ignoriert.
- `core` behält Docling und sentence-transformers als Pflichtabhängigkeit (Nutzerentscheidung, nicht aufteilen).
- Embedding-Gewichte `intfloat/multilingual-e5-large` werden beim Build in die Stage `base` geladen; zur Laufzeit darf kein Container huggingface.co kontaktieren.
- Alle Container laufen als unprivilegierter Nutzer `normly` (UID/GID 10001).
- Basis-Images per Tag gepinnt (`python:3.12-slim`, `node:22-alpine`, `pgvector/pgvector:pg17`, `caddy:2`, `axllent/mailpit:v1`, `ollama/ollama` auf den beim Implementieren aktuellen Minor-Tag); Digest-Pinning kommt mit TP2.
- Nur das Frontend (bzw. Caddy) ist von außen erreichbar; `api`, `chat`, `accounts` veröffentlichen keine Ports.
- Produktionsmodell `google/gemma-4-31B-it`; Entwicklungs-/Self-Hosting-Modell: kleinste Gemma-Variante in der Ollama-Bibliothek (Task 8 prüft den Tag).
- `docs/superpowers/`, CLAUDE.md und `docs/adr/`, `docs/srs/` bleiben Deutsch; `docs/guide/` und READMEs sind Englisch (ADR-020).
- CI-Doku-Job erwartet exakt `3 issues found` beim Zensical-Build; neue Doku darf keine neuen Link-Issues erzeugen.

---

## Arbeitsweise: Bauen und Testen auf der STACKIT-VM (E8)

Die Images werden **auf der VM** gebaut, nicht lokal. Der Arbeitsbaum wird per rsync hinübergespiegelt (kein GitHub-Zugang auf der VM nötig). Zugangsdaten:

- VM: `ssh ubuntu@213.17.23.196` (Schlüssel dieses Rechners ist hinterlegt).
- Produktions-`.env` liegt auf der VM unter `/opt/normly/.env` (Rechte 600, enthält Secrets — **nie ausgeben, nie kopieren, nie in Logs zitieren**).
- Arbeitsbaum auf der VM: `/opt/normly/src`.

Sync-Befehl (vom Entwicklungsrechner, aus der Repository-Wurzel; wird in Task 3 als Skript festgehalten):

```bash
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.next' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'test-results' \
  --exclude '.worktrees' --exclude 'site' --exclude '.env' \
  ./ ubuntu@213.17.23.196:/opt/normly/src/
```

Build-/Run-Befehle werden immer als `ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose ...'` ausgeführt. Unit-Tests (pytest, vitest) laufen weiterhin **lokal** in den vorhandenen `.venv`s bzw. mit `npm test`.

Python-Pakete lokal: `core/.venv`, `api/.venv`, `chat/.venv`, `accounts/.venv` (je `bin/pytest`). Nach Änderungen an `core` muss `core` in den abhängigen Venvs nicht neu installiert werden (editable installs).

---

## File Structure

**Neu:**
- `.dockerignore` — Build-Kontext der Python-Images schlank halten.
- `.env.example` — dokumentierte Vorlage aller Variablen, ohne Secrets.
- `docker/python.Dockerfile` — Stages `base`, `api`, `chat`, `accounts`, `pipeline`.
- `docker/caddy/Caddyfile` — TLS-Terminierung, `reverse_proxy frontend:3000`.
- `frontend/Dockerfile`, `frontend/.dockerignore` — Next.js standalone.
- `compose.yaml` — alle Dienste, Profile, Healthchecks, Volumes.
- `scripts/sync-to-vm.sh` — rsync-Spiegelung des Arbeitsbaums auf die VM (Entwicklungswerkzeug für E8).
- `core/src/normly_core/migrate.py` — `python -m normly_core.migrate`: Alembic `upgrade head` aus `NORMLY_DATABASE_URL`.
- `core/tests/test_migrate.py`.
- `chat/src/normly_chat/llm_client.py` — `LlmClient`-Protokoll, `OpenAiCompatibleClient`, `build_llm_client_from_env`.
- `chat/tests/test_llm_client.py`.

**Geändert:**
- `.gitignore` — `.env`, `data/`.
- `chat/src/normly_chat/main.py`, `dependencies.py`, `routers/chat.py`, `synthesis.py` — Umstellung auf `LlmClient`.
- `chat/tests/conftest.py`, `test_chat_router.py`, `test_structural_end_to_end.py` — neue Variablennamen.
- `docs/adr/README.md` — ADR-022, offener Punkt gestrichen.
- `CLAUDE.md` — Satz zur Modellherkunft.
- `docs/srs/03-anforderungen.md` — REQ-DIST-001, Kapitel 3.5.9.
- `docs/guide/self-hosting.md`, `docs/guide/getting-started.md` — tatsächlicher Compose-Weg.
- `frontend/README.md` — Hinweis auf Compose-Betrieb.

---

### Task 1: Repository-Hygiene für Container-Builds

**Files:**
- Create: `.dockerignore`
- Create: `frontend/.dockerignore`
- Modify: `.gitignore`

**Interfaces:**
- Produces: Build-Kontexte ohne Venvs, `node_modules`, Tests und Doku; `.env` kann in der Repository-Wurzel liegen, ohne je committet zu werden.

- [ ] **Step 1: `.dockerignore` an der Wurzel anlegen**

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

- [ ] **Step 2: `frontend/.dockerignore` anlegen**

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

- [ ] **Step 3: `.gitignore` ergänzen**

Am Ende von `.gitignore` anfügen:

```
.env
.env.*
!.env.example
data/
```

- [ ] **Step 4: Prüfen**

Run: `touch .env && git check-ignore -v .env && rm .env && git check-ignore -v .env.example; echo "exit=$?"`
Expected: erste Zeile nennt `.gitignore:…:.env`; `.env.example` wird **nicht** ignoriert (`exit=1` für den zweiten Aufruf).

- [ ] **Step 5: Commit**

```bash
git add .dockerignore frontend/.dockerignore .gitignore
git commit -s -m "build: add dockerignore files and ignore local env files

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `python -m normly_core.migrate` — Migrationen aus der Umgebung heraus

`alembic.ini` hat ein leeres `sqlalchemy.url`; heute setzen nur die Tests die URL programmatisch (`core/tests/conftest.py:50-53`). Der `migrate`-Dienst braucht denselben Weg als Kommando.

**Files:**
- Create: `core/src/normly_core/migrate.py`
- Create: `core/tests/test_migrate.py`

**Interfaces:**
- Produces: `normly_core.migrate.upgrade_to_head(database_url: str, core_dir: Path) -> None`; `normly_core.migrate.main(argv: list[str] | None = None) -> int`; Umgebungsvariablen `NORMLY_DATABASE_URL` (Pflicht) und `NORMLY_CORE_DIR` (Default `/app/core`, Verzeichnis mit `alembic.ini` und `migrations/`). Exit 0 bei Erfolg, 1 bei fehlender Konfiguration.

- [ ] **Step 1: Fixture-Namen in `core/tests/conftest.py` prüfen**

Run: `grep -n "def db_url\|def postgres_container\|CORE_DIR" core/tests/conftest.py`
Expected: Fixture `db_url` (session-scoped, Zeile 44) und `CORE_DIR = Path(__file__).parents[1]` (Zeile 13) — beide am 2026-10-04 verifiziert; der Test unten nutzt `db_url` und definiert `CORE_DIR` selbst.

- [ ] **Step 2: Failing test schreiben**

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

- [ ] **Step 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd core && .venv/bin/pytest tests/test_migrate.py -v`
Expected: FAIL — `No module named normly_core.migrate` (returncode 1, aber ohne die erwarteten Meldungen).

- [ ] **Step 4: Modul implementieren**

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

- [ ] **Step 5: Tests laufen lassen**

Run: `cd core && .venv/bin/pytest tests/test_migrate.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/migrate.py core/tests/test_migrate.py
git commit -s -m "feat(core): add python -m normly_core.migrate for env-driven alembic upgrade

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Python-Basis-Stage mit eingebackenen Embedding-Gewichten, Sync-Skript, Docker auf der VM

**Files:**
- Create: `docker/python.Dockerfile` (nur Stage `base` in diesem Task)
- Create: `scripts/sync-to-vm.sh`

**Interfaces:**
- Produces: Stage `base` mit installiertem `normly-core`, `libgl1`, Nutzer `normly` (10001), `ENV NORMLY_EMBEDDING_MODEL_PATH=/opt/models/multilingual-e5-large`, Gewichte unter diesem Pfad, `WORKDIR /app`, `core/` unter `/app/core`. Spätere Stages bauen mit `FROM base AS <name>`.

- [ ] **Step 1: Docker und Compose auf der VM installieren**

Run:
```bash
ssh ubuntu@213.17.23.196 'sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 && sudo usermod -aG docker ubuntu && sudo systemctl enable --now docker'
ssh ubuntu@213.17.23.196 'docker --version && docker compose version && mkdir -p /opt/normly/src'
```
Expected: `Docker version 29.x`, `Docker Compose version v2.40.x`. Der Gruppenwechsel greift bei der nächsten SSH-Sitzung (jeder `ssh`-Aufruf ist eine neue Sitzung).

- [ ] **Step 2: Sync-Skript anlegen**

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

- [ ] **Step 3: Stage `base` schreiben**

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

- [ ] **Step 4: Auf der VM bauen und prüfen**

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
Expected: Build endet erfolgreich (erster Build dauert 10–20 Minuten wegen Torch und 2,2 GB Gewichten); Größe im Bereich 6–8 GB; der Lauf mit `--network none` gibt `dim 1024` aus — das beweist, dass die Gewichte aus dem Image kommen, nicht aus dem Netz. `whoami 0` ist hier noch in Ordnung (USER kommt in den Ziel-Stages). Falls `embed_query` anders heißt: `grep -n "def " core/src/normly_core/pipeline/embeddings.py` und die passende Methode verwenden.

- [ ] **Step 5: Commit**

```bash
git add docker/python.Dockerfile scripts/sync-to-vm.sh
git commit -s -m "build: add shared python base image stage with baked-in embedding weights

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Ziel-Stages `api`, `chat`, `accounts`

**Files:**
- Modify: `docker/python.Dockerfile` (anhängen)

**Interfaces:**
- Consumes: Stage `base` aus Task 3.
- Produces: Images, die mit `uvicorn normly_<svc>.main:app --host 0.0.0.0 --port 8000` starten, als Nutzer `normly`, Port 8000. Die Images erwarten `NORMLY_DATABASE_URL` (alle), `NORMLY_API_BASE_URL`/`NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_LLM_*` (chat), `NORMLY_SMTP_*`/`NORMLY_PUBLIC_BASE_URL`/`NORMLY_GOOGLE_*` (accounts, optional).

- [ ] **Step 1: Stages anhängen**

An `docker/python.Dockerfile` anfügen:

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

- [ ] **Step 2: Bauen und prüfen, dass `normly-core` nicht aus einem Index geladen wurde**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && for t in api chat accounts; do docker build -f docker/python.Dockerfile --target $t -t normly-$t:local --progress=plain . 2>&1 | tee /tmp/build-$t.log | tail -2; grep -i "downloading normly" /tmp/build-$t.log && echo "!! normly-core came from an index" || echo "ok: normly-core resolved locally ($t)"; done'
ssh ubuntu@213.17.23.196 'for t in api chat accounts; do docker run --rm --network none normly-$t:local python -c "import os, importlib; importlib.import_module(\"normly_$t.main\"); print(\"$t import ok, uid\", os.getuid())"; done'
```
Expected: drei Builds erfolgreich, jeweils `ok: normly-core resolved locally`, Import-Checks drucken `uid 10001`. Die drei Builds dürfen die `base`-Schichten wiederverwenden (im Log `CACHED` für die base-Schritte).

- [ ] **Step 3: Commit**

```bash
git add docker/python.Dockerfile
git commit -s -m "build: add api, chat and accounts image stages

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Ziel-Stage `pipeline` (Migrationen, Ingestion, Docling-Modelle)

**Files:**
- Modify: `docker/python.Dockerfile` (anhängen)

**Interfaces:**
- Consumes: Stage `base`; `python -m normly_core.migrate` aus Task 2.
- Produces: Image mit `ENTRYPOINT ["python", "-m", "normly_core.pipeline"]`, `ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling`, `ENV NORMLY_CORE_DIR=/app/core`; Migrationen über `--entrypoint python … -m normly_core.migrate`.

- [ ] **Step 1: Stage anhängen**

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

- [ ] **Step 2: Bauen und beide Einstiege prüfen**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker build -f docker/python.Dockerfile --target pipeline -t normly-pipeline:local . 2>&1 | tail -2'
ssh ubuntu@213.17.23.196 'docker run --rm --network none normly-pipeline:local --help | head -5; docker run --rm --network none --entrypoint python normly-pipeline:local -m normly_core.migrate; echo "migrate exit=$?"; docker run --rm --network none normly-pipeline:local ingest dguv --directory /nonexistent; echo "ingest exit=$?"'
```
Expected: `--help` zeigt die Subkommandos `ingest`, `backfill-document-embeddings`, …; `migrate` endet mit `exit=1` und der Meldung `NORMLY_DATABASE_URL environment variable is required` (keine URL gesetzt, gewollt); `ingest` endet mit `exit=1` und derselben Meldung. Keine Traceback-Ausgabe.

- [ ] **Step 3: Docling-Modelle offline laden**

Run:
```bash
ssh ubuntu@213.17.23.196 'docker run --rm --network none --entrypoint python normly-pipeline:local -c "
import os
from normly_core.pipeline.docling_extraction import _get_converter
_get_converter(os.environ[\"NORMLY_DOCLING_ARTIFACTS_PATH\"])
print(\"docling converter built offline\")
"'
```
Expected: `docling converter built offline`. Falls der Aufruf wegen fehlender Modelle fehlschlägt, in der Fehlermeldung ablesen, welches Modell fehlt, und es in Step 1 zur Download-Liste hinzufügen (z. B. `rapidocr` oder `easyocr`, falls OCR aktiviert ist).

Bekannt und **nicht** Teil dieses Tasks: Mit frisch geladenen Docling-Modellen liefert die DGUV-Titelerkennung in zwei Tests `None` (siehe `docs/superpowers/specs/2026-09-02-ci-pipeline-design.md`, Offene Punkte). Das betrifft Ingestion-Qualität, nicht den Container.

- [ ] **Step 4: Commit**

```bash
git add docker/python.Dockerfile
git commit -s -m "build: add pipeline image stage with docling models and migrate entrypoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Frontend-Image (Next.js standalone)

**Files:**
- Create: `frontend/Dockerfile`

**Interfaces:**
- Produces: Image `normly-frontend:local`, Port 3000, `node server.js`, Nutzer `normly`; liest `NORMLY_API_BASE_URL`, `NORMLY_ACCOUNTS_BASE_URL`, `NORMLY_CHAT_BASE_URL`, `NORMLY_PUBLIC_BASE_URL`, optional `NORMLY_INSTANCE_NAME`, `NORMLY_BRAND_COLOR_HSL`, `NORMLY_LOGO_PATH` zur Laufzeit (`frontend/README.md`).

- [ ] **Step 1: Dockerfile schreiben**

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

- [ ] **Step 2: Bauen und starten**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src/frontend && docker build -t normly-frontend:local . 2>&1 | tail -2 && docker image ls normly-frontend:local --format "{{.Size}}"'
ssh ubuntu@213.17.23.196 'cid=$(docker run -d --rm -p 127.0.0.1:3100:3000 -e NORMLY_API_BASE_URL=http://api:8000 -e NORMLY_ACCOUNTS_BASE_URL=http://accounts:8000 -e NORMLY_CHAT_BASE_URL=http://chat:8000 -e NORMLY_PUBLIC_BASE_URL=http://localhost:3100 normly-frontend:local); sleep 4; curl -s -o /dev/null -w "frontend http=%{http_code}\n" http://127.0.0.1:3100/; curl -s http://127.0.0.1:3100/manifest.webmanifest | head -c 120; echo; docker exec $cid id -u; docker stop $cid >/dev/null'
```
Expected: Build erfolgreich, Größe unter 300 MB; `frontend http=200`; Manifest-JSON wird ausgeliefert (beweist `public/`-Kopie); `id -u` = `10001`.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -s -m "build(frontend): add multi-stage Dockerfile for Next.js standalone output

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: LLM-Client-Auswahl im Chat-Dienst (`NORMLY_LLM_*`)

Heute: `OllamaClient(base_url, model)` fest in `chat/src/normly_chat/main.py:37-40`, Variablen `NORMLY_OLLAMA_BASE_URL`/`NORMLY_OLLAMA_MODEL`. Ziel: Protokoll `LlmClient`, zweiter Client für die OpenAI-kompatible API von STACKIT AI Model Serving, Auswahl per `NORMLY_LLM_PROVIDER`.

**Files:**
- Create: `chat/src/normly_chat/llm_client.py`
- Create: `chat/tests/test_llm_client.py`
- Modify: `chat/src/normly_chat/main.py:18,37-40`
- Modify: `chat/src/normly_chat/dependencies.py:13,35-36`
- Modify: `chat/src/normly_chat/routers/chat.py:21,23,39,63`
- Modify: `chat/src/normly_chat/synthesis.py:68-69,81,95,101`
- Modify: `chat/tests/conftest.py:86,132-135`, `chat/tests/test_chat_router.py:40`, `chat/tests/test_structural_end_to_end.py:143`

**Interfaces:**
- Produces: `normly_chat.llm_client.LlmClient` (Protocol mit `chat(messages: list[dict]) -> str`), `OpenAiCompatibleClient(base_url: str, model: str, api_key: str, *, timeout: float = 120.0, transport: httpx.BaseTransport | None = None)`, `build_llm_client_from_env(environ: Mapping[str, str] = os.environ) -> LlmClient`; `app.state.llm_client`; `dependencies.get_llm_client`. Variablen: `NORMLY_LLM_PROVIDER` (`ollama` | `openai-compatible`, Default `ollama`), `NORMLY_LLM_BASE_URL` (Pflicht), `NORMLY_LLM_MODEL` (Pflicht), `NORMLY_LLM_API_KEY` (Pflicht nur bei `openai-compatible`).
- `OllamaClient` bleibt unverändert; `SynthesisAnswer.ollama_calls` behält seinen Namen (öffentliches Antwortfeld, kein Umbenennen in diesem Task).

- [ ] **Step 1: Failing tests schreiben**

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

- [ ] **Step 2: Fehlschlag bestätigen**

Run: `cd chat && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: FAIL — `No module named normly_chat.llm_client`.

- [ ] **Step 3: Modul implementieren**

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

- [ ] **Step 4: Tests laufen lassen**

Run: `cd chat && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verdrahtung umstellen**

`chat/src/normly_chat/main.py`: Import `from normly_chat.ollama_client import OllamaClient` ersetzen durch `from normly_chat.llm_client import build_llm_client_from_env`; die Zeilen

```python
    app.state.ollama_client = OllamaClient(
        base_url=os.environ["NORMLY_OLLAMA_BASE_URL"],
        model=os.environ.get("NORMLY_OLLAMA_MODEL", "llama3.1:8b-instruct-q4_0"),
    )
```

ersetzen durch

```python
    app.state.llm_client = build_llm_client_from_env()
```

`chat/src/normly_chat/dependencies.py`: Import `OllamaClient` ersetzen durch `from normly_chat.llm_client import LlmClient`; Funktion umbenennen:

```python
def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client
```

`chat/src/normly_chat/routers/chat.py`: im Import `get_ollama_client` → `get_llm_client`; `from normly_chat.ollama_client import OllamaClient` → `from normly_chat.llm_client import LlmClient`; Parameter `ollama_client: OllamaClient = Depends(get_ollama_client)` → `llm_client: LlmClient = Depends(get_llm_client)`; Aufruf `build_synthesis_answer(..., PostgresSegmentRepository(session), ollama_client,)` → `llm_client`.

`chat/src/normly_chat/synthesis.py`: Parameter `ollama_client` in `_is_faithful` und `build_synthesis_answer` → `llm_client` (nur der Parametername und seine Verwendungen in den Zeilen 68–69, 81, 95, 101; das Feld `ollama_calls` bleibt).

- [ ] **Step 6: Tests auf die neuen Variablen umstellen**

In `chat/tests/conftest.py` (Fixture `client`, Zeile 86) ersetzen:

```python
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("NORMLY_LLM_MODEL", "test-model")
```

In derselben Datei (Fixture `e2e_client`, Zeilen 132–135) ersetzen:

```python
    monkeypatch.setenv("NORMLY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", os.environ["NORMLY_TEST_OLLAMA_BASE_URL"])
    monkeypatch.setenv(
        "NORMLY_LLM_MODEL", os.environ.get("NORMLY_TEST_OLLAMA_MODEL", "gemma3:4b"),
    )
```

In `chat/tests/test_chat_router.py:40` und `chat/tests/test_structural_end_to_end.py:143` die Zeile `monkeypatch.setenv("NORMLY_OLLAMA_BASE_URL", …)` durch die zwei Zeilen `NORMLY_LLM_BASE_URL` (gleicher Wert) und `NORMLY_LLM_MODEL` = `"test-model"` ersetzen.

In `chat/tests/test_ollama_client.py:20` den Default `"llama3.1:8b-instruct-q4_0"` durch `"gemma3:4b"` ersetzen (Testvariablen `NORMLY_TEST_OLLAMA_*` behalten ihren Namen).

Run: `grep -rn "NORMLY_OLLAMA_\|get_ollama_client\|ollama_client" chat/src chat/tests | grep -v "^chat/src/normly_chat/ollama_client.py" | grep -v "_FakeOllamaClient\|ollama_calls"`
Expected: keine Treffer in `chat/src`; in Tests nur noch `test_synthesis.py`, wo `_FakeOllamaClient` als Keyword-Argument-Name verwendet wird — dort prüfen, ob `build_synthesis_answer` positional aufgerufen wird (ja, Zeilen 42, 73, 99, 160); dann sind keine Änderungen nötig.

- [ ] **Step 7: Gesamte Chat-Suite**

Run: `cd chat && .venv/bin/pytest -q`
Expected: alle Tests grün (die Ollama-abhängigen bleiben `skipped`, solange `NORMLY_TEST_OLLAMA_BASE_URL` nicht gesetzt ist).

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
- Consumes: Images/Targets aus Task 3–6; `python -m normly_core.migrate` (Task 2); `NORMLY_LLM_*` (Task 7).
- Produces: `docker compose up` startet je nach `COMPOSE_PROFILES` die Instanz. Profile: `bundled` (postgres, ollama, ollama-pull, mailpit), `edge` (caddy), `tools` (pipeline, nur per `run`). Interne Hostnamen: `postgres`, `ollama`, `mailpit`, `api`, `chat`, `accounts`, `frontend`, jeweils Port 5432/11434/1025/8000/8000/8000/3000.

- [ ] **Step 1: Ollama-Modell-Tag bestimmen**

Run: `curl -s -o /dev/null -w "gemma4 %{http_code}\n" https://ollama.com/library/gemma4; curl -s -o /dev/null -w "gemma3 %{http_code}\n" https://ollama.com/library/gemma3`
Expected: Wenn `gemma4 200`, ist das Entwicklungsmodell die kleinste Variante dieser Seite (Tag von der Seite ablesen, z. B. `gemma4:<kleinste>b`); sonst `gemma3:4b`. Den gewählten Tag in `.env.example` (Step 3) und in `chat/tests/conftest.py`/`test_ollama_client.py` (Task 7, falls abweichend von `gemma3:4b`) eintragen.

- [ ] **Step 2: Image-Tags pinnen**

Run: `for i in ollama/ollama axllent/mailpit caddy pgvector/pgvector; do echo "== $i"; curl -s "https://hub.docker.com/v2/repositories/$( [[ $i == */* ]] && echo $i || echo library/$i )/tags?page_size=20&ordering=last_updated" | python3 -c "import sys,json; print(', '.join(t['name'] for t in json.load(sys.stdin)['results'][:12]))"; done`
Expected: Tag-Listen. Wähle: `pgvector/pgvector:pg17`, `caddy:2`, `axllent/mailpit:v1` (falls kein `v1`-Sammeltag existiert, den aktuellen `v1.x.y`), `ollama/ollama:<aktueller Minor-Tag, z. B. 0.13>` (nicht `latest`). Die gewählten Tags in Step 3 eintragen.

- [ ] **Step 3: `compose.yaml` schreiben**

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

Hinweise zur Datei: `$$NORMLY_LLM_MODEL` (doppeltes Dollar) lässt Compose die Variable **nicht** selbst ersetzen, sondern reicht sie an die Shell im Container durch, die sie aus `env_file` bekommt. `required: false` bei `depends_on` braucht Compose ≥ 2.20 (die VM hat 2.40).

- [ ] **Step 4: `.env.example` schreiben**

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

- [ ] **Step 5: Caddyfile schreiben**

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

- [ ] **Step 6: Syntaxprüfung lokal**

Run: `cp .env.example .env && docker compose config --quiet && echo "compose config ok" && docker compose --profile edge config --quiet; echo "edge exit=$? (1 expected: NORMLY_PUBLIC_HOST unset)"; rm .env`
Expected: `compose config ok`; der zweite Aufruf schlägt mit der `NORMLY_PUBLIC_HOST`-Meldung fehl. Lokal wird nichts gebaut oder gestartet.

- [ ] **Step 7: Commit**

```bash
git add compose.yaml .env.example docker/caddy/Caddyfile
git commit -s -m "build: add compose setup with bundled, edge and tools profiles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Verifikation auf der VM — Self-Hosting-Pfad und Produktionspfad

**Files:** keine Codeänderung erwartet; Fehler werden in den Tasks 3–8 behoben und dort nachcommittet.

**Interfaces:**
- Consumes: alles aus Task 1–8; `/opt/normly/.env` (Produktionswerte, vom Nutzer angelegt).

- [ ] **Step 1: Self-Hosting-Pfad mit gebündelten Diensten (eigene Postgres, nicht Flex)**

Run:
```bash
scripts/sync-to-vm.sh
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && cp .env.example .env && sed -i "s/^NORMLY_FRONTEND_BIND=.*/NORMLY_FRONTEND_BIND=127.0.0.1/" .env && docker compose up -d --build 2>&1 | tail -15'
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && sleep 60 && docker compose ps --format "table {{.Service}}\t{{.Status}}" && docker compose logs migrate --no-log-prefix | tail -3'
```
Expected: `migrate` mit `Exited (0)` und `migrations: at head`; `postgres`, `ollama`, `mailpit`, `api`, `accounts`, `chat`, `frontend` `Up … (healthy)`; `ollama-pull` `Exited (0)` nach dem Download (kann einige Minuten dauern, bis dahin `Up`).

- [ ] **Step 2: Funktionsproben (Self-Hosting)**

Run:
```bash
ssh ubuntu@213.17.23.196 'curl -s -o /dev/null -w "frontend %{http_code}\n" http://127.0.0.1:3000/; curl -s -o /dev/null -w "search page %{http_code}\n" http://127.0.0.1:3000/search; curl -s -X POST http://127.0.0.1:3000/api/auth/register -H "Content-Type: application/json" -d "{\"email\":\"smoke@example.org\",\"password\":\"Smoke-Test-Passw0rd!\"}" -o /dev/null -w "register %{http_code}\n"; sleep 2; curl -s http://127.0.0.1:8025/api/v1/messages | python3 -c "import sys,json; d=json.load(sys.stdin); print(\"mailpit messages:\", d.get(\"total\"))"'
```
Expected: `frontend 200`, `search page 200`, `register` 200/201/202 (je nach Route), `mailpit messages: 1` (die Verifizierungs-Mail). Falls der Registrierungs-Endpunkt anders heißt: `ls frontend/src/app/api/auth` und den Pfad anpassen.

Chat-Probe (Ollama, CPU — kann 30–120 s dauern):

Run:
```bash
ssh ubuntu@213.17.23.196 'curl -s -m 300 -X POST http://127.0.0.1:3000/api/chat -H "Content-Type: application/json" -d "{\"message\":\"Was regelt die DGUV Vorschrift 1?\",\"jurisdiction\":\"DE\",\"language\":\"de\"}" | head -c 400; echo'
```
Expected: JSON-Antwort mit `answer`/`text`-Feld (bei leerer Datenbank die Fallback-Antwort — das ist korrekt, es gibt noch keine Segmente). Keine 5xx. Falls das Request-Schema abweicht: `grep -n "class ChatRequest" -A8 chat/src/normly_chat/schemas.py`.

- [ ] **Step 3: Idempotenz und Offline-Verhalten**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose up -d 2>&1 | grep -ciE "recreat|creat" ; docker compose logs migrate --no-log-prefix | tail -1; docker exec normly-api-1 python -c "
import socket
try:
    socket.create_connection((\"huggingface.co\", 443), timeout=3); print(\"network reachable (fine) -\")
except Exception as e: print(\"no network:\", e)
"; docker compose logs api chat 2>&1 | grep -ci "huggingface" || true'
```
Expected: zweites `up` erzeugt/ersetzt **keine** Container (Zähler 0, nur „Running"); `migrate` meldet weiterhin `at head`; in den Logs von `api`/`chat` kommt `huggingface` **nicht** vor (Zähler 0) — die Gewichte kamen aus dem Image.

- [ ] **Step 4: Self-Hosting-Stack stoppen, Produktionspfad vorbereiten**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose --profile bundled down -v && rm .env && ln -s /opt/normly/.env .env && ls -l .env'
ssh ubuntu@213.17.23.196 'grep -qE "^COMPOSE_PROFILES=" /opt/normly/.env || echo "COMPOSE_PROFILES=edge" >> /opt/normly/.env; grep -qE "^NORMLY_PUBLIC_HOST=" /opt/normly/.env || echo "NORMLY_PUBLIC_HOST=app.normly.ai" >> /opt/normly/.env; grep -qE "^NORMLY_FRONTEND_BIND=" /opt/normly/.env || echo "NORMLY_FRONTEND_BIND=127.0.0.1" >> /opt/normly/.env; grep -oE "^[A-Z_]+=" /opt/normly/.env | tr -d = | tr "\n" " "; echo'
```
Expected: Symlink `.env -> /opt/normly/.env`; die Variablenliste enthält `NORMLY_DATABASE_URL NORMLY_LLM_PROVIDER NORMLY_LLM_BASE_URL NORMLY_LLM_MODEL NORMLY_LLM_API_KEY NORMLY_PUBLIC_BASE_URL COMPOSE_PROFILES NORMLY_PUBLIC_HOST NORMLY_FRONTEND_BIND`. **Werte nie ausgeben.**

- [ ] **Step 5: Produktionspfad starten**

Run:
```bash
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose up -d 2>&1 | tail -10 && sleep 90 && docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}" && docker compose logs migrate --no-log-prefix | tail -2'
```
Expected: `migrate Exited (0)` mit `at head` — damit ist auch das Postgres-Flex-Passwort verifiziert; `api`, `accounts`, `chat`, `frontend` healthy; `caddy Up`; in der Ports-Spalte nur `caddy` mit `0.0.0.0:80`/`443` und `frontend` mit `127.0.0.1:3000`. Kein `postgres`, `ollama`, `mailpit`.

Bei `migrate`-Fehler `password authentication failed`: Passwort in `/opt/normly/.env` stimmt nicht mit Postgres Flex überein — Nutzer bitten, es zu prüfen (nicht selbst ändern). Bei `could not connect`: ACL der Flex-Instanz prüfen (muss `213.17.23.196/32` enthalten).

- [ ] **Step 6: TLS und Ende-zu-Ende über die öffentliche Adresse**

Run (vom Entwicklungsrechner):
```bash
curl -sS -o /dev/null -w "https://app.normly.ai -> http=%{http_code} ssl=%{ssl_verify_result} issuer=%{certs}\n" https://app.normly.ai/ 2>/dev/null | cut -c1-80
curl -s -o /dev/null -w "http redirect %{http_code} -> %{redirect_url}\n" http://app.normly.ai/
curl -s -m 180 -X POST https://app.normly.ai/api/chat -H "Content-Type: application/json" -d '{"message":"Was regelt die DGUV Vorschrift 1?","jurisdiction":"DE","language":"de"}' | head -c 400; echo
ssh ubuntu@213.17.23.196 'cd /opt/normly/src && docker compose logs chat --since 5m 2>&1 | grep -ciE "model-serving|chat/completions|200 OK" || true'
```
Expected: `http=200 ssl=0` (gültiges Let's-Encrypt-Zertifikat); HTTP → 308/301 auf `https://app.normly.ai/`; Chat liefert eine Antwort (bei leerer Datenbank die Fallback-Antwort) ohne 5xx; die Chat-Logs zeigen den Aufruf an Model Serving beziehungsweise keinen Fehler. Für eine echte Gemma-Antwort braucht es Segmente in der Datenbank — der Datenimport ist TP4; alternativ eine Mini-Ingestion per `docker compose run --rm pipeline ingest dguv --directory /data/raw/dguv` mit einer einzelnen PDF unter `/opt/normly/src/data/raw/dguv/` durchführen und die Chat-Probe wiederholen.

- [ ] **Step 7: Firewall-Nachweis**

Run: `for p in 8000 3000 5432 11434 8025; do timeout 3 bash -c "cat < /dev/null > /dev/tcp/213.17.23.196/$p" 2>/dev/null && echo "port $p OPEN (!)" || echo "port $p closed"; done`
Expected: alle fünf `closed`; nur 22, 80, 443 sind offen.

- [ ] **Step 8: Befunde festhalten**

Wenn in Step 1–7 Korrekturen an Dockerfiles, Compose oder Code nötig waren, sind sie in den jeweiligen Dateien committet (Conventional-Commit `fix(build): …`). Abschließend die Ergebnisse (Image-Größen, Startzeiten, Besonderheiten) als Abschnitt „Verifikation 2026-10-xx" an das Ende der Spec `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md` anfügen und committen:

```bash
git add docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md
git commit -s -m "docs: record TP1 verification results on the STACKIT VM

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Dokumentation — ADR-022, CLAUDE.md, SRS, Self-Hosting-Guide

**Files:**
- Modify: `docs/adr/README.md` (ADR-022 vor `## Offene Punkte`, Zeile 745; Zeile der offenen Punkte „Öffentlicher Lesezugriff auf STACKIT Container Registry" entfernen)
- Modify: `CLAUDE.md:33-35`
- Modify: `docs/srs/03-anforderungen.md` (REQ-DIST-001 „Weitere Informationen"; Abschnitt 3.5.9)
- Modify: `docs/guide/self-hosting.md`, `docs/guide/getting-started.md`
- Modify: `frontend/README.md` (Hinweis unter „Environment variables")

- [ ] **Step 1: ADR-022 einfügen**

Direkt vor `## Offene Punkte` in `docs/adr/README.md` einfügen:

```markdown
## ADR-022 — Betriebsumgebung Phase 1 und Modellherkunftsregel

**Status:** beschlossen (2026-09-23, ergänzt 2026-10-03)

**Entscheidung:**

1. **Zielumgebung:** eine STACKIT-VM (`g1a.4d`) mit Docker Compose, Caddy
   für TLS, PostgreSQL Flex (Einzelinstanz, pgvector), Secrets Manager,
   später Object Storage. Kein SKE, kein Load Balancer. Bestätigt ADR-005.
2. **LLM-Inferenz:** STACKIT AI Model Serving (OpenAI-kompatible API,
   Region eu01), Startmodell `google/gemma-4-31B-it`. Ollama bleibt für
   lokale Entwicklung und Self-Hosting.
3. **Modellherkunftsregel:** Produktiv eingesetzte Sprachmodelle sind
   Open-Weight-Modelle unter OSI-anerkannter Lizenz, betrieben
   ausschließlich auf STACKIT-Infrastruktur; keine Anfrage erreicht den
   Modellhersteller. Europäische Herkunft ist Präferenz, nicht Pflicht.
   Wiedervorlage: sobald STACKIT ein europäisches Modell in passender
   Größe anbietet, wird der Wechsel geprüft.
4. **DNS:** die Zone `normly.ai` liegt vollständig bei STACKIT DNS
   (Registrar bleibt Strato); kein Cloudflare mehr. App unter
   `app.normly.ai`.
5. **Mailversand:** SMTP aus dem bestehenden Strato-Mailpaket
   (`noreply@normly.ai`), SPF und DKIM in der STACKIT-Zone.
6. **Umgebungen:** zunächst nur eine Produktionsumgebung auf STACKIT; das
   lokale Compose-Setup übernimmt die Rolle der Staging-Umgebung.
   Bewusste, befristete Abweichung von REQ-DIST-001, aufzuheben, sobald es
   Nutzer gibt, die ein fehlerhaftes Deployment treffen würde.
7. **Images:** ein gemeinsames Python-Basis-Image mit allen
   `core`-Abhängigkeiten und eingebackenen Embedding-Gewichten; keine
   Aufteilung der Abhängigkeiten.

**Begründung:** Die VM mit Compose ist die günstigste Umgebung und zugleich
das Self-Hosting-Artefakt aus ADR-010. AI Model Serving liefert
GPU-Inferenz pro Token ohne Dauerkosten; die Daten gehen an STACKIT, nicht
an den Modellhersteller — Gewichte sind eine Datei, kein Dienst. Die
Herkunftsregel schließt die bisher ungeregelte Lücke, dass das
Standardmodell (Llama, Meta-Lizenz) weder offen lizenziert noch
geregelt war; europäische Pflicht hätte nur eine eigene GPU-VM übrig
gelassen, da der STACKIT-Katalog kein europäisches Chat-Modell führt.
Cloudflare als DNS wäre ein US-Dienst in der Betriebskette gewesen. Die
Mail der Domain lag bereits bei Strato; ein zweiter Anbieter hätte einen
MX-Wechsel bedeutet.

**Verworfen:** Ollama auf CPU in Produktion (Antwortzeiten), eigene GPU-VM
(Dauerkosten), europäische Modellherkunft als Pflicht (kein Angebot),
Subzonen-Delegation nur für `app` (Cloudflare bliebe autoritativ), IONOS
als zweiter Mailanbieter (MX-Konflikt), Aufteilung der
`core`-Abhängigkeiten in Extras (Nutzerentscheidung zugunsten der
Einfachheit).

**Konsequenz:** CLAUDE.md erhält einen Satz zur Modellherkunft; REQ-DIST-001
und Kapitel 3.5.9 der SRS verweisen hierher; `docs/guide/self-hosting.md`
beschreibt den Compose-Weg. Folgearbeiten: Embedding-Modell nur einmal
laden und VM auf `g1a.2d` verkleinern (TP1a), Image-Pipeline (TP2),
Secrets-Bezug per AppRole (TP3), Rollout/Rollback/Datenstand (TP4). Details:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

---

```

Zusätzlich in der Tabelle unter `## Offene Punkte` die Zeile `| Öffentlicher Lesezugriff auf STACKIT Container Registry | offen | im Portal prüfen |` entfernen (durch ADR-021 gegenstandslos: Registry ist GHCR).

- [ ] **Step 2: CLAUDE.md ergänzen**

Nach dem Punkt „Der Kern darf nicht von proprietären Bestandteilen abhängen." (Zeile 33–34) einfügen:

```markdown
- **Sprachmodelle nur als Open-Weight-Modelle mit OSI-Lizenz, betrieben auf
  STACKIT.** Keine Anfrage erreicht den Modellhersteller; europäische
  Herkunft ist Präferenz, nicht Pflicht. → ADR-022
```

- [ ] **Step 3: SRS anpassen**

In `docs/srs/03-anforderungen.md`, REQ-DIST-001, Zeile `**Weitere Informationen:** Gilt auch für ML-Daten und Logs.` ersetzen durch:

```markdown
**Weitere Informationen:** Gilt auch für ML-Daten und Logs. **Befristete Abweichung (ADR-022, 2026-09-23):** In Phase 1 existiert nur eine Produktionsumgebung auf STACKIT; das lokale Compose-Setup übernimmt die Rolle der Staging-Umgebung. Aufzuheben, sobald es Nutzer gibt, die ein fehlerhaftes Deployment treffen würde.
```

In Abschnitt 3.5.9 den Satz `Als Quell- und Build-Plattform wird STACKIT Git (Forgejo) mit STACKIT Pipelines eingesetzt.` ersetzen durch:

```markdown
Quellcode, CI/CD und Container-Registry des freien Kerns liegen seit ADR-021 auf GitHub (REQ-GIT-001, REQ-BUILD-002). Für Sprachmodelle gilt ADR-022: ausschließlich Open-Weight-Modelle mit OSI-anerkannter Lizenz, betrieben auf STACKIT-Infrastruktur; keine Anfrage erreicht den Modellhersteller.
```

- [ ] **Step 4: Self-Hosting-Guide schreiben**

`docs/guide/self-hosting.md` vollständig ersetzen:

```markdown
# Self-Hosting

normly ships as container images plus a Compose setup that starts a
working instance with one command ([ADR-010](../adr/README.md#adr-010-auslieferung-als-container-daten-getrennt-vom-image)).
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
  by the project itself ([ADR-022](../adr/README.md#adr-022-betriebsumgebung-phase-1-und-modellherkunftsregel)).
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
```

- [ ] **Step 5: Getting-Started-Seite und Frontend-README anpassen**

`docs/guide/getting-started.md` vollständig ersetzen:

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

In `frontend/README.md`, direkt unter der Überschrift `## Environment variables` einfügen:

```markdown
When running via the repository's `compose.yaml`, the three `*_BASE_URL`
variables are set by Compose to the internal service names; only the
optional branding variables and `NORMLY_PUBLIC_BASE_URL` come from `.env`.
```

- [ ] **Step 6: Doku-Build gegen die Baseline prüfen**

Run:
```bash
docker run --rm -v "$PWD":/repo:ro -w /tmp python:3.12 bash -c 'cp -r /repo /work && cd /work && pip install -q "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" >/dev/null 2>&1; zensical build 2>&1' | sed 's/\x1b\[[0-9;]*m//g' | grep -E "issues found|does not exist"
```
Expected: `3 issues found` (die drei bekannten Wiki-Link-Treffer in `docs/superpowers/specs/`), keine neuen `does not exist`-Zeilen. Der ADR-022-Anker in `self-hosting.md` muss exakt `#adr-022-betriebsumgebung-phase-1-und-modellherkunftsregel` lauten (Umlaute werden zu Grundbuchstaben, Sonderzeichen entfallen — vgl. die vorhandenen Anker in `docs/srs/README.md`).

- [ ] **Step 7: Commit**

```bash
git add docs/adr/README.md CLAUDE.md docs/srs/03-anforderungen.md docs/guide/self-hosting.md docs/guide/getting-started.md frontend/README.md
git commit -s -m "docs: add ADR-022 (phase-1 operations, model provenance), self-hosting guide

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Gesamtprüfung und PR

- [ ] **Step 1: Alle Testsuiten lokal**

Run:
```bash
(cd core && .venv/bin/pytest -q -x --ignore=tests/pipeline 2>&1 | tail -3)
(cd api && .venv/bin/pytest -q 2>&1 | tail -2)
(cd accounts && .venv/bin/pytest -q 2>&1 | tail -2)
(cd chat && .venv/bin/pytest -q --ignore=tests/test_structural_end_to_end.py 2>&1 | tail -2)
(cd frontend && npm test 2>&1 | tail -4)
```
Expected: alle grün (Ollama-Tests `skipped`). `core/tests/pipeline` ist lokal langsam (Docling) und von diesem Teilprojekt nicht berührt; wer Zeit hat, lässt es mitlaufen.

- [ ] **Step 2: Lizenzheader und Secrets-Scan**

Run:
```bash
for f in docker/python.Dockerfile docker/caddy/Caddyfile frontend/Dockerfile compose.yaml .env.example scripts/sync-to-vm.sh core/src/normly_core/migrate.py chat/src/normly_chat/llm_client.py core/tests/test_migrate.py chat/tests/test_llm_client.py .dockerignore frontend/.dockerignore; do grep -q "SPDX-License-Identifier: AGPL-3.0-or-later" "$f" && echo "ok  $f" || echo "MISSING header: $f"; done
git grep -nE "(sk-|Bearer [A-Za-z0-9]{20,}|postgresql\+psycopg://[^:]+:[^@c][^@]*@)" -- ':!docs/superpowers' ':!*.md' || echo "no credential-looking strings"
```
Expected: alle `ok`; `no credential-looking strings` (die einzige URL mit Passwort ist `change-me` in `.env.example`).

- [ ] **Step 3: Branch-Zustand**

Run: `git status --short && git log --oneline main..HEAD`
Expected: Arbeitsbaum sauber; Commit-Liste der Tasks 1–10 plus Spec/Plan-Commits.

- [ ] **Step 4: Push und PR — nur nach ausdrücklicher Freigabe des Nutzers** (löst einen CI-Lauf aus)

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

**Spec coverage:** Image-Aufbau (Tasks 3–6), Compose mit Profilen, Migrate-Einmal-Dienst, Healthchecks, nur Frontend/Caddy erreichbar (Task 8, geprüft in Task 9 Step 7), LLM-Client mit Provider-Auswahl und Tests (Task 7), Modellgewichte im Image ohne Laufzeit-Download (Task 3, geprüft in Task 9 Step 3), Docling-Modelle nur im Pipeline-Image (Task 5), Ingestion auf der VM per `run` (Task 8 Profil `tools`, Guide in Task 10), Dokumentation ADR-022/CLAUDE.md/SRS/Self-Hosting/Frontend-README (Task 10), Verifikation beider Pfade inklusive Idempotenz (Task 9). BFF-Verifikation aus der Spec: in Task 8 implizit — Backends ohne `ports`, Frontend-Route-Handler nutzen `getBackendUrls()` serverseitig (`frontend/src/lib/backend-urls.ts`); Client-Komponenten rufen nur `/api/...`. Sollte in Task 9 Step 2 eine Seite im Browser gegen `api:8000` laufen wollen, zeigt sich das als Netzwerkfehler und wird dort behoben.

**Type consistency:** `build_llm_client_from_env`, `get_llm_client`, `app.state.llm_client`, `LlmClient`, `OpenAiCompatibleClient(base_url, model, api_key, *, timeout, transport)` sind in Task 7 und 8 (`.env.example`) identisch benannt; `normly_core.migrate.main`/`upgrade_to_head` in Task 2 und 5/8 (`python -m normly_core.migrate`) konsistent; `NORMLY_CORE_DIR` Default `/app/core` entspricht dem `COPY core /app/core` in Task 3.

**Offen gelassen, bewusst:** exakte Ollama- und Mailpit-Tags (Task 8 Step 1–2 ermitteln sie). Verifiziert beim Schreiben: `EmbeddingModel.embed_query` existiert, `db_url`/`CORE_DIR` in `core/tests/conftest.py`, Frontend-Routen `/api/auth/register` und `/api/chat`, `ChatRequest` mit `message`/`jurisdiction`/`language`.
