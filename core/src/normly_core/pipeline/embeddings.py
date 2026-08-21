# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-large"

#: Points the model loader at pre-provisioned weights on local disk.
MODEL_PATH_ENV_VAR = "NORMLY_EMBEDDING_MODEL_PATH"


class EmbeddingModel:
    """
    The local embedding model. Inference never leaves the machine.

    Provisioning, however, does unless it is told otherwise: passing a bare
    model id makes `sentence-transformers` download the weights from
    huggingface.co, a US-hosted service. That default is fine for local
    development and this test suite, where the weights land in the developer's
    own cache.

    **A production deployment must not rely on it.** The weights belong in the
    container image or in STACKIT object storage, mounted into the container,
    with the path handed over through `model_path` or the
    `NORMLY_EMBEDDING_MODEL_PATH` environment variable. `SentenceTransformer`
    loads a local model directory just as it loads a model id, so nothing else
    changes — but nothing reaches huggingface.co at runtime any more.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        *,
        model_path: str | Path | None = None,
    ):
        self._model_name = model_name
        resolved_path = model_path if model_path is not None else os.environ.get(
            MODEL_PATH_ENV_VAR
        )
        self._model = SentenceTransformer(
            str(resolved_path) if resolved_path else model_name
        )

    def embed(self, text: str) -> list[float]:
        # e5 models are trained with an instruction prefix; "passage: " is the
        # documented convention for indexing content (as opposed to "query: " for
        # search queries issued against the index).
        prefixed = f"passage: {text}"
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return vector.tolist()

    def embed_query(self, text: str) -> list[float]:
        # "query: " is e5's documented instruction prefix for search queries,
        # as opposed to "passage: " for indexed content -- same model, same
        # vector space, different prefix so the model can tell which role the
        # text plays.
        prefixed = f"query: {text}"
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return vector.tolist()
