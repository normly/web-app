# Design: Containerisation (STACKIT deployment, sub-project 1/4)

As of: 2026-10-01, approved 2026-10-04 · Status: approved. Roadmap and
fundamental decisions E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

## Goal

The repository yields five container images and a Compose setup
that starts a runnable normly instance with one invocation (REQ-DIST-004,
ADR-010). The same setup runs with a different configuration on the
STACKIT VM against PostgreSQL Flex and STACKIT AI Model Serving (E8:
verification happens directly there). Plus the one code change that
operation on STACKIT requires: an OpenAI-compatible LLM client in the
chat service.

Not part of this sub-project: image build in the CI and push to the GHCR
(TP2), DNS, Secrets Manager, cloud-init (TP3), rollout script, rollback,
data version import and export (TP4).

## The owner's preliminary decisions (from the roadmap, not to be renegotiated)

- `core` keeps Docling and sentence-transformers as mandatory dependencies.
  Consequence: one shared Python base image.
- The weights of `intfloat/multilingual-e5-large` are baked into this
  base image at build time.
- Iteration on the STACKIT VM: check out the repository there, build the images
  there.

## Image structure

Five published images plus one internal base image. All run as an
unprivileged user, all base images are pinned by tag (digest
pinning comes with signing in TP2).

| Image | Base | Content | Process |
|---|---|---|---|
| `normly-python-base` (internal, not published) | `python:3.12-slim` | `libgl1`, `core` installed (all dependencies), e5 weights under `/opt/models/multilingual-e5-large`, `ENV NORMLY_EMBEDDING_MODEL_PATH` pointing to them | — |
| `normly-api` | Base | `api` installed | `uvicorn normly_api.main:app --host 0.0.0.0 --port 8000` |
| `normly-chat` | Base | `chat` installed | `uvicorn normly_chat.main:app …` |
| `normly-accounts` | Base | `accounts` installed | `uvicorn normly_accounts.main:app …` |
| `normly-pipeline` | Base | `core/alembic.ini` + `core/migrations`, Docling models under `/opt/models/docling` (`docling-tools models download layout tableformer`), `ENV NORMLY_DOCLING_ARTIFACTS_PATH` | Entrypoint `python -m normly_core.pipeline`; migrations via `alembic upgrade head` |
| `normly-frontend` | `node:22-alpine` (multi-stage) | `npm ci`, `next build`; at runtime only `.next/standalone`, `.next/static`, `public` | `node server.js`, port 3000 |

Decisions on this:

- **Download the model weights at build time, do not copy them from the Hugging Face
  cache.** The build step calls `SentenceTransformer(MODEL_NAME).save(path)`.
  This makes the build reproducible and independent of the machine; it
  is the only moment in which huggingface.co is contacted. For the
  build on the STACKIT VM this is permissible: it is a download of public
  weights, no user data leaves the system. In TP2 the GitHub pipeline
  takes this over; then the VM no longer touches huggingface.co at all.
- **Docling models only in the pipeline image**, not in the base: `api`,
  `chat`, `accounts` do not need them, and this keeps the shared layer
  smaller.
- **The build context is the repository root** for all Python images (they
  need `core/` and their own package), `frontend/` for the frontend.
  A `.dockerignore` at the root excludes `.venv`, `node_modules`,
  `tests`, `.git`, `docs`, `site`.
- **Expected sizes:** base approx. 5 GB of dependencies plus 2.2 GB of weights;
  the three service images each add under 50 MB on top; pipeline plus approx.
  1 GB of Docling models; frontend under 300 MB.

## Compose structure

One file `compose.yaml` at the repository root, services can be switched on via profiles,
configuration via `.env` (template `.env.example` in the repo,
without secrets).

| Service | Profile | Image | Purpose |
|---|---|---|---|
| `postgres` | `bundled` | `pgvector/pgvector:pg17` | Database for self-hosting and development |
| `ollama` | `bundled` | `ollama/ollama` | LLM for self-hosting and development |
| `ollama-pull` | `bundled` | `ollama/ollama` | One-off service, pulls the configured model, then exits |
| `mailpit` | `bundled` | `axllent/mailpit` | Mail catcher, SMTP 1025, UI 8025 |
| `migrate` | always | `normly-pipeline` | One-off service `alembic upgrade head`, idempotent |
| `api`, `chat`, `accounts` | always | one image each | `depends_on: migrate: condition: service_completed_successfully` |
| `frontend` | always | `normly-frontend` | the only externally visible service |
| `caddy` | `edge` | `caddy:2` | TLS via Let's Encrypt, `reverse_proxy frontend:3000` |
| `pipeline` | manual (`docker compose run --rm pipeline ingest …`) | `normly-pipeline` | Ingestion on the VM, raw data from a volume |

