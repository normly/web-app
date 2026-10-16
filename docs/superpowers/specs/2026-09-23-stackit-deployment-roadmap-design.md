# Design: STACKIT deployment roadmap (overview, 4 sub-projects)

As of: 2026-09-23, amended 2026-10-01 (E8, TP1 preliminary decisions) · Status:
approved by the owner, the sub-projects follow, each with its own spec and plan.

## Context

Today the application runs only locally from development venvs. The repository
contains no Dockerfile, no Compose setup and no deployment step;
the GitHub CI (`.github/workflows/ci.yml`) only tests. ADR-005 and ADR-010
require signed container images plus a runnable Compose setup,
REQ-INST-001 operation exclusively on STACKIT, REQ-INST-002/004
automated deployment with rollback. On 2026-09-23 no resource for
operation exists on STACKIT yet.

A first brainstorming on 2026-09-11 had recorded the split into four
sub-projects and "VM with Compose, no Kubernetes", but broke off
at the LLM question. This document settles the fundamental questions and
fixes the scope of the sub-projects. It is deliberately an overview:
details (Dockerfile structure, Compose structure, secrets flow, rollout script)
are decided by each sub-project in its own brainstorming.

## Runtime needs of the application (read from the code)

- `frontend` (Next.js, `standalone` output, BFF): needs
  `NORMLY_API_BASE_URL`, `NORMLY_ACCOUNTS_BASE_URL`, `NORMLY_CHAT_BASE_URL`,
  `NORMLY_PUBLIC_BASE_URL`; configuration is read at runtime, one
  image for all instances.
- `api`, `chat`, `accounts` (each FastAPI/uvicorn): one shared
  PostgreSQL database with pgvector (`NORMLY_DATABASE_URL`).
- `api` and `chat` load the embedding model `intfloat/multilingual-e5-large`
  locally (`NORMLY_EMBEDDING_MODEL_PATH`); without a path set,
  `sentence-transformers` downloads from huggingface.co — forbidden in production,
  see the docstring in `core/src/normly_core/pipeline/embeddings.py`.
- `chat` today speaks exclusively the Ollama REST API
  (`chat/src/normly_chat/ollama_client.py`, `NORMLY_OLLAMA_BASE_URL`,
  default model `llama3.1:8b-instruct-q4_0`).
- `accounts` needs SMTP (`NORMLY_SMTP_*`) for magic link, verification,
  password reset, email change; optionally Google OAuth
  (`NORMLY_GOOGLE_CLIENT_ID/SECRET`, `NORMLY_GOOGLE_REDIRECT_URI` must point to
  the frontend callback route, see `frontend/README.md`).
- `core`: Alembic migrations (`core/migrations`), ingestion CLI
  (`python -m normly_core.pipeline`) with Docling/Torch (~6 GB of
  dependencies, `libgl1`), only for the data import, not in running
  operation.

## Fundamental decisions

All confirmed by the owner in this session, unless dated otherwise.

### E1 — Target environment: one STACKIT VM with Docker Compose (2026-09-11)

Confirms ADR-005. No SKE, no load balancer. Caddy terminates TLS on
the VM via Let's Encrypt. A move to SKE remains possible because the images
are identical, and is a separate later project.

### E2 — LLM inference: STACKIT AI Model Serving, initial model Gemma 4 31B

Managed, GPU-backed, billed per token, region eu01, OpenAI-compatible
API at `https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1`.
STACKIT itself operates exclusively open-weight models; according to the FAQ,
requests are neither stored nor used for training, no data exchange
between customers. This keeps the operations promise (CLAUDE.md,
REQ-INST-001): the data goes to STACKIT, not to the
model vendor.

Rejected: Ollama on the VM via CPU (response times of seconds to
minutes with 8B models, unacceptable for users); dedicated GPU VM with Ollama
(ongoing costs without load, no managed advantage).

The production model is selectable via configuration; default value
`google/gemma-4-31B-it` (Apache-2.0). Ollama remains for local development
and self-hosting, there also with a Gemma model of the same family,
so that prompts do not behave differently.

### E3 — Model-origin rule (new, becomes ADR-022 and a CLAUDE.md sentence)

Previously unregulated; today's Llama default is itself a Meta model.
Decided:

- Only open-weight models under an OSI-approved license (Apache-2.0, MIT,
  …). Thus permitted in the STACKIT catalog of 2026-09-23: Gemma 4 31B
  (Apache-2.0), gpt-oss 20B/120B (MIT), Qwen3-VL-235B (Apache-2.0). Not
  permitted: Llama 3.3 (Llama license), Qwen3.8 (Qwen license).
- Operation exclusively on STACKIT infrastructure; no request reaches
  the model vendor.
