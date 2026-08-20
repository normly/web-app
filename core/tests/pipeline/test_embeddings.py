# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel


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
