# Email Templates and Per-Account Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every email normly sends becomes a branded HTML mail (with a plain-text part) in the recipient's language, and Normtracker mails name the standard and link to it.

**Architecture:** A Jinja2 renderer in `normly_core.notifications.mail` turns `(kind, locale, params)` into subject, text and HTML from one base layout plus a per-locale text dictionary. `EmailSender.send` gains an optional `html`. Accounts get a stored `locale`; the frontend resolves the visitor's language (cookie → `Accept-Language` → `de`) and passes it to every mail-triggering accounts call; the language switch updates the stored value.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Jinja2 3.1, pytest + testcontainers; Next.js 16, vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-email-templates-design.md`

## Global Constraints

- Branch `feature/45-email-templates` (off `develop`); PR targets `develop`. No push without asking the owner (pushes trigger CI).
- Every commit: Conventional Commits, `git commit -s` (DCO sign-off of the human committer), trailer `Assisted-by: Claude Code`. Never `Co-Authored-By`.
- New source files start with the AGPL header used across the repo:
  `# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors` (Python, Jinja `{# … #}`), `// …` (TypeScript).
- Supported locales: exactly `de` and `en`; default `de`.
- Colors: only the shadcn "neutral" tokens `muted #f5f5f5`, `card #ffffff`, `foreground #0a0a0a`, `border #e5e5e5`, `primary #171717`, `primary-foreground #fafafa`, `muted-foreground #737373`, radius `8px`.
- Link targets come from `NORMLY_PUBLIC_BASE_URL`; never hard-code `normly.ai` in code.
- Footer links from `NORMLY_IMPRINT_URL` / `NORMLY_PRIVACY_URL`; omitted when unset.
- Render before the `try` around `send()`; delivery stays fail-soft exactly as today.
- Database access only through the repository layer (no SQL in routers or `detection.py`).
- Python tests: `cd <package> && ../.venv/bin/pytest <path> -v` (needs Docker for testcontainers). Frontend: `cd frontend && npx vitest run <path>`.

## File Structure

| File | Responsibility |
|---|---|
| `core/src/normly_core/notifications/email.py` (modify) | `html` parameter, multipart sending |
| `core/src/normly_core/notifications/mail/__init__.py` (new) | public API re-exports |
| `core/src/normly_core/notifications/mail/texts.py` (new) | all subjects and copy, per locale |
| `core/src/normly_core/notifications/mail/render.py` (new) | Jinja env, tokens, `render_email`, `format_duration`, `format_date` |
| `core/src/normly_core/notifications/mail/templates/base.html.j2` (new) | HTML layout |
| `core/src/normly_core/notifications/mail/templates/base.txt.j2` (new) | text layout |
| `core/migrations/versions/0039_account_locale.py` (new) | `account.locale` |
| `core/src/normly_core/graph/{domain,postgres/orm,postgres/repositories}.py` (modify) | locale field, `update_locale`, locale in abandoned list |
| `core/src/normly_core/notifications/detection.py` (modify) | Normtracker mail content |
| `core/src/normly_core/notifications/abandoned_registration.py` (modify) | monolingual warning |
| `accounts/src/normly_accounts/schemas.py` + 7 routers (modify) | locale in requests, rendering |
| `frontend/src/lib/i18n/resolve-locale.ts` (new) | one locale resolution |
| `frontend/src/app/api/account/locale/route.ts` (new) | store locale on switch |
| 7 BFF routes, `layout.tsx`, `provider.tsx` (modify) | pass locale |
| `.env.example`, `docs/guide/self-hosting.md`, `docs/guide/operations.md` (modify) | config docs |

---

### Task 1: `EmailSender` sends HTML alongside text

**Files:**
- Modify: `core/src/normly_core/notifications/email.py`
- Test: `core/tests/pipeline/test_email.py`

**Interfaces:**
- Produces: `EmailSender.send(*, to: str, subject: str, body: str, html: str | None = None) -> None`; `RecordingEmailSender.sent: list[dict[str, str | None]]` with keys `to`, `subject`, `body`, `html`.

- [ ] **Step 1: Write the failing tests** — replace `test_recording_email_sender_records_every_call` and append the SMTP tests in `core/tests/pipeline/test_email.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd core && ../.venv/bin/pytest tests/pipeline/test_email.py -v`
Expected: FAIL — `send() got an unexpected keyword argument 'html'`.

- [ ] **Step 3: Implement** in `email.py`:

```python
class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None: ...
```

`SmtpEmailSender.send`:

```python
    def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if html is not None:
            # multipart/alternative: clients that render HTML show the last
            # part, every other client falls back to the plain text.
            message.add_alternative(html, subtype="html")
        # (rest unchanged)
```

`RecordingEmailSender`:

```python
    sent: list[dict[str, str | None]] = field(default_factory=list)

    def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, "html": html})
```

`NullEmailSender.send` gets the same `html: str | None = None` parameter (body unchanged).

- [ ] **Step 4: Run to verify pass** — same command, expected PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/notifications/email.py core/tests/pipeline/test_email.py
git commit -s -m "feat(core): send HTML mail alongside the plain-text part

Refs #45

Assisted-by: Claude Code"
```

---

### Task 2: Mail renderer with base layout and texts

**Files:**
- Modify: `core/pyproject.toml` (dependency), `uv.lock`
- Create: `core/src/normly_core/notifications/mail/__init__.py`, `texts.py`, `render.py`, `templates/base.html.j2`, `templates/base.txt.j2`
- Test: `core/tests/notifications/test_mail_render.py`

**Interfaces:**
- Produces (import from `normly_core.notifications.mail`):
  - `RenderedEmail(subject: str, text: str, html: str)` (frozen dataclass)
  - `render_email(kind: str, locale: str, *, base_url: str | None, action_url: str | None = None, **params: str) -> RenderedEmail` — unknown locale → `de`; unknown kind → `ValueError`; a placeholder missing from `params` → `KeyError`.
  - `format_duration(duration: timedelta, locale: str) -> str` — `"48 Stunden"`, `"1 hour"`, `"15 Minuten"`.
  - `format_date(value: date, locale: str) -> str` — `"21.10.2026"`, `"21 October 2026"`.
  - Kinds and their placeholders: `verification` (`validity`), `magic_link` (`validity`), `password_reset` (`validity`), `email_change` (`validity`, `new_email`), `watch_new_edition` / `watch_national_adoption` (`designation`, `title`, `document`), `watch_rights_change` / `watch_no_longer_available` (`designation`, `title`), `deletion_warning` (`date`).

- [ ] **Step 1: Add the dependency** — in `core/pyproject.toml` `dependencies`, after `"cryptography>=43,<46",` add:

```toml
    "jinja2>=3.1,<4.0",
```

Run: `uv lock` (from the repo root). Expected: `uv.lock` changes only in the `normly-core` dependency list (jinja2 3.1.6 is already locked).

- [ ] **Step 2: Write the failing tests** — `core/tests/notifications/test_mail_render.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, timedelta

import pytest

from normly_core.notifications.mail import format_date, format_duration, render_email

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
```

- [ ] **Step 3: Run to verify failure**

Run: `cd core && ../.venv/bin/pytest tests/notifications/test_mail_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_core.notifications.mail'`.

