# accounts/src/normly_accounts/email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol


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

        with smtplib.SMTP(self.host, self.port) as client:
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
