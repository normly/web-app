# core/tests/pipeline/test_email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.notifications.email import RecordingEmailSender


def test_recording_email_sender_records_every_call():
    sender = RecordingEmailSender()
    sender.send(to="a@example.de", subject="Test", body="Body")
    assert sender.sent == [{"to": "a@example.de", "subject": "Test", "body": "Body"}]
