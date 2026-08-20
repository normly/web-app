# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from tests.test_documents_search import _seed_document


def test_detail_returns_a_classified_document(client, db_session):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(f"/v1/documents/{document.id}", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)


def test_detail_hides_a_document_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(f"/v1/documents/{document.id}", params={"jurisdiction": "FR"})

    assert response.status_code == 404


def test_detail_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(f"/v1/documents/{uuid.uuid4()}", params={"jurisdiction": "DE"})

    assert response.status_code == 404
