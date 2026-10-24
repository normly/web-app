# Design: Image pipeline (STACKIT deployment, sub-project 2/4)

As of: 2026-10-08 · Status: implemented and verified live (PR #14, merge
ea70cc8, release `v0.1.0`, 2026-10-08; results at the end of this document). Roadmap and fundamental decisions E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.
Predecessor: `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md`
(merged as PR #12, 2026-10-08).

## Goal

The five container images from TP1 are no longer built only on the STACKIT VM,
but built centrally in GitHub Actions, signed and published with
version tags in the GitHub Container Registry (GHCR)
(REQ-DIST-004, REQ-GIT-005, ADR-010, ADR-021). The same Git tag yields
the same image: dependencies, base images and model weights are
pinned (REQ-BUILD-001).

This creates what is missing today:

- **Rollback point.** Today every build on the VM overwrites
  `normly-api:local`; there is no previous image (REQ-INST-004
  requires one).
- **Self-hosting without an own build.** ADR-010 promises publicly
  obtainable, signed images; `docs/guide/self-hosting.md` says today
  "No published images yet".
- **Traceability.** A running image can be attributed to a commit, workflow
  and signature.
- **Relief for the VM.** A pure operations server pulls finished images
  instead of keeping source code, build tools and around 5 GB of build layer
  (prerequisite for the downsizing from TP1a).

Not part of this sub-project: switching the VM from "build itself"
to "pull a tag", rollout and rollback script, signature verification as a
mandatory step before start, data version import (all TP4). The
live system on `app.normly.ai` remains untouched by TP2.

## The owner's decisions (2026-10-08, not to be renegotiated)

### D1 — Signature: cosign keyless via GitHub OIDC

Every pushed image is signed with cosign via its digest. The
workflow receives a short-lived certificate from Sigstore (Fulcio) per run;
the signature lands in the transparency log (Rekor). No private
key is ever generated, stored or rotated. The certificate binds
the signature to repository, workflow file and commit.

**The owner's rationale:** The trust anchor — the public
Sigstore infrastructure — is **operated by the Linux Foundation, a
non-profit organization**. This distinguishes it qualitatively from the
commercial US services in the build chain that ADR-021 permits for the free
core (GitHub Actions, GHCR). A further dependency on a
non-profit operator weighs less than the key management of the
alternative.

**Rejected:** own cosign key pair (private key as a
GitHub secret, public key in the repo). No Sigstore dependency, but instead
rotation, secure storage outside GitHub and, on key loss,
re-signing of all images.

### D2 — One version for all five images, Git tag as the single source

A Git tag `vX.Y.Z` produces all five images from the same commit with
the same version tag. There is no version per package.

**The owner's rationale:** The services are tested against each other only in one shared
combination; `api` and `chat` even share the
base image. A rollback in TP4 then means "all images to 0.1.0", a
single step, and which combination was tested together can be read from the tag.
The version fields in the four `pyproject.toml` and in
`frontend/package.json` are set by hand to the same
value in the release commit; the workflow aborts if tag and `core` version do not
match.

**Rejected:** own version per package. Allows republishing only the frontend,
but needs one tag per package per release, and the
tested combination can no longer be read off.

**First release tag:** `v0.1.0` on the state after the merge of this
sub-project, so that TP4 has a rollback point from the start.

### D3 — Builds happen only on merge to `main`, on release tags and manually

Pull requests continue to trigger only the test pipeline. A broken
Dockerfile only shows up after the merge, but loudly and without harm:
`edge` stays on the last working state, a release tag
fails visibly.

**Rationale:** At the time of the decision the repo was private, the
organization on the Free plan (2,000 Actions minutes per month); a
full build takes an estimated 10 to 15 minutes. **Addendum 2026-10-08:**
The owner set the repository to public after the spec was approved;
Actions minutes are therefore unlimited. The decision stands
nevertheless: fewer runs means less waiting time per PR and
less noise, and a PR build without a push yields no
artifact anyway. Revisit if broken Dockerfiles on `main` become a
recurring problem.

**Rejected:** additional build without push on pull requests that
change the Dockerfile, Compose or dependencies. Catches build errors before the
merge, but costs a full build per PR, and a path filter misses
code changes that break the build nevertheless.

### D4 — Reproducibility completely in TP2

All three items carried over from TP1 are done here: lock file for
the Python dependencies, Torch only from the CPU index, model weights with a
fixed revision in a build stage of their own. Not postponed.

## Inventory (2026-10-08, read from the repo)

- `docker/python.Dockerfile`: one file, stage `base` (python:3.12-slim,
  `core` dependencies via `pip install --extra-index-url` CPU Torch,
  e5 weights via `SentenceTransformer(...).save()`), on top of it the targets
  `api`, `chat`, `accounts`, `pipeline` (the latter additionally downloads the
  Docling models via `docling-tools models download`).
- `frontend/Dockerfile`: node:22-alpine, three stages, `standalone` output.
- `compose.yaml`: all services with `build:` and a local tag
  (`normly-api:local` etc.); `migrate` and `pipeline` share
  `normly-pipeline:local`.
- `.github/workflows/ci.yml`: six test jobs, each `pip install -e ../core
  -e .[dev]`; no image build.
- No Git tag in the repo; all packages are at `0.1.0`.
- Model weights today without a fixed revision: e5 downloads `main`; Docling downloads
  the layout model `docling-project/docling-layout-heron` and its
  ONNX variant from `main`, the Tableformer models
  `docling-project/docling-models` via tag `v2.3.0`. The download CLI
  offers no option for pinning.
- Python dependencies only as ranges in `pyproject.toml`; the three
  service packages note in a comment that the technical safeguard
  against resolving `normly-core` via an index is still pending.
- GitHub: organization on the Free plan. Repository **public** since 2026-10-08
  (still private during the brainstorming), hence
  unlimited Actions minutes. GHCR storage is free only for public
  packages; a private package with around 5 GB per Python image
  would immediately exceed the free quota. The roadmap decision "package
  public" is thus a prerequisite, not just a convenience. The owner has
  confirmed that the organization allows public packages.

## Build pipeline

### Workflow `.github/workflows/images.yml`

Separate from `ci.yml`. Triggers: `push` to `main`, `push` of a tag
`v*`, `workflow_dispatch`. Permissions at job level: `contents: read`,
`packages: write` (GHCR), `id-token: write` (keyless signature). Everything via
the built-in `GITHUB_TOKEN`, no PAT.

One job, sequence:

1. Checkout.
2. On a tag trigger: read the version from the tag (`v0.1.0` → `0.1.0`) and
   check it against `core/pyproject.toml`; abort on a mismatch (D2).
3. Free up disk space: remove preinstalled tools of the runner
   that are not needed (Android SDK, .NET, Haskell, CodeQL bundles). The
   GitHub runner has around 14 GB free, the base layer alone is around
   5 GB, plus the cache export.
4. Create a Buildx builder, log in to GHCR with `GITHUB_TOKEN`.
5. Compute the tag list (see Tagging) and pass it as a Bake variable.
6. `docker buildx bake --push` via `docker-bake.hcl`.
7. Signature: for each of the five images `cosign sign --yes <image>@<digest>`
   with the digest from the Bake metadata output. The digest is signed,
   never a moving tag.
8. Summary in the job summary: image digests, tags, run time.

Marketplace actions only where they save work and come from Docker,
Sigstore or GitHub itself: `actions/checkout`,
`docker/setup-buildx-action`, `docker/login-action`, `docker/bake-action`,
`sigstore/cosign-installer`. All by major tag with a comment stating which
version was current at the time of writing.

### `docker-bake.hcl` in the repo root

One Bake file defines the five targets and is the only
build definition for the CI. `compose.yaml` keeps its `build:` blocks
for the local build; both point to the same Dockerfiles and targets.

- Group `default` = `api`, `chat`, `accounts`, `pipeline`, `frontend`.
- The four Python targets share context (repo root) and Dockerfile; a
  single Bake invocation builds them in one BuildKit session, which deduplicates identical
  stages. The base layer is thus built once and
  uploaded once, and the registry stores it once.
- Only `linux/amd64`. The VM is x86_64; multi-arch would be double the build time
  without a taker. Revisit as soon as an ARM operator turns up.
- Variables: `REGISTRY` (default `ghcr.io/normly/web-app`) and `TAGS`
  (list, set by the CI; locally default `local`). The
  model revisions are not Bake variables; they are
  `ARG` defaults in the Dockerfile (see Reproducibility).
- Layer cache in the registry: per target `cache-from`/`cache-to` of type
  `registry` under `ghcr.io/normly/web-app/cache:<target>` with `mode=max`.
  Not the GitHub Actions cache: that is limited to 10 GB per repository.
  A follow-up build that only changes application code thus skips
  the Torch installation and the model download.
- Attestations: BuildKit produces an SLSA provenance and an
  SBOM per image (`attest` with `type=provenance,mode=max` and `type=sbom`) and
  pushes them next to the image. REQ-GIT-005 requires both per release;
  with Buildx it costs one line.

### Tagging

Image names: `ghcr.io/normly/web-app/api`, `.../chat`, `.../accounts`,
`.../pipeline`, `.../frontend`.

| Trigger | Tags |
|---|---|
| Push to `main` | `edge`, `sha-<7 characters>` |
| Git tag `vX.Y.Z` | `X.Y.Z`, `X.Y`, `latest`, `sha-<7 characters>` |
| `workflow_dispatch` | like the branch or tag on which it is started |

`latest` always points to the newest release, never to `edge`. `X.Y`
moves with the newest patch release of the minor line. The operator
decides how far their pin should be allowed to move.

### Signature verification by operators

An operator verifies without a GitHub account:

```bash
cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/api:0.1.0
```

The invocation appears verbatim in `docs/guide/self-hosting.md`. The verification as a
mandatory step before start on the VM (acceptance test REQ-GIT-005:
an unsigned artifact is rejected) belongs to the rollout script from TP4.

### Public packages

After the first successful push, six packages (five images, one
cache package) must be set to public by hand in the GitHub package settings.
If the organization does not allow creating public packages,
this has to be enabled beforehand in the org settings under Packages.
Both are possible only in the portal, not from the workflow; both
are listed as a mandatory step in the verification and in
`docs/guide/releasing.md`.

## Compose integration

`compose.yaml` keeps the `build:` blocks. The image names change:

| today | new |
|---|---|
| `normly-api:local` | `ghcr.io/normly/web-app/api:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-chat:local` | `ghcr.io/normly/web-app/chat:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-accounts:local` | `ghcr.io/normly/web-app/accounts:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-pipeline:local` (migrate, pipeline) | `ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-frontend:local` | `ghcr.io/normly/web-app/frontend:${NORMLY_IMAGE_TAG:-edge}` |

Effect: `docker compose up -d` pulls the published images if
they are missing locally; `docker compose pull` updates them; `docker compose
up -d --build` continues to build locally and tags the result under the same
name (harmless, the local build then wins until the next `pull`).
No second Compose file, no override.

`.env.example` gets `NORMLY_IMAGE_TAG` with an explanation of the tag families.
`compose.yaml` gets a note in its header comment that `docker-bake.hcl`
is the CI build definition and both files name the same targets.

The VM continues to run from `/opt/normly/src` with a local build until TP4 switches it
to `pull`. The change of the image names in `compose.yaml` only changes something
there once the next `git pull` plus `up -d --build` runs;
even then the VM continues to build locally under the new name.

## Reproducible builds

### Lock file with uv

A `pyproject.toml` in the repo root declares the four Python packages to be a
uv workspace:

```toml
[tool.uv.workspace]
members = ["core", "api", "chat", "accounts"]

[tool.uv.sources]
normly-core = { workspace = true }
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

Plus a single `uv.lock` in the repo root, under version control. Effect:

- `normly-core` is resolved explicitly from the checkout, never from
  an index. This closes the typosquat gap that
  `api/pyproject.toml`, `chat/pyproject.toml` and
  `accounts/pyproject.toml` today note as open in a comment; the
  comments are shortened accordingly.
- Torch (transitively via sentence-transformers) comes exclusively from
  the CPU index, all other packages exclusively from PyPI. Today
  `--extra-index-url` applies to every package.
- One lock file instead of four; resolution in seconds.
- `[project] version` in the four packages remains the source for the
  workflow's version check (D2). The root `pyproject.toml` has
  no `[project]` section; it is a purely virtual
  workspace anchor and is never built or installed as a package.

**Rejected:** pip-tools with a `requirements.txt` per package. Keeps the
per-package venvs, but produces four lock files whose resolutions
can drift apart, and solves neither the index separation for Torch nor
the `normly-core` resolution cleanly.

### Consequences for development and CI

- **One development environment** in the repo root (`.venv`), set up with
  `uv sync --all-packages --all-extras`. The previous `.venv` per package
  remain locally, but are no longer maintained; `.gitignore`
  knows both. `CONTRIBUTING.md` describes the new route (install uv,
  `uv sync`, `uv run pytest` in the respective package).
- **`ci.yml`:** the four Python jobs switch from `pip install -e ../core
  -e .[dev]` to `uv sync --locked --package normly-<name> --extra dev`
  and `uv run --package normly-<name> pytest`. `--locked` fails
  if `uv.lock` does not match the `pyproject.toml` (correction after the
  overall review 2026-10-08: `--frozen` does not check, `--locked` checks) — this way the
  lock file is checked in every PR, without a job of its own. uv comes via
  `astral-sh/setup-uv` with a pinned uv version; `test-core` keeps the
  `libgl1` step and its known red DGUV signature (not part of
  this sub-project).
- **Chat end-to-end tests** (`chat/tests/conftest.py`, today via
  `api/.venv/bin/uvicorn` and `accounts/.venv/bin/uvicorn`): start the
  neighboring services via `sys.executable -m uvicorn` from the shared
  environment. This removes the reason for their exclusion in the CI
  (`--ignore=tests/test_structural_end_to_end.py`); the exclusion is
  lifted if the four tests run green in the CI, otherwise it stays
  with an updated comment.
- The frontend side is already locked with `package-lock.json` and `npm ci`;
  nothing changes there.

### Dockerfile

`docker/python.Dockerfile`, new stage sequence:

1. `deps`: `python:3.12-slim` pinned by digest; uv via `COPY --from`
   from `ghcr.io/astral-sh/uv:<version>` (also by digest). Copies
   only `pyproject.toml`, `uv.lock` and the four package `pyproject.toml`,
   then `uv sync --locked --no-dev --no-install-workspace --package
   normly-core` into `/app/.venv`. This layer changes only when the
   lock file changes.
2. `weights`: downloads the model weights with `huggingface_hub.snapshot_download`
   at a fixed revision (see table) to `/opt/models`, in Docling's
   folder convention (`<repo_id with / → -->`), thereby replacing both the
   `SentenceTransformer(...).save()` call and `docling-tools models
   download`. For e5 only what is needed is downloaded (`ignore_patterns` for
   `onnx/`, `openvino/` and the `.bin` duplicates of the safetensors weights);
   the repo is in sentence-transformers format, `SentenceTransformer`
   reads it directly from the path. A stage of its own, so that a change of the
   lock file does not re-download the weights and vice versa.
3. `base`: `deps` plus `COPY --from=weights /opt/models /opt/models` plus
   `core` source code, installed with `uv sync --locked --no-dev --package
   normly-core`. User `normly` as before.
4. `api`, `chat`, `accounts`, `pipeline`: as before, only with `uv sync
   --locked --no-dev --package normly-<name>` instead of `pip install`.
   `pipeline` no longer downloads models itself; `NORMLY_DOCLING_ARTIFACTS_PATH`
   points to `/opt/models/docling` from the `weights` stage.

uv remains in the images as a single static binary (around 40 MB),
because each target stage needs it for its `uv sync`, and a
runtime stage of its own per target would double the Dockerfile structure from TP1.
Deliberately accepted.

`frontend/Dockerfile`: `node:22-alpine` pinned by digest; otherwise
unchanged.

### Model weights with a fixed revision

| Model | Hugging Face repo | today | new |
|---|---|---|---|
| Embedding e5 | `intfloat/multilingual-e5-large` | `main` | commit SHA |
| Docling Layout | `docling-project/docling-layout-heron` | `main` | commit SHA |
| Docling Layout ONNX | `docling-project/docling-layout-heron-onnx` | `main` | commit SHA |
| Docling Tableformer | `docling-project/docling-models` | tag `v2.3.0` | commit SHA |

The four revisions are in exactly one place: as `ARG` defaults with a
date comment in `docker/python.Dockerfile`, directly before the
`weights` stage. Neither `docker-bake.hcl` nor `compose.yaml` overrides
them; both build routes thus download the same weights. The concrete SHAs
are determined by the implementation plan at the time of writing (in each case
the commit that `main` or `v2.3.0` points to on that day).

Effect: a change of the weights is a deliberate commit with a visible
diff. The same Git tag yields the same embeddings, the prerequisite
for the versioned data version from TP4 to match the image.

The docstring instructions in `core/src/normly_core/pipeline/docling_extraction.py`
("docling-tools models download …") are adapted to the new retrieval via
`snapshot_download` with revision; `tests/pipeline/test_docling_offline.py`
remains the proof that no network access takes place at runtime.

## Documentation

- **ADR-023 "Image publication: GHCR, keyless signing, one version,
  lock file"** in `docs/adr/README.md`. Status accepted (2026-10-08).
  Decision: D1–D4 in short form. Rationale: Linux Foundation as the
  non-profit operator of the trust anchor; monorepo combination as the
  unit of testing; sparing build triggers; reproducibility as a
  prerequisite for matching the data version. Rejected: own key,
  version per package, PR builds, pip-tools. Consequence: references from
  REQ-BUILD-001, REQ-DIST-004, REQ-GIT-005.
- **`docs/srs/03-requirements.md`:** REQ-BUILD-001 and REQ-DIST-004
  get the reference to ADR-023 under "Further information".
  REQ-GIT-005 still names the STACKIT Container
  Registry in its acceptance criteria; the sentence is switched to GHCR (ADR-021) and gets the
  note that the verification as a mandatory step before start is part of TP4.
- **`docs/guide/self-hosting.md`:** the pull route becomes the default
  (`docker compose pull && docker compose up -d`), the local build the
  alternative. Requirements: the note about 45 GB of build cache applies only
  to the local build. New section "Verifying image signatures"
  with the `cosign verify` invocation and a sentence on provenance and SBOM.
  "Known gaps" loses the item "No published images yet".
- **`docs/guide/releasing.md`** (new, English, in the Zensical navigation
  after Self-Hosting): bump the version fields (four `pyproject.toml`,
  `package.json`, `package-lock.json`), release commit, set an annotated tag,
  push the tag, watch the run, set the packages to public the first time;
  change model revisions; what `edge`, `X.Y` and `latest`
  mean.
- **`CONTRIBUTING.md`:** section on the development environment with uv.
- **`README.md`:** a sentence that images are on GHCR, with a link to
  self-hosting.
- **Roadmap spec:** the TP2 section gets a reference to this spec and
  the note "implemented" after the verification.

## Verification

Nothing counts as done before it has actually run once. Every
push that triggers a workflow is agreed with the owner beforehand
(the usual rule from the STACKIT days; minutes have been free since the
repo was made public, but runs on `main` are visible
from outside).

1. **Locally, before the PR:** `uv lock` produces the lock file; `uv sync
   --all-packages --all-extras`; all four Python test suites and
   `npm test` green; `docker buildx bake` builds all five images locally;
   `docker compose up -d --build` starts the stack as verified in TP1
   (bundled profile); the chat end-to-end tests run from the shared
   environment.
2. **First `main` run after the merge:** pushes `edge` and `sha-…` for
   all five images, signatures and attestations. Note from the log:
   total run time, free disk space before the build, size of the
   pushed images. Set the packages to public.
3. **Signature verification from outside:** `cosign verify` as in the docs, without
   GitHub sign-in, against a public package; additionally
   `docker buildx imagetools inspect` shows provenance and SBOM.
4. **Pull route:** on a machine with an empty image cache
   `NORMLY_IMAGE_TAG=edge`, `docker compose pull`, `docker compose up -d`,
   the stack runs without a local build.
5. **Release:** version fields at `0.1.0` (already set so), tag
   `v0.1.0`, push of the tag. The run delivers `0.1.0`, `0.1`, `latest`;
   the version check (D2) let it pass. Compare the run time with
   run 2: the registry cache must take effect.
6. **Negative test of the version check:** a tag `v9.9.9` on the same
   commit makes the run abort in the second step, before a build
   begins (under one minute); then delete the tag locally and on GitHub.

## Risks and open items

- **Disk space on the runner.** If the freed space is not enough,
  the fallback is to split the Python targets and the frontend into two jobs
  or to set the cache export to `mode=min`. The first real run
  decides.
- **Org setting for public packages.** Confirmed by the owner on 2026-10-08:
  allowed. Remains a mandatory step after the first push
  (switch visibility per package).
- **Hugging Face availability at build time.** Contacted only at build time
  (as before); with fixed revisions the build reacts to a
  deleted repo with a clear error instead of silently different
  weights. Mirroring in STACKIT Object Storage remains an option for
  TP4.
- **Two build definitions** (`compose.yaml`, `docker-bake.hcl`) for
  the same targets. Deliberately accepted: both are short, and a
  Bake overlay over the Compose file would have dragged along the double target
  `migrate`/`pipeline` and the profile logic.
- **Drift of the version fields.** The workflow checks only `core`; the three
  other `pyproject.toml` and `package.json` could diverge.
  Accepted, `releasing.md` names all five places; a check of all
  five is one more line and can be added in the plan.

## Carried over to later sub-projects

- **TP4:** switch the VM to `docker compose pull`, rollout/rollback script
  with `NORMLY_IMAGE_TAG`, `cosign verify` as a mandatory step before start
  (acceptance test REQ-GIT-005), data version dump with a reference to the
  model revision of the producing image.
- **TP1a:** benefits from the relief for the VM; can be built independently of TP2.
- **Maintenance:** `uv lock --upgrade` as a recurring task; the seven
  npm findings from TP1 remain a maintenance PR of their own.

## Verification 2026-10-08 (Task 8, after the merge of PR #14)

All steps of the verification plan have run; measured, not assumed.

| Step | Result |
|---|---|
| PR #14, test pipeline | five jobs green; `test-core` red with the known four DGUV tests (cf. CI spec 2026-09-02); `uv sync --locked` in all jobs without lock errors (147 packages resolved, 135 installed) |
| First `Images` run on `main` (merge ea70cc8) | successful, **9 min 25 s**, cold (no registry cache); after the cleanup the runner had 110 GB free, disk space is not a bottleneck |
| Second run on `main` (README commit 9937b92, shortly afterwards) | waited for the first thanks to the concurrency group, then **5 min 09 s** with registry cache |
| Public packages | all six (`api`, `chat`, `accounts`, `pipeline`, `frontend`, `cache`) were anonymously readable **without a manual step** (HTTP 200 on the manifest): GitHub links packages to the public repo via the `org.opencontainers.image.source` label and adopts its visibility. The manual step from `releasing.md` remains documented as a fallback |
| Signature verification from outside | `cosign verify` (v3.1.3, without GitHub sign-in) confirms `api:edge`: certificate from the workflow `images.yml`, entry in the transparency log; SBOM (SPDX, syft 1.51.0) and SLSA provenance present on the image |
| Pull route | locally: `docker compose pull` pulls five images (Python images 7.5 GB each on disk, frontend 337 MB); `docker compose up -d` with `NORMLY_IMAGE_TAG=edge`: `migrate` exit 0, api/accounts/chat healthy, frontend HTTP 200, without a local build |
| Release `v0.1.0` (annotated tag on ea70cc8) | successful, **4 min 32 s**; version check of all five fields passed; `0.1.0`, `0.1`, `latest`, `sha-ea70cc8` point to the same digest (`api`: `sha256:e67d62a7…`) |
| Negative test `v9.9.9` | run aborts after **7 s** in the step "Check that a release tag matches the package versions", one `::error::` line per version field, no build; tag deleted locally and on GitHub |

**Findings:**

- The release image from ea70cc8 has a different digest than the `edge` image
  from the same commit (`sha256:96d067d4…` vs. `sha256:e67d62a7…`). Confirms
  the open item from ADR-023 and REQ-BUILD-001: same inputs, but
  no bit-identical images (timestamps in layers, apt packages).
- The concurrency group from the overall review proved itself on the first evening:
  two pushes to `main` within two minutes ran serially.
- The runner disk space cleanup was not necessary with a 145 GB root volume,
  but does no harm; it stays in.

**Follow-up work (not part of TP2):**

- `test-core` red: **resolved 2026-10-08.** Not the model revision (local
  cache and CI had the same commits), but missing system fonts:
  the fixture does not embed Helvetica, pdfium renders with a substitute font in the font-less
  container, and the layout model classifies the
  title line as `page_header` (FURNITURE). Proven by
  single-variable tests (locale, threads, determinism: no effect;
  `fonts-liberation` installed: identical to the host, 30/30 tests green).
  Fix: `fonts-liberation` in CI job and image; a PR of its own.
- Switch the weights stage to a lean parent image (a lock change
  re-downloads the weights today); `api`/`chat`/`accounts` without Docling models;
  `uv` out of the runtime images; pin the SBOM scanner image; set `latest` only
  if the tag is the highest.
- TP4: switch the VM to `docker compose pull`, `cosign verify` as a
  mandatory step before start.