Decisions on this:

- **Profiles instead of several Compose files.** An override cannot remove
  services, only change them; profiles can. `.env.example` sets
  `COMPOSE_PROFILES=bundled`, so that `docker compose up` starts everything for self-hosters without
  any further parameter (REQ-DIST-004: "one invocation"). The
  production `.env` on the VM sets `COMPOSE_PROFILES=edge` and points
  `NORMLY_DATABASE_URL` to Postgres Flex and the LLM to AI Model
  Serving.
- **Only the frontend is reachable**, backends sit in an internal
  network. The frontend is built as a BFF (`frontend/README.md`): the browser
  talks exclusively to Next.js route handlers, never to `api`, `chat`
  or `accounts` directly. This is to be verified before the ports are
  closed; if a route does point directly to a backend after all,
  it is routed through the BFF, not the backend opened.
- **Migrations as a one-off service before start**, not in the services'
  entrypoint. This way Alembic runs exactly once per `up`, not three times
  simultaneously from three containers.
- **Healthchecks** against `GET /openapi.json` per backend and `GET /` on the
  frontend, Postgres via `pg_isready`. Dedicated `/health` endpoints with a
  DB check would be better, but are a code change in three services and
  are noted as follow-up work for TP4, where rollback decisions depend
  on them.
- **Ollama model for development and self-hosting:** the smallest
  Gemma variant that the Ollama library offers at implementation time
  (check the tag during implementation and enter it in `.env.example`).
  Gemma family because of E2/E3; small, because it computes on CPU.
  The answer quality is then below production level; this is documented and accepted for
  self-hosters.
- **Ingestion runs on the VM** in the pipeline image; raw files are placed in
  a volume under `/data/raw/<source>`. Export and import of the
  data version as a versioned dump are TP4.

## Code change: LLM client in the chat service

Today: `OllamaClient(base_url, model).chat(messages) -> str`
(`chat/src/normly_chat/ollama_client.py`), created in `main.py`,
passed through via `dependencies.get_ollama_client`, used in
`routers/chat.py` and `synthesis._is_faithful`.

New:

- A protocol `LlmClient` with `chat(messages: list[dict]) -> str`.
- `OpenAiCompatibleClient(base_url, model, api_key)` calls
  `POST {base_url}/chat/completions` with `Authorization: Bearer` and
  returns `choices[0].message.content`. Like `OllamaClient`, a thin
  httpx call, no SDK dependency.
- Selection in `main.py` via `NORMLY_LLM_PROVIDER` (`ollama` | `openai-compatible`),
  `NORMLY_LLM_BASE_URL`, `NORMLY_LLM_MODEL`, `NORMLY_LLM_API_KEY` (only with the
  second provider). The old names `NORMLY_OLLAMA_BASE_URL` /
  `NORMLY_OLLAMA_MODEL` are dropped; they are referenced only in `main.py`, tests and
  docs, there is no deployment that would still need them.
- Production values: `openai-compatible`,
  `https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1`,
  `google/gemma-4-31B-it`, token from the `.env` (TP3: from the Secrets
  Manager).
- `get_ollama_client` becomes `get_llm_client`; type annotations to the
  protocol.

Tests: unit tests for `OpenAiCompatibleClient` with a mocked httpx transport
(success, HTTP error, request shape), one test for the provider selection in
`main.py`. Existing tests that stub `OllamaClient` remain valid via the
protocol.

## Documentation

- **ADR-022 "Operating environment phase 1"** in `docs/adr/README.md`: E1–E8
  with rationale and rejected options; model-origin rule with a revisit
  "European model"; temporary deviation from REQ-DIST-001. The
  open item "Public read access to STACKIT Container Registry" (wording at the time)
  in the register is deleted as settled by ADR-021.
- **CLAUDE.md**, section "Non-negotiable": a sentence on
  model origin (open-weight, OSI license, operation only on STACKIT, no
  data to the model vendor) with a reference to ADR-022.
- **SRS** `docs/srs/03-requirements.md`: REQ-DIST-001 (deviation with a
  reference), chapter 3.5 running text (model origin). REQ-INST-003
  (secrets flow) only in TP3, once the route is settled.
- **`docs/guide/self-hosting.md`**: replace the placeholder with the
  actual route: prerequisites, `cp .env.example .env`,
  `docker compose up`, first visit, where mails end up, how the model
  is changed. Note that the data version dump procedure follows (TP4).
