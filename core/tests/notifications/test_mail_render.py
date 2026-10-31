# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, timedelta

import pytest

from normly_core.notifications.mail import (
    contact_address,
    format_date,
    format_days,
    format_duration,
    render_bilingual_email,
    render_email,
)
from normly_core.notifications.mail.texts import COMMON

KINDS = [
    "verification", "magic_link", "password_reset", "email_change",
    "watch_new_edition", "watch_national_adoption", "watch_rights_change",
    "watch_no_longer_available", "deletion_warning",
]
PARAMS = {
    "validity": "1 Stunde", "new_email": "neu@example.de", "designation": "DIN 1",
    "title": "Titel", "document": "DIN 1:2026", "date": "21.10.2026",
}
ACTION = "https://app.example.org/do?token=abc&x=1"


@pytest.fixture(autouse=True)
def _no_footer_env(monkeypatch):
    monkeypatch.delenv("NORMLY_IMPRINT_URL", raising=False)
    monkeypatch.delenv("NORMLY_PRIVACY_URL", raising=False)


@pytest.mark.parametrize("locale", ["de", "en"])
@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_renders_in_every_locale(kind, locale):
    mail = render_email(kind, locale, base_url="https://app.example.org", action_url=ACTION, **PARAMS)

    assert mail.subject and "{" not in mail.subject
    assert "{" not in mail.text and "{{" not in mail.html
    assert ACTION in mail.text
    assert "https://app.example.org/do?token=abc&amp;x=1" in mail.html
    assert f'lang="{locale}"' in mail.html


def test_german_and_english_differ():
    de = render_email("magic_link", "de", base_url=None, action_url=ACTION, validity="15 Minuten")
    en = render_email("magic_link", "en", base_url=None, action_url=ACTION, validity="15 minutes")
    assert de.subject == "Dein Anmeldelink für normly"
    assert en.subject == "Your sign-in link for normly"


def test_unknown_locale_falls_back_to_german():
    mail = render_email("magic_link", "fr", base_url=None, action_url=ACTION, validity="15 Minuten")
    assert mail.subject == "Dein Anmeldelink für normly"


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown email kind"):
        render_email("nope", "de", base_url=None)


def test_missing_placeholder_raises():
    with pytest.raises(KeyError):
        render_email("verification", "de", base_url=None, action_url=ACTION)


def test_inserted_values_are_escaped_in_html_only():
    mail = render_email(
        "watch_rights_change", "de", base_url=None, action_url=ACTION,
        designation="DIN 1", title="<script>alert(1)</script>",
    )
    assert "<script>" not in mail.html
    assert "&lt;script&gt;" in mail.html
    assert "<script>alert(1)</script>" in mail.text


def test_without_action_url_there_is_no_button_and_no_link():
    mail = render_email("deletion_warning", "de", base_url=None, date="21.10.2026")
    assert "http" not in mail.text
    assert "<a " not in mail.html


def test_footer_links_appear_only_when_configured(monkeypatch):
    plain = render_email("deletion_warning", "de", base_url=None, date="21.10.2026")
    assert "Impressum" not in plain.html and "Datenschutz" not in plain.html

    monkeypatch.setenv("NORMLY_IMPRINT_URL", "https://example.org/imprint")
    monkeypatch.setenv("NORMLY_PRIVACY_URL", "https://example.org/privacy")
    linked = render_email("deletion_warning", "de", base_url=None, date="21.10.2026")
    assert 'href="https://example.org/imprint"' in linked.html
    assert 'href="https://example.org/privacy"' in linked.html
    assert "https://example.org/imprint" in linked.text


def test_layout_uses_the_shadcn_neutral_tokens():
    mail = render_email("magic_link", "de", base_url=None, action_url=ACTION, validity="15 Minuten")
    for value in ("#f5f5f5", "#ffffff", "#0a0a0a", "#e5e5e5", "#171717", "#fafafa", "#737373"):
        assert value in mail.html


@pytest.mark.parametrize(("duration", "locale", "expected"), [
    (timedelta(hours=48), "de", "48 Stunden"),
    (timedelta(hours=48), "en", "48 hours"),
    (timedelta(hours=1), "de", "1 Stunde"),
    (timedelta(hours=1), "en", "1 hour"),
    (timedelta(minutes=15), "de", "15 Minuten"),
    (timedelta(minutes=15), "en", "15 minutes"),
])
def test_format_duration(duration, locale, expected):
    assert format_duration(duration, locale) == expected