- European origin is a preference, not a requirement — the current catalog
  has no European chat model (Mistral only as an English
  embedding model). Revisit in the ADR: as soon as STACKIT offers a European
  model of suitable size, the switch will be examined.

Rejected: European origin as a requirement (would have left only the dedicated GPU VM,
buys a marketing argument without any data protection gain).

### E4 — DNS: entire zone `normly.ai` to STACKIT DNS

The registrar remains Strato (a German company, sees no traffic). The
nameservers are switched at Strato to `ns1.stackit.cloud` and `ns2.stackit.zone`;
beforehand all records — including the website entries — are created
in the STACKIT zone. Cloudflare (US) is dropped completely, and with it
proxy/CDN for the website; for a static website without
load peaks this is bearable. App hostname: `app.normly.ai`.

Rejected: delegating only `app.normly.ai` as a subzone (Cloudflare would remain
authoritative for the apex zone and thus in the resolution chain); leaving everything at
Cloudflare (breaks the rule that is the selling point).

### E5 — Mail sending: Strato SMTP from the existing mail package (changed 2026-10-03)

Originally (2026-09-23) IONOS Business. During the DNS move it turned out that
the domain's mail is already at Strato (MX `smtpin.rzone.de`,
autoconfig, DKIM policy, active mailbox `mail@normly.ai`). A
domain has only one mail recipient; IONOS alongside would have meant an MX change
and the migration of the existing mailbox. Decision:
additional mailbox `noreply@normly.ai` in the Strato package, SMTP access
from it (`smtp.strato.de`, port 587 STARTTLS), create a new SPF record
(was missing entirely so far), copy the DKIM records from the Strato customer area into the
STACKIT zone. Strato is a German company. Strato's
throttling only becomes relevant at several hundred mails per day;
at that point a switch of the entire mail hosting is a topic of its own.
Rejected: IONOS Business (MX conflict), own Postfix (deliverability).

### E6 — Images: GHCR via GitHub Actions (ADR-021, confirmed)

Package publicly readable (owner decision of 2026-09-14). Signing
runs in the GitHub pipeline and is covered by the ADR-021 exception.

### E7 — Only production on STACKIT, staging locally

REQ-DIST-001 requires separate environments with their own database. Deliberate
simplification for phase 1: one production environment on STACKIT; the local
Compose setup from sub-project 1 takes on the role of the staging environment.
A real staging environment (second VM, second database) comes as soon as there are
users whom a faulty deployment would hit. Recorded in ADR-022
as a deliberate, temporary deviation.

### E8 — Iteration directly on the STACKIT VM instead of locally (2026-10-01)

Owner decision against the recommendation to verify sub-project 1 locally
first: VM and Postgres Flex are booked immediately, the repository
is checked out on the VM and the images are built there (`docker
compose build`), without the detour via the GHCR. Advantage: real environment from
the start. Accepted: around €235/month accrue from booking, and every
iteration needs a build on the VM instead of on the development machine.
The GHCR pull route replaces the VM build with sub-project 2/4. The files
themselves (Dockerfiles, Compose) are the same; the local Compose setup
remains a result of TP1 for self-hosters and as a staging substitute (E7).

## STACKIT products to book

List prices from the STACKIT price list (PDF, version 18), region EU01,
net per month at 720 h. Prices serve for orientation; the portal
is binding.

| Product | Configuration | approx. €/month | Purpose |
|---|---|---|---|
| Project | own project for operations, separate from the Git project | 0 | Separation of operations / data project |
| Compute Engine | `g1a.4d` (4 vCPU, 16 GB, AMD), Ubuntu LTS, variant without the suffix `-m` | 142 | all containers via Compose |
| Block Storage (VM) | 80 GB boot volume, Premium Performance 1 (class 2 would be ~€12/month more expensive and brings nothing for a Compose VM; Premium Capacity is too slow for Docker builds) | approx. 8 | OS, images, model weights |
| Public IP (IPv4) | one | 3 | Entry point for Caddy |
| PostgreSQL Flex | `2.4` Single (2 vCPU, 4 GB), 20 GB Premium Capacity, newest PG version; extension `vector` | 92 | one DB for all services |
| DNS | zone `normly.ai`, tariff DNS-100 | 2 | see E4 |
| Secrets Manager | one instance, AppRole auth (public preview since 2026-08-31) | < 1 | REQ-INST-003 |
| Object Storage | one bucket, Standard, AES-256 at rest by default | 0.03/GB | data version dumps, DB backups, model weights |
| AI Model Serving | one token, model `google/gemma-4-31B-it` | per token | see E2 |

