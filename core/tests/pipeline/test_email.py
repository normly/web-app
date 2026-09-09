# core/tests/pipeline/test_email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.notifications.email import NullEmailSender, RecordingEmailSender


def test_recording_email_sender_records_every_call():
    sender = RecordingEmailSender()
    sender.send(to="a@example.de", subject="Test", body="Body")
    assert sender.sent == [{"to": "a@example.de", "subject": "Test", "body": "Body"}]


def test_null_email_sender_always_raises():
    sender = NullEmailSender()
    with pytest.raises(RuntimeError, match="no SMTP relay configured"):
        sender.send(to="a@example.de", subject="Test", body="Body")
