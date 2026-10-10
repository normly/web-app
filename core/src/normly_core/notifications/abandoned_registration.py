# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Warning e-mail before an abandoned registration is deleted."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from normly_core import retention
from normly_core.graph.postgres.repositories import PostgresAccountRepository
from normly_core.notifications.email import EmailSender, NullEmailSender

logger = logging.getLogger(__name__)

SUBJECT = "Dein normly-Konto wird gelöscht / Your normly account will be deleted"


def build_warning_body(*, delete_on: str, base_url: str | None) -> str:
    link_de = f"Melde dich bei normly an: {base_url}" if base_url else "Melde dich bei normly an."
    link_en = f"Sign in to normly: {base_url}" if base_url else "Sign in to normly."
    return (
        "Hallo,\n\n"
        "dein normly-Konto wurde nie bestätigt und seit langem nicht genutzt. "
        f"Es wird frühestens am {delete_on} gelöscht, wenn du dich bis dahin nicht anmeldest.\n"
        f"{link_de}\n\n"
        "---\n\n"
        "Hello,\n\n"
        "your normly account was never confirmed and has not been used for a long time. "
        f"It will be deleted on {delete_on} at the earliest unless you sign in before then.\n"
        f"{link_en}\n"
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
    delete_on = (now + retention.ACCOUNT_DELETION_NOTICE_PERIOD).date().isoformat()
    body = build_warning_body(delete_on=delete_on, base_url=base_url)
    repo = PostgresAccountRepository(session)
    sent = 0
    for account_id, email in repo.abandoned_registrations_to_warn(cutoff):
        try:
            sender.send(to=email, subject=SUBJECT, body=body)
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
