# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import NotificationPreference, NotificationTriggerType
from normly_core.graph.postgres.orm import DocumentORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDocumentRepository,
    PostgresNotificationRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresWatchlistRepository,
)
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import RecordingEmailSender

from .test_detection import (
    _classify,
    _make_delivery,
    _make_source,
    _set_created_at,
)

_LONG_AGO = datetime(2020, 1, 1, tzinfo=timezone.utc)
_WATCHED_AT = datetime(2026, 3, 1, tzinfo=timezone.utc)
_RETIRED_1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
_RETIRED_2 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _setup(db_session, tag, *, preference=NotificationPreference.IN_APP, documents=1):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, tag)
    doc_repo = PostgresDocumentRepository(db_session)
    docs = []
    for index in range(documents):
        docs.append(
            doc_repo.create_document(
                origin_issuer="DGUV", origin_number=f"{tag}-{index}", edition="2026",
                part=None, delivery_id=delivery.id,
                work_id=docs[0].work_id if docs else None,
            )
        )
    account = PostgresAccountRepository(db_session).create_account(
        email=f"{tag}@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=preference
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=docs[0].work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _WATCHED_AT)
    return account, docs, delivery


def _retire(db_session, document_id, when):
    db_session.execute(
        sa.update(DocumentORM).where(DocumentORM.id == document_id).values(retired_at=when)
    )
    db_session.flush()


def _notifications(db_session, account):
    return PostgresNotificationRepository(db_session).list_for_account(account.id)


def test_retired_document_notifies_once(db_session):
    account, (doc,), _ = _setup(db_session, "nla-once")
    _retire(db_session, doc.id, _RETIRED_1)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 1
    (notification,) = _notifications(db_session, account)
    assert notification.trigger_type == NotificationTriggerType.NO_LONGER_AVAILABLE
    assert notification.trigger_document_id == doc.id
    assert notification.work_id == doc.work_id
    assert notification.trigger_edge_id is None
    assert notification.trigger_jurisdiction is None
    assert notification.may_process is None


def test_retirement_before_watching_is_history(db_session):
    account, (doc,), _ = _setup(db_session, "nla-history")
    _retire(db_session, doc.id, _LONG_AGO)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 0
    assert _notifications(db_session, account) == []


def test_second_run_does_not_notify_again(db_session):
    account, (doc,), _ = _setup(db_session, "nla-idem")
    _retire(db_session, doc.id, _RETIRED_1)

    run_notify_watchers(db_session, RecordingEmailSender())
    second = run_notify_watchers(db_session, RecordingEmailSender())

    assert second.notifications_created == 0
    assert len(_notifications(db_session, account)) == 1


