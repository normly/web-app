# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import sqlalchemy as sa

from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationPreference,
    NotificationTriggerType,
    TdmOptOutResult,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import EdgeORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import RecordingEmailSender


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=datetime(2026, 1, 1).date(), responsible_person="Test Reviewer",
    )


def _make_delivery(db_session, source_id, tag):
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source_id, content_hash=f"sha256:{tag}", ingested_at=datetime.now(timezone.utc),
    )


def _classify(db_session, document_id, delivery_id, *, jurisdiction="DE", may_process=True):
    return PostgresRightsRepository(db_session).classify(
        document_id=document_id, jurisdiction=jurisdiction, may_process=may_process,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        legal_basis_reference="§5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="pipeline", delivery_id=delivery_id,
    )


def _set_created_at(db_session, orm_class, row_id, when):
    """
    Force a row's created_at to an explicit, unambiguous value.

    Both WatchlistORM.created_at and EdgeORM.created_at are
    server_default=sa.func.now(), and Postgres's now() is transaction-scoped:
    it returns the SAME value for every statement inside one transaction. The
    db_session fixture runs a whole test in one transaction, so a watch and an
    edge created "one after the other" here come back byte-identical, and a
    time.sleep() between them would change nothing. Only an explicit UPDATE
    establishes a real ordering. Production is unaffected -- notify-watchers
    runs in its own process and transaction, separated from any HTTP request
    that added a watch by real wall-clock time.
    """
    db_session.execute(
        sa.update(orm_class).where(orm_class.id == row_id).values(created_at=when)
    )
    db_session.flush()


_BEFORE = datetime(2020, 1, 1, tzinfo=timezone.utc)
_AFTER = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_new_edition_edge_produces_one_notification_and_no_duplicate_on_a_second_run(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "new-edition")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    # Only edges newer than the watch notify, and this test's edge was
    # created earlier in the same transaction -- whose now() is a single
    # frozen value. Backdate the watch so the edge is unambiguously newer.
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1
    assert first_run.emails_sent == 0  # preference is IN_APP, not EMAIL/BOTH
    assert sender.sent == []

    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert len(notifications) == 1
    assert notifications[0].trigger_type == NotificationTriggerType.NEW_EDITION

    second_run = run_notify_watchers(db_session, sender)
    assert second_run.notifications_created == 0
    assert len(PostgresNotificationRepository(db_session).list_for_account(account.id)) == 1


def test_national_adoption_edge_produces_one_notification_and_no_duplicate_on_a_second_run(
    db_session,
):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "national-adoption")
    doc_repo = PostgresDocumentRepository(db_session)
    original = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    adoption = doc_repo.create_document(
        origin_issuer="BS", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id, work_id=original.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=adoption.id, to_document_id=original.id,
        edge_type=EdgeType.ADOPTED_FROM, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="adoption-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=original.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1

    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert notifications[0].trigger_type == NotificationTriggerType.NATIONAL_ADOPTION

    second_run = run_notify_watchers(db_session, sender)
    assert second_run.notifications_created == 0


def test_email_preference_sends_mail_and_sets_emailed_at(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "email-pref")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="email-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.BOTH
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    run_notify_watchers(db_session, sender)

    assert len(sender.sent) == 1
    assert sender.sent[0]["to"] == "email-watcher@example.de"
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert notifications[0].emailed_at is not None


def test_notification_preference_none_creates_no_notification(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "pref-none")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="3", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="3", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="pref-none@example.de", password_hash=None
    )
    # Default preference is NONE -- no update_notification_preference call.
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    # Backdated so this stays a test of the NONE preference: without it the
    # edge would be filtered out as history and the assertion would hold for
    # the wrong reason.
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    run_notify_watchers(db_session, RecordingEmailSender())
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []


