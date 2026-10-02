# AGENTS.md

Operational guidance for AI agents working in `normly/web-app`.

## Monorepo Architecture

No root package manager or workspace file exists. The repo contains four Python packages, one Next.js frontend, and documentation:

- `core/` (`normly-core`): Central domain models, SQLAlchemy ORM, Alembic migrations, PostgreSQL repository layer, ingestion pipeline (`docling`), and embeddings.
  - System dependency: Requires `libgl1` and `libglib2.0-0` (apt) for Docling's PDF extraction.
  - Pipeline CLI: `python -m normly_core.pipeline.cli {ingest|backfill-document-embeddings|cleanup-notifications|notify-watchers}`.
- `accounts/` (`normly-accounts`), `api/` (`normly-api`), `chat/` (`normly-chat`): FastAPI services.
  - **Critical**: All three depend on `normly-core`. Never install `normly-core` from PyPI (it is unpublished; any match is a typosquat). Always install editable from the local checkout: `pip install -e ../core -e .[dev]`.
- `frontend/`: Next.js 16 (App Router, standalone output, installable PWA) acting as a Backend-For-Frontend (BFF).
  - Browser requests talk only to frontend Route Handlers (`src/app/api/...`), which proxy to `accounts/`, `api/`, and `chat/`.
  - Auth tokens are confined to `httpOnly` cookies handled by the BFF layer; page JavaScript never inspects raw tokens.
- `docs/`: Technical documentation built with Zensical.

## Essential Commands

### Local Development & Docker Compose

- 1-Command full stack with Docker Compose and tmux: `make dev`
  - Seed sample data: `make seed`
  - Inspect Ollama: `make llm-ps`
  - Follow Ollama logs: `make llm-logs`
- Host-native development (with hot-reloading):
  - Setup environment: `make setup`
  - Run all services concurrently: `make dev-native`
  - Seed sample data: `make seed-local`

### Python Services (`core/`, `api/`, `accounts/`, `chat/`)

- Python version: 3.12 (minimum >= 3.11).
- Setup (from within package directory):
  - `core`: `pip install -e .[dev]`
  - `accounts`, `api`, `chat`: `pip install -e ../core -e .[dev]`
- Testing (requires Docker daemon for `testcontainers[postgres]` with `pgvector/pgvector:pg16`):
  - All tests: `pytest`
  - Single test file: `pytest tests/path/to/test_file.py`
  - Single test function: `pytest tests/path/to/test_file.py::test_name`
  - **Chat test quirk**: `chat/tests/test_structural_end_to_end.py` requires sibling local venvs (`../api/.venv/bin/uvicorn`, `../accounts/.venv/bin/uvicorn`) and a running Ollama server. Without them, exclude it:
    `pytest --ignore=tests/test_structural_end_to_end.py`

### Frontend (`frontend/`)

- Node version: Node 22 (`npm ci`).
- Unit tests: `npm test` (Vitest, scoped to `tests/unit/**/*.{test,spec}.{ts,tsx}`).
  - Single unit test: `npx vitest run tests/unit/path/to/test.test.ts`
- Typecheck: `npx tsc --noEmit`
- E2E tests: `npm run test:e2e` (Playwright; builds and starts standalone server on port 3000, forces `de-DE` locale).
- Production build: `npm run build`

### Database & Migrations (`core/`)

- All Alembic migrations live centrally in `core/migrations/` configured via `core/alembic.ini`.
- Apply migrations: `cd core && alembic upgrade head`
- Check current revision: `cd core && alembic current`

### Documentation (`docs/`)

- Dependencies: `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`
- Build: `zensical build`
- Notice: 3 `[[wiki-link]]` warnings in `docs/superpowers/specs/` are a known, expected baseline.

## Framework & Operational Quirks

- **No `NEXT_PUBLIC_*` runtime vars in frontend**: All frontend configurations (`NORMLY_API_BASE_URL`, `NORMLY_ACCOUNTS_BASE_URL`, `NORMLY_CHAT_BASE_URL`, `NORMLY_INSTANCE_NAME`, etc.) are read at request time via `process.env` in server routes/components to allow multi-tenant deployment from a single image (ADR-010).
- **Google OAuth Redirect URI**: `accounts`'s `NORMLY_GOOGLE_REDIRECT_URI` must point to the frontend's route handler (`https://<domain>/api/auth/google/callback`) rather than `accounts` itself, so tokens remain sealed in `httpOnly` cookies.
- **Repository-only DB access (ADR-006)**: Business logic in services and pipeline must access the database exclusively via repository classes in `normly_core.graph.postgres.repositories`. Never execute ad-hoc SQL or direct ORM queries in business logic.
- **Lineage tracking**: Every derived artifact (segment, embedding, graph edge, export) must reference its source delivery to support legal revocation.

## Repo Conventions & Constraints

- **Commit format**: Conventional Commits with Developer Certificate of Origin (`git commit -s -m "type(scope): description"`). Signed-off-by is strictly required; pseudonyms not permitted.
- **Branches & PRs**: Never commit directly to `main`. Create feature branches and open pull requests against `main`.
- **License headers**: Every new source file must include a license header:
  - Free core (`core`, `accounts`, `api`, `chat`, `frontend`):
    ```
    // SPDX-License-Identifier: AGPL-3.0-or-later
    // Copyright (C) 2026 normly contributors
    ```
    *(use `#` comment syntax in Python files)*
  - SDKs / API specifications: `Apache-2.0`
- **Language policy (ADR-020)**:
  - Code, identifiers, commits, guides, references, and `README.md` files must be in English.
  - Domain-specific terms without accurate English equivalents retain German names (e.g. `Normenausschuss`, `Regelwerk`).
  - `CLAUDE.md`, `docs/adr/`, `docs/srs/`, and `docs/superpowers/` remain German.
- **Strict prohibitions**: No US cloud services for hosting/data/secrets (production runs on STACKIT; GitHub is only used for open source code/CI/GHCR per ADR-021). No DRM/licensing enforcement in the free core. No scraping of commercial standards catalogs.
