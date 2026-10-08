# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import httpx
import pytest
from fastapi.testclient import TestClient

from normly_chat.dependencies import get_accounts_client, get_api_client, get_session
from normly_chat.main import create_app


def test_missing_message_returns_400(client):
    response = client.post(
        "/v1/chat", json={"jurisdiction": "DE", "language": "de", "message": ""},
    )
    assert response.status_code == 400


def test_missing_jurisdiction_returns_400(client):
    response = client.post(
        "/v1/chat", json={"jurisdiction": "", "language": "de", "message": "Frage"},
    )
    assert response.status_code == 400


def test_a_downstream_outage_is_503_not_500(monkeypatch, db_url, db_session):
    """
    api/ being unreachable during a structural lookup must not surface as an
    unhandled 500: it's the same class of failure as the database going away
    (see chat/'s errors.py, which folds httpx.HTTPError into the same
    infrastructure-error -> 503 handling as SQLAlchemyError/OSError), and
    callers need the same "retry me" signal. Mirrors
    accounts/tests/test_error_handling.py's technique of overriding a
    dependency with one that raises, then asserting on the resulting status
    code and ErrorResponse-shaped body.
    """
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    monkeypatch.setenv("NORMLY_API_BASE_URL", "http://localhost:8001")
    monkeypatch.setenv("NORMLY_ACCOUNTS_BASE_URL", "http://localhost:8002")
    monkeypatch.setenv("NORMLY_LLM_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("NORMLY_LLM_MODEL", "test-model")
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    class _BrokenApiClient:
        def search_document(self, issuer, designation, jurisdiction):
            raise httpx.ConnectError("simulated outage")

    app.dependency_overrides[get_api_client] = lambda: _BrokenApiClient()

    # A validity question ("gültig") routes to the structural path, which is
    # the only one that reaches api_client.search_document.
    with TestClient(app, raise_server_exceptions=False) as broken_client:
        response = broken_client.post(
            "/v1/chat",
            json={
                "jurisdiction": "DE", "language": "de",
                "message": "Ist DIN EN ISO 9001 gültig?",
            },
        )

    assert response.status_code == 503
    body = response.json()
    # ErrorResponse-shaped: a single `detail` string, and nothing about the
    # underlying failure leaked into it.
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str)
    assert "outage" not in body["detail"]


class _NoDocumentApiClient:
    """A structural lookup that finds nothing -- the request still completes."""

    def search_document(self, issuer, designation, jurisdiction):
        return None


class _RecordingAccountsClient:
    """
    An accounts service that recognizes no token at all. That is enough to
    prove the router PARSED the Authorization header: it records exactly what
    it was handed, and returning None means the request proceeds anonymously
    (the normal case for an invalid or expired token).
    """

    def __init__(self):
        self.validated = []

    def validate_session(self, session_token):
        self.validated.append(session_token)
        return None


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_an_authorization_header_is_parsed_and_the_request_still_completes(
    client, scheme,
):
    """
    The Authorization header parsing at the top of chat() had no test at all.
    RFC 7235 makes the auth scheme case-insensitive, so a lowercase "bearer"
    must yield the same token rather than silently degrading to anonymous.
    """
    accounts_client = _RecordingAccountsClient()
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: accounts_client

    response = client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "de",
            "message": "Ist DIN EN ISO 9001 noch gültig?",
        },
        headers={"Authorization": f"{scheme} an-unrecognized-token"},
    )

    assert response.status_code == 200
    # The token reached the accounts client verbatim, with the scheme stripped.
    assert accounts_client.validated == ["an-unrecognized-token"]
    # Unrecognized token -> anonymous session, and the answer is still served.
    assert response.json()["session_token"]


def test_a_non_bearer_authorization_header_is_ignored(client):
    accounts_client = _RecordingAccountsClient()
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: accounts_client

    response = client.post(
        "/v1/chat",
        json={
            "jurisdiction": "DE", "language": "de",
            "message": "Ist DIN EN ISO 9001 noch gültig?",
        },
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )

    assert response.status_code == 200
    assert accounts_client.validated == []
