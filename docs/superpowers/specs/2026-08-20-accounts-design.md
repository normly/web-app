# Design: Accounts — E-Mail/Passwort und Google-Login (v1)

**Datum:** 2026-08-20
**Status:** zur Durchsicht
**Teilprojekt:** viertes von mehreren zur Umsetzung des normly-MVP (freier Kern)

## Kontext

Die ersten drei Teilprojekte (Datenmodell & Referenzgraph-Schema, Ingestion-Pipeline,
Backend-API) haben einen befüllten Referenzgraph und eine öffentliche, anonym nutzbare
Lese-API gebaut. Das bereits genehmigte, aber zurückgestellte LLM-Chat-Design
(`2026-08-20-llm-chat-design.md` — Zählung wird bei Bedarf noch angepasst, siehe dortigen
Hinweis) sah zunächst rein anonyme Sitzungen vor. Der Auftraggeber möchte echte
Konto-Funktionalität von Anfang an, nicht erst nachträglich nachrüsten — dieses Teilprojekt
liefert sie, bevor der Chat darauf aufbaut.

REQ-ACC-004 zählt abschließend auf, wofür ein Konto nötig ist: erhöhte Kontingente,
gespeicherte Verläufe, Uploads, lizenzierte Inhalte, Offline-Nutzung, kostenpflichtige
Dienste. REQ-INT-003 verlangt SSO für Organisationen (OAuth2/SAML) sowie „Email, mit Google"
als weitere Login-Wege. SRS Kapitel 3.3.2 nennt zusätzlich MFA und Magic-Link/OTP als
Sicherheitsthemen. Das ist zusammen zu groß für ein Teilprojekt.

**Entschieden mit dem Auftraggeber:**

1. Umfang: E-Mail/Passwort-Registrierung (bcrypt-gehashte Passwörter) plus Google-OAuth-Login.
   Generisches Organisations-SSO (OAuth2/SAML für beliebige Fremd-Identitätsanbieter), MFA und
   Magic-Link/OTP sind eigene, spätere Teilprojekte.
2. Architektur: eigenes Top-Level-Paket `accounts/`, eigene Tabellen im bestehenden
   `core`-Schema. Andere Dienste (künftig `chat/`, spätere Uploads) prüfen Sitzungstoken gegen
   `accounts/` statt Auth-Logik zu duplizieren.
3. Sitzungsmechanik: serverseitige, opake Session-Tokens (DB-Lookup) — dasselbe Muster wie
   der anonyme `session_token` im LLM-Chat-Design, sofort widerrufbar (Logout, Sperrung), kein
   JWT.
4. E-Mail-Versand (Verifizierung, Passwort-Reset): EU-Anbieter oder selbst betriebener
   SMTP-Relay auf STACKIT — konsistent mit CLAUDE.mds „keine US-Dienste für Betrieb"
   (SendGrid/Mailgun/AWS SES sind US-Anbieter). Konkreter Anbieter ist eine spätere,
   austauschbare Deployment-Entscheidung hinter einer Abstraktionsschicht.
5. Anonyme Nutzung bleibt für freie Inhalte weiterhin uneingeschränkt möglich (ADR-017/
   REQ-ACC-001) — dieses Teilprojekt fügt eine Option hinzu, ersetzt nichts.

## Ziel dieses Teilprojekts

Nutzer können sich per E-Mail/Passwort oder Google-Konto registrieren und anmelden. Andere
Dienste können einen Sitzungstoken gegen einen Endpunkt dieses Dienstes prüfen und die
zugehörige Konto-Identität erhalten. Passwort-Reset und E-Mail-Verifizierung funktionieren
über einen EU-/selbst-gehosteten E-Mail-Versand.

## Nicht-Ziele

- **Organisations-SSO** (REQ-INT-003, OAuth2/SAML für Fremd-Identitätsanbieter) — eigenes,
  späteres Teilprojekt; pro Organisation eigener Konfigurationsaufwand.
- **Multi-Faktor-Authentifizierung** (SRS 3.3.2) — spätere Sicherheitserweiterung, das
  Datenmodell blockiert eine Nachrüstung nicht strukturell.
- **Magic-Link/OTP-Login** — laut SRS nur „denkbar", nicht gefordert.
- **Login-Versuchsbegrenzung/Brute-Force-Schutz** — eigene Infrastrukturentscheidung, gleiche
  Begründung wie die bereits in den vorigen Teilprojekten zurückgestellte Ratenbegrenzung
  (REQ-SEC-004).
- **Kontingent-Erhöhung für angemeldete Konten, kontogebundene Verläufe/Merklisten selbst.**
  Dieses Teilprojekt liefert nur die Konto-Grundlage (Registrierung, Login, Sitzungsprüfung);
  welche Funktionen ein Konto konkret freischaltet, entscheiden die jeweiligen
  Fach-Teilprojekte (Chat, Uploads, …), die `accounts/`s Sitzungsprüfung konsumieren.
