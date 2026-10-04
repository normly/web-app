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
- About 20 GB of disk for images and models, plus about 45 GB of free disk
  for Docker's build cache during the first build.
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
