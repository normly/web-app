# accounts/tests/test_account_export.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json
import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import (
    ChatAnswerType, ChatMessageRole, LegalBasisCategory, NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import DocumentORM
from normly_core.graph.postgres.repositories import (
    PostgresChatRepository, PostgresDeliveryRepository, PostgresDocumentRepository,
    PostgresNotificationRepository, PostgresSegmentRepository, PostgresSourceRepository,
    PostgresWatchlistRepository, PostgresWorkRepository,
)

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _register(client, email="export-target@example.de", password="correct horse"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


def _account_id(client, headers) -> uuid.UUID:
    return uuid.UUID(client.get("/v1/accounts/session", headers=headers).json()["account_id"])


def _delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=f"sha256:{uuid.uuid4()}", ingested_at=NOW,
    )


def _document(db_session, delivery, *, number="TST-1", edition="2026", part=None, work_id=None):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="TestIssuer", origin_number=number, edition=edition, part=part,
        delivery_id=delivery.id, work_id=work_id,
    )


def _chat_with_message(db_session, account_id, token="chat-secret-token-1"):
    chat = PostgresChatRepository(db_session)
    chat_session = chat.create_session(
        session_token=token, jurisdiction="DE", language="de", created_at=NOW,
        account_id=account_id,
    )
    message = chat.create_message(
        session_id=chat_session.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=NOW,
    )
    return chat_session, message


def _walk_keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _walk_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk_keys(inner)


def test_export_includes_account_fields(client):
    headers = _register(client, email="export@example.de")

    response = client.get("/v1/accounts/export", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "export@example.de"
    assert body["account"]["google_linked"] is False


def test_export_requires_authorization(client):
    assert client.get("/v1/accounts/export").status_code == 401


def test_export_chat_sessions_carry_the_id_and_never_the_token(client, db_session):
    headers = _register(client, email="chatexport@example.de")
    chat_session, _ = _chat_with_message(db_session, _account_id(client, headers))
    db_session.commit()

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["chat_sessions"]) == 1
    exported = body["chat_sessions"][0]
    assert exported["id"] == str(chat_session.id)
    assert "session_token" not in exported
    assert "chat-secret-token-1" not in json.dumps(body)
    assert exported["messages"][0]["content"] == "Antwort"
    assert exported["messages"][0]["answer_type"] == "synthesis"
    assert exported["messages"][0]["citations"] == []


def test_export_message_without_answer_type_is_null(client, db_session):
    headers = _register(client, email="nulltype@example.de")
    account_id = _account_id(client, headers)
    chat = PostgresChatRepository(db_session)
    chat_session = chat.create_session(
        session_token="t-null", jurisdiction="DE", language="de", created_at=NOW,
        account_id=account_id,
    )
    chat.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Frage",
        answer_type=None, created_at=NOW,
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert body["chat_sessions"][0]["messages"][0]["answer_type"] is None


