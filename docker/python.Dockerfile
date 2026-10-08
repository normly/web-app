# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# One Dockerfile, four runtime targets (api, chat, accounts, pipeline) on a
# shared chain of stages, so BuildKit builds and pushes the heavy layers once:
#
#   deps     third-party dependencies, installed from uv.lock (--locked)
#   weights  model weights at pinned revisions (the only stage that talks
#            to huggingface.co)
#   base     deps + weights + the core package
#   api/chat/accounts/pipeline  base + the service's own package
#
# Inputs are pinned: base images by digest, Python packages (including the
# build backend) by uv.lock, model weights by commit (REQ-BUILD-001,
# ADR-023). The one unpinned input left is the Debian apt packages
# libgl1/libglib2.0-0 (Debian snapshots are impractical; accepted).
# Build context: repo root.

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
# changes, not when application code does. The `build` group holds the
# build backend (hatchling) so the package installs below need no index.
# --no-install-workspace leaves the four normly packages out; each stage
# below adds its own.
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY api/pyproject.toml api/
COPY chat/pyproject.toml chat/
COPY accounts/pyproject.toml accounts/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group build --all-packages --no-install-workspace

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

# From here on uv targets the environment built in `deps` (UV_PYTHON pointed
# at the system interpreter there, only so `uv sync` could create the venv;
# left as is, `uv pip install` would write to /usr/local, off the PATH).
ENV UV_PYTHON=/app/.venv/bin/python

# The core package itself (code, alembic.ini, migrations). Dependencies are
# already in the environment, so --no-deps installs only the package.
COPY --chown=normly:normly core /app/core
RUN uv pip install --no-deps --no-build-isolation /app/core

# ---------------------------------------------------------------------------
FROM base AS api
COPY --chown=normly:normly api /app/api
RUN uv pip install --no-deps --no-build-isolation /app/api
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS chat
COPY --chown=normly:normly chat /app/chat
RUN uv pip install --no-deps --no-build-isolation /app/chat
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_chat.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS accounts
COPY --chown=normly:normly accounts /app/accounts
RUN uv pip install --no-deps --no-build-isolation /app/accounts
USER normly
EXPOSE 8000
CMD ["uvicorn", "normly_accounts.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
FROM base AS pipeline
ENV NORMLY_DOCLING_ARTIFACTS_PATH=/opt/models/docling \
    NORMLY_CORE_DIR=/app/core
USER normly
ENTRYPOINT ["python", "-m", "normly_core.pipeline"]