- **`frontend/README.md`** and the services' README tables: new
  `NORMLY_LLM_*` variables.

## Verification (on the STACKIT VM, E8)

1. **Self-hosting path:** `COMPOSE_PROFILES=bundled docker compose up`
   starts without rework; migrations run through; the frontend responds
   on port 3000; registration produces a mail in Mailpit; a
   chat request returns an answer from Ollama.
2. **Production path:** `.env` with Postgres Flex, AI Model Serving and
   profile `edge`; `docker compose up`; `https://app.normly.ai` responds with a
   valid certificate as soon as DNS is in place (until then via the IP with
   Caddy in HTTP mode); the chat answer comes from Gemma 4; no container
   except `caddy` has a published port.
3. **Idempotency:** a second `docker compose up` changes nothing; `migrate`
   ends with "nothing to upgrade".
4. **No runtime download:** network access from the service containers to
   huggingface.co is not needed at runtime (check: start with
   outgoing access blocked except Postgres and Model Serving).
5. Existing test suites of all packages green; new tests for the
   LLM client green; `test-docs` at the 3-issue baseline.

## Review (2026-10-04, owner): approved

- Postgres version in the `bundled` profile: **17**, matching the booked
  Flex instance (version 17), so that dumps remain interchangeable.
- Caddy only in the `edge` profile; self-hosters without their own domain start without
  TLS termination; the self-hosting guide describes how the profile
  is switched on.
- Healthchecks via `/openapi.json`; dedicated `/health` endpoints with a
  DB check noted as follow-up work for TP4.

Target environment verified on 2026-10-04: VM `normly-prod` (Ubuntu 26.04 LTS,
`g1a.4d`, Public IP `213.17.23.196`, SSH as `ubuntu`), `/opt/normly/.env`
present (600), Postgres Flex reachable via TCP (ACL on the VM IP),
AI Model Serving responds with the token and lists `google/gemma-4-31B-it`.
Docker is not yet installed on the VM; that is the first
implementation step.

## Verification 2026-10-04

Checked on the STACKIT VM (Docker 29, Compose 2.40; versions according to Task 3), images built there.

**Image sizes:** python-base 6.59 GB; api 6.62 GB; chat 6.62 GB; accounts 6.65 GB; pipeline 7.94 GB; frontend 336 MB. The Python images are large because Torch and the embedding weights (multilingual-e5-large) are in the image.

**Self-hosting path (profile bundled, own Postgres, Ollama gemma3:4b; 2026-10-04: default model now gemma4:e4b, Apache-2.0; gemma3 fell under the Gemma Terms of Use):** `up -d --build` with cached layers (observed); after around 2 minutes all services healthy, `migrate` exit 0 with `migrations: at head` (revision 0031), `ollama-pull` exit 0. Frontend and /search return 200, registration 200 with exactly one mail in Mailpit, chat 200 with a fallback answer (empty database); the Ollama inference itself was therefore not checked on the bundled path; the only evidence for the bundled LLM is the successful `ollama-pull` and the health check. A second `up -d` creates no containers, `migrate` stays `at head`. The weights come from the image; the "huggingface" hits in the logs are only the URL text of a tokenizer warning.

**Production path (Postgres Flex, Model Serving, Caddy):** The first start failed because the database `normly` had not yet been created on the Flex instance (connection and sign-in worked). After creating it: `migrate` exit 0 `at head`; api, accounts, chat, frontend healthy; caddy Up; time until healthy not measured (at the check after 90 s all services were healthy). Ports: only caddy on 80/443, frontend on 127.0.0.1:3000; no postgres, ollama, mailpit.

**TLS and end-to-end:** `https://app.normly.ai/` returns 200 with a valid Let's Encrypt certificate (ssl_verify_result 0); HTTP redirects to HTTPS with 308. Chat via the public address: 200, fallback answer, no errors in the chat logs. Without segments the fallback answer needs no model; the call was therefore evidenced separately: the Model Serving call was confirmed from within the chat container (`OpenAiCompatibleClient`, google/gemma-4-31B-it, answer `'Test'` received).

**Firewall:** From outside, 8000, 3000, 5432, 11434 and 8025 are closed, 80 and 443 open.

**Observations:** The tokenizer warning (`fix_mistral_regex`) when loading the embedding model is harmless, but should be watched on a later model update. Containers have outgoing internet access; "offline" is evidenced by the weights in the image, not by a network block.