def test_export_citations_name_the_document_readably(client, db_session):
    headers = _register(client, email="citeexport@example.de")
    chat_session, message = _chat_with_message(db_session, _account_id(client, headers))
    delivery = _delivery(db_session)
    document = _document(db_session, delivery, number="TST-7", edition="2024", part="2")
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading=None, text="Abschnitt", language="de",
    )
    PostgresChatRepository(db_session).add_citation(
        message_id=message.id, document_id=document.id, segment_id=segment.id,
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    citations = body["chat_sessions"][0]["messages"][0]["citations"]
    assert citations == [{
        "document": {
            "id": str(document.id), "origin_issuer": "TestIssuer",
            "origin_number": "TST-7", "edition": "2024", "part": "2",
        },
        "segment_id": str(segment.id),
    }]


def test_export_citation_of_a_tombstoned_document_stays_readable(client, db_session):
    headers = _register(client, email="tombexport@example.de")
    chat_session, message = _chat_with_message(db_session, _account_id(client, headers))
    document = _document(db_session, _delivery(db_session), number="TST-GONE")
    # After a takedown: the segment is gone (segment_id NULL), the document row
    # remains as a tombstone carrying only identifiers.
    PostgresChatRepository(db_session).add_citation(
        message_id=message.id, document_id=document.id, segment_id=None,
    )
    db_session.execute(
        sa.update(DocumentORM).where(DocumentORM.id == document.id).values(retired_at=NOW)
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    citation = body["chat_sessions"][0]["messages"][0]["citations"][0]
    assert citation["segment_id"] is None
    assert citation["document"]["origin_number"] == "TST-GONE"
    assert citation["document"]["origin_issuer"] == "TestIssuer"
    assert citation["document"]["id"] == str(document.id)


def test_export_watchlist_lists_all_documents_of_the_work_including_retired(client, db_session):
    headers = _register(client, email="watchlistexport@example.de")
    account_id = _account_id(client, headers)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    delivery = _delivery(db_session)
    old = _document(db_session, delivery, number="W-1", edition="2020", work_id=work.id)
    new = _document(db_session, delivery, number="W-1", edition="2025", work_id=work.id)
    db_session.execute(
        sa.update(DocumentORM).where(DocumentORM.id == old.id).values(retired_at=NOW)
    )
    PostgresWatchlistRepository(db_session).add_watch(account_id=account_id, work_id=work.id)
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert len(body["watchlist"]) == 1
    entry = body["watchlist"][0]
    assert entry["work_id"] == str(work.id)
    editions = {d["edition"] for d in entry["documents"]}
    assert editions == {"2020", "2025"}
    assert {d["id"] for d in entry["documents"]} == {str(old.id), str(new.id)}
    assert all(
        set(d) == {"id", "origin_issuer", "origin_number", "edition", "part"}
        for d in entry["documents"]
    )


def test_export_watchlist_entry_for_a_work_without_documents(client, db_session):
    headers = _register(client, email="emptywork@example.de")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=_account_id(client, headers), work_id=work.id
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert body["watchlist"][0]["documents"] == []


def _notification(db_session, account_id, work_id):
    PostgresNotificationRepository(db_session).create(
        account_id=account_id, work_id=work_id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=None,
        trigger_document_id=None, trigger_jurisdiction=None, may_process=None,
        may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )


def test_export_includes_notifications(client, db_session):
    headers = _register(client, email="notificationsexport@example.de")
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    _notification(db_session, _account_id(client, headers), work.id)
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["work_id"] == str(work.id)
    assert body["notifications"][0]["trigger_type"] == "new_edition"
    assert body["notifications"][0]["emailed_at"] is None


def test_export_includes_notifications_even_for_email_preference_accounts(client, db_session):
    # The in-app feed hides notifications for EMAIL-only accounts (display
    # concern); a personal-data export is not a display and must show all.
    headers = _register(client, email="emailprefexport@example.de")
    client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    _notification(db_session, _account_id(client, headers), work.id)
    db_session.commit()

    assert client.get("/v1/accounts/notifications", headers=headers).json() == []

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["work_id"] == str(work.id)


def test_export_has_no_password_or_token_fields(client, db_session):
    headers = _register(client, email="nosecrets@example.de")
    _chat_with_message(db_session, _account_id(client, headers), token="tok-nosecrets-9")
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    keys = {key.lower() for key in _walk_keys(body)}
    assert not [k for k in keys if "password" in k or "token" in k or "hash" in k]
    assert "tok-nosecrets-9" not in json.dumps(body)


def test_export_does_not_contain_the_deletion_warning(client, db_session):
    from normly_core.graph.postgres.orm import AccountORM

    headers = _register(client, email="warned@example.de")
    db_session.execute(
        sa.update(AccountORM)
        .where(AccountORM.id == _account_id(client, headers))
        .values(deletion_warned_at=NOW)
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=headers).json()

    assert not [k for k in _walk_keys(body) if "warn" in k.lower()]


def test_export_contains_nothing_of_another_account(client, db_session):
    mine = _register(client, email="mine@example.de")
    theirs = _register(client, email="theirs@example.de")
    other_session, other_message = _chat_with_message(
        db_session, _account_id(client, theirs), token="their-token"
    )
    delivery = _delivery(db_session)
    other_doc = _document(db_session, delivery, number="THEIRS-1")
    PostgresChatRepository(db_session).add_citation(
        message_id=other_message.id, document_id=other_doc.id, segment_id=None,
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=_account_id(client, theirs), work_id=work.id
    )
    db_session.commit()

    body = client.get("/v1/accounts/export", headers=mine).json()

    assert body["chat_sessions"] == []
    assert body["watchlist"] == []
    serialised = json.dumps(body)
    assert str(other_session.id) not in serialised
    assert "THEIRS-1" not in serialised
    assert "theirs@example.de" not in serialised
