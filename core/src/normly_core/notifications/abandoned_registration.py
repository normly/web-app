# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Warning e-mail before an abandoned registration is deleted."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

from sqlalchemy.orm import Session

from normly_core import retention
from normly_core.graph.postgres.repositories import PostgresAccountRepository
from normly_core.notifications.email import EmailSender, NullEmailSender
from normly_core.notifications.mail import RenderedEmail, format_date, render_email

logger = logging.getLogger(__name__)

def build_warning_email(*, delete_on: date, base_url: str | None, locale: str) -> RenderedEmail:
    return render_email(
        "deletion_warning", locale, base_url=base_url, action_url=base_url,
        date=format_date(delete_on, locale),
    )


def warn_abandoned_registrations(
    session: Session, sender: EmailSender, *, now: datetime, cutoff: datetime,
) -> int:
    """
    Mails every abandoned, not yet warned registration and records the warning
    only after the mail was handed over. A failed send leaves the account
    unwarned (so it is retried next run and never deleted). Returns the number
    of warnings delivered.

    Commits after every delivered mail, so a later failure cannot roll back the
    record of a mail that already went out (which would mail everyone again).
    Callers must therefore expect the session's pending work to be committed.
    """
    if isinstance(sender, NullEmailSender):
        logger.warning("no SMTP relay configured: abandoned registrations are not warned, so none are deleted")
        return 0
    base_url = os.environ.get("NORMLY_PUBLIC_BASE_URL") or None
    delete_on = (now + retention.ACCOUNT_DELETION_NOTICE_PERIOD).date()
    repo = PostgresAccountRepository(session)
    sent = 0
    for account_id, email, locale in repo.abandoned_registrations_to_warn(cutoff):
        mail = build_warning_email(delete_on=delete_on, base_url=base_url, locale=locale)
        try:
            sender.send(to=email, subject=mail.subject, body=mail.text, html=mail.html)
        except Exception:
            # Fail-soft like notify-watchers: no address in the log.
            logger.exception("warning e-mail for account %s failed", account_id)
            continue
        # No lock or re-check here: an account that signs in meanwhile gets one
        # needless mail; the next run's reset and the delete re-check protect it.
        repo.mark_deletion_warned(account_id, now)
        session.commit()
        sent += 1
    return sent
