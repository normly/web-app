# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import dataclasses
import uuid

import pytest

from normly_api.routers.documents import _document_to_response

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


def test_unresolvable_lineage_raises_a_named_error_not_an_attribute_error(db_session):
    """
    Lineage is mandatory, so a document whose delivery cannot be resolved is a
    broken invariant. It must fail with a message naming the missing link --
    not with an AttributeError on None, and not as a retryable-looking 503.
    """
    document = _seed_document(db_session, jurisdiction="DE")
    orphaned = dataclasses.replace(document, created_via_delivery_id=uuid.uuid4())

    with pytest.raises(RuntimeError, match="unknown delivery"):
        _document_to_response(orphaned, db_session)
