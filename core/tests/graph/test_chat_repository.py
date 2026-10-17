# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.domain import ChatAnswerType, ChatMessageRole
from normly_core.graph.postgres.repositories import PostgresChatRepository


def _now():
    return datetime.now(timezone.utc)


def test_create_session_defaults_to_anonymous(db_session):
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-1", jurisdiction="DE", language="de", created_at=_now(),
    )
    assert session.account_id is None
    assert session.jurisdiction == "DE"
    assert session.language == "de"


def test_get_session_by_token_round_trips(db_session):
    repo = PostgresChatRepository(db_session)
    created = repo.create_session(
        session_token="tok-2", jurisdiction="DE", language="en", created_at=_now(),
    )
    found = repo.get_session_by_token("tok-2")
    assert found is not None
    assert found.id == created.id


def test_get_session_by_token_returns_none_for_unknown_token(db_session):
    repo = PostgresChatRepository(db_session)
    assert repo.get_session_by_token("does-not-exist") is None


def test_create_message_and_list_messages_for_session_preserves_order(db_session):
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-4", jurisdiction="DE", language="de", created_at=_now(),
    )
    first = repo.create_message(
        session_id=session.id, role=ChatMessageRole.USER, content="Frage",
        answer_type=None, created_at=_now(),
    )
    second = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=_now(),
    )

    messages = repo.list_messages_for_session(session.id)
    assert [m.id for m in messages] == [first.id, second.id]
    assert messages[1].answer_type == ChatAnswerType.SYNTHESIS


def test_add_citation_links_message_to_document(db_session):
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )
    from normly_core.graph.domain import LegalBasisCategory
    from datetime import date

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/x",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:chat-citation", ingested_at=_now(),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )

    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-5", jurisdiction="DE", language="de", created_at=_now(),
    )
    message = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.STRUCTURAL, created_at=_now(),
    )
    citation = repo.add_citation(
        message_id=message.id, document_id=document.id, segment_id=None,
    )
    assert citation.document_id == document.id
    assert citation.segment_id is None


def test_list_sessions_for_account_returns_only_that_accounts_sessions_newest_first(db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    account_a = PostgresAccountRepository(db_session).create_account(
        email="sessions-a@example.de", password_hash=None,
    )
    account_b = PostgresAccountRepository(db_session).create_account(
        email="sessions-b@example.de", password_hash=None,
    )
    repo = PostgresChatRepository(db_session)
    older = repo.create_session(
        session_token="tok-a-older", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), account_id=account_a.id,
    )
    newer = repo.create_session(
        session_token="tok-a-newer", jurisdiction="DE", language="en",
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc), account_id=account_a.id,
    )
    repo.create_session(
        session_token="tok-b", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 15, tzinfo=timezone.utc), account_id=account_b.id,
    )
    repo.create_session(
        session_token="tok-anon", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )

    sessions = repo.list_sessions_for_account(account_a.id)

    assert [s.id for s in sessions] == [newer.id, older.id]


def _account(db_session, email):
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def test_a_new_session_has_no_title_and_set_session_title_stores_one(db_session):
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-title", jurisdiction="DE", language="de", created_at=_now(),
    )
    assert session.title is None

    repo.set_session_title(session.id, "Schutzbrillen beim Schweißen")

    assert repo.get_session_by_token("tok-title").title == "Schutzbrillen beim Schweißen"


def test_get_session_for_account_returns_only_the_owners_session(db_session):
    owner = _account(db_session, "owner-lookup@example.de")
    other = _account(db_session, "other-lookup@example.de")
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-owned", jurisdiction="DE", language="de", created_at=_now(),
        account_id=owner.id,
    )

    assert repo.get_session_for_account(session.id, owner.id).id == session.id
    assert repo.get_session_for_account(session.id, other.id) is None


def test_first_user_messages_for_sessions_returns_the_earliest_question_per_session(db_session):
    repo = PostgresChatRepository(db_session)
    first = repo.create_session(
        session_token="tok-first-a", jurisdiction="DE", language="de", created_at=_now(),
    )
    second = repo.create_session(
        session_token="tok-first-b", jurisdiction="DE", language="de", created_at=_now(),
    )
    empty = repo.create_session(
        session_token="tok-first-c", jurisdiction="DE", language="de", created_at=_now(),
    )
    t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc)
    repo.create_message(
        session_id=first.id, role=ChatMessageRole.USER, content="Spätere Frage",
        answer_type=None, created_at=t1,
    )
    repo.create_message(
        session_id=first.id, role=ChatMessageRole.USER, content="Erste Frage",
        answer_type=None, created_at=t0,
    )
    repo.create_message(
        session_id=second.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.FALLBACK, created_at=t0,
    )
    repo.create_message(
        session_id=second.id, role=ChatMessageRole.USER, content="Frage B",
        answer_type=None, created_at=t1,
    )

    result = repo.first_user_messages_for_sessions([first.id, second.id, empty.id])

    assert result == {first.id: "Erste Frage", second.id: "Frage B"}
    assert repo.first_user_messages_for_sessions([]) == {}


def test_a_user_message_sorts_before_its_answer_when_both_share_a_timestamp(db_session):
    # routers/chat.py stores question and answer with the same `now`.
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-tie", jurisdiction="DE", language="de", created_at=_now(),
    )
    same = _now()
    answer = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="Antwort",
        answer_type=ChatAnswerType.FALLBACK, created_at=same,
    )
    question = repo.create_message(
        session_id=session.id, role=ChatMessageRole.USER, content="Frage",
        answer_type=None, created_at=same,
    )

    assert [m.id for m in repo.list_messages_for_session(session.id)] == [question.id, answer.id]


def test_add_citation_stores_the_paragraph_index(db_session):
    from datetime import date

    from normly_core.graph.domain import LegalBasisCategory
    from normly_core.graph.postgres.repositories import (
        PostgresDeliveryRepository,
        PostgresDocumentRepository,
        PostgresSourceRepository,
    )

    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de/p",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:paragraph-index", ingested_at=_now(),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number="2", edition="2021", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresChatRepository(db_session)
    session = repo.create_session(
        session_token="tok-pi", jurisdiction="DE", language="de", created_at=_now(),
    )
    message = repo.create_message(
        session_id=session.id, role=ChatMessageRole.ASSISTANT, content="A\n\nB",
        answer_type=ChatAnswerType.SYNTHESIS, created_at=_now(),
    )

    with_index = repo.add_citation(
        message_id=message.id, document_id=document.id, segment_id=None, paragraph_index=1,
    )
    without_index = repo.add_citation(
        message_id=message.id, document_id=document.id, segment_id=None,
    )

    assert with_index.paragraph_index == 1
    assert without_index.paragraph_index is None
    stored = repo.citations_for_messages([message.id])[message.id]
    assert sorted(c.paragraph_index is None for c in stored) == [False, True]