- [ ] **Step 4: Create `texts.py`**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Subjects and copy of every email, per locale. Placeholders use str.format."""

from __future__ import annotations

_DE_WATCH_NOTE = (
    "Du erhältst diese Mail, weil das Regelwerk auf deiner Watchlist steht. "
    "Benachrichtigungen änderst du in deinem Konto."
)
_EN_WATCH_NOTE = (
    "You receive this email because the standard is on your watchlist. "
    "You can change notifications in your account."
)

COMMON: dict[str, dict[str, str]] = {
    "de": {
        "claim": "KI-gestütztes Wissen zu Normen und Regelwerken, offen für alle",
        "imprint": "Impressum",
        "privacy": "Datenschutz",
        "fallback_link": "Falls der Button nicht funktioniert, öffne diesen Link:",
    },
    "en": {
        "claim": "AI-powered Norms and Standards, Open to Everyone",
        "imprint": "Imprint",
        "privacy": "Privacy Policy",
        "fallback_link": "If the button does not work, open this link:",
    },
}

KINDS: dict[str, dict[str, dict[str, str | None]]] = {
    "de": {
        "verification": {
            "subject": "Bestätige deine E-Mail-Adresse",
            "heading": "Willkommen bei normly",
            "paragraph": "Bitte bestätige deine E-Mail-Adresse, um dein Konto zu aktivieren.",
            "button": "E-Mail bestätigen",
            "note": "Der Link ist {validity} gültig. Du hast dich nicht registriert? "
                    "Dann ignoriere diese Mail.",
        },
        "magic_link": {
            "subject": "Dein Anmeldelink für normly",
            "heading": "Bei normly anmelden",
            "paragraph": "Klicke auf den Button, um dich anzumelden. Falls du noch kein "
                         "Konto hast, wird es dabei angelegt.",
            "button": "Anmelden",
            "note": "Der Link ist {validity} gültig und nur einmal verwendbar. Du hast ihn "
                    "nicht angefordert? Dann ignoriere diese Mail.",
        },
        "password_reset": {
            "subject": "Passwort zurücksetzen",
            "heading": "Passwort zurücksetzen",
            "paragraph": "Du hast angefordert, dein Passwort zurückzusetzen.",
            "button": "Neues Passwort festlegen",
            "note": "Der Link ist {validity} gültig. Du hast das nicht angefordert? "
                    "Dann bleibt dein Passwort unverändert.",
        },
        "email_change": {
            "subject": "Bestätige deine neue E-Mail-Adresse",
            "heading": "Neue E-Mail-Adresse bestätigen",
            "paragraph": "Bestätige, dass du künftig {new_email} für dein normly-Konto "
                         "verwenden möchtest.",
            "button": "Adresse bestätigen",
            "note": "Der Link ist {validity} gültig. Du hast das nicht angefordert? "
                    "Dann ignoriere diese Mail.",
        },
        "watch_new_edition": {
            "subject": "Neue Ausgabe: {designation}",
            "heading": "Neue Ausgabe von {designation}",
            "paragraph": "Für „{title}“ auf deiner Watchlist ist eine neue Ausgabe "
                         "erschienen: {document}.",
            "button": "Regelwerk ansehen",
            "note": _DE_WATCH_NOTE,
        },
        "watch_national_adoption": {
            "subject": "Neue nationale Fassung: {designation}",
            "heading": "Neue nationale Fassung von {designation}",
            "paragraph": "Für „{title}“ auf deiner Watchlist ist eine neue nationale "
                         "Fassung erschienen: {document}.",
            "button": "Regelwerk ansehen",
            "note": _DE_WATCH_NOTE,
        },
        "watch_rights_change": {
            "subject": "Rechteänderung: {designation}",
            "heading": "Rechteänderung bei {designation}",
            "paragraph": "Die Nutzungsrechte für „{title}“ haben sich geändert.",
            "button": "Details ansehen",
            "note": _DE_WATCH_NOTE,
        },
        "watch_no_longer_available": {
            "subject": "Nicht mehr verfügbar: {designation}",
            "heading": "{designation} ist nicht mehr verfügbar",
            "paragraph": "„{title}“ ist in normly nicht mehr verfügbar.",
            "button": "Watchlist öffnen",
            "note": _DE_WATCH_NOTE,
        },
        "deletion_warning": {
            "subject": "Dein normly-Konto wird gelöscht",
            "heading": "Dein Konto wird bald gelöscht",
            "paragraph": "Dein Konto wurde nie bestätigt und lange nicht genutzt. Es wird "
                         "frühestens am {date} gelöscht, wenn du dich bis dahin nicht anmeldest.",
            "button": "Bei normly anmelden",
            "note": None,
        },
    },
    "en": {
        "verification": {
            "subject": "Confirm your email address",
            "heading": "Welcome to normly",
            "paragraph": "Please confirm your email address to activate your account.",
            "button": "Confirm email",
            "note": "The link is valid for {validity}. You did not sign up? "
                    "Then ignore this email.",
        },
        "magic_link": {
            "subject": "Your sign-in link for normly",
            "heading": "Sign in to normly",
            "paragraph": "Click the button to sign in. If you do not have an account yet, "
                         "it will be created.",
            "button": "Sign in",
            "note": "The link is valid for {validity} and can be used once. You did not "
                    "request it? Then ignore this email.",
        },
        "password_reset": {
            "subject": "Reset your password",
            "heading": "Reset your password",
            "paragraph": "You asked to reset your password.",
            "button": "Set a new password",
            "note": "The link is valid for {validity}. You did not request this? "
                    "Then your password stays unchanged.",
        },
        "email_change": {
            "subject": "Confirm your new email address",
            "heading": "Confirm your new email address",
            "paragraph": "Confirm that you want to use {new_email} for your normly account "
                         "from now on.",
            "button": "Confirm address",
            "note": "The link is valid for {validity}. You did not request this? "
                    "Then ignore this email.",
        },
        "watch_new_edition": {
            "subject": "New edition: {designation}",
            "heading": "New edition of {designation}",
            "paragraph": "A new edition of “{title}” on your watchlist has been "
                         "published: {document}.",
            "button": "View standard",
            "note": _EN_WATCH_NOTE,
        },
        "watch_national_adoption": {
            "subject": "New national adoption: {designation}",
            "heading": "New national adoption of {designation}",
            "paragraph": "A new national adoption of “{title}” on your watchlist has been "
                         "published: {document}.",
            "button": "View standard",
            "note": _EN_WATCH_NOTE,
        },
        "watch_rights_change": {
            "subject": "Rights change: {designation}",
            "heading": "Rights change for {designation}",
            "paragraph": "The usage rights for “{title}” have changed.",
            "button": "View details",
            "note": _EN_WATCH_NOTE,
        },
        "watch_no_longer_available": {
            "subject": "No longer available: {designation}",
            "heading": "{designation} is no longer available",
            "paragraph": "“{title}” is no longer available in normly.",
            "button": "Open watchlist",
            "note": _EN_WATCH_NOTE,
        },
        "deletion_warning": {
            "subject": "Your normly account will be deleted",
            "heading": "Your account will be deleted soon",
            "paragraph": "Your account was never confirmed and has not been used for a long "
                         "time. It will be deleted on {date} at the earliest unless you sign "
                         "in before then.",
            "button": "Sign in to normly",
            "note": None,
        },
    },
}
```

- [ ] **Step 5: Create `render.py`**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Renders an email kind into subject, plain text and HTML."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from normly_core.notifications.mail.texts import COMMON, KINDS

DEFAULT_LOCALE = "de"

# shadcn/ui "neutral" theme (light), the values the frontend's tokens resolve
# to. Mail clients ignore CSS variables and <style> blocks inconsistently, so
# the template inlines these.
TOKENS = {
    "muted": "#f5f5f5",
    "card": "#ffffff",
    "foreground": "#0a0a0a",
    "border": "#e5e5e5",
    "primary": "#171717",
    "primary_foreground": "#fafafa",
    "muted_foreground": "#737373",
    "radius": "8px",
}

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    # Only the HTML layout escapes; the text part must carry values verbatim.
    autoescape=lambda name: name is not None and name.endswith(".html.j2"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

_UNITS = {
    "de": {"minute": ("Minute", "Minuten"), "hour": ("Stunde", "Stunden")},
    "en": {"minute": ("minute", "minutes"), "hour": ("hour", "hours")},
}
_EN_MONTHS = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


def _supported(locale: str) -> str:
    return locale if locale in KINDS else DEFAULT_LOCALE


def format_duration(duration: timedelta, locale: str) -> str:
    minutes = int(duration.total_seconds() // 60)
    if minutes % 60 == 0:
        count, unit = minutes // 60, "hour"
    else:
        count, unit = minutes, "minute"
    singular, plural = _UNITS[_supported(locale)][unit]
    return f"{count} {singular if count == 1 else plural}"


def format_date(value: date, locale: str) -> str:
    if _supported(locale) == "en":
        return f"{value.day} {_EN_MONTHS[value.month - 1]} {value.year}"
    return value.strftime("%d.%m.%Y")


def render_email(
    kind: str, locale: str, *, base_url: str | None, action_url: str | None = None,
    **params: str,
) -> RenderedEmail:
    locale = _supported(locale)
    if kind not in KINDS[locale]:
        raise ValueError(f"unknown email kind {kind!r}")
    copy = {
        key: value.format(**params) if value is not None else None
        for key, value in KINDS[locale][kind].items()
    }
    context = {
        **COMMON[locale],
        "lang": locale,
        "tokens": TOKENS,
        "subject": copy["subject"],
        "heading": copy["heading"],
        "paragraph": copy["paragraph"],
        "button": copy["button"] if action_url else None,
        "action_url": action_url,
        "note": copy["note"],
        "base_url": base_url,
        "imprint_url": os.environ.get("NORMLY_IMPRINT_URL") or None,
        "privacy_url": os.environ.get("NORMLY_PRIVACY_URL") or None,
    }
    return RenderedEmail(
        subject=copy["subject"],
        text=_ENV.get_template("base.txt.j2").render(context),
        html=_ENV.get_template("base.html.j2").render(context),
    )
```

- [ ] **Step 6: Create `__init__.py`**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.notifications.mail.render import (
    RenderedEmail,
    format_date,
    format_duration,
    render_email,
)

__all__ = ["RenderedEmail", "format_date", "format_duration", "render_email"]
```

- [ ] **Step 7: Create `templates/base.html.j2`** (the owner's layout, tokens inlined):

```html
{# SPDX-License-Identifier: AGPL-3.0-or-later #}
{# Copyright (C) 2026 normly contributors #}
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html dir="ltr" lang="{{ lang }}">
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type"/>
<meta name="x-apple-disable-message-reformatting"/>
<title>{{ subject }}</title>
</head>
<body style="margin:0;background-color:{{ tokens.muted }};font-family:system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;color:{{ tokens.foreground }}">
<div style="display:none;overflow:hidden;line-height:1px;opacity:0;max-height:0;max-width:0">{{ paragraph }}</div>
<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="max-width:560px;padding:32px 16px">
<tbody><tr><td>
<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="padding-bottom:24px">
<tbody><tr><td>
{% if base_url %}
<a href="{{ base_url }}" style="color:{{ tokens.foreground }};font-size:20px;font-weight:600;text-decoration:none" target="_blank">normly</a>
{% else %}
<span style="color:{{ tokens.foreground }};font-size:20px;font-weight:600">normly</span>
{% endif %}
</td></tr></tbody>
</table>
<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:{{ tokens.card }};border:1px solid {{ tokens.border }};border-radius:{{ tokens.radius }};padding:32px">
<tbody><tr><td>
<p style="margin:0 0 16px;font-size:20px;font-weight:600">{{ heading }}</p>
<p style="margin:0 0 24px;font-size:15px;line-height:24px">{{ paragraph }}</p>
{% if button %}
<a href="{{ action_url }}" style="display:inline-block;background:{{ tokens.primary }};color:{{ tokens.primary_foreground }};padding:10px 20px;border-radius:{{ tokens.radius }};font-size:14px;font-weight:500;text-decoration:none" target="_blank">{{ button }}</a>
<p style="margin:24px 0 0;font-size:13px;line-height:20px;color:{{ tokens.muted_foreground }}">{{ fallback_link }}<br/><a href="{{ action_url }}" style="color:{{ tokens.muted_foreground }};text-decoration:underline;word-break:break-all" target="_blank">{{ action_url }}</a></p>
{% endif %}
{% if note %}
<p style="margin:16px 0 0;font-size:13px;line-height:20px;color:{{ tokens.muted_foreground }}">{{ note }}</p>
{% endif %}
</td></tr></tbody>
</table>
<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="padding-top:24px">
<tbody><tr><td>
<p style="font-size:12px;line-height:18px;margin:0;color:{{ tokens.muted_foreground }}">normly · {{ claim }}
{% if imprint_url or privacy_url %}
<br/>
{% if imprint_url %}<a href="{{ imprint_url }}" style="color:{{ tokens.muted_foreground }};text-decoration:underline" target="_blank">{{ imprint }}</a>{% endif %}
{% if imprint_url and privacy_url %} · {% endif %}
{% if privacy_url %}<a href="{{ privacy_url }}" style="color:{{ tokens.muted_foreground }};text-decoration:underline" target="_blank">{{ privacy }}</a>{% endif %}
{% endif %}
</p>
</td></tr></tbody>
</table>
</td></tr></tbody>
</table>
</body>
</html>
```

- [ ] **Step 8: Create `templates/base.txt.j2`**

```
{# SPDX-License-Identifier: AGPL-3.0-or-later #}
{# Copyright (C) 2026 normly contributors #}
{{ heading }}

{{ paragraph }}
{% if button %}

{{ button }}: {{ action_url }}
{% endif %}
{% if note %}

{{ note }}
{% endif %}

--
normly · {{ claim }}
{% if imprint_url %}
{{ imprint }}: {{ imprint_url }}
{% endif %}
{% if privacy_url %}
{{ privacy }}: {{ privacy_url }}
{% endif %}
```

- [ ] **Step 9: Run to verify pass** — same command as Step 3, expected PASS. Then check the templates ship with the package: `cd core && ../.venv/bin/python -c "import normly_core.notifications.mail.render as r, pathlib; print(sorted(p.name for p in (pathlib.Path(r.__file__).parent/'templates').iterdir()))"` → `['base.html.j2', 'base.txt.j2']`. Also build the wheel and check it lists both templates: `uv build --package normly-core --wheel -o /tmp/claude-wheel && unzip -l /tmp/claude-wheel/normly_core-*.whl | grep templates/` (expected: two lines). If missing, add to `core/pyproject.toml` under `[tool.hatch.build.targets.wheel]`: `artifacts = ["src/normly_core/notifications/mail/templates/*.j2"]` and re-check.

- [ ] **Step 10: Commit**

```bash
git add core/pyproject.toml uv.lock core/src/normly_core/notifications/mail core/tests/notifications/test_mail_render.py
git commit -s -m "feat(core): render branded mails from a Jinja2 base layout

Refs #45

Assisted-by: Claude Code"
```

---

### Task 3: `account.locale` in schema, domain and repository

**Files:**
- Create: `core/migrations/versions/0039_account_locale.py`
- Modify: `core/src/normly_core/graph/domain.py` (`Account`, `AccountRepository`), `core/src/normly_core/graph/postgres/orm.py` (`AccountORM`), `core/src/normly_core/graph/postgres/repositories.py` (`_account_to_domain`, `PostgresAccountRepository`)
- Modify: `core/src/normly_core/notifications/abandoned_registration.py` (only the tuple unpacking, see Step 6)
- Test: `core/tests/graph/test_account_repository.py`, `core/tests/graph/test_account_locale_migration.py` (new)

**Interfaces:**
- Produces: `Account.locale: str` (last field); `AccountRepository.create_account(*, email: str, password_hash: str | None, locale: str = "de") -> Account`; `AccountRepository.update_locale(account_id: uuid.UUID, *, locale: str) -> None`; `abandoned_registrations_to_warn(cutoff) -> list[tuple[uuid.UUID, str, str]]` = `(id, email, locale)`.

- [ ] **Step 1: Write failing repository tests** — append to `core/tests/graph/test_account_repository.py` (it already imports `PostgresAccountRepository`; add `import pytest`, `import sqlalchemy as sa` and `from sqlalchemy.exc import IntegrityError` if absent):

```python
def test_create_account_defaults_to_german(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="locale-default@example.de", password_hash=None
    )
    assert account.locale == "de"


def test_create_account_stores_the_given_locale(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="locale-en@example.de", password_hash=None, locale="en")
    assert repo.get_account_by_id(account.id).locale == "en"


def test_update_locale(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="locale-update@example.de", password_hash=None)
    repo.update_locale(account.id, locale="en")
    db_session.expire_all()
    assert repo.get_account_by_id(account.id).locale == "en"


def test_the_database_rejects_an_unsupported_locale(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="locale-bad@example.de", password_hash=None)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repo.update_locale(account.id, locale="fr")
            db_session.flush()
```

- [ ] **Step 2: Write the failing migration test** — `core/tests/graph/test_account_locale_migration.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

CORE_DIR = Path(__file__).parents[2]


def _has_locale(connection) -> bool:
    return connection.execute(
        sa.text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'account' AND column_name = 'locale'"
        )
    ).scalar_one() == 1


def test_0039_round_trip_gives_existing_accounts_german(db_url, migrated_engine):
    # Same approach as test_no_longer_available_migration.py: drives Alembic
    # against the shared database and leaves it at "head" again.
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    account = uuid.uuid4()
    try:
        command.downgrade(alembic_cfg, "0038")
        with migrated_engine.begin() as connection:
            assert not _has_locale(connection)
            connection.execute(
                sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0039@example.de')"),
                {"a": account},
            )

        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            assert _has_locale(connection)
            assert connection.execute(
                sa.text("SELECT locale FROM account WHERE id = :a"), {"a": account}
            ).scalar_one() == "de"
    finally:
        command.upgrade(alembic_cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})
```

- [ ] **Step 3: Run to verify failure**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_account_repository.py tests/graph/test_account_locale_migration.py -v`
Expected: FAIL — repository tests with `create_account() got an unexpected keyword argument 'locale'`; the migration test at `assert _has_locale(connection)` after the upgrade (no revision 0039 yet).

- [ ] **Step 4: Migration** — `core/migrations/versions/0039_account_locale.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add account.locale

The language an account's emails are written in. Job-triggered mails
(Normtracker, deletion warning) have no request to take a language from, so
it is stored. Existing accounts get German, the only language mails had.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account", sa.Column("locale", sa.String(2), nullable=False, server_default="de")
    )
    op.create_check_constraint("ck_account_locale", "account", "locale IN ('de', 'en')")


def downgrade() -> None:
    op.drop_constraint("ck_account_locale", "account", type_="check")
    op.drop_column("account", "locale")
```

- [ ] **Step 5: ORM, domain, repository**

`orm.py`, `AccountORM` — after `notification_preference`:

```python
    # Language of the account's emails; 'de' or 'en' (ck_account_locale).
    locale: Mapped[str] = mapped_column(
        sa.String(2), nullable=False, default="de", server_default="de"
    )

    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_account_email"),
        sa.CheckConstraint("locale IN ('de', 'en')", name="ck_account_locale"),
    )
```

`domain.py`, `Account` — add as last field `locale: str`. `AccountRepository` protocol:

```python
    def create_account(
        self, *, email: str, password_hash: str | None, locale: str = "de"
    ) -> Account: ...
```

and after `update_notification_preference`:

```python
    def update_locale(self, account_id: uuid.UUID, *, locale: str) -> None: ...
```

and change `abandoned_registrations_to_warn`:

```python
    def abandoned_registrations_to_warn(
        self, cutoff: datetime
    ) -> list[tuple[uuid.UUID, str, str]]:
        """(account id, email, locale) of abandoned registrations not yet warned."""
        ...
```

`repositories.py` — `_account_to_domain` passes `locale=orm.locale`. `create_account`:

```python
    def create_account(
        self, *, email: str, password_hash: str | None, locale: str = "de"
    ) -> Account:
        orm = AccountORM(id=uuid.uuid4(), email=email, password_hash=password_hash, locale=locale)
```

After `update_notification_preference`:

```python
    def update_locale(self, account_id: uuid.UUID, *, locale: str) -> None:
        self._session.execute(
            sa.update(AccountORM).where(AccountORM.id == account_id).values(locale=locale)
        )
```

`abandoned_registrations_to_warn`:

```python
    def abandoned_registrations_to_warn(
        self, cutoff: datetime
    ) -> list[tuple[uuid.UUID, str, str]]:
        ids = self._abandoned_registration_ids(cutoff, unwarned=True)
        if not ids:
            return []
        rows = self._session.execute(
            select(AccountORM.id, AccountORM.email, AccountORM.locale)
            .where(AccountORM.id.in_(ids))
            .order_by(AccountORM.created_at)
        ).all()
        return [(row.id, row.email, row.locale) for row in rows]
```

- [ ] **Step 6: Keep the warning job working** — in `abandoned_registration.py` change only the loop header to `for account_id, email, _locale in repo.abandoned_registrations_to_warn(cutoff):` (Task 5 uses the locale).

- [ ] **Step 7: Run to verify pass**

Run: `cd core && ../.venv/bin/pytest tests/graph tests/retention -v`
Expected: PASS (including `test_migration_determinism.py`).

- [ ] **Step 8: Commit**

```bash
git add core/migrations/versions/0039_account_locale.py core/src/normly_core/graph core/src/normly_core/notifications/abandoned_registration.py core/tests/graph
git commit -s -m "feat(core): store the language of an account's emails

Refs #45

Assisted-by: Claude Code"
```

---

### Task 4: Accounts service renders mails in the request's language

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py`, `routers/registration.py`, `routers/email_verification.py`, `routers/password_reset.py`, `routers/magic_link.py`, `routers/email_change.py`, `routers/google.py`, `routers/profile.py`, `routers/login.py`
- Test: `accounts/tests/test_registration.py`, `test_email_verification.py`, `test_password_reset.py`, `test_magic_link.py`, `test_email_change.py`, `test_google_login.py`, `test_profile.py`

**Interfaces:**
- Consumes: `render_email`, `format_duration` (Task 2); `EmailSender.send(..., html=)` (Task 1); `create_account(..., locale=)`, `update_locale`, `Account.locale` (Task 3).
- Produces: request field `locale: Literal["de", "en"] = "de"` on `RegisterRequest`, `PasswordResetRequestRequest`, `VerifyEmailResendRequest`, `EmailChangeRequest`, `MagicLinkRequestRequest`, `MagicLinkConfirmRequest`; `UpdateProfileRequest.locale: Literal["de", "en"] | None = None`; query parameter `locale` (same Literal, default `de`) on `GET /v1/accounts/google/callback`; `AccountResponse.locale: str`.

- [ ] **Step 1: Write failing tests.** Add to `accounts/tests/test_registration.py` (add `from normly_core.graph.postgres.repositories import PostgresAccountRepository`):

```python
def test_register_mails_in_german_by_default_with_html(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "de-default@example.de", "password": "correct horse battery staple"},
    )
    mail = email_sender.sent[0]
    assert mail["subject"] == "Bestätige deine E-Mail-Adresse"
    assert "48 Stunden" in mail["body"]
    assert mail["html"] is not None and 'lang="de"' in mail["html"]


def test_register_stores_the_locale_and_mails_in_it(client, email_sender, db_session):
    response = client.post(
        "/v1/accounts/register",
        json={"email": "en-user@example.de", "password": "correct horse battery staple",
              "locale": "en"},
    )
    assert response.json()["account"]["locale"] == "en"
    assert email_sender.sent[0]["subject"] == "Confirm your email address"
    account = PostgresAccountRepository(db_session).get_account_by_email("en-user@example.de")
    assert account.locale == "en"


def test_register_rejects_an_unsupported_locale(client):
    response = client.post(
        "/v1/accounts/register",
        json={"email": "fr@example.de", "password": "correct horse battery staple",
              "locale": "fr"},
    )
    assert response.status_code == 422
```

In the same file replace the `body.startswith("Bitte bestätige deine E-Mail-Adresse: http://localhost:3000/verify-email?token=")` assertion with `assert "http://localhost:3000/verify-email?token=" in body`, and change `_RaisingEmailSender.send` to `def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:`. Make the same `_RaisingEmailSender` signature change in `test_magic_link.py` and `test_password_reset.py`.

`test_magic_link.py` — replace the `body.startswith("Zum Anmelden: …")` assertion with `assert "http://localhost:3000/magic-link?token=" in body`; add (import `re` and `PostgresAccountRepository` if absent):

```python
def test_magic_link_mails_in_the_request_language(client, email_sender):
    client.post(
        "/v1/accounts/magic-link/request", json={"email": "ml-en@example.de", "locale": "en"}
    )
    assert email_sender.sent[0]["subject"] == "Your sign-in link for normly"
    assert "15 minutes" in email_sender.sent[0]["body"]


def test_magic_link_confirm_creates_the_account_with_the_request_language(
    client, email_sender, db_session
):
    client.post("/v1/accounts/magic-link/request", json={"email": "ml-new@example.de"})
    token = re.search(r"token=([^&\s]+)", email_sender.sent[0]["body"]).group(1)

    response = client.post(
        "/v1/accounts/magic-link/confirm", json={"token": token, "locale": "en"}
    )

    assert response.status_code == 200
    account = PostgresAccountRepository(db_session).get_account_by_email("ml-new@example.de")
    assert account.locale == "en"
```

`test_password_reset.py` — replace the `body.startswith(…)` assertion with `assert "http://localhost:3000/reset-password?token=" in body`; add:

```python
def test_password_reset_mails_in_the_request_language(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "reset-en@example.de", "password": "correct horse battery staple"},
    )
    email_sender.sent.clear()

    client.post(
        "/v1/accounts/password-reset/request",
        json={"email": "reset-en@example.de", "locale": "en"},
    )

    assert email_sender.sent[0]["subject"] == "Reset your password"
    assert "1 hour" in email_sender.sent[0]["body"]
```

`test_email_change.py` — replace the `body.startswith(…)` assertion with `assert "http://localhost:3000/confirm-email-change?token=" in body`; add:

```python
def test_email_change_mails_in_the_request_language(client, email_sender):
    headers = _register_and_authorize(client)

    client.post(
        "/v1/accounts/email/change",
        json={"new_email": "changed-en@example.de", "locale": "en"}, headers=headers,
    )

    mail = email_sender.sent[-1]
    assert mail["subject"] == "Confirm your new email address"
    assert "changed-en@example.de" in mail["body"]
```

`test_email_verification.py` — add (follow the file's existing register-then-clear pattern):

```python
def test_resend_mails_in_the_request_language(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "resend-en@example.de", "password": "correct horse battery staple"},
    )
    email_sender.sent.clear()

    client.post(
        "/v1/accounts/verify-email/resend", json={"email": "resend-en@example.de", "locale": "en"}
    )

    assert email_sender.sent[0]["subject"] == "Confirm your email address"
```

`test_google_login.py` — add (import `PostgresAccountRepository`):

```python
def test_google_callback_stores_the_locale_on_a_new_account(client, db_session):
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-locale", email="google-en@example.de", email_verified=True
        )
    )
    _seed_state(db_session, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback",
        params={"code": "fake-code", "state": "fake-state", "locale": "en"},
    )

    assert response.status_code == 200
    account = PostgresAccountRepository(db_session).get_account_by_email("google-en@example.de")
    assert account.locale == "en"
```

`test_profile.py` — add:

```python
def test_update_profile_sets_the_locale(client):
    _, headers = _register_and_authorize(client)

    response = client.patch("/v1/accounts/profile", json={"locale": "en"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["locale"] == "en"


def test_update_profile_rejects_an_unsupported_locale(client):
    _, headers = _register_and_authorize(client)
    response = client.patch("/v1/accounts/profile", json={"locale": "fr"}, headers=headers)
    assert response.status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: the new tests FAIL (`locale` key missing, subjects German, 200 instead of 422).

- [ ] **Step 3: Schemas** — in `schemas.py` change the import to `from typing import Literal` + existing, add `Locale = Literal["de", "en"]` below the imports, and add `locale: Locale = "de"` as last field of `RegisterRequest`, `PasswordResetRequestRequest`, `VerifyEmailResendRequest`, `EmailChangeRequest`, `MagicLinkRequestRequest`, `MagicLinkConfirmRequest`. `UpdateProfileRequest` gets `locale: Locale | None = None`; `AccountResponse` gets `locale: str` (last field). In `login.py` (`_create_session_response`) and `profile.py` (`_account_response`) add `locale=account.locale` to the `AccountResponse(...)` call.

- [ ] **Step 4: Routers.** Each router adds `from normly_core.notifications.mail import format_duration, render_email` and renders before the `try`. Registration (`registration.py`):

```python
    account = account_repo.create_account(
        email=payload.email, password_hash=hash_password(payload.password),
        locale=payload.locale,
    )
    ...
    mail = render_email(
        "verification", payload.locale, base_url=_public_base_url(),
        action_url=f"{_public_base_url()}/verify-email?token={token.token}",
        validity=format_duration(_VERIFICATION_TOKEN_LIFETIME, payload.locale),
    )
    try:
        email_sender.send(
            to=account.email, subject=mail.subject, body=mail.text, html=mail.html,
        )
    except Exception:
        # (existing comment and logger call unchanged)
```

`email_verification.py` (resend) — identical `render_email("verification", payload.locale, …)` call and `send(...)` replacing the hand-built subject/body.

`password_reset.py` (request):

```python
        mail = render_email(
            "password_reset", payload.locale, base_url=_public_base_url(),
            action_url=f"{_public_base_url()}/reset-password?token={token.token}",
            validity=format_duration(_RESET_TOKEN_LIFETIME, payload.locale),
        )
        try:
            email_sender.send(
                to=account.email, subject=mail.subject, body=mail.text, html=mail.html,
            )
```

`magic_link.py` — request:

```python
    mail = render_email(
        "magic_link", payload.locale, base_url=_public_base_url(),
        action_url=f"{_public_base_url()}/magic-link?token={token.token}",
        validity=format_duration(_MAGIC_LINK_TOKEN_LIFETIME, payload.locale),
    )
    try:
        email_sender.send(
            to=payload.email, subject=mail.subject, body=mail.text, html=mail.html,
        )
```

confirm — `account_repo.create_account(email=consumed.email, password_hash=None, locale=payload.locale)`.

`email_change.py` — move `confirm_url` out of the `try`:

```python
    confirm_url = (
        f"{_public_base_url()}/confirm-email-change"
        f"?token={quote(token.token)}&email={quote(payload.new_email)}"
    )
    mail = render_email(
        "email_change", payload.locale, base_url=_public_base_url(), action_url=confirm_url,
        new_email=payload.new_email,
        validity=format_duration(_EMAIL_CHANGE_TOKEN_LIFETIME, payload.locale),
    )
    try:
        email_sender.send(
            to=payload.new_email, subject=mail.subject, body=mail.text, html=mail.html,
        )
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
```

`google.py` — add `from typing import Literal`, a callback parameter `locale: Literal["de", "en"] = "de",` after `error`, and `account_repo.create_account(email=profile.email, password_hash=None, locale=locale)`. Existing accounts keep their stored locale.

`profile.py` `update_profile` — before `session.commit()`:

```python
    if payload.locale is not None:
        account_repo.update_locale(account.id, locale=payload.locale)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: PASS, whole suite (including `test_openapi_and_end_to_end.py` and `test_account_lifecycle_e2e.py`, which extract tokens with `token=([^&\s]+)` from the text body).

- [ ] **Step 6: Commit**

```bash
git add accounts
git commit -s -m "feat(accounts): send branded mails in the requester's language

Refs #45

Assisted-by: Claude Code"
```

---

### Task 5: Normtracker and deletion-warning mails

**Files:**
- Modify: `core/src/normly_core/notifications/detection.py`, `core/src/normly_core/notifications/abandoned_registration.py`
- Test: `core/tests/notifications/test_detection.py`, `core/tests/notifications/test_no_longer_available.py`, `core/tests/retention/test_abandoned_warning.py`

**Interfaces:**
- Consumes: `render_email`, `format_date`, `RenderedEmail` (Task 2); `Account.locale`, `abandoned_registrations_to_warn` triple (Task 3); `PostgresDocumentRepository.get_document_unchecked`, `.list_designations`, `.list_titles` (existing).
- Produces: `build_warning_email(*, delete_on: date, base_url: str | None, locale: str) -> RenderedEmail` replaces `build_warning_body`; `SUBJECT` constant removed.

- [ ] **Step 1: Write failing tests.** `test_detection.py` — extend `test_email_preference_sends_mail_and_sets_emailed_at` and add a sibling (the file's helpers `_make_source`, `_make_delivery`, `_set_created_at`, `_BEFORE` exist):

```python
def test_new_edition_mail_names_the_standard_and_links_the_new_edition(db_session, monkeypatch):
    monkeypatch.setenv("NORMLY_PUBLIC_BASE_URL", "https://app.example.org")
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "email-content")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="7", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="7", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    doc_repo.add_designation(
        document_id=old.id, issuer="DGUV", designation="DGUV Vorschrift 7", language="de",
        edition="2020", is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=new.id, issuer="DGUV", designation="DGUV Vorschrift 7 (2026)",
        language="de", edition="2026", is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_title(
        document_id=old.id, language="de", title="Grundsätze der Prävention",
        delivery_id=delivery.id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account_repo = PostgresAccountRepository(db_session)
    account = account_repo.create_account(email="content-watcher@example.de", password_hash=None)
    account_repo.update_notification_preference(account.id, preference=NotificationPreference.EMAIL)
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    run_notify_watchers(db_session, sender)

    mail = sender.sent[0]
    assert mail["subject"] == "Neue Ausgabe: DGUV Vorschrift 7"
    assert "Grundsätze der Prävention" in mail["body"]
    assert "DGUV Vorschrift 7 (2026)" in mail["body"]
    assert f"https://app.example.org/documents/{new.id}" in mail["body"]
    assert mail["html"] is not None


def test_watch_mail_uses_the_account_locale_and_falls_back_to_origin_fields(
    db_session, monkeypatch
):
    monkeypatch.delenv("NORMLY_PUBLIC_BASE_URL", raising=False)
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "email-en")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="8", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="8", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account_repo = PostgresAccountRepository(db_session)
    account = account_repo.create_account(
        email="en-watcher@example.de", password_hash=None, locale="en"
    )
    account_repo.update_notification_preference(account.id, preference=NotificationPreference.EMAIL)
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    run_notify_watchers(db_session, sender)

    mail = sender.sent[0]
    assert mail["subject"] == "New edition: DGUV 8:2020"
    assert "DGUV 8:2026" in mail["body"]
    assert "http" not in mail["body"]
```

`test_no_longer_available.py` — in `test_email_preference_sends_mail_with_the_new_subject` replace the subject assertion with `assert sender.sent[0]["subject"].startswith("Nicht mehr verfügbar: ")`.

`test_abandoned_warning.py` — rename `test_abandoned_unwarned_account_gets_a_bilingual_warning` to `test_abandoned_unwarned_account_gets_a_warning_in_its_language` and replace its subject/body assertions:

```python
    assert mail["subject"] == "Dein normly-Konto wird gelöscht"
    delete_on = (NOW + NOTICE).date().strftime("%d.%m.%Y")
    assert delete_on in mail["body"]
    assert "https://app.example.org" in mail["body"]
    assert mail["html"] is not None
```

and add:

```python
def test_warning_uses_the_account_locale(db_session, monkeypatch):
    monkeypatch.setenv("NORMLY_PUBLIC_BASE_URL", "https://app.example.org")
    account = _account(db_session, "warn-en@example.de")
    PostgresAccountRepository(db_session).update_locale(account.id, locale="en")
    sender = RecordingEmailSender()

    _cleanup_user_data(db_session, NOW, sender)

    assert sender.sent[0]["subject"] == "Your normly account will be deleted"
```

Change `FailingEmailSender.send` to `def send(self, *, to, subject, body, html=None):`.

- [ ] **Step 2: Run to verify failure**

Run: `cd core && ../.venv/bin/pytest tests/notifications tests/retention -v`
Expected: the new/changed tests FAIL (old subjects, no link, bilingual body).

- [ ] **Step 3: `detection.py`.** Imports: add `import os`, `import uuid`, `from normly_core.notifications.mail import RenderedEmail, render_email`. Remove `_EMAIL_SUBJECTS`. Add below `NotifyWatchersSummary`:

```python
@dataclass(frozen=True)
class _MailFacts:
    """What the mail is about: the watched document and the one to link to."""

    watched_document_id: uuid.UUID
    linked_document_id: uuid.UUID | None
    jurisdiction: str | None


def _describe(
    document_repo: PostgresDocumentRepository, document_id: uuid.UUID, locale: str
) -> tuple[str, str]:
    """(designation, title); falls back to the origin fields and the designation."""
    designations = document_repo.list_designations(document_id)
    primary = next((d for d in designations if d.is_primary), None) or (
        designations[0] if designations else None
    )
    if primary is not None:
        designation = primary.designation
    else:
        document = document_repo.get_document_unchecked(document_id)
        designation = f"{document.origin_issuer} {document.origin_number}:{document.edition}"
    titles = document_repo.list_titles(document_id)
    title = next((t.title for t in titles if t.language == locale), None) or (
        titles[0].title if titles else designation
    )
    return designation, title


def _render_watch_email(
    document_repo: PostgresDocumentRepository, account: Account,
    trigger_type: NotificationTriggerType, facts: _MailFacts,
) -> RenderedEmail:
    base_url = os.environ.get("NORMLY_PUBLIC_BASE_URL") or None
    designation, title = _describe(document_repo, facts.watched_document_id, account.locale)
    document = designation
    if facts.linked_document_id is not None:
        document = _describe(document_repo, facts.linked_document_id, account.locale)[0]
    if facts.jurisdiction:
        document = f"{document} ({facts.jurisdiction})"
    action_url = None
    if base_url is not None:
        action_url = (
            f"{base_url}/documents/{facts.linked_document_id}"
            if facts.linked_document_id is not None else f"{base_url}/"
        )
    return render_email(
        f"watch_{trigger_type.value}", account.locale, base_url=base_url,
        action_url=action_url, designation=designation, title=title, document=document,
    )
```

`_create_and_maybe_email` gains two keyword parameters `document_repo: PostgresDocumentRepository` and `facts: _MailFacts`, and its email branch becomes:

```python
        mail = _render_watch_email(document_repo, account, trigger_type, facts)
        try:
            email_sender.send(
                to=account.email, subject=mail.subject, body=mail.text, html=mail.html,
            )
            emailed_at = datetime.now(timezone.utc)
        except Exception:
            # Fail-soft, best-effort, no retry -- see Global Constraints.
            logger.exception("notify-watchers email delivery failed for %s", account.email)
```

The three call sites in `run_notify_watchers` pass `document_repo=document_repo` and:
- edge loop: `facts=_MailFacts(edge.to_document_id, edge.from_document_id, edge.jurisdiction)`
- retirement loop: `facts=_MailFacts(document.id, None, None)`
- rights loop: `facts=_MailFacts(document_id, document_id, None)`

- [ ] **Step 4: `abandoned_registration.py`** — replace `SUBJECT` and `build_warning_body` with:

```python
def build_warning_email(*, delete_on: date, base_url: str | None, locale: str) -> RenderedEmail:
    return render_email(
        "deletion_warning", locale, base_url=base_url, action_url=base_url,
        date=format_date(delete_on, locale),
    )
```

(imports: `from datetime import date, datetime`, `from normly_core.notifications.mail import RenderedEmail, format_date, render_email`). In `warn_abandoned_registrations`, replace the `delete_on`/`body` lines and the loop:

```python
    delete_on = (now + retention.ACCOUNT_DELETION_NOTICE_PERIOD).date()
    repo = PostgresAccountRepository(session)
    sent = 0
    for account_id, email, locale in repo.abandoned_registrations_to_warn(cutoff):
        mail = build_warning_email(delete_on=delete_on, base_url=base_url, locale=locale)
        try:
            sender.send(to=email, subject=mail.subject, body=mail.text, html=mail.html)
```

(rest of the loop unchanged). Grep for other users first: `grep -rn "build_warning_body\|abandoned_registration import SUBJECT" core accounts` — update any hit the same way.

- [ ] **Step 5: Run to verify pass**

Run: `cd core && ../.venv/bin/pytest tests/notifications tests/retention tests/pipeline/test_email.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/notifications core/tests/notifications core/tests/retention
git commit -s -m "feat(core): name the standard and link it in Normtracker mails

Refs #45

Assisted-by: Claude Code"
```

---

### Task 6: Frontend passes the visitor's language and stores it on switch

**Files:**
- Create: `frontend/src/lib/i18n/resolve-locale.ts`, `frontend/src/app/api/account/locale/route.ts`
- Modify: `frontend/src/app/layout.tsx`, `frontend/src/lib/i18n/provider.tsx`, BFF routes `api/auth/register`, `api/auth/magic-link/request`, `api/auth/magic-link/confirm`, `api/auth/password-reset/request`, `api/auth/verify-email/resend`, `api/account/email` (`route.ts` each), `api/auth/google/callback/route.ts`
- Test: `frontend/tests/unit/resolve-locale.test.ts` (new), `frontend/tests/unit/account-locale-route.test.ts` (new), `frontend/tests/unit/auth-routes.test.ts`, `frontend/tests/unit/i18n.test.tsx`

**Interfaces:**
- Consumes: accounts request field `locale` and `PATCH /v1/accounts/profile {locale}` (Task 4); google callback query `locale`.
- Produces: `resolveLocale(cookieValue: string | undefined, acceptLanguage: string | null): Locale`, `localeFromRequest(request: NextRequest): Locale`, `LOCALE_COOKIE = "normly_locale"`; route `PUT /api/account/locale` → `204` (no session: no backend call) or the backend status on failure.

- [ ] **Step 1: Write failing tests.** `frontend/tests/unit/resolve-locale.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { localeFromRequest, resolveLocale } from "@/lib/i18n/resolve-locale";

describe("resolveLocale", () => {
  it("prefers a valid cookie", () => {
    expect(resolveLocale("en", "de-DE")).toBe("en");
  });

  it("falls back to Accept-Language", () => {
    expect(resolveLocale(undefined, "en-GB,en;q=0.9")).toBe("en");
    expect(resolveLocale("fr", "de-DE")).toBe("de");
  });

  it("defaults to German", () => {
    expect(resolveLocale(undefined, null)).toBe("de");
  });

  it("reads cookie and header from a request", () => {
    const request = new NextRequest("http://localhost/x", {
      headers: { cookie: "normly_locale=en", "accept-language": "de-DE" },
    });
    expect(localeFromRequest(request)).toBe("en");
  });
});
```

`frontend/tests/unit/account-locale-route.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { PUT } from "@/app/api/account/locale/route";

const originalFetch = global.fetch;

function request(cookie?: string) {
  return new NextRequest("http://localhost/api/account/locale", {
    method: "PUT",
    body: JSON.stringify({ locale: "en" }),
    headers: { "content-type": "application/json", ...(cookie ? { cookie } : {}) },
  });
}

describe("PUT /api/account/locale", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("answers 204 without calling the backend when nobody is signed in", async () => {
    global.fetch = vi.fn();
    const response = await PUT(request());
    expect(response.status).toBe(204);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("stores the locale on the signed-in account", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));

    const response = await PUT(request("normly_account_session=acct-tok"));

    expect(response.status).toBe(204);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://accounts.internal/v1/accounts/profile",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ locale: "en" }),
        headers: expect.objectContaining({ Authorization: "Bearer acct-tok" }),
      }),
    );
  });
});
```

`auth-routes.test.ts` — at the end of "magic-link request forwards the payload without needing a cookie" add:

```ts
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ email: "a@example.de", locale: "de" });
```

and add a test that sends `headers: { "content-type": "application/json", cookie: "normly_locale=en" }` to the same route and expects `locale: "en"` in the forwarded body.

`i18n.test.tsx` — add (import `act` from `@testing-library/react`, `vi`, `afterEach` from vitest):

```tsx
function Switch() {
  const { setLocale } = useTranslation();
  return <button onClick={() => setLocale("en")}>switch</button>;
}

it("stores the new locale on the account when switching", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  render(
    <LocaleProvider initialLocale="de">
      <Switch />
    </LocaleProvider>,
  );

  await act(async () => screen.getByText("switch").click());

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/account/locale",
    expect.objectContaining({ method: "PUT", body: JSON.stringify({ locale: "en" }) }),
  );
  vi.unstubAllGlobals();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run tests/unit/resolve-locale.test.ts tests/unit/account-locale-route.test.ts tests/unit/auth-routes.test.ts tests/unit/i18n.test.tsx`
Expected: FAIL — modules not found / `locale` missing / fetch not called.

- [ ] **Step 3: `resolve-locale.ts`**

```ts
// frontend/src/lib/i18n/resolve-locale.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextRequest } from "next/server";
import type { Locale } from "@/lib/i18n/provider";

export const LOCALE_COOKIE = "normly_locale";

// One rule for the page and for every BFF route that triggers a mail: the
// language the visitor sees is the language their mail is written in.
export function resolveLocale(cookieValue: string | undefined, acceptLanguage: string | null): Locale {
  if (cookieValue === "de" || cookieValue === "en") {
    return cookieValue;
  }
  return (acceptLanguage ?? "").toLowerCase().startsWith("en") ? "en" : "de";
}

export function localeFromRequest(request: NextRequest): Locale {
  return resolveLocale(
    request.cookies.get(LOCALE_COOKIE)?.value,
    request.headers.get("accept-language"),
  );
}
```

- [ ] **Step 4: `layout.tsx`** — import `{ LOCALE_COOKIE, resolveLocale } from "@/lib/i18n/resolve-locale"` and replace the body of `resolveInitialLocale`:

```ts
async function resolveInitialLocale(): Promise<Locale> {
  return resolveLocale(
    (await cookies()).get(LOCALE_COOKIE)?.value,
    (await headers()).get("accept-language"),
  );
}
```

- [ ] **Step 5: BFF routes.** In `register`, `magic-link/request`, `magic-link/confirm`, `password-reset/request`, `verify-email/resend` and `account/email`, import `{ localeFromRequest } from "@/lib/i18n/resolve-locale"` and change the forwarded body to:

```ts
      body: JSON.stringify({ ...payload, locale: localeFromRequest(request) }),
```

In `google/callback/route.ts`, after the `error` line:

```ts
  forwardedParams.set("locale", localeFromRequest(request));
```

- [ ] **Step 6: `api/account/locale/route.ts`**

```ts
// frontend/src/app/api/account/locale/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

// The language switch calls this for every visitor: the session cookie is
// httpOnly, so only this route can tell whether there is an account whose
// stored mail language should follow the switch.
export async function PUT(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return new NextResponse(null, { status: 204 });
  }

  const { locale } = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/profile`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify({ locale }),
  });
  return new NextResponse(null, { status: backendResponse.ok ? 204 : backendResponse.status });
}
```

- [ ] **Step 7: `provider.tsx`** — in `setLocale`, after the cookie line:

```ts
    // Mails are written in the account's stored language; the route ignores
    // anonymous visitors. Fire-and-forget: the cookie already switched the UI.
    fetch("/api/account/locale", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ locale: next }),
    }).catch(() => {});
```

- [ ] **Step 8: Run the whole frontend suite**

Run: `cd frontend && npm test`
Expected: PASS. Route tests that compare the forwarded body exactly (e.g. `password-reset-route.test.ts`, `verify-email-routes.test.ts`, `account-email-route.test.ts`, `signup`/`login` page tests) may now see an extra `locale: "de"` — update those expectations to include it; do not loosen them to `objectContaining`. Then `npx tsc --noEmit` and `npm run lint` — expected clean.

- [ ] **Step 9: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): pass the visitor's language to mail-sending calls

Refs #45

Assisted-by: Claude Code"
```

---

### Task 7: Configuration and operator documentation

**Files:**
- Modify: `.env.example`, `docs/guide/self-hosting.md`, `docs/guide/operations.md`

- [ ] **Step 1: `.env.example`** — after the commented real-relay block (after `# NORMLY_MAILPIT_BIND=127.0.0.1`), add:

```
# Footer links in e-mails; each is left out when unset. Imprint and privacy
# policy belong to whoever operates the instance.
# NORMLY_IMPRINT_URL=https://example.org/imprint
# NORMLY_PRIVACY_URL=https://example.org/privacy
```

- [ ] **Step 2: `docs/guide/self-hosting.md`** — replace the Mail bullet with:

```markdown
- Mail: a real SMTP relay (`NORMLY_SMTP_*`; STARTTLS is used as soon as a
  username is set). Mails link to `NORMLY_PUBLIC_BASE_URL`; set
  `NORMLY_IMPRINT_URL` and `NORMLY_PRIVACY_URL` to your own imprint and
  privacy policy, otherwise the mail footer carries no such links.
```

- [ ] **Step 3: `docs/guide/operations.md`** — in the abandoned-registrations paragraph replace `(German and English, deletion date,` with `(in the account's language, deletion date,`.

- [ ] **Step 4: Build the docs** — `zensical build` per the CI docs job (`.github/workflows/ci.yml`, line ~76–80) if available locally; otherwise skip and say so.

- [ ] **Step 5: Commit**

```bash
git add .env.example docs/guide/self-hosting.md docs/guide/operations.md
git commit -s -m "docs: document mail footer links and per-account mail language

Refs #45

Assisted-by: Claude Code"
```

---

### Task 8: Whole-branch verification

- [ ] **Step 1:** Run every suite the CI runs: `cd accounts && ../.venv/bin/pytest`, `cd core && ../.venv/bin/pytest`, `cd api && ../.venv/bin/pytest`, `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py`, `cd frontend && npm test`. Expected: all green (api/chat only to catch an `Account`/`EmailSender` user outside accounts/core).
- [ ] **Step 2: Visual check** — render one mail per kind to HTML files in the scratchpad and open them in the browser (or send through the bundled Mailpit with `docker compose --profile bundled up`), in `de` and `en`; compare against the owner's layout. Report what was looked at.
- [ ] **Step 3: Production follow-up for the owner** (not code): set `NORMLY_IMPRINT_URL=https://normly.ai/imprint` and `NORMLY_PRIVACY_URL=https://normly.ai/privacy` in the server `.env` at deploy time.
