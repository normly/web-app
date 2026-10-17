# core/tests/pipeline/test_email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.notifications.email import NullEmailSender, RecordingEmailSender, SmtpEmailSender


def test_recording_email_sender_records_every_call():
    sender = RecordingEmailSender()
    sender.send(to="a@example.de", subject="Test", body="Body")
    assert sender.sent == [{"to": "a@example.de", "subject": "Test", "body": "Body"}]


def test_null_email_sender_always_raises():
    sender = NullEmailSender()
    with pytest.raises(RuntimeError, match="no SMTP relay configured"):
        sender.send(to="a@example.de", subject="Test", body="Body")


@pytest.mark.parametrize("from_address", ["normly", "", "@normly.ai", "noreply@", "normly <noreply>"])
def test_smtp_email_sender_rejects_a_from_address_without_local_part_and_domain(from_address):
    # A relay may accept `MAIL FROM:<normly>` and drop the mail afterwards,
    # with no bounce address to report it -- so fail at construction instead.
    with pytest.raises(ValueError, match="NORMLY_SMTP_FROM"):
        SmtpEmailSender(host="smtp.example.org", port=587, from_address=from_address)


@pytest.mark.parametrize("from_address", ["noreply@normly.ai", "normly <noreply@normly.ai>"])
def test_smtp_email_sender_accepts_a_full_from_address(from_address):
    sender = SmtpEmailSender(host="smtp.example.org", port=587, from_address=from_address)
    assert sender.from_address == from_address