def test_cleanup_of_a_read_notification_does_not_renotify(db_session):
    account, (doc,), _ = _setup(db_session, "nla-cleanup")
    _retire(db_session, doc.id, _RETIRED_1)
    run_notify_watchers(db_session, RecordingEmailSender())
    repo = PostgresNotificationRepository(db_session)
    (created,) = repo.list_for_account(account.id)
    repo.mark_read(created.id, account_id=account.id, read_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
    _set_created_at(db_session, NotificationORM, created.id, _LONG_AGO)
    assert repo.delete_read_before(datetime(2026, 7, 2, tzinfo=timezone.utc)) == 1

    again = run_notify_watchers(db_session, RecordingEmailSender())

    assert again.notifications_created == 0
    assert _notifications(db_session, account) == []


def test_retirement_after_a_return_is_a_new_notification(db_session):
    account, (doc,), _ = _setup(db_session, "nla-return")
    _retire(db_session, doc.id, _RETIRED_1)
    run_notify_watchers(db_session, RecordingEmailSender())
    _retire(db_session, doc.id, None)
    assert run_notify_watchers(db_session, RecordingEmailSender()).notifications_created == 0
    _retire(db_session, doc.id, _RETIRED_2)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 1
    assert len(_notifications(db_session, account)) == 2


def test_two_retired_documents_of_one_work_notify_twice(db_session):
    account, docs, _ = _setup(db_session, "nla-two", documents=2)
    for doc in docs:
        _retire(db_session, doc.id, _RETIRED_1)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 2
    notified = {n.trigger_document_id for n in _notifications(db_session, account)}
    assert notified == {doc.id for doc in docs}


def test_preference_none_gets_no_notification(db_session):
    account, (doc,), _ = _setup(db_session, "nla-none", preference=NotificationPreference.NONE)
    _retire(db_session, doc.id, _RETIRED_1)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 0
    assert _notifications(db_session, account) == []


def test_email_preference_sends_mail_with_the_new_subject(db_session):
    account, (doc,), _ = _setup(
        db_session, "nla-mail", preference=NotificationPreference.EMAIL
    )
    _retire(db_session, doc.id, _RETIRED_1)
    sender = RecordingEmailSender()

    summary = run_notify_watchers(db_session, sender)

    assert summary.notifications_created == 1
    assert summary.emails_sent == 1
    assert len(sender.sent) == 1
    assert sender.sent[0]["subject"] == "Ein beobachtetes Regelwerk ist nicht mehr verfügbar"
    assert sender.sent[0]["to"] == account.email
    (notification,) = _notifications(db_session, account)
    assert notification.emailed_at is not None


def test_retired_document_does_not_disturb_the_rights_change_path(db_session):
    account, (doc,), delivery = _setup(db_session, "nla-rights")
    _classify(db_session, doc.id, delivery.id)
    # First run establishes the rights baseline.
    run_notify_watchers(db_session, RecordingEmailSender())
    # The import purges the classification of a retired document.
    db_session.execute(sa.text("DELETE FROM rights_classification"))
    _retire(db_session, doc.id, _RETIRED_1)

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 1
    (notification,) = _notifications(db_session, account)
    assert notification.trigger_type == NotificationTriggerType.NO_LONGER_AVAILABLE


# --- end to end through the real importer -----------------------------------

from datetime import timedelta  # noqa: E402

from normly_core.graph.domain import ImportRecord  # noqa: E402

from exchange.test_takedown import _frozen, _scenario  # noqa: E402


def _import(scenario, dump, imported_at):
    scenario.repository.replace_knowledge_base(
        _frozen(dump), record=ImportRecord("2026.10.2", 1, "rev", imported_at)
    )


def _retirement_notifications(db_session, scenario):
    return [
        n for n in _notifications(db_session, scenario.account)
        if n.trigger_type == NotificationTriggerType.NO_LONGER_AVAILABLE
    ]


def _scan(db_session):
    return run_notify_watchers(db_session, RecordingEmailSender())


def _watch_created_at(db_session, scenario):
    return db_session.execute(
        sa.select(WatchlistORM.created_at).where(WatchlistORM.id == scenario.watch.id)
    ).scalar_one()


def test_importer_takedown_notifies_watchers_once_and_again_after_return(db_session):
    s = _scenario(db_session)
    PostgresAccountRepository(db_session).update_notification_preference(
        s.account.id, preference=NotificationPreference.IN_APP
    )
    watched = _watch_created_at(db_session, s)
    first, second, third = (watched + timedelta(days=d) for d in (1, 2, 3))

    _import(s, s.full, first)
    _scan(db_session)
    assert _retirement_notifications(db_session, s) == []

    _import(s, s.without, first)
    _scan(db_session)
    (notification,) = _retirement_notifications(db_session, s)
    assert notification.trigger_document_id == s.drop.id
    assert notification.work_id == s.drop.work_id

    _import(s, s.without, second)
    _scan(db_session)
    assert len(_retirement_notifications(db_session, s)) == 1

    _import(s, s.full, second)
    _scan(db_session)
    _import(s, s.without, third)
    _scan(db_session)
    assert len(_retirement_notifications(db_session, s)) == 2


def test_importer_takedown_before_the_watch_does_not_notify(db_session):
    s = _scenario(db_session)
    PostgresAccountRepository(db_session).update_notification_preference(
        s.account.id, preference=NotificationPreference.IN_APP
    )
    before_watch = _watch_created_at(db_session, s) - timedelta(days=1)

    _import(s, s.full, before_watch)
    _import(s, s.without, before_watch)
    _scan(db_session)

    assert _retirement_notifications(db_session, s) == []
