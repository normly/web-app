# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_chat.accounts_client import ChatAccountIdentity
from normly_chat.llm_result import LlmResult


class _FakeAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, token):
        return self._identity


def test_missing_authorization_header_returns_401(client):
    response = client.get("/v1/chat/sessions")
    assert response.status_code == 401


def test_invalid_account_token_returns_401(client):
    from normly_chat.dependencies import get_accounts_client
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(None)
    from normly_chat.dependencies import get_session
    # Reuse the same db_session override the `client` fixture already set up.
    app.dependency_overrides[get_session] = client.app.dependency_overrides[get_session]

    from fastapi.testclient import TestClient
    with TestClient(app) as raising_client:
        response = raising_client.get(
            "/v1/chat/sessions", headers={"Authorization": "Bearer not-a-real-token"},
        )
    assert response.status_code == 401


def test_returns_only_the_authenticated_accounts_sessions(client, db_session):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )
    from datetime import datetime, timezone

    account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router@example.de", password_hash=None,
    )
    other_account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router-other@example.de", password_hash=None,
    )
    chat_repo = PostgresChatRepository(db_session)
    mine = chat_repo.create_session(
        session_token="mine-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    chat_repo.create_session(
        session_token="theirs-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=other_account.id,
    )

    from normly_chat.dependencies import get_accounts_client
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)

    response = client.get(
        "/v1/chat/sessions", headers={"Authorization": "Bearer whatever-the-fake-accepts"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_token"] == mine.session_token


def _seed(db_session, email, tokens):
    from datetime import datetime, timezone
    from normly_core.graph.domain import ChatMessageRole
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository, PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(
        email=email, password_hash=None,
    )
    repo = PostgresChatRepository(db_session)
    sessions = []
    for token in tokens:
        chat_session = repo.create_session(
            session_token=token, jurisdiction="DE", language="de",
            created_at=datetime.now(timezone.utc), account_id=account.id,
        )
        repo.create_message(
            session_id=chat_session.id, role=ChatMessageRole.USER, content="Frage",
            answer_type=None, created_at=datetime.now(timezone.utc),
        )
        sessions.append(chat_session)
    return account, sessions


def _act_as(client, account):
    from normly_chat.dependencies import get_accounts_client
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)


_AUTH = {"Authorization": "Bearer whatever-the-fake-accepts"}


def test_delete_own_session_returns_204_and_removes_it_with_a_log_entry(client, db_session):
    from sqlalchemy import text
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    account, (mine,) = _seed(db_session, "del-own@example.de", ["del-own-tok"])
    _act_as(client, account)

    response = client.delete(f"/v1/chat/sessions/{mine.id}", headers=_AUTH)

    assert response.status_code == 204
    repo = PostgresChatRepository(db_session)
    assert repo.get_session_by_token("del-own-tok") is None
    assert repo.list_messages_for_session(mine.id) == []
    logged = db_session.execute(
        text("select count(*) from deletion_log where kind = 'chat_session' and entity_id = :i"),
        {"i": mine.id},
    ).scalar_one()
    assert logged == 1


def test_delete_foreign_or_unknown_session_is_404_and_changes_nothing(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    me, _ = _seed(db_session, "del-me@example.de", ["del-me-tok"])
    _, (theirs,) = _seed(db_session, "del-them@example.de", ["del-them-tok"])
    _act_as(client, me)

    foreign = client.delete(f"/v1/chat/sessions/{theirs.id}", headers=_AUTH)
    unknown = client.delete(f"/v1/chat/sessions/{uuid.uuid4()}", headers=_AUTH)

    assert foreign.status_code == 404
    assert unknown.status_code == 404
    assert foreign.json() == unknown.json()
    assert PostgresChatRepository(db_session).get_session_by_token("del-them-tok") is not None


def test_delete_without_valid_account_is_401(client, db_session):
    from normly_chat.dependencies import get_accounts_client

    _, (target,) = _seed(db_session, "del-401@example.de", ["del-401-tok"])
    assert client.delete(f"/v1/chat/sessions/{target.id}").status_code == 401
    assert client.delete("/v1/chat/sessions").status_code == 401
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(None)
    assert client.delete(f"/v1/chat/sessions/{target.id}", headers=_AUTH).status_code == 401
    assert client.delete("/v1/chat/sessions", headers=_AUTH).status_code == 401


def test_delete_all_removes_only_own_sessions(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresChatRepository

    me, _ = _seed(db_session, "delall-me@example.de", ["delall-a", "delall-b"])
    _seed(db_session, "delall-them@example.de", ["delall-c"])
    _act_as(client, me)

    response = client.delete("/v1/chat/sessions", headers=_AUTH)

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    repo = PostgresChatRepository(db_session)
    assert repo.get_session_by_token("delall-a") is None
    assert repo.get_session_by_token("delall-c") is not None


from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from normly_core.graph.domain import ChatAnswerType, ChatMessageRole, LegalBasisCategory


def _app_for(client, identity, *, api_client=None, llm_client=None):
    from normly_chat.dependencies import (
        get_accounts_client, get_api_client, get_budget_guard, get_llm_client, get_session,
    )
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = client.app.dependency_overrides[get_session]
    # The client fixture's admitting guard, so no counter leaves the test transaction.
    app.dependency_overrides[get_budget_guard] = client.app.dependency_overrides[get_budget_guard]
    app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)
    if api_client is not None:
        app.dependency_overrides[get_api_client] = lambda: api_client
    if llm_client is not None:
        app.dependency_overrides[get_llm_client] = lambda: llm_client
    return app


def _owned_session(db_session, email, *, language="de"):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )

    account = PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)
    chat_repo = PostgresChatRepository(db_session)
    chat_session = chat_repo.create_session(
        session_token=f"tok-{email}", jurisdiction="DE", language=language,
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    identity = ChatAccountIdentity(account_id=account.id, email=email)
    return chat_repo, chat_session, identity


def _exchange(chat_repo, chat_session, question, answer_type):
    now = datetime.now(timezone.utc)
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content=question,
        answer_type=None, created_at=now,
    )
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content="Antwort.",
        answer_type=answer_type, created_at=now,
    )


