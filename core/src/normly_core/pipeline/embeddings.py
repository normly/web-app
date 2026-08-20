# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-large"


class EmbeddingModel:
    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        # e5 models are trained with an instruction prefix; "passage: " is the
        # documented convention for indexing content (as opposed to "query: " for
        # search queries issued against the index).
        prefixed = f"passage: {text}"
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return vector.tolist()