- **Konto-Löschung/DSGVO-Auskunft/-Export.** Wichtig, aber ein eigenes Thema mit eigenen
  Anforderungen — hier nicht spezifiziert.

## Architektur

### Paketstruktur

Zwei Ansätze wurden abgewogen:

1. **Eigenes `accounts/`-Verzeichnis, eigene Tabellen, eigener HTTP-Dienst.**
2. Teil von `api/` — verworfen: bricht `api/`s bereits geprüfte „rein lesend"-Eigenschaft
   (Registrierung/Login sind Schreibzugriffe), gleiche Begründung wie beim LLM-Chat-Design.

**Entschieden: Ansatz 1.**

```
accounts/
  pyproject.toml        # eigenes Paket, hängt von normly_core ab
  src/normly_accounts/
    main.py              # FastAPI-App, mountet /v1/accounts
    dependencies.py       # DB-Session, SMTP-Client, Google-OAuth-Client
    security.py            # Passwort-Hashing (bcrypt), Token-Erzeugung
    schemas.py               # Pydantic-Modelle
    email.py                  # EmailSender-Abstraktion + SMTP-Implementierung
    routers/
      registration.py          # Registrierung, E-Mail-Verifizierung
      login.py                   # Login, Logout, Passwort-Reset
      google.py                    # Google-OAuth-Flow
      session.py                    # Token-Validierung für andere Dienste
  tests/
```

Andere Dienste rufen `GET /v1/accounts/session` wie einen gewöhnlichen HTTP-Endpunkt auf —
kein direkter Python-Import, gleiches Dogfooding-Prinzip wie zwischen `chat/` und `api/`
vorgesehen.

### Datenmodell (neue Tabellen im bestehenden `core`-Schema)

| Tabelle | Spalten | Zweck |
|---|---|---|
| `account` | `id` (PK), `email` (eindeutig), `password_hash` (nullable), `email_verified_at` (nullable), `created_at` | Kern-Identität |
| `account_session` | `id` (PK), `account_id` (FK), `session_token` (eindeutig, opak), `created_at`, `expires_at` | Aktive Sitzungen |
| `account_google_identity` | `account_id` (FK), `google_subject_id` (eindeutig) | Verknüpfung Google-Konto ↔ normly-Konto |
| `account_token` | `id` (PK), `account_id` (FK), `purpose` (`password_reset`/`email_verification`), `token` (eindeutig, opak, einmalig), `created_at`, `expires_at`, `used_at` (nullable) | Einmal-Tokens für Reset/Verifizierung |

Sitzungen laufen 30 Tage nach der letzten Nutzung ab (`expires_at` wird bei jeder erfolgreichen
`/session`-Prüfung verlängert — „sliding window", kein hartes Fixdatum), damit aktive Nutzer
nicht mitten in der Nutzung ausgeloggt werden, inaktive Sitzungen aber nicht unbegrenzt gültig
bleiben.

`password_hash` ist nullable — ein Konto, das ausschließlich über Google angelegt wurde, hat
keins. Registrierung erlaubt sofortigen Login ohne abgeschlossene E-Mail-Verifizierung;
`email_verified_at` hält den Status für spätere, striktere Gates fest (YAGNI: kein Blockieren
in diesem Teilprojekt). `account_token` deckt sowohl Passwort-Reset als auch
E-Mail-Verifizierung über ein `purpose`-Feld ab statt zweier fast identischer Tabellen.

Repository-Zugriff nach demselben Muster wie überall im Projekt: Protocol in `domain.py`,
Postgres-Implementierung in `repositories.py`, Alembic-Migration für die vier Tabellen.

## Endpunkte (v1)

| Endpunkt | Zweck |
|---|---|
| `POST /v1/accounts/register` | E-Mail + Passwort → Konto anlegen, Verifizierungs-Mail versenden, Session zurückgeben |
| `POST /v1/accounts/login` | E-Mail + Passwort → Session |
| `POST /v1/accounts/logout` | Session widerrufen |
| `POST /v1/accounts/password-reset/request` | E-Mail → Reset-Mail versenden |
| `POST /v1/accounts/password-reset/confirm` | Token + neues Passwort → Passwort ändern |
| `GET /v1/accounts/verify-email?token=` | E-Mail-Verifizierung abschließen |
| `GET /v1/accounts/google/login` | Redirect zu Googles Consent-Screen |
| `GET /v1/accounts/google/callback` | Google-Antwort verarbeiten, Konto anlegen/verknüpfen, Session zurückgeben |
| `GET /v1/accounts/session` | Token-Validierung für andere Dienste |

### Google-OAuth-Fluss

Standard Authorization-Code-Flow. `google/login` leitet zu Googles Consent-Screen um.
`google/callback` tauscht den erhaltenen Code gegen ein Google-Profil (E-Mail,
`subject_id`) — legt bei unbekannter `subject_id` ein neues Konto an, oder verknüpft
`account_google_identity` mit einem bestehenden Konto derselben E-Mail-Adresse, falls
vorhanden. Erstellt eine Session. Das Redirect-Verhalten nach dem Callback (wohin der Browser
geschickt wird) bleibt bewusst der Frontend-Seite überlassen — API-first, wie bei allen
bisherigen Teilprojekten.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| E-Mail bereits registriert | 409 — UX erfordert diese Auskunft bei der Registrierung |
| Login mit falschen Zugangsdaten | 401, generische Meldung — keine Unterscheidung „E-Mail unbekannt" vs. „Passwort falsch" (Enumeration-Schutz) |
| Abgelaufener/ungültiger/bereits verwendeter Reset- oder Verifizierungs-Token | 400 |
| Google-OAuth abgelehnt/fehlgeschlagen | 400, Fehlerzustand im Redirect |
| Unbekannter/abgelaufener `session_token` bei `/session` | 401 |
| E-Mail-Versand (SMTP) nicht erreichbar | 503, kein Detail-Leak; Registrierung/Reset-Anfrage selbst schlägt NICHT fehl — Konto/Token werden angelegt, Mail-Versand wird separat nachgeholt oder geloggt (siehe Offene Punkte: kein Retry-Mechanismus in diesem Teilprojekt) |
| Datenbankverbindung down | 503, kein Detail-Leak |

## Testkonzept

- Echtes PostgreSQL (Testcontainer-Muster wie überall im Projekt).
- Echtes bcrypt-Hashing — kein Mocking nötig, ausreichend schnell für Tests.
- **Google OAuth**: nur der Token-Austausch/Profilabruf gegen Googles API wird gezielt
  gemockt (ein HTTP-Call, nicht die eigene Verknüpfungs-/Kontenlogik) — eine echte
  Google-Testverbindung ist in einer automatisierten Suite nicht sinnvoll herstellbar, gleiche
  Begründung wie beim DB-down-Test im Backend-API-Teilprojekt.
- **E-Mail-Versand** hinter der `EmailSender`-Abstraktion — Tests nutzen eine
  Test-Implementierung, die versendete Mails aufzeichnet, statt echte Mails zu verschicken.
- Registrierung → Login → Logout End-to-End gegen echte Session-Tabellen.
- Passwort-Reset- und Verifizierungs-Token: Ablauf, Einmaligkeit (`used_at`),
  ungültige/abgelaufene Token explizit getestet.
- Google-Konto-Verknüpfung: neues Google-Konto legt neues normly-Konto an; Google-Login mit
  bereits per E-Mail/Passwort registrierter Adresse verknüpft statt dupliziert.
- `GET /v1/accounts/session`: gültiger Token liefert `account_id`, abgelaufener/unbekannter
  Token liefert 401 — das ist der Vertrag, auf den sich künftige Dienste (`chat/` u. a.)
  verlassen.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-ACC-004 | Liefert die Konto-Grundlage, auf der kontopflichtige Funktionen später aufbauen |
| REQ-INT-003 (Teilmenge) | E-Mail/Passwort und Google-Login; Organisations-SSO ist Folgearbeit |
| ADR-017 / REQ-ACC-001 | Anonyme Nutzung bleibt unverändert möglich — Konto ist eine zusätzliche Option, keine Voraussetzung |
| CLAUDE.md „keine US-Dienste für Betrieb" | E-Mail-Versand über EU-/selbst gehosteten SMTP-Relay statt US-Transaktions-E-Mail-Dienst |
| SRS 3.3.2 (Passwort-Hashing) | bcrypt für `account.password_hash` |

## Offene Punkte / Folgearbeiten

- **Organisations-SSO** (OAuth2/SAML für Fremd-Identitätsanbieter), **MFA**,
  **Magic-Link/OTP** — eigene, spätere Teilprojekte.
- **Login-Versuchsbegrenzung/Brute-Force-Schutz** — eigene Infrastrukturentscheidung, wie die
  bereits zurückgestellte Ratenbegrenzung in den vorigen Teilprojekten.
- **Kein Retry-Mechanismus für fehlgeschlagenen E-Mail-Versand.** Wenn der SMTP-Relay beim
  Versenden einer Verifizierungs- oder Reset-Mail down ist, wird das aktuell nur geloggt —
  keine Warteschlange/kein automatischer erneuter Versuch. Für den Start ausreichend, sobald
  es zum echten Problem wird nachzuziehen.
- **Konto-Löschung, DSGVO-Auskunft/-Export** — eigenes Thema, hier nicht spezifiziert.
- **Konkreter E-Mail-Anbieter/SMTP-Konfiguration** — spätere Deployment-Entscheidung, analog
  zu den vorigen Teilprojekten (z. B. Datenbank-Hosting, LLM-Provisionierung).
- **LLM-Chat-Design muss nachgezogen werden**, sobald dieses Teilprojekt steht:
  `chat_session` sollte dann optional eine echte `account_id` verknüpfen können
  (`GET /v1/accounts/session` liefert die Identität), anonyme Nutzung bleibt zusätzlich
  bestehen.