def _document(db_session, number):
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/sessions",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=f"sha256:sessions-{number}",
        ingested_at=datetime.now(timezone.utc),
    )
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=number, edition="2020", part=None,
        delivery_id=delivery.id,
    )


class _LabelApiClient:
    def __init__(self, known_ids):
        self._known = set(known_ids)

    def get_document(self, document_id, jurisdiction):
        if document_id not in self._known:
            return None
        return {
            "origin_issuer": "DGUV", "origin_number": "1",
            "designations": [{"designation": "DGUV Vorschrift 1", "is_primary": True}],
        }


class _ExhaustedGuard:
    def pool_available(self, pool):
        return False


class _TitleLlm:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self._error:
            raise self._error
        return LlmResult(text=self._response, input_tokens=5, output_tokens=3, truncated=False)


def test_messages_endpoint_returns_paragraphs_and_resolved_citations(client, db_session):
    chat_repo, chat_session, identity = _owned_session(db_session, "messages@example.de")
    known = _document(db_session, "known")
    gone = _document(db_session, "gone")
    now = datetime.now(timezone.utc)
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Was gilt?",
        answer_type=None, created_at=now,
    )
    answer = chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content="Eins.\n\nZwei.",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=now,
    )
    chat_repo.add_citation(
        message_id=answer.id, document_id=known.id, segment_id=None, paragraph_index=1,
    )
    chat_repo.add_citation(
        message_id=answer.id, document_id=gone.id, segment_id=None, paragraph_index=0,
    )
    app = _app_for(client, identity, api_client=_LabelApiClient({known.id}))

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/v1/chat/sessions/{chat_session.id}/messages",
            headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(chat_session.id)
    assert body["session_token"] == chat_session.session_token
    assert body["title"] == "Was gilt?"
    question, reply = body["messages"]
    assert question["role"] == "user"
    assert question["paragraphs"] == ["Was gilt?"]
    assert reply["paragraphs"] == ["Eins.", "Zwei."]
    assert reply["answer_type"] == "synthesis"
    assert reply["citations"] == [{
        "document_id": str(known.id), "segment_id": None,
        "designation": "DGUV Vorschrift 1", "section": None, "paragraph_index": 1,
    }]


def test_messages_endpoint_hides_foreign_sessions(client, db_session):
    _, chat_session, _ = _owned_session(db_session, "owner-msg@example.de")
    _, _, stranger = _owned_session(db_session, "stranger-msg@example.de")
    app = _app_for(client, stranger, api_client=_LabelApiClient(set()))

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/v1/chat/sessions/{chat_session.id}/messages",
            headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 404


def test_messages_endpoint_requires_an_account(client):
    response = client.get(f"/v1/chat/sessions/{uuid.uuid4()}/messages")
    assert response.status_code == 401


