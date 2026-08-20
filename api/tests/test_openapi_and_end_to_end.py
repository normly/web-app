# api/tests/test_openapi_and_end_to_end.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def test_openapi_schema_documents_every_v1_endpoint(client):
    schema = client.get("/openapi.json").json()

    paths = set(schema["paths"].keys())
    assert paths == {
        "/v1/documents",
        "/v1/documents/{document_id}",
        "/v1/documents/{document_id}/edges",
        "/v1/documents/{document_id}/validity",
        "/v1/export",
    }
    assert schema["info"]["license"]["name"] == "Apache-2.0"


def test_openapi_schema_documents_the_error_responses_with_their_model(client):
    """
    The error bodies are only useful to a client generator if the schema names
    them. Asserting the $ref, not just the status code, is what catches a
    `responses={404: {"description": ...}}` that documents no model at all.
    """
    schema = client.get("/openapi.json").json()
    error_ref = "#/components/schemas/ErrorResponse"

    def responses_for(path):
        return schema["paths"][path]["get"]["responses"]

    def model_ref(path, status):
        return responses_for(path)[status]["content"]["application/json"]["schema"]["$ref"]

    # The 400/503 pair comes from the app-wide handlers, so every path declares
    # it -- including /v1/export, which reaches it through its own 400 override.
    for path in schema["paths"]:
        assert model_ref(path, "400") == error_ref, path
        assert model_ref(path, "503") == error_ref, path

    # 404 only where a route can actually raise one.
    for path in (
        "/v1/documents",
        "/v1/documents/{document_id}",
        "/v1/documents/{document_id}/edges",
        "/v1/documents/{document_id}/validity",
    ):
        assert model_ref(path, "404") == error_ref, path

    # /v1/export addresses no single document and so must claim no 404.
    assert "404" not in responses_for("/v1/export")

    # The route-level override wins over the router-level 400 it merges with.
    assert "format" in responses_for("/v1/export")["400"]["description"]


def test_full_read_path_across_all_endpoints_for_a_realistic_graph(client, db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:capstone-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=standard.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    rights_repo = PostgresRightsRepository(db_session)
    for doc in (standard, legal_act):
        rights_repo.classify(
            document_id=doc.id, jurisdiction="EU", may_process=True,
            may_index_fulltext=False, may_cite_passages=False, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="test", delivery_id=delivery.id,
        )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=standard.id, to_document_id=legal_act.id,
        edge_type=EdgeType.BASED_ON_LAW, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    search = client.get(
        "/v1/documents",
        params={"issuer": "CEN", "designation": "EN ISO 12100:2010", "jurisdiction": "EU"},
    )
    assert search.status_code == 200
    document_id = search.json()["id"]
    assert search.json()["source"]["retrieval_path"] == (
        "https://single-market-economy.ec.europa.eu"
    )

    detail = client.get(f"/v1/documents/{document_id}", params={"jurisdiction": "EU"})
    assert detail.status_code == 200
    assert detail.json()["designations"][0]["designation"] == "EN ISO 12100:2010"

    edges = client.get(f"/v1/documents/{document_id}/edges", params={"jurisdiction": "EU"})
    assert edges.status_code == 200
    assert edges.json()[0]["edge_type"] == "based_on_law"

    validity = client.get(
        f"/v1/documents/{document_id}/validity", params={"jurisdiction": "EU"}
    )
    assert validity.status_code == 200
    assert validity.json()["status"] == "valid"

    export = client.get("/v1/export", params={"jurisdiction": "EU"})
    assert export.status_code == 200
    assert document_id in {d["id"] for d in export.json()["documents"]}

    forbidden = client.get(f"/v1/documents/{document_id}", params={"jurisdiction": "FR"})
    assert forbidden.status_code == 404
