# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Mails of the user management. Sending never fails the administrative action."""

from __future__ import annotations

import logging
import os

from normly_core.graph.domain import AccountInvitation
from normly_core.notifications.email import EmailSender
from normly_core.notifications.mail import (
    contact_address, format_days, render_bilingual_email, render_email,
)
from normly_core.notifications.mail.texts import ROLE_LABELS

logger = logging.getLogger(__name__)

INVITATION_LIFETIME_DAYS = 7
_PUBLISHER_CLAUSE = {"de": " für {name}", "en": " for {name}"}


def public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")


def _send(sender: EmailSender, *, to: str, mail) -> bool:
    try:
        sender.send(to=to, subject=mail.subject, body=mail.text, html=mail.html)
    except Exception:
        # Never log the token or the address' mail body.
        logger.exception("user management email delivery failed")
        return False
    return True


def send_invitation(
    sender: EmailSender, invitation: AccountInvitation, *, publisher_name: str | None,
    message: str | None,
) -> bool:
    locale = invitation.locale
    mail = render_email(
        "invitation", locale, base_url=public_base_url(),
        action_url=f"{public_base_url()}/invitation?token={invitation.token}",
        quote=message or None,
        role=ROLE_LABELS[locale][invitation.role.value],
        publisher=_PUBLISHER_CLAUSE[locale].format(name=publisher_name) if publisher_name else "",
        validity=format_days(INVITATION_LIFETIME_DAYS, locale),
    )
    return _send(sender, to=invitation.email, mail=mail)


def send_account_notice(
    sender: EmailSender, kind: str, *, email: str, locale: str | None
) -> bool:
    contact = contact_address()
    if locale is None:
        mail = render_bilingual_email(
            kind, base_url=public_base_url(),
            params={"de": {"contact": contact}, "en": {"contact": contact}},
        )
    else:
        mail = render_email(kind, locale, base_url=public_base_url(), contact=contact)
    return _send(sender, to=email, mail=mail)
