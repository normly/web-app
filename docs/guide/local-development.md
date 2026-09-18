# Local Development

This guide explains how to run, seed, and develop **normly** on your local machine.

---

## Architecture Overview

normly consists of four Python backend packages and one Next.js frontend:

- **Database**: PostgreSQL 16 with the `pgvector` extension.
- **`core/`**: Central data model, Alembic migrations, PostgreSQL repository layer, and ingestion pipeline (`docling`).
- **`accounts/`** (Port `8001`): FastAPI service for registration, authentication, sessions, profile, and watchlists.
- **`api/`** (Port `8002`): FastAPI service providing deterministic reference graph queries (works, documents, edges, validity).
- **`chat/`** (Port `8003`): FastAPI service for natural-language search and chat synthesis over the reference graph.
- **`frontend/`** (Port `3000`): Next.js 16 App Router application acting as a Backend-For-Frontend (BFF), proxying requests to the backend services.

---

## Option 1: Quickstart with Docker Compose

The fastest way to run all services without installing Python 3.12, Node 22, or system dependencies locally:

```bash
docker compose up --build
```

This will automatically:
1. Start PostgreSQL with `pgvector` on port `5432`.
2. Run database migrations to `head`.
3. Launch `accounts` (8001), `api` (8002), and `chat` (8003).
4. Launch `frontend` on port `3000`.

### Seeding Sample Data

In a separate terminal, run:

```bash
./scripts/seed-data.sh --compose
```

This ingests sample DGUV and technical regulations into the running database.

### Enabling Local LLM Chat (Optional)

To start with local Ollama support:

```bash
docker compose --profile chat-llm up --build
```

---

## Option 2: Native Local Development (Hot-Reload)

For active code development where you want instantaneous hot-reloading without rebuilding containers:

### Prerequisites

- **Python**: 3.12 (>= 3.11)
- **Node.js**: v22 & `npm`
- **Docker**: For running PostgreSQL with `pgvector`
- **System**: `libgl1` and `libglib2.0-0` (Debian/Ubuntu: `sudo apt-get install -y libgl1 libglib2.0-0` for Docling PDF processing)

### Automated Setup

Run the setup script:

```bash
./scripts/dev-setup.sh
```

This script will:
1. Start the PostgreSQL `normly-pg` Docker container on port `5432`.
2. Create `.venv` and install `core`, `accounts`, `api`, and `chat` in editable (`-e`) mode.
3. Apply all Alembic migrations (`alembic upgrade head`).
4. Seed initial sample documents into the database.
5. Install frontend dependencies with `npm ci`.

### Running All Services

Once setup is complete, run:

```bash
./scripts/dev-run.sh
```

All four services start concurrently with hot-reload enabled (`uvicorn --reload` and `next dev`). Press `Ctrl+C` to cleanly stop all services.

---

## Service Catalog

| Service | Local URL | Interactive API Docs | Purpose |
|---|---|---|---|
| **Frontend** | [http://localhost:3000](http://localhost:3000) | — | Web app & BFF proxy |
| **Accounts** | [http://localhost:8001](http://localhost:8001) | [/docs](http://localhost:8001/docs) | Authentication, sessions, watchlists |
| **API** | [http://localhost:8002](http://localhost:8002) | [/docs](http://localhost:8002/docs) | Reference graph search, document detail |
| **Chat** | [http://localhost:8003](http://localhost:8003) | [/docs](http://localhost:8003/docs) | Natural language queries |
| **Postgres** | `localhost:5432` | — | Database (`normly`/`normly`) |

---

## Querying the Database Directly

If you only want to query the reference graph without running the frontend:

### 1. Interactive Swagger UI
Start only Postgres and the API service:
```bash
uvicorn normly_api.main:app --port 8002 --reload
```
Browse to [http://localhost:8002/docs](http://localhost:8002/docs) to query `/v1/documents/search`, `/v1/work/{id}`, or `/v1/documents/{id}/edges`.

### 2. Python Script / REPL
Query directly via the repository layer:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from normly_core.graph.postgres.repositories import DocumentRepository

engine = create_engine("postgresql+psycopg://normly:normly@localhost:5432/normly")
with Session(engine) as session:
    repo = DocumentRepository(session)
    for doc in repo.search("DGUV"):
        print(doc.title)
```

### 3. Direct SQL
```bash
psql -h localhost -p 5432 -U normly -d normly
```

---

## Running Tests

- **Backend (Python)**:
  ```bash
  cd core && pytest
  cd accounts && pytest
  cd api && pytest
  cd chat && pytest --ignore=tests/test_structural_end_to_end.py
  ```
- **Frontend (Vitest)**:
  ```bash
  cd frontend && npm test
  ```
