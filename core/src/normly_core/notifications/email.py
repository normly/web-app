# core/src/normly_core/notifications/email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol


_SMTP_TIMEOUT_SECONDS = 10


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


@dataclass
class SmtpEmailSender:
    """
    Sends mail through an EU-hosted or self-hosted SMTP relay. Never a
    US-hosted transactional email API (SendGrid/Mailgun/SES) -- see the
    design spec's context section for why. The concrete host/credentials
    are a deployment-time configuration concern, not hardcoded here.
    """

    host: str
    port: int
    from_address: str
    username: str | None = None
    password: str | None = None

    def send(self, *, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        # Every route is a sync `def` and so runs on Starlette's bounded
        # threadpool. Without a timeout an unresponsive relay pins a worker
        # thread forever, and the routers' try/except around send() cannot
        # help -- the call never returns to raise.
        with smtplib.SMTP(self.host, self.port, timeout=_SMTP_TIMEOUT_SECONDS) as client:
            if self.username is not None:
                client.starttls()
                client.login(self.username, self.password or "")
            client.send_message(message)


@dataclass
class RecordingEmailSender:
    """Test double: records sent emails instead of sending them."""

    sent: list[dict[str, str]] = field(default_factory=list)

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


@dataclass
class NullEmailSender:
    """
    Fallback used when no SMTP relay is configured. Unlike RecordingEmailSender
    (a deliberate test double that simulates success), this always raises --
    it exists specifically so notify-watchers' fail-soft try/except leaves
    `emailed_at` at None instead of stamping a real timestamp for mail that
    was never sent. accounts/'s own lifespan() has no equivalent persisted
    "was this delivered" column that anything relies on, so it keeps using
    RecordingEmailSender for its own fallback -- this class is specific to
    notify-watchers' need for emailed_at to be trustworthy stored data.
    """

    def send(self, *, to: str, subject: str, body: str) -> None:
        raise RuntimeError(
            "no SMTP relay configured -- set NORMLY_SMTP_HOST to send real "
            "notification email"
        )
