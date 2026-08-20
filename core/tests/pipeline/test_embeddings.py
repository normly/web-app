# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import normly_core.pipeline.embeddings as embeddings
from normly_core.pipeline.embeddings import MODEL_PATH_ENV_VAR, MODEL_NAME, EmbeddingModel


def test_embed_returns_1024_dimensional_vector():
    model = EmbeddingModel()

    vector = model.embed("Der Unternehmer hat dafür zu sorgen, dass Gefährdungen vermieden werden.")

    assert len(vector) == 1024
    assert all(isinstance(component, float) for component in vector)


def test_embed_is_deterministic_for_the_same_text():
    model = EmbeddingModel()
    text = "Sicherheit am Arbeitsplatz"

    first = model.embed(text)
    second = model.embed(text)

    assert first == second


def test_model_name_matches_the_loaded_model():
    assert MODEL_NAME == "intfloat/multilingual-e5-large"


def _loaded_argument(monkeypatch, **kwargs):
    """
    What the constructor asked `SentenceTransformer` to load — which code path
    it took, not what the model computes, which the tests above already cover
    against the real model.
    """
    loaded: list[str] = []

    def loader(name_or_path):
        loaded.append(name_or_path)
        return object()

    monkeypatch.setattr(embeddings, "SentenceTransformer", loader)
    EmbeddingModel(**kwargs)
    return loaded[0]


def test_a_local_model_path_is_loaded_instead_of_the_hosted_model_id(monkeypatch, tmp_path):
    """
    Production must never fetch the weights from huggingface.co: it provisions
    them locally and points the model at that directory.
    """
    monkeypatch.delenv(MODEL_PATH_ENV_VAR, raising=False)

    assert _loaded_argument(monkeypatch, model_path=tmp_path) == str(tmp_path)


def test_the_model_path_can_come_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(MODEL_PATH_ENV_VAR, str(tmp_path))

    assert _loaded_argument(monkeypatch) == str(tmp_path)


def test_without_a_local_path_the_hosted_model_id_is_used(monkeypatch):
    monkeypatch.delenv(MODEL_PATH_ENV_VAR, raising=False)

    assert _loaded_argument(monkeypatch) == MODEL_NAME
