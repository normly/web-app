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


def _block(kind: str, locale: str, action_url: str | None, params: dict[str, str]) -> dict:
    """One language's copy of a mail: what the layout shows between header and footer."""
    if kind not in KINDS[locale]:
        raise ValueError(f"unknown email kind {kind!r}")
    copy = {
        key: value.format(**params) if value is not None else None
        for key, value in KINDS[locale][kind].items()
    }
    return {
        "subject": copy["subject"],
        "heading": copy["heading"],
        "paragraph": copy["paragraph"],
        "button": copy["button"] if action_url else None,
        "action_url": action_url,
        "note": copy["note"],
        "fallback_link": COMMON[locale]["fallback_link"],
    }


def _render(
    blocks: list[dict], subject: str, locale: str, base_url: str | None
) -> RenderedEmail:
    context = {
        **COMMON[locale],
        "lang": locale,
        "tokens": TOKENS,
        "subject": subject,
        "blocks": blocks,
        "base_url": base_url,
        "imprint_url": os.environ.get("NORMLY_IMPRINT_URL") or None,
        "privacy_url": os.environ.get("NORMLY_PRIVACY_URL") or None,
    }
    return RenderedEmail(
        subject=subject,
        text=_ENV.get_template("base.txt.j2").render(context),
        html=_ENV.get_template("base.html.j2").render(context),
    )


def render_email(
    kind: str, locale: str, *, base_url: str | None, action_url: str | None = None,
    **params: str,
) -> RenderedEmail:
    locale = _supported(locale)
    block = _block(kind, locale, action_url, params)
    return _render([block], block["subject"], locale, base_url)


def render_bilingual_email(
    kind: str, *, base_url: str | None, action_url: str | None = None,
    params: dict[str, dict[str, str]],
) -> RenderedEmail:
    """
    One mail with the German and the English copy in a single layout, for a
    recipient whose language is unknown. `params` maps each locale to its own
    placeholder values (dates are formatted per language).
    """
    blocks = [_block(kind, locale, action_url, params[locale]) for locale in ("de", "en")]
    subject = " / ".join(block["subject"] for block in blocks)
    return _render(blocks, subject, "de", base_url)
