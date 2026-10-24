# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
import os
import uuid
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
    PostgresNotifiedRetirementRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresRightsRepository,
    PostgresWatchlistRepository,
)
from normly_core.notifications.email import EmailSender
from normly_core.notifications.mail import RenderedEmail, render_email

logger = logging.getLogger(__name__)

_NEW_EDITION_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY)
_NATIONAL_ADOPTION_EDGE_TYPES = (EdgeType.ADOPTED_FROM,)

@dataclass(frozen=True)
class NotifyWatchersSummary:
    watches_scanned: int
    notifications_created: int
    emails_sent: int


@dataclass(frozen=True)
class _MailFacts:
    """What the mail is about: the watched document and the one to link to."""

    watched_document_id: uuid.UUID
    linked_document_id: uuid.UUID | None
    jurisdiction: str | None


def _is_cleared(rights_repo: PostgresRightsRepository, document_id: uuid.UUID) -> bool:
    """
    True if the document has an active classification that allows processing.
    The rights classification is the only gate for what a mail may show of a
    document beyond its designation: titles and links to it need clearance.
    """
    return any(
        c.may_process and c.revoked_at is None
        for c in rights_repo.list_classifications_for_document_unchecked(document_id)
    )


def _describe(
    document_repo: PostgresDocumentRepository, document_id: uuid.UUID, locale: str,
    *, show_title: bool,
) -> tuple[str, str]:
    """
    (designation, title). The designation falls back to the origin fields. The
    title is only read for a cleared document (`show_title`); otherwise, and
    when none exists, the designation stands in for it.
    """
    designations = document_repo.list_designations(document_id)
    primary = next((d for d in designations if d.is_primary), None) or (
        designations[0] if designations else None
    )
    if primary is not None:
        designation = primary.designation
    else:
        document = document_repo.get_document_unchecked(document_id)
        designation = f"{document.origin_issuer} {document.origin_number}:{document.edition}"
    titles = document_repo.list_titles(document_id) if show_title else []
    title = next((t.title for t in titles if t.language == locale), None) or (
        titles[0].title if titles else designation
    )
    return designation, title


def _render_watch_email(
    document_repo: PostgresDocumentRepository, rights_repo: PostgresRightsRepository,
    account: Account, trigger_type: NotificationTriggerType, facts: _MailFacts,
) -> RenderedEmail:
    base_url = os.environ.get("NORMLY_PUBLIC_BASE_URL") or None
    locale = account.locale or "de"  # unknown language: German, as before it was stored
    designation, title = _describe(
        document_repo, facts.watched_document_id, locale,
        show_title=_is_cleared(rights_repo, facts.watched_document_id),
    )
    document = designation
    link_cleared = False
    if facts.linked_document_id is not None:
        # Only the designation of the linked document is used, never its title.
        document = _describe(
            document_repo, facts.linked_document_id, locale, show_title=False
        )[0]
        link_cleared = _is_cleared(rights_repo, facts.linked_document_id)
    if facts.jurisdiction:
        document = f"{document} ({facts.jurisdiction})"
    action_url = None
    if base_url is not None:
        action_url = (
            f"{base_url}/documents/{facts.linked_document_id}"
            if link_cleared else f"{base_url}/"
        )
    return render_email(
        f"watch_{trigger_type.value}", locale, base_url=base_url,
        action_url=action_url, designation=designation, title=title, document=document,
    )


def run_notify_watchers(session: Session, email_sender: EmailSender) -> NotifyWatchersSummary:
    watchlist_repo = PostgresWatchlistRepository(session)
    notification_repo = PostgresNotificationRepository(session)
    notified_edge_repo = PostgresNotifiedEdgeRepository(session)
    notified_retirement_repo = PostgresNotifiedRetirementRepository(session)
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
                    document_repo=document_repo, rights_repo=rights_repo,
                    facts=_MailFacts(edge.to_document_id, edge.from_document_id, edge.jurisdiction),
                )
                notifications_created += 1
                if notification.emailed_at is not None:
                    emails_sent += 1
                notified_edge_repo.mark_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                )

        for document in documents:
            # Tombstoned documents (retired by a knowledge-base import) are
            # returned by list_documents_for_work_unchecked. Only retirements
            # after the watch began are news; the retirement timestamp is part
            # of the dedup key, so a retirement after a return notifies anew.
            retired_at = document.retired_at
            if retired_at is None or retired_at <= watch.created_at:
                continue
            if notified_retirement_repo.has_been_notified(
                account_id=account.id, work_id=watch.work_id,
                document_id=document.id, retired_at=retired_at,
            ):
                continue
            notification = _create_and_maybe_email(
                notification_repo, email_sender, account=account, work_id=watch.work_id,
                trigger_type=NotificationTriggerType.NO_LONGER_AVAILABLE,
                trigger_edge_id=None, trigger_document_id=document.id,
                trigger_jurisdiction=None,
                may_process=None, may_index_fulltext=None,
                may_cite_passages=None, may_export_free=None,
                document_repo=document_repo, rights_repo=rights_repo,
                facts=_MailFacts(document.id, None, None),
            )
            notifications_created += 1
            if notification.emailed_at is not None:
                emails_sent += 1
            notified_retirement_repo.mark_notified(
                account_id=account.id, work_id=watch.work_id,
                document_id=document.id, retired_at=retired_at,
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
                    document_repo=document_repo, rights_repo=rights_repo,
                    facts=_MailFacts(document_id, document_id, None),
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
    document_repo: PostgresDocumentRepository,
    rights_repo: PostgresRightsRepository,
    facts: _MailFacts,
):
    emailed_at = None
    if account.notification_preference in (
        NotificationPreference.EMAIL, NotificationPreference.BOTH,
    ):
        try:
            mail = _render_watch_email(document_repo, rights_repo, account, trigger_type, facts)
        except Exception:
            # One broken mail must not abort the run: the job commits once at
            # the end, so an abort would roll back the notifications of the
            # mails already sent and mail them again next run. No address in
            # the log.
            logger.exception("notify-watchers email rendering failed for account %s", account.id)
            mail = None
        if mail is not None:
            try:
                email_sender.send(
                    to=account.email, subject=mail.subject, body=mail.text, html=mail.html,
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
