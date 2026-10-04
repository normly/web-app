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
# CPU-only torch wheels: the target VM has no GPU, CUDA builds would add ~4 GB of dead weight.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/core-requirements.txt

# 2) Embedding weights, fetched once at build time (the only moment
#    huggingface.co is contacted). Cached until the model name changes.
#    Downloaded into a throwaway HF_HOME and chowned in the same RUN, so the
#    layer holds only the saved weights, already owned by normly.
RUN HF_HOME=/tmp/hf python - <<'PY' \
    && rm -rf /tmp/hf \
    && chown -R normly:normly /opt/models
from sentence_transformers import SentenceTransformer
SentenceTransformer("intfloat/multilingual-e5-large").save("/opt/models/multilingual-e5-large")
PY

# 3) The core package itself (code, alembic.ini, migrations). Changes here
#    only rebuild from this layer on.
COPY core /app/core
RUN pip install --no-deps /app/core \
    && chown -R normly:normly /app

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
