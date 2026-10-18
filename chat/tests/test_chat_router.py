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
    # Unrecognized token -> anonymous request: answered, but nothing stored.
    assert response.json()["session_token"] is None


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


class _FixedAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, session_token):
        return self._identity


def _count_chat_rows(db_session):
    from sqlalchemy import func, select
    from normly_core.graph.postgres.orm import (
        ChatMessageCitationORM, ChatMessageORM, ChatSessionORM,
    )

    return tuple(
        db_session.execute(select(func.count()).select_from(orm)).scalar_one()
        for orm in (ChatSessionORM, ChatMessageORM, ChatMessageCitationORM)
    )


_BODY = {"jurisdiction": "DE", "language": "de", "message": "Ist DIN EN ISO 9001 noch gültig?"}


def test_anonymous_request_is_answered_and_stores_nothing(client, db_session):
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)
    before = _count_chat_rows(db_session)

    response = client.post("/v1/chat", json=_BODY)

    assert response.status_code == 200
    assert response.json()["answer"]
    assert response.json()["session_token"] is None
    assert _count_chat_rows(db_session) == before


def test_anonymous_request_with_an_account_session_token_does_not_attach(client, db_session):
    from datetime import datetime, timezone
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository, PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(
        email="chat-anon-token@example.de", password_hash=None,
    )
    PostgresChatRepository(db_session).create_session(
        session_token="acct-session-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)
    before = _count_chat_rows(db_session)

    response = client.post("/v1/chat", json={**_BODY, "session_token": "acct-session-tok"})

    assert response.status_code == 200
    assert response.json()["session_token"] is None
    assert _count_chat_rows(db_session) == before


def test_request_with_a_valid_account_stores_session_messages_and_returns_a_token(
    client, db_session,
):
    from normly_chat.accounts_client import ChatAccountIdentity
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    account = PostgresAccountRepository(db_session).create_account(
        email="chat-valid-acct@example.de", password_hash=None,
    )
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(identity)
    before = _count_chat_rows(db_session)

    response = client.post(
        "/v1/chat", json=_BODY, headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 200
    assert response.json()["session_token"]
    after = _count_chat_rows(db_session)
    assert after[0] == before[0] + 1
    assert after[1] == before[1] + 2


class _OneDocumentApiClient:
    """A validity question about one known, valid document."""

    DOCUMENT_ID = "66666666-6666-6666-6666-666666666666"

    def search_document(self, issuer, designation, jurisdiction):
        return {"id": self.DOCUMENT_ID}

    def get_validity(self, document_id, jurisdiction):
        return {"status": "valid", "replaced_by": [], "withdrawn_reference": None}

    def get_edges(self, document_id, jurisdiction):
        return []

    def get_document(self, document_id, jurisdiction):
        return {
            "origin_issuer": "ISO", "origin_number": "9001",
            "designations": [{"designation": "DIN EN ISO 9001", "is_primary": True}],
        }


def test_the_answer_carries_paragraphs_and_labelled_citations(client):
    client.app.dependency_overrides[get_api_client] = lambda: _OneDocumentApiClient()

    response = client.post("/v1/chat", json=_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] is None
    assert body["answer"] == "DIN EN ISO 9001 ist noch gültig."
    assert body["paragraphs"] == ["DIN EN ISO 9001 ist noch gültig."]
    assert body["citations"] == [{
        "document_id": _OneDocumentApiClient.DOCUMENT_ID, "segment_id": None,
        "designation": "DIN EN ISO 9001", "section": None, "paragraph_index": 0,
    }]


class _FailingDocumentApiClient(_OneDocumentApiClient):
    def get_document(self, document_id, jurisdiction):
        raise httpx.ConnectError("api/ is down")


def test_a_failing_document_lookup_drops_the_chip_but_keeps_the_answer(client):
    client.app.dependency_overrides[get_api_client] = lambda: _FailingDocumentApiClient()

    response = client.post("/v1/chat", json=_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["citations"] == []


def test_a_stored_answer_keeps_its_paragraph_index_and_returns_the_session_id(client, db_session):
    from normly_chat.accounts_client import ChatAccountIdentity
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(
        email="chat-paragraph@example.de", password_hash=None,
    )
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(identity)
    # The document must exist for the citation's foreign key.
    from datetime import date, datetime, timezone

    from normly_core.graph.domain import LegalBasisCategory
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DIN", retrieval_path="https://example.de/router",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:router-paragraph",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    class _KnownDocumentApiClient(_OneDocumentApiClient):
        DOCUMENT_ID = str(document.id)

    client.app.dependency_overrides[get_api_client] = lambda: _KnownDocumentApiClient()

    response = client.post("/v1/chat", json=_BODY, headers={"Authorization": "Bearer valid"})

    body = response.json()
    session_id = body["session_id"]
    assert session_id is not None
    chat_repo = PostgresChatRepository(db_session)
    chat_session = chat_repo.get_session_by_token(body["session_token"])
    assert str(chat_session.id) == session_id
    answer = chat_repo.list_messages_for_session(chat_session.id)[1]
    [citation] = chat_repo.citations_for_messages([answer.id])[answer.id]
    assert citation.paragraph_index == 0