Base load around €250/month plus tokens in the iteration phase; after TP1a
and downsizing to `g1a.2d` around €180/month. LLM price tiers according to the list:
Standard €0.15 input / €0.25 output per million tokens, Plus 0.45 / 0.65,
Premium 1.50 / 1.75. Only the portal shows which tier each model
is assigned to.

Rationale for the VM size: `api` and `chat` each hold ~3 GB RAM for the
embedding model with Torch, plus frontend, accounts, Caddy; the ingestion
needs a further 6–8 GB when required. With 8 GB (`g1a.2d`) the ingestion
would no longer be possible on the VM.

Rationale for Postgres Single: the 3-node variant (€142) brings
high availability, which is worth nothing before the first user; a flavor change
works without downtime according to the docs, Flex does backups itself.

Not booked: SKE, load balancer, STACKIT Container Registry.

**Booking time:** originally VM, Public IP, Postgres Flex and Object
Storage only after completion of sub-project 1 (to avoid costs for empty
resources). With E8 (2026-10-01), project, VM, Public IP
and Postgres Flex are booked immediately; DNS zone, AI token, Secrets Manager and
Strato mailbox `noreply@` in parallel, Object Storage with sub-project 4.

## Sub-projects

Order strictly 1 → 4; each needs the previous one. Each sub-project
gets its own brainstorming, its own spec, plan and PR. With E8
only the booking of VM and Postgres moves from TP3 ahead of TP1; the rest of the
scope stays.

### TP1 — Containerisation (verified on the STACKIT VM, see E8)

**Scope:**
- Dockerfiles for `frontend`, `api`, `chat`, `accounts` and a
  pipeline image from `core` (migrations and ingestion, with Docling).
- A Compose setup that starts with one invocation: PostgreSQL with pgvector,
  Ollama (local development / self-hosting), a mail catcher, all four
  services; migrations run before the app starts; the embedding model is
  provided without a runtime download.
- The one code change: an OpenAI-compatible LLM client in `chat` behind
  the same interface as `OllamaClient`, selectable via configuration;
  switch of the Ollama default model from Llama to a Gemma model (E3).
- Anchoring the model-origin rule: ADR-022, CLAUDE.md sentence.

**Result:** self-hosting promise from ADR-010 / REQ-DIST-004 fulfilled;
`docs/guide/self-hosting.md` loses its placeholder.

**Decided in advance on 2026-10-01 (owner):**
- The dependencies of `core` stay unsplit (Docling and
  sentence-transformers as mandatory). Against the recommendation of optional
  extras `[ingest]`/`[embeddings]`. Consequence: one shared Python
  base image (~5 GB) with all dependencies; the four Python images
  only add their own package on top; Docker shares the base layer,
  it is pulled again only when dependencies change.
- Embedding weights (`multilingual-e5-large`, 2.2 GB) are baked into the
  base image at build time, path fixed via
  `NORMLY_EMBEDDING_MODEL_PATH`. No runtime download, no init step.

**Open for the TP1 brainstorming:** split of the Compose base vs. overrides
for production; migration run (init container vs. entrypoint); mail catcher;
Ollama model for development; place of ingestion (locally with dump export vs.
on the VM); how the CI builds the images without slowing down the test jobs.

### TP2 — Image pipeline

**Scope:** GitHub Actions job that builds and signs the five images and pushes them to
the GHCR (`ghcr.io/normly/web-app/...`) — on merge to `main` as a
pre-release, on Git tag `vX.Y.Z` as a release. `permissions: packages:
write` with `GITHUB_TOKEN`, no PAT. Set the package to public on the first push
(manually in the GitHub package settings, do not forget).

**Result:** images are publicly obtainable and signed
(REQ-DIST-004, REQ-GIT-005).

**Open:** signing method (cosign keyless via GitHub OIDC vs. own
key); tagging scheme; whether multi-arch is needed (VM is x86_64).

**As of 2026-10-08:** design in
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`
(decisions D1–D4: cosign keyless, one version per tag, build only on
`main`/tags, full reproducibility with uv lock and pinned
weights), implemented according to `docs/superpowers/plans/2026-10-08-tp2-image-pipeline.md`.
**Implemented and verified live 2026-10-08** (PR #14, release `v0.1.0`;
measurements in the section "Verification 2026-10-08" of the TP2 spec).

### TP3 — Target environment on STACKIT

**Scope:**
1. DNS move according to E4 as the first step (create the zone, copy the
   records, switch the nameservers at Strato, wait for propagation).
2. Bookings according to the table.
3. VM setup via cloud-init (Docker, Compose, Caddy, firewall only
   80/443/SSH), Compose overrides for production.
4. Secrets flow: credentials are kept in the Secrets Manager; the VM obtains
   them via AppRole at start, not permanently in environment variables
   (REQ-INST-003).
5. Strato SMTP (E5) including SPF/DKIM records; AI Model Serving token (E2);
   Google OAuth redirect URI to `https://app.normly.ai/api/auth/google/callback`.

