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
