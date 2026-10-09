# Self-Hosting

normly ships as container images plus a Compose setup that starts a
working instance with one command ([ADR-010](../adr/README.md#adr-010-auslieferung-als-container-daten-getrennt-vom-image)).
The knowledge base is **not** part of the images; it arrives as a
separately versioned dump (see "Importing the knowledge base").

## Requirements

- Docker Engine 24+ with Compose v2.20+ (`docker compose version`).
- 16 GB RAM for the bundled setup (two services load a 2 GB embedding
  model; the bundled Ollama runs a small Gemma model on CPU).
- About 20 GB of disk for images and models. Building the images yourself
  instead of pulling them needs about 45 GB more for Docker's build cache.
- A Linux host. The images are built for `linux/amd64`.

## Quick start (everything bundled)

```bash
git clone https://github.com/normly/web-app.git normly && cd normly
cp .env.example .env
# edit .env: set NORMLY_BUNDLED_POSTGRES_PASSWORD and the matching password
# inside NORMLY_DATABASE_URL
docker compose up -d
```

The first start pulls the five normly images from
`ghcr.io/normly/web-app` (about 3 GB to download, about 8 GB on disk; PyTorch, the embedding weights and
Docling's models are inside), pulls the Ollama model, runs the database
migrations and then brings up the four services. `NORMLY_IMAGE_TAG` in
`.env` selects which published tag you follow: `edge` (newest commit on
`main`, the default), a release such as `0.1.0`, its minor line `0.1`, or
`latest` (newest release). To update, change the tag if you want, then
`docker compose pull && docker compose up -d`.

To build the images from source instead — for example on a modified
checkout — run `docker compose up -d --build`; this takes 10–20 minutes
and needs the extra disk space listed above.

Afterwards:

- App: <http://localhost:3000> (the frontend is bound to localhost only;
  for remote access use the `edge` profile or an SSH tunnel, see
  `NORMLY_FRONTEND_BIND` in `.env.example`)
- Mail catcher (every e-mail the app sends): <http://localhost:8025>

Check `docker compose ps -a` (exited one-shot containers are hidden
otherwise): api, accounts, chat, frontend, postgres and ollama report
`healthy`; `migrate` and `ollama-pull` exit 0. On the first start, chat
answers may return 503 until `ollama-pull` has finished.

Running `docker compose up -d` again is safe: migrations are idempotent and
unchanged containers are left alone.

Changing `NORMLY_BUNDLED_POSTGRES_PASSWORD` after the first start has no
effect on an existing `postgres-data` volume.

### Changing the LLM model

Edit `NORMLY_LLM_MODEL` in `.env`, then run `docker compose up -d`;
`ollama-pull` re-runs and pulls the new tag.

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
  PostgreSQL 16+ with the `vector` extension available. The target
  database must already exist (the migration creates tables, not the
  database). Special characters in the password must be URL-encoded in
  the URL, and a literal `$` in `.env` must be written `$$` (Compose
  interpolates env files).
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

## Importing the knowledge base

The images contain no knowledge base. Set `NORMLY_KB_BASE_URL` in `.env` to the
public location of the versioned dumps, then run:

```bash
docker compose run --rm kb-import              # newest dump
docker compose run --rm kb-import 2026.10.1    # a fixed version
```

Before anything is written, the import checks the Ed25519 signature of the
dump manifest against the public key shipped in the image, the embedding model
revision (embeddings from another revision are incompatible with this
installation), and the SHA-256 checksum of every table file. A dump that fails
any check is refused and the database stays unchanged.

The import is idempotent: running it again with the same dump changes nothing.
It also stops without writing if user data (watchlists, notifications, chat
citations) still points at rows the new dump removes.

## Ingesting documents

```bash
mkdir -p data/raw/dguv   # put source PDFs here
docker compose run --rm pipeline ingest dguv --directory /data/raw/dguv
```

Sources: `eur-lex`, `dguv`, `baua`. Other maintenance commands:
`backfill-document-embeddings`, `cleanup-notifications`, `notify-watchers`.

## Known gaps

- No Helm chart. Kubernetes is not a target for the free core right now.
