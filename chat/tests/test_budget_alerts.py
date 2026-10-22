# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import logging
from datetime import datetime, timezone

from normly_core.notifications.email import RecordingEmailSender

from normly_chat.budget_alerts import BudgetAlert, BudgetAlerter

_ALERT = BudgetAlert(
    pool="anonymous", period="2026-10", threshold=80, total_tokens=8_100_000,
    budget_tokens=10_000_000, resets_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
)


def test_every_recipient_gets_a_mail_naming_pool_threshold_and_numbers():
    sender = RecordingEmailSender()
    BudgetAlerter(sender, ("lead-a@example.org", "lead-b@example.org")).send(_ALERT)

    assert [mail["to"] for mail in sender.sent] == ["lead-a@example.org", "lead-b@example.org"]
    mail = sender.sent[0]
    assert "anonymous" in mail["subject"] and "80 %" in mail["subject"]
    assert "8100000" in mail["body"]
    assert "10000000" in mail["body"]
    assert "2026-11-01T00:00:00+00:00" in mail["body"]


def test_without_recipients_the_alert_is_only_logged(caplog):
    sender = RecordingEmailSender()
    with caplog.at_level(logging.WARNING):
        BudgetAlerter(sender, ()).send(_ALERT)

    assert sender.sent == []
    assert "anonymous" in caplog.text


class _FailingSender:
    def __init__(self):
        self.attempts = 0

    def send(self, *, to, subject, body, html=None):
        self.attempts += 1
        raise OSError("relay down")


def test_a_failing_relay_is_logged_and_the_next_recipient_is_still_tried(caplog):
    sender = _FailingSender()
    with caplog.at_level(logging.ERROR):
        BudgetAlerter(sender, ("lead-a@example.org", "lead-b@example.org")).send(_ALERT)

    assert sender.attempts == 2
    assert "relay down" in caplog.text