def test_session_list_shows_the_stored_or_fallback_title(client, db_session):
    chat_repo, titled, identity = _owned_session(db_session, "titles-list@example.de")
    untitled = chat_repo.create_session(
        session_token="tok-untitled", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=identity.account_id,
    )
    empty = chat_repo.create_session(
        session_token="tok-empty", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=identity.account_id,
    )
    chat_repo.set_session_title(titled.id, "Gespeicherter Titel")
    chat_repo.create_message(
        session_id=untitled.id, role=ChatMessageRole.USER, content="Erste Frage hier",
        answer_type=None, created_at=datetime.now(timezone.utc),
    )
    app = _app_for(client, identity)

    with TestClient(app) as test_client:
        body = test_client.get("/v1/chat/sessions", headers={"Authorization": "Bearer t"}).json()

    titles = {item["id"]: item["title"] for item in body}
    assert titles == {
        str(titled.id): "Gespeicherter Titel",
        str(untitled.id): "Erste Frage hier",
        str(empty.id): None,
    }


def test_title_endpoint_generates_stores_and_then_reuses_the_title(client, db_session):
    chat_repo, chat_session, identity = _owned_session(db_session, "title-gen@example.de")
    _exchange(chat_repo, chat_session, "Brauche ich eine Schutzbrille?", ChatAnswerType.SYNTHESIS)
    llm = _TitleLlm("Schutzbrille beim Schweißen")
    app = _app_for(client, identity, llm_client=llm)

    with TestClient(app) as test_client:
        first = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )
        second = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert first.json() == {"title": "Schutzbrille beim Schweißen"}
    assert second.json() == {"title": "Schutzbrille beim Schweißen"}
    assert llm.calls == 1
    assert chat_repo.get_session_by_token(chat_session.session_token).title == (
        "Schutzbrille beim Schweißen"
    )


def test_title_endpoint_falls_back_without_storing_when_the_model_fails(client, db_session):
    import httpx

    chat_repo, chat_session, identity = _owned_session(db_session, "title-fail@example.de")
    _exchange(chat_repo, chat_session, "Kurze Frage", ChatAnswerType.SYNTHESIS)
    app = _app_for(client, identity, llm_client=_TitleLlm(error=httpx.ConnectError("down")))

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    assert response.json() == {"title": "Kurze Frage"}
    assert chat_repo.get_session_by_token(chat_session.session_token).title is None


def test_title_endpoint_skips_the_model_when_the_registered_pool_is_spent(client, db_session):
    from normly_chat.dependencies import get_budget_guard

    chat_repo, chat_session, identity = _owned_session(db_session, "title-pool@example.de")
    _exchange(chat_repo, chat_session, "Kurze Frage", ChatAnswerType.SYNTHESIS)
    llm = _TitleLlm("Nie benutzt")
    app = _app_for(client, identity, llm_client=llm)
    app.dependency_overrides[get_budget_guard] = lambda: _ExhaustedGuard()

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    assert response.json() == {"title": "Kurze Frage"}
    assert llm.calls == 0


@pytest.mark.parametrize("answer_type", [ChatAnswerType.STRUCTURAL, ChatAnswerType.FALLBACK])
def test_title_endpoint_skips_the_model_for_a_chat_without_an_ai_answer(
    client, db_session, answer_type,
):
    chat_repo, chat_session, identity = _owned_session(
        db_session, f"title-no-ai-{answer_type.value}@example.de",
    )
    _exchange(chat_repo, chat_session, "Ist DIN EN ISO 9001 noch gültig?", answer_type)
    llm = _TitleLlm("Nie benutzt")
    app = _app_for(client, identity, llm_client=llm)

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert response.status_code == 200
    assert response.json() == {"title": "Ist DIN EN ISO 9001 noch gültig?"}
    assert llm.calls == 0
    assert chat_repo.get_session_by_token(chat_session.session_token).title is None


def test_title_endpoint_is_404_for_foreign_or_empty_sessions(client, db_session):
    _, chat_session, owner = _owned_session(db_session, "title-owner@example.de")
    _, _, stranger = _owned_session(db_session, "title-stranger@example.de")

    with TestClient(_app_for(client, stranger, llm_client=_TitleLlm("x"))) as test_client:
        foreign = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )
    with TestClient(_app_for(client, owner, llm_client=_TitleLlm("x"))) as test_client:
        empty = test_client.post(
            f"/v1/chat/sessions/{chat_session.id}/title", headers={"Authorization": "Bearer t"},
        )

    assert foreign.status_code == 404
    assert empty.status_code == 404
