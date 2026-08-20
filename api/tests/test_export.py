# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from tests.test_edges import _seed_two_documents_with_an_edge


def test_export_returns_a_license_notice_and_the_classified_graph(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    body = response.json()
    assert body["license"]["license_name"] == "ODbL-1.0"
    assert body["jurisdiction"] == "EU"
    document_ids = {d["id"] for d in body["documents"]}
    assert str(standard.id) in document_ids
    assert str(legal_act.id) in document_ids
    assert len(body["edges"]) == 1


def test_export_excludes_documents_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "FR"})

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_export_rejects_an_unsupported_format(client, db_session):
    response = client.get("/v1/export", params={"jurisdiction": "EU", "format": "xml"})

    assert response.status_code == 400