def test_rights_change_is_not_flagged_on_first_observation_but_is_on_a_real_change(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "rights-change")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="4", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    _classify(db_session, document.id, delivery.id, may_process=True)
    account = PostgresAccountRepository(db_session).create_account(
        email="rights-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=document.work_id)
    db_session.flush()
    baseline_repo = PostgresRightsNotificationBaselineRepository(db_session)

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 0  # first observation, nothing to compare against
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []
    # The first observation must still establish a baseline -- in the
    # dedicated tracking table, NOT as a row in the user-facing Notification
    # feed -- so a later genuine change has something to diff against.
    baseline = baseline_repo.get_baseline(
        account_id=account.id, work_id=document.work_id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    assert baseline is not None
    assert baseline.may_process is True

    # Re-classify with unchanged values -- a re-ingestion with the same
    # rights must NOT produce a notification (classified_at always moves,
    # the boolean fields don't).
    _classify(db_session, document.id, delivery.id, may_process=True)
    unchanged_run = run_notify_watchers(db_session, sender)
    assert unchanged_run.notifications_created == 0
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []

    # A genuine change must produce exactly one notification, and advance
    # the baseline to the new (now-current) state.
    _classify(db_session, document.id, delivery.id, may_process=False)
    changed_run = run_notify_watchers(db_session, sender)
    assert changed_run.notifications_created == 1
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert len(notifications) == 1
    assert notifications[0].trigger_type == NotificationTriggerType.RIGHTS_CHANGE
    assert notifications[0].may_process is False
    advanced_baseline = baseline_repo.get_baseline(
        account_id=account.id, work_id=document.work_id, trigger_document_id=document.id,
        trigger_jurisdiction="DE",
    )
    assert advanced_baseline is not None
    assert advanced_baseline.may_process is False

    # A reversion back to the ORIGINAL (may_process=True) state is itself a
    # genuine change relative to the now-advanced baseline, and must also be
    # detected -- this is the specific correctness property this baseline
    # table restores: a frozen first-observation snapshot would have wrongly
    # treated this as "back to normal, no notification".
    _classify(db_session, document.id, delivery.id, may_process=True)
    reverted_run = run_notify_watchers(db_session, sender)
    assert reverted_run.notifications_created == 1
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert len(notifications) == 2
    assert {n.may_process for n in notifications} == {True, False}


def _seed_edge_and_watch(db_session, tag, *, edge_created_at, watch_created_at):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, tag)
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number=tag, edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number=tag, edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    _set_created_at(db_session, EdgeORM, edge.id, edge_created_at)

    account = PostgresAccountRepository(db_session).create_account(
        email=f"{tag}@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, watch_created_at)
    return account


def test_edge_created_before_the_watch_is_skipped_as_history(db_session):
    """
    Marking a Work as a favorite must not backfill its entire edge history as
    fresh notifications -- a years-old replacement is not news to someone who
    just started watching. Only edges strictly newer than the watch notify.
    """
    account = _seed_edge_and_watch(
        db_session, "edge-before-watch", edge_created_at=_BEFORE, watch_created_at=_AFTER,
    )

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 0
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []


def test_deleting_a_read_notification_does_not_cause_a_duplicate_on_the_next_run(db_session):
    # Regression test for the bug the final review of the notification-
    # cleanup branch found: before notified_edge existed, the Notification
    # row itself was the only dedup marker for NEW_EDITION/NATIONAL_ADOPTION.
    # Once cleanup-notifications could delete a read Notification row, the
    # next notify-watchers run had no memory that the edge was already
    # handled -- it recreated the notification and, under EMAIL/BOTH,
    # re-sent the email. This proves that no longer happens.
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "no-duplicate-after-cleanup")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-no-dup@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.BOTH
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1
    assert len(sender.sent) == 1

    notification_repo = PostgresNotificationRepository(db_session)
    created = notification_repo.list_for_account(account.id)[0]
    # delete_read_before compares against created_at, which defaults to the
    # transaction's frozen now() -- today's real date, not the fictional
    # _BEFORE/_AFTER timeline the rest of this test uses. Backdate it
    # explicitly so it is unambiguously older than the _AFTER cutoff, same
    # technique as test_notification_repository.py's delete_read_before
    # tests and _set_created_at above.
    _set_created_at(db_session, NotificationORM, created.id, _BEFORE)
    notification_repo.mark_read(created.id, account_id=account.id, read_at=_AFTER)
    deleted_count = notification_repo.delete_read_before(_AFTER)
    assert deleted_count == 1
    assert notification_repo.list_for_account(account.id) == []

    second_run = run_notify_watchers(db_session, sender)

    assert second_run.notifications_created == 0
    assert notification_repo.list_for_account(account.id) == []
    assert len(sender.sent) == 1  # unchanged from after first_run -- no re-send


def test_edge_created_after_the_watch_produces_a_notification(db_session):
    account = _seed_edge_and_watch(
        db_session, "edge-after-watch", edge_created_at=_AFTER, watch_created_at=_BEFORE,
    )

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 1
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert len(notifications) == 1
    assert notifications[0].trigger_type == NotificationTriggerType.NEW_EDITION


def test_an_edge_created_at_the_exact_watch_timestamp_is_treated_as_history(db_session):
    """
    The rule is strict: an edge whose created_at equals the watch's is not
    newer than the watch, so it is history, not a change since watching.
    """
    same_moment = datetime(2026, 6, 1, tzinfo=timezone.utc)
    account = _seed_edge_and_watch(
        db_session, "edge-at-watch", edge_created_at=same_moment, watch_created_at=same_moment,
    )

    summary = run_notify_watchers(db_session, RecordingEmailSender())

    assert summary.notifications_created == 0
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []
