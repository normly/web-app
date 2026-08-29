# Profilverwaltung — Design

Sub-Projekt 3 des Frontends, letztes der drei geplanten Sub-Projekte. Sub-Projekt 1
(App-Grundgerüst + Chat) und Sub-Projekt 2 (Referenzgraph-Suche/-Browsing) sind
abgeschlossen und in `main` gemergt. Dieses Dokument beschreibt Konto-/
Profilverwaltung: E-Mail ändern, Passwort setzen/ändern, Sitzungen einsehen und
abmelden, Datenexport, Kontolöschung.

## Entschieden mit dem Auftraggeber

1. **Funktionsumfang:** E-Mail ändern, Sitzungen einsehen/abmelden, Konto löschen
   (die drei ursprünglich in Sub-Projekt 1s Spec skizzierten Punkte), plus Passwort
   setzen/ändern (schließt eine gefundene Lücke — `accounts/` unterstützt
   Passwort-Reset bereits, das Frontend hat dafür aber noch keine Anbindung), plus
   Datenexport gemäß DSGVO Art. 20 (in keiner Anforderung explizit gefordert, aber
   für ein Konto mit personenbezogenen Daten sachgerecht).
2. **Kontolöschung:** Hartes Löschen — Konto UND alle verknüpften Daten
   (Chat-Sitzungen/-Nachrichten) werden entfernt, nicht nur der Konto-Link auf
   `NULL` gesetzt. Entspricht dem DSGVO-Recht auf Löschung am konsequentesten.
3. **Datenexport-Umfang:** Konto-Stammdaten (E-Mail, Erstellungsdatum, verknüpfte
   Google-Identität) plus vollständiger Chat-Verlauf (alle eigenen Sitzungen mit
   Nachrichten) — deckt die tatsächlich gespeicherten personenbezogenen Daten ab.
4. **Avatarbild:** Direkt in Postgres als `bytea` gespeichert, nicht über
   STACKIT Object Storage — letzteres existiert im Projekt noch nirgends, selbst
   die Ingestion-Pipeline verschiebt diese Anbindung bewusst auf eine spätere
   Deployment-Entscheidung; das Avatarbild soll diese Architekturentscheidung
   nicht vorwegnehmen. Serverseitig auf 256×256 verkleinert, keine neue
   Abhängigkeit nötig (`Pillow` bringt `core/` bereits mit). Kein eigener
   Abruf-Endpunkt — als Base64-Data-URL Teil der bestehenden `AccountResponse`.
5. **Vor-/Nachname:** Optional, ausschließlich über `/account` nachträglich
   einzugeben — **nicht** Teil der Registrierung, um REQ-ACC-001s Prinzip
   niedriger Registrierungshürden nicht anzutasten und die bereits gemergte
   Registrierungsform aus Sub-Projekt 1 unverändert zu lassen. Dient in erster
   Linie der Initialen-Platzhalteranzeige, wenn kein Avatarbild gesetzt ist.

## Architektur

Zehn neue `accounts/`-Endpunkte (alle authentifiziert via `Authorization: Bearer
<session-token>`) plus eine neue Frontend-Seite `/account` nach demselben
BFF-Muster wie die vorherigen Sub-Projekte — kein direkter Client-Zugriff auf
`accounts/`.

### Backend (`accounts/`)

**E-Mail-Änderung** — zweistufig, wiederverwendet den bestehenden
Verifizierungs-Mechanismus (`AccountToken`/`EmailSender`):

- `POST /v1/accounts/email/change` (authentifiziert, `{new_email: str}`) — legt
  einen `AccountToken` mit neuem Zweck `AccountTokenPurpose.EMAIL_CHANGE` an,
  nutzt das bereits vorhandene `email`-Feld des Tokens für die neue Adresse (keine
  Schemaänderung nötig), verschickt den Bestätigungslink an die **neue** Adresse.
  Ist `new_email` bereits einem anderen Konto zugeordnet: 409 (authentifizierte
  Aktion, kein Enumerationsrisiko wie bei anonymer Registrierung).
- `GET /v1/accounts/email/confirm?token=` — bei Klick: `Account.email` wird erst
  jetzt umgestellt, Token als verbraucht markiert (`consume_token`). Analog zum
  bestehenden `verify-email`-Muster.
- **Warum zweistufig:** Verhindert stille Kontoübernahme bei kompromittierter
  Sitzung (ein Angreifer mit gestohlenem Token könnte sonst die E-Mail sofort auf
  eine eigene Adresse umstellen und den echten Besitzer aussperren) und fängt
  Tippfehler in der neuen Adresse ab, bevor sie wirksam werden.

**Passwort setzen/ändern:**

- `POST /v1/accounts/password` (authentifiziert, `{current_password: str | None,
  new_password: str}`) — existiert bereits ein `password_hash`, wird
  `current_password` gegen `verify_password` geprüft (401 bei Fehlen oder
  Falschangabe); bei passwortlosen Konten (Google- oder Magic-Link-Erstanmeldung,
  `password_hash IS NULL`) entfällt die Prüfung, da die gültige Sitzung selbst
  schon die Identität belegt und nichts zum Vergleichen existiert. Nutzt
  `hash_password`/`set_password_hash`, dieselben bereits vorhandenen Bausteine wie
  der Passwort-Reset-Flow.

**Sitzungen:**

- Neue Repository-Methode `list_sessions_for_account(account_id) ->
  list[AccountSession]` (bislang nicht vorhanden — nur `get_session_by_token`
  existiert).
- Neue Repository-Methode `revoke_session_by_id(session_id, account_id) -> bool`
  (statt der bestehenden token-basierten `revoke_session`) — prüft serverseitig,
  dass die Sitzung wirklich zum aufrufenden Konto gehört, bevor sie entfernt wird;
  verhindert Erraten fremder Sitzungs-IDs.
- `GET /v1/accounts/sessions` → `[{id, created_at, expires_at, is_current: bool}]`
  — `is_current` durch Vergleich der Sitzungs-ID mit dem aktuell verwendeten
  Bearer-Token, damit die UI „dieses Gerät" kennzeichnen kann.
- `DELETE /v1/accounts/sessions/{session_id}` — meldet eine fremde Sitzung ab; ist
  die eigene aktive Sitzung betroffen, meldet die Antwort das explizit, damit das
  Frontend auch den lokalen Cookie löscht (sonst bliebe der Browser mit einem
  serverseitig bereits ungültigen Token zurück).

**Kontolöschung:**

- `DELETE /v1/accounts/me` (authentifiziert, `{password: str | None}` bei
  vorhandenem Passwort zur Bestätigung; bei passwortlosen Konten prüft das
  Frontend stattdessen, dass die Nutzerin die eigene E-Mail-Adresse exakt in ein
  Bestätigungsfeld eingetippt hat, bevor der Request überhaupt abgeschickt wird —
  serverseitig ist bei passwortlosen Konten keine zusätzliche Prüfung nötig, da
  die gültige Sitzung die Identität bereits belegt) — neue Repository-Methode
  `delete_account(account_id)` löscht explizit
  in Abhängigkeitsreihenfolge: `chat_message_citation` → `chat_message` →
  `chat_session` → `account_token`/`account_session`/`account_google_identity` →
  `account`. Die bestehende Fremdschlüsselbeziehung auf `chat_session.account_id`
  ist vermutlich `SET NULL` (passend zum anonymen-Sitzungs-Verhalten) statt
  `CASCADE` — wird bei der Implementierung geprüft; falls ja, übernimmt die
  Repository-Methode die Löschreihenfolge explizit statt sich auf
  Datenbank-Cascade zu verlassen.

**Name und Avatarbild:**

- Neue `Account`-Spalten: `first_name: str | None`, `last_name: str | None`,
  `avatar_image: bytes | None`, `avatar_content_type: str | None`.
- `AccountResponse` erweitert um `first_name`, `last_name`,
  `avatar_data_url: str | None` (Base64-Data-URL, z. B.
  `data:image/jpeg;base64,...`, `None` wenn kein Bild gesetzt).
- `PATCH /v1/accounts/profile` (authentifiziert, `{first_name: str | None,
  last_name: str | None}`) — beide Felder optional und unabhängig voneinander
  löschbar (leer übermittelt = auf `None` zurücksetzen).
- `POST /v1/accounts/avatar` (authentifiziert, multipart-Upload, Obergrenze
  5 MB vor der Verkleinerung) — validiert Format (JPEG/PNG/WebP), verkleinert
  mit `Pillow` auf 256×256, speichert `avatar_image` + `avatar_content_type`.
- `DELETE /v1/accounts/avatar` — setzt beide Spalten auf `None` zurück.
- **Initialen-Platzhalter-Logik** (frontend-seitig, aus den bereits vorhandenen
  Feldern abgeleitet, kein Server-Rendering nötig): sind `first_name`/
  `last_name` gesetzt, erste Buchstaben beider Felder; ist nur eins gesetzt,
  dessen erster Buchstabe; sind keine gesetzt, der erste Buchstabe der
  E-Mail-Adresse.

**Export:**

- `GET /v1/accounts/export` (authentifiziert) → JSON:
  ```json
  {
    "account": {
      "email": "...", "created_at": "...", "email_verified": true,
      "google_linked": false, "first_name": "...", "last_name": "...",
      "avatar_data_url": "..."
    },
    "chat_sessions": [
      {
        "session_token": "...", "jurisdiction": "DE", "language": "de",
        "created_at": "...",
        "messages": [
          {"role": "user", "content": "...", "created_at": "..."},
          {
            "role": "assistant", "content": "...", "created_at": "...",
            "citations": [{"document_id": "...", "segment_id": null}]
          }
        ]
      }
    ]
  }
  ```
  Kein Pagination-Bedarf für den ersten Wurf (YAGNI) — als offener Punkt
  vermerkt, falls Nutzung mit sehr langen Verläufen das relevant macht.

### Frontend

**Neue Seite `/account`** (Server/Client-Split-Muster wie `/search` und
`/documents/[id]`): Abschnitte für Name (Vor-/Nachname, optional) und
Avatarbild (Upload mit Vorschau + „Entfernen"-Button), E-Mail ändern, Passwort
setzen/ändern, aktive Sitzungen (Liste mit „dieses Gerät"-Kennzeichnung und
Abmelden-Button je Zeile), Datenexport (Download-Button), Kontolöschung (mit
Bestätigung). `AppHeader`s bislang reine Text-E-Mail-Anzeige wird auf `/account`
verlinkt und zeigt zusätzlich das Avatarbild bzw. den Initialen-Platzhalter.

**Passwort-Reset-Anbindung** (die gefundene Lücke — `accounts/` unterstützt es
bereits, das Frontend bislang nicht): kein eigener Tab in `AuthDialog`, sondern
ein „Passwort vergessen?"-Link in `LoginForm`, der zu einer
Anfrage-/Bestätigungs-Ansicht wechselt — entspricht der üblichen Position dieses
Flows und vermeidet einen zusätzlichen, selten genutzten Tab.

**Neue BFF-Route-Handler** (gleiches Proxy-Muster, korrekt encodiert von Anfang
an — nach dem in Sub-Projekt 1 gefundenen Path-Traversal-Fix wird hier von Beginn
an sauber gebaut): `POST /api/account/email`, `GET /api/account/email/confirm`,
`POST /api/account/password`, `PATCH /api/account/profile`,
`POST /api/account/avatar`, `DELETE /api/account/avatar`,
`GET /api/account/sessions`, `DELETE /api/account/sessions/[id]`,
`DELETE /api/account`, `GET /api/account/export`,
`POST /api/auth/password-reset/request`, `POST /api/auth/password-reset/confirm`.

**i18n:** neuer `account`-Namensraum für alle Beschriftungen/Fehlermeldungen
dieser Seite, plus Ergänzungen im bestehenden `auth`-Namensraum für den
Passwort-vergessen-Flow.

## Datenfluss

**E-Mail-Änderungszyklus:**
```
/account → POST /api/account/email {new_email}
  → accounts/ legt AccountToken(purpose=EMAIL_CHANGE, email=new_email) an, sendet Mail
Nutzer klickt Link → GET /api/account/email/confirm?token=
  → Account.email wird umgestellt, Token verbraucht
```

**Sitzungs-Abmeldezyklus:**
```
/account → GET /api/account/sessions → Liste mit is_current-Kennzeichnung
Klick auf "Abmelden" bei einer Zeile → DELETE /api/account/sessions/{id}
  → falls is_current: Frontend löscht auch den lokalen normly_account_session-Cookie
```

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Neue E-Mail bereits vergeben | 409, klare Fehlermeldung |
| Aktuelles Passwort falsch (Ändern/Löschen) | 401, generische Fehlermeldung |
| Sitzung nicht gefunden/fremd | 404 |
| Export bei sehr langem Verlauf | Kein Pagination-Bedarf für den ersten Wurf; offener Punkt |
| Avatar-Upload zu groß / falsches Format | 400, klare Fehlermeldung mit erlaubten Formaten und Obergrenze |

## Testkonzept

- **`accounts/`:** Pytest je neuem Endpunkt und neuer Repository-Methode —
  insbesondere ein Cascade-Löschtest, der tatsächlich prüft, dass
  Chat-Nachrichten/-Zitate mitgelöscht werden, nicht nur der Account selbst; ein
  Test, der bestätigt, dass Sitzung X nicht durch Konto Y abgemeldet werden kann
  (fremde Sitzungs-ID); Tests für den Avatar-Upload (zu große Datei, falsches
  Format, erfolgreiche Verkleinerung auf 256×256) und für das unabhängige
  Zurücksetzen von Vor-/Nachname.
- **`frontend/`:** BFF-Route- und Komponententests nach etabliertem Muster,
  Playwright-Erweiterung um E-Mail-Änderung und Kontolöschung als
  End-to-End-Fluss.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-ACC-004 (kontopflichtige Funktionen) | Macht „gespeicherte Verläufe" erstmals einseh-, export- und löschbar, nicht nur speicherbar — dieselbe abschließende Liste, keine neue Kontopflicht |
| ADR-017 (anonyme Nutzung ohne Kontopflicht) | Begründet u. a. mit „ohne Konto entstehen keine personenbezogenen Daten, die geschützt werden müssten" — mit Konto liefert dieses Sub-Projekt genau diesen Schutz (Auskunft, Löschung, Portabilität) nach |
| CLAUDE.md „Alles Persistierte verschlüsselt" | Kontolöschung entfernt die Daten vollständig, nicht nur eine Referenz darauf |

## Offene Punkte

- Multi-Faktor-Authentifizierung — in SRS Kapitel 3.3.2 als Ausblick genannt,
  hier nicht gebaut.
- Keine Ratenbegrenzung auf den neuen `accounts/`-Endpunkten — passt zum
  bisherigen Stand (`accounts/` hat aktuell gar keine Ratenbegrenzung, anders als
  `api/` seit Sub-Projekt 2); eigenständiges künftiges Thema, falls relevant.
- Keine Export-Paginierung für sehr lange Chat-Verläufe.
- Kein Audit-Log für Kontolöschungen oder E-Mail-Änderungen.
