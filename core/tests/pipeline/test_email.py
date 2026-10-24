# core/tests/pipeline/test_email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.notifications.email import NullEmailSender, RecordingEmailSender, SmtpEmailSender


def test_recording_email_sender_records_every_call():
    sender = RecordingEmailSender()
    sender.send(to="a@example.de", subject="Test", body="Body")
    sender.send(to="b@example.de", subject="Test", body="Body", html="<p>Body</p>")
    assert sender.sent == [
        {"to": "a@example.de", "subject": "Test", "body": "Body", "html": None},
        {"to": "b@example.de", "subject": "Test", "body": "Body", "html": "<p>Body</p>"},
    ]


class _FakeSmtp:
    sent = []

    def __init__(self, host, port, timeout):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, message):
        _FakeSmtp.sent.append(message)


def _send_with_fake_smtp(monkeypatch, **kwargs):
    _FakeSmtp.sent = []
    monkeypatch.setattr("normly_core.notifications.email.smtplib.SMTP", _FakeSmtp)
    sender = SmtpEmailSender(host="smtp.example.org", port=25, from_address="noreply@normly.ai")
    sender.send(to="a@example.de", subject="Test", **kwargs)
    return _FakeSmtp.sent[0]


def test_smtp_email_sender_sends_text_and_html_as_alternatives(monkeypatch):
    message = _send_with_fake_smtp(monkeypatch, body="Plain", html="<p>Rich</p>")
    assert message.get_content_type() == "multipart/alternative"
    parts = list(message.iter_parts())
    assert [part.get_content_type() for part in parts] == ["text/plain", "text/html"]
    assert parts[0].get_content().strip() == "Plain"
    assert parts[1].get_content().strip() == "<p>Rich</p>"


def test_smtp_email_sender_without_html_sends_plain_text(monkeypatch):
    message = _send_with_fake_smtp(monkeypatch, body="Plain")
    assert message.get_content_type() == "text/plain"


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