def test_format_date():
    assert format_date(date(2026, 10, 21), "de") == "21.10.2026"
    assert format_date(date(2026, 10, 21), "en") == "21 October 2026"


def test_bilingual_mail_has_both_languages_in_one_document():
    mail = render_bilingual_email(
        "deletion_warning", base_url="https://app.example.org",
        action_url="https://app.example.org",
        params={"de": {"date": "21.10.2026"}, "en": {"date": "21 October 2026"}},
    )

    assert mail.subject == "Dein normly-Konto wird gelöscht / Your normly account will be deleted"
    for part in (mail.text, mail.html):
        assert "Dein Konto wird bald gelöscht" in part
        assert "Your account will be deleted soon" in part
        assert "21.10.2026" in part and "21 October 2026" in part
        assert part.index("Dein Konto") < part.index("Your account")
    assert mail.html.count("<html") == 1
    assert 'lang="de"' in mail.html
    assert "\n---\n" in mail.text
    assert "Bei normly anmelden" in mail.html and "Sign in to normly" in mail.html


def test_bilingual_mail_still_escapes_html_only():
    mail = render_bilingual_email(
        "watch_rights_change", base_url=None, action_url=ACTION,
        params={
            "de": {"designation": "DIN 1", "title": "<b>x</b>"},
            "en": {"designation": "DIN 1", "title": "<b>x</b>"},
        },
    )
    assert "<b>x</b>" not in mail.html
    assert "&lt;b&gt;x&lt;/b&gt;" in mail.html
    assert "<b>x</b>" in mail.text


@pytest.mark.parametrize("locale", ["de", "en"])
def test_invitation_renders_role_publisher_and_the_escaped_personal_message(locale):
    mail = render_email(
        "invitation", locale, base_url="https://app.example.org", action_url=ACTION,
        quote="Hallo <b>Team</b>\nwie besprochen", role="Publisher",
        publisher=" für VDE Verlag" if locale == "de" else " for VDE Verlag",
        validity=format_days(7, locale),
    )
    assert "VDE Verlag" in mail.text and "Publisher" in mail.text
    assert "Hallo <b>Team</b>" in mail.text
    assert "Hallo &lt;b&gt;Team&lt;/b&gt;" in mail.html
    assert ACTION in mail.text
    assert "{" not in mail.text


def test_mails_without_a_quote_show_no_quote_label():
    mail = render_email("magic_link", "de", base_url=None, action_url=ACTION, validity="15 Minuten")
    assert "Persönliche Nachricht" not in mail.text


@pytest.mark.parametrize("kind", ["account_blocked", "account_removed"])
@pytest.mark.parametrize("locale", ["de", "en"])
def test_account_notices_name_the_contact_and_have_no_button(kind, locale):
    mail = render_email(kind, locale, base_url=None, contact="support@normly.example")
    assert "support@normly.example" in mail.text
    # The fallback-link sentence is rendered only together with a button.
    assert COMMON[locale]["fallback_link"] not in mail.text
    assert COMMON[locale]["fallback_link"] not in mail.html
    assert "{" not in mail.text


def test_account_notice_bilingual():
    mail = render_bilingual_email(
        "account_blocked", base_url=None,
        params={"de": {"contact": "a@b.example"}, "en": {"contact": "a@b.example"}},
    )
    assert mail.subject == "Dein normly-Konto wurde gesperrt / Your normly account has been blocked"


def test_format_days():
    assert format_days(7, "de") == "7 Tage"
    assert format_days(1, "en") == "1 day"


def test_contact_address_prefers_the_contact_variable(monkeypatch):
    monkeypatch.setenv("NORMLY_CONTACT_EMAIL", "kontakt@normly.example")
    monkeypatch.setenv("NORMLY_IMPRINT_URL", "https://normly.example/impressum")
    assert contact_address() == "kontakt@normly.example"
    monkeypatch.delenv("NORMLY_CONTACT_EMAIL")
    assert contact_address() == "https://normly.example/impressum"