**Result:** `app.normly.ai` responds with a manually started
version; the database runs on Postgres Flex; no secret in the repo or on
GitHub.

**Open:** Terraform (STACKIT provider) vs. portal plus cloud-init for the
VM; exactly how the AppRole secret ID bootstrap gets onto the VM; whether
the Postgres Flex ACL is restricted to the VM IP (yes, default assumption).

### TP4 — Deployment automation

**Scope:** rollout of new images to the VM without STACKIT credentials on
GitHub — that is, pull-based from the VM (script that pulls a tag,
runs migrations, restarts services). Rollback to the previous
tag. Import of the versioned data version from Object Storage; backup of the
database to Object Storage.

**Result:** REQ-INST-002 (automated), REQ-INST-004 (rollback),
ADR-010 (data separate from the image) fulfilled.

**Open:** trigger of the rollout (manual invocation via SSH vs. a timer that
polls GHCR); dump format and versioning of the data version;
retention period of the backups (open item from the ADR register).

### TP1a — Load the embedding model only once, VM on `g1a.2d` (follow-up work directly after TP1)

**Occasion (2026-10-03):** While creating the server in the portal, the
owner questioned the costs. The 16 GB of `g1a.4d` (€141.59/month) are
necessary because `api` and `chat` each load the same embedding model
(`multilingual-e5-large`, ~3 GB RAM with Torch) themselves and the
ingestion needs a further 6–8 GB. Decision: book `g1a.4d` for the
iteration phase, then remove the duplication and downsize the server
to `g1a.2d` (€70.79/month) — permanently around €71/month
less. STACKIT allows changing the machine type while the server
is stopped.

**Scope:** Only one service holds the model in memory; the other obtains
embeddings via an internal HTTP interface. The obvious choice is `api`
as the holder (it already offers search) and an endpoint that `chat`
calls for query embeddings; the exact interface, error handling
and the startup behavior are settled by a short brainstorming of its own.
A further prerequisite for the small server is that the ingestion no longer
runs on the VM, but locally with dump import — TP4 delivers that.
The downsizing itself therefore only happens once TP1a *and* the
dump import from TP4 are in place; TP1a itself can be built immediately
after TP1.

**Result:** VM idle below 5 GB RAM; `g1a.2d` comfortable.

## Documentation that comes along

- **ADR-022 "Operating environment phase 1"**: E1–E7 with rationale and
  rejected options; revisit European model; temporary deviation from
  REQ-DIST-001. Written in TP1, because the model-origin rule touches
  code there.
- **CLAUDE.md**: a sentence on model origin under "Non-negotiable".
- **SRS**: REQ-INST-003 (secrets flow via AppRole), REQ-DIST-001
  (staging deviation with a reference to ADR-022), chapter 3.5 running text
  (model origin), REQ-GIT-005 (acceptance test still names the STACKIT
  Container Registry; since ADR-021 it is the GHCR; correct in TP2).
- **`docs/guide/self-hosting.md`**: fill in TP1 with the actual
  Compose route.
- **ADR register "Open items"**: "Public read access to STACKIT
  Container Registry" (wording at the time) has become moot through ADR-021 and is
  deleted.

## Non-goals

- Kubernetes/SKE, load balancer, multi-region.
- Real staging environment on STACKIT (see E7).
- Native app, licensed full texts, commercial layer.
- Switching the embedding model to STACKIT Model Serving embeddings
  (would mean re-embedding the entire collection; `e5-mistral-7b`
  is English-focused, `Qwen3-VL-Embedding-8B` has different
  dimensions). Stays local in `api`/`chat`.

## Still to check in the portal (cannot be settled from here)

- Price tier of Gemma 4 31B in AI Model Serving and rate limits per model.
- Data processing agreement / terms and conditions for AI Model Serving (logging,
  retention).
- Meaning of the flavor suffix `-m` (double price, not explained in the docs)
  — take the variant without the suffix.
- Whether Postgres Flex can switch from Single → Replica without being recreated.

## Sources

- STACKIT AI Model Serving: catalog
  (`docs.stackit.cloud/de/products/data-and-ai/ai-model-serving/basics/available-shared-models/`),
  FAQ, "Use the models".
- STACKIT Machine Types EU01, PostgreSQL Flex Flavors and Supported
  Extensions, DNS FAQ, Secrets Manager FAQ, Object Storage Core Features.
- STACKIT price list PDF version 18 (`stackit.com/en/asset/download/37788/file/STACKIT_price_list.pdf?version=18`).
