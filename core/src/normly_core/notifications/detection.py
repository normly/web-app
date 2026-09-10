# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.domain import (
    Account,
    EdgeType,
    NotificationPreference,
    NotificationTriggerType,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresRightsRepository,
    PostgresWatchlistRepository,
)
from normly_core.notifications.email import EmailSender

logger = logging.getLogger(__name__)

_NEW_EDITION_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY)
_NATIONAL_ADOPTION_EDGE_TYPES = (EdgeType.ADOPTED_FROM,)

_EMAIL_SUBJECTS = {
    NotificationTriggerType.NEW_EDITION: "Neue Ausgabe eines beobachteten Regelwerks",
    NotificationTriggerType.NATIONAL_ADOPTION: "Neue nationale Fassung eines beobachteten Regelwerks",
    NotificationTriggerType.RIGHTS_CHANGE: "Rechteänderung an einem beobachteten Regelwerk",
}


@dataclass(frozen=True)
class NotifyWatchersSummary:
    watches_scanned: int
    notifications_created: int
    emails_sent: int


def run_notify_watchers(session: Session, email_sender: EmailSender) -> NotifyWatchersSummary:
    watchlist_repo = PostgresWatchlistRepository(session)
    notification_repo = PostgresNotificationRepository(session)
    notified_edge_repo = PostgresNotifiedEdgeRepository(session)
    account_repo = PostgresAccountRepository(session)
    document_repo = PostgresDocumentRepository(session)
    edge_repo = PostgresEdgeRepository(session)
    rights_repo = PostgresRightsRepository(session)
    baseline_repo = PostgresRightsNotificationBaselineRepository(session)

    watches = watchlist_repo.list_all_watches()
    notifications_created = 0
    emails_sent = 0

    for watch in watches:
        account = account_repo.get_account_by_id(watch.account_id)
        if account is None or account.notification_preference == NotificationPreference.NONE:
            continue

        documents = document_repo.list_documents_for_work_unchecked(watch.work_id)
        document_ids = [document.id for document in documents]

        for edge_types, trigger_type in (
            (_NEW_EDITION_EDGE_TYPES, NotificationTriggerType.NEW_EDITION),
            (_NATIONAL_ADOPTION_EDGE_TYPES, NotificationTriggerType.NATIONAL_ADOPTION),
        ):
            for edge in edge_repo.list_incoming_edges_for_work_unchecked(document_ids, edge_types):
                # Only changes that happened AFTER the watch was added are
                # news. Without this, marking a Work as a favorite backfills
                # its entire edge history -- every past replacement and
                # adoption, however old -- as fresh notifications on the very
                # first scan, and mails all of them under EMAIL/BOTH. The
                # rule is strict: an edge created at or before the moment of
                # watching is history, not a change since watching.
                if edge.created_at <= watch.created_at:
                    continue
                if notified_edge_repo.has_been_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                ):
                    continue
                notification = _create_and_maybe_email(
                    notification_repo, email_sender, account=account, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                    trigger_document_id=None, trigger_jurisdiction=None,
                    may_process=None, may_index_fulltext=None,
                    may_cite_passages=None, may_export_free=None,
                )
                notifications_created += 1
                if notification.emailed_at is not None:
                    emails_sent += 1
                notified_edge_repo.mark_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                )

        for document_id in document_ids:
            for classification in rights_repo.list_classifications_for_document_unchecked(
                document_id
            ):
                baseline = baseline_repo.get_baseline(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_document_id=document_id,
                    trigger_jurisdiction=classification.jurisdiction,
                )
                if baseline is None:
                    # First observation -- establish the baseline, no notification.
                    baseline_repo.upsert_baseline(
                        account_id=account.id, work_id=watch.work_id,
                        trigger_document_id=document_id,
                        trigger_jurisdiction=classification.jurisdiction,
                        may_process=classification.may_process,
                        may_index_fulltext=classification.may_index_fulltext,
                        may_cite_passages=classification.may_cite_passages,
                        may_export_free=classification.may_export_free,
                    )
                    continue
                if (
                    baseline.may_process == classification.may_process
                    and baseline.may_index_fulltext == classification.may_index_fulltext
                    and baseline.may_cite_passages == classification.may_cite_passages
                    and baseline.may_export_free == classification.may_export_free
                ):
                    continue
                notification = _create_and_maybe_email(
                    notification_repo, email_sender, account=account, work_id=watch.work_id,
                    trigger_type=NotificationTriggerType.RIGHTS_CHANGE, trigger_edge_id=None,
                    trigger_document_id=document_id,
                    trigger_jurisdiction=classification.jurisdiction,
                    may_process=classification.may_process,
                    may_index_fulltext=classification.may_index_fulltext,
                    may_cite_passages=classification.may_cite_passages,
                    may_export_free=classification.may_export_free,
                )
                notifications_created += 1
                if notification.emailed_at is not None:
                    emails_sent += 1
                # Advance the baseline to the now-current state, so a later
                # reversion back to an earlier state is itself detected as a
                # genuine change, not silently ignored because it matches
                # the ORIGINAL baseline.
                baseline_repo.upsert_baseline(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_document_id=document_id,
                    trigger_jurisdiction=classification.jurisdiction,
                    may_process=classification.may_process,
                    may_index_fulltext=classification.may_index_fulltext,
                    may_cite_passages=classification.may_cite_passages,
                    may_export_free=classification.may_export_free,
                )

    return NotifyWatchersSummary(
        watches_scanned=len(watches), notifications_created=notifications_created,
        emails_sent=emails_sent,
    )


def _create_and_maybe_email(
    notification_repo: PostgresNotificationRepository,
    email_sender: EmailSender,
    *,
    account: Account,
    work_id,
    trigger_type: NotificationTriggerType,
    trigger_edge_id,
    trigger_document_id,
    trigger_jurisdiction: str | None,
    may_process: bool | None,
    may_index_fulltext: bool | None,
    may_cite_passages: bool | None,
    may_export_free: bool | None,
):
    emailed_at = None
    if account.notification_preference in (
        NotificationPreference.EMAIL, NotificationPreference.BOTH,
    ):
        try:
            email_sender.send(
                to=account.email, subject=_EMAIL_SUBJECTS[trigger_type],
                body=(
                    f"Ein von dir beobachtetes Regelwerk hat eine Änderung erfahren "
                    f"({trigger_type.value}). Melde dich bei normly an, um die Details zu sehen."
                ),
            )
            emailed_at = datetime.now(timezone.utc)
        except Exception:
            # Fail-soft, best-effort, no retry -- see Global Constraints.
            logger.exception("notify-watchers email delivery failed for %s", account.email)

    return notification_repo.create(
        account_id=account.id, work_id=work_id, trigger_type=trigger_type,
        trigger_edge_id=trigger_edge_id, trigger_document_id=trigger_document_id,
        trigger_jurisdiction=trigger_jurisdiction, may_process=may_process,
        may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
        may_export_free=may_export_free, emailed_at=emailed_at,
    )
