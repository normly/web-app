# api/tests/test_error_handling.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from fastapi.testclient import TestClient

from normly_api.dependencies import get_session
from normly_api.main import create_app


def test_missing_required_query_parameter_is_400_not_422(client):
    response = client.get("/v1/documents")

    assert response.status_code == 400
    assert "detail" in response.json()


def test_a_broken_database_dependency_is_503(monkeypatch, db_url):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    app = create_app()

    def _broken_session():
        raise ConnectionError("simulated database outage")
        yield  # pragma: no cover -- unreachable, keeps this a generator

    app.dependency_overrides[get_session] = _broken_session

    with TestClient(app, raise_server_exceptions=False) as broken_client:
        response = broken_client.get(
            "/v1/documents", params={"issuer": "x", "designation": "y", "jurisdiction": "DE"}
        )

    assert response.status_code == 503
    assert "detail" in response.json()
    assert "outage" not in response.json()["detail"]
