# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.pipeline.embeddings import EmbeddingModel


def test_embed_query_returns_a_vector_of_the_same_dimension_as_embed():
    model = EmbeddingModel()
    passage_vector = model.embed("Arbeitsschutz in Werkstätten")
    query_vector = model.embed_query("Wie sicher sind Werkstätten?")

    assert len(query_vector) == len(passage_vector)


def test_embed_query_and_embed_produce_different_vectors_for_the_same_text():
    # Different instruction prefixes ("query: " vs "passage: ") must reach the
    # model differently -- if they didn't, embed_query would be pointless.
    model = EmbeddingModel()
    text = "Sicherheit am Arbeitsplatz"
    assert model.embed(text) != model.embed_query(text)
