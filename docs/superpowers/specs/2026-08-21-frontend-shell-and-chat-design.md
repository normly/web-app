# Design: Frontend-Grundgerüst und Chat-Oberfläche (v1)

**Datum:** 2026-08-21
**Status:** genehmigt
**Teilprojekt:** sechstes von mehreren zur Umsetzung des normly-MVP (freier Kern) — erstes von drei
Frontend-Teilprojekten

## Kontext

Fünf Backend-Dienste sind gebaut und gemergt: `core/` (Bibliothek), `api/` (lesende
Referenzgraph-API), `accounts/` (Registrierung/Login/Sitzung/Google-OAuth/Magic-Link),
`chat/` (Strukturfragen + RAG-Synthese über den Referenzgraphen, Sitzungsidentität mit
optionaler Kontoverknüpfung). Es existiert noch keinerlei Nutzeroberfläche — alle Dienste sind
bisher ausschließlich per HTTP erreichbar.

Der Gesamtumfang „Frontend" zerfällt in drei unabhängige Bereiche: Chat, Referenzgraph-Suche/
-Browsing, Konto-/Profilverwaltung. Mit dem Auftraggeber abgestimmt: diese werden als drei
sequenzielle Teilprojekte innerhalb **einer** Next.js-Anwendung umgesetzt (ein Grundgerüst,
mehrere Bereiche/Routen — kein separates Deployment pro Bereich). Dieses Teilprojekt ist das
erste: Grundgerüst plus Chat-Oberfläche, der laut SRS Kapitel 3.1.1 (`REQ-UI-001` bis
`REQ-UI-005`) am genauesten spezifizierte und produktseitig zentrale Fall.

**Entschieden mit dem Auftraggeber:**

1. Umfang dieses Teilprojekts: Next.js-Grundgerüst (Routing, PWA-Basis, Theming/White-Label,
   WCAG-Basis) **und** die Chat-Oberfläche nach `REQ-UI-001`–`005`, **plus** ein minimaler
   Login-Einstieg (E-Mail/Passwort, Magic-Link, Google), damit Sitzungen von Anfang an ans
   Konto verknüpft werden können. Suche/Browsing des Referenzgraphen (Teilprojekt 2) und
   Profilverwaltung/Kontoeinstellungen (Teilprojekt 3) sind eigene, spätere Teilprojekte.
2. Styling: Tailwind CSS + shadcn/ui. shadcn/ui liefert Komponenten als Code im Repository
   (kein Laufzeit-Dienst, kein Widerspruch zu „keine US-Dienste für Betrieb/Build") und baut
   auf Radix-UI-Primitives auf, die Tastaturbedienung, ARIA-Attribute und Fokus-Management
   bereits mitbringen — direkter Vorteil für `REQ-UI-004` (WCAG 2.1 AA).
3. Backend-Anbindung: alle drei Dienste (`api/`, `accounts/`, `chat/`) laufen produktiv hinter
   demselben Reverse Proxy unter Pfad-Prefixen — aus Sicht des Browsers derselbe Origin wie
   das Frontend. Keine CORS-Konfiguration nötig.
4. Sitzungs-Token-Speicherung: httpOnly-Cookies statt `localStorage`. Next.js Route Handler
   (`/app/api/*`) nehmen Login-/Chat-Antworten server-seitig entgegen und setzen den Token als
   httpOnly-Cookie — clientseitiges JavaScript sieht den Rohtoken nie, robuster gegen
   XSS-Token-Diebstahl.
5. Push-Benachrichtigungen: bewusst **nicht** Teil dieses (oder eines nahen) Teilprojekts.
   Echte Web-Push-Zustellung läuft im Browser-Standard zwingend über den jeweiligen
   Anbieter-Push-Dienst (Google FCM für Chrome/Android, Apple APNs für Safari/iOS) — das ist
   keine Wahl unsererseits, sondern wie der Web-Push-Standard technisch funktioniert, und
   kollidiert mit „keine US-Dienste für Betrieb". Der für `REQ-MOB-001` ohnehin nötige Service
   Worker wird aber jetzt schon angelegt (App-Shell-Caching, Installierbarkeit) — ein späterer
   Push-Handler ließe sich dort ergänzen, ohne die Grundstruktur zu ändern. Siehe Offene
   Punkte.
6. UI-Beschriftung von Anfang an DE/EN zweisprachig (nachträglich präzisiert, ursprünglich als
   Folgearbeit vorgesehen) — Cookie-basiert statt URL-Präfix, siehe „Internationalisierung
   (DE/EN)" unten.

## Ziel dieses Teilprojekts

Eine installierbare, unter eigener Konfiguration anpassbare, DE/EN-zweisprachige
Chat-Weboberfläche: Texteingabe, Antwortanzeige mit Ladezustand, Quellenverlinkung je Antwort,
mehrere wechselbare Chat-Sitzungen mit Historie, WCAG-2.1-AA-konform — vollständig nutzbar
ohne Konto (`REQ-ACC-001`), mit optionalem Login, der die Sitzung ans Konto bindet und damit
geräteübergreifende Historie ermöglicht.

## Nicht-Ziele

- **Referenzgraph-Suche/-Browsing unabhängig vom Chat** (gegen `api/`, ohne LLM) — eigenes,
  direkt anschließendes Teilprojekt (Nr. 2).
- **Profilverwaltung/Kontoeinstellungen** (E-Mail ändern, Sitzungen einsehen/abmelden, Konto
  löschen) — eigenes, späteres Teilprojekt (Nr. 3). `accounts/` bietet dafür heute noch keine
  Endpunkte (nur Registrierung/Login/Logout/Passwort-Reset/Google-OAuth/Magic-Link/
  Sitzungsprüfung) — Teilprojekt 3 braucht voraussichtlich zusätzliche `accounts/`-Arbeit,
  nicht nur Frontend.
- **Push-Benachrichtigungen** — siehe „Entschieden mit dem Auftraggeber" Punkt 5.
- **Vollständiges Offline-Lesen von Inhalten.** Dieses Teilprojekt liefert nur die
  PWA-Basisinstallierbarkeit (App-Shell-Caching) — Chat selbst braucht zwingend eine
  Live-Verbindung zum LLM und ist nicht offline-fähig. Offline-Zugriff auf bereits abgerufene
  freie Inhalte (`REQ-MOB-001`s eigentliches Offline-Versprechen) gehört zu Teilprojekt 2, wo
  tatsächlich Dokumentinhalte im UI erscheinen.
- **Native Anwendung** (`REQ-MOB-002`) — kommerzielle Schicht, eigenes, viel späteres
  Teilprojekt, an lizenzierte Offline-Volltexte gekoppelt.
- **Rate-Limiting/Kontingent für anonyme Nutzung** (`REQ-ACC-003`) — eigene
  Infrastrukturentscheidung, wie in den Backend-Teilprojekten an mehreren Stellen vermerkt,
  hier nicht Teil des Umfangs. Solange nicht vorhanden, ist die Nutzung in diesem Teilprojekt
  faktisch unbegrenzt.
- **Sprachen über Deutsch/Englisch hinaus.** Die UI-Beschriftung ist von Anfang an DE/EN
  zweisprachig (siehe „Internationalisierung (DE/EN)" unten) — weitere Sprachen sind
  Folgearbeit, kein allgemeiner Übersetzungsmechanismus für beliebige Sprachen in diesem
  Teilprojekt.

## Architektur

### Paketstruktur

Neues Top-Level-Verzeichnis `frontend/`, Next.js (App Router, TypeScript), `output:
"standalone"` (deckt sich mit CLAUDE.mds Vorgabe „keine plattformspezifischen Primitive —
alles muss im Container hinter beliebigem Reverse Proxy laufen").

```
frontend/
  package.json
  next.config.ts          # output: "standalone"
  tailwind.config.ts
  public/
    manifest.webmanifest    # Name, Icons, Theme-Farbe -- aus derselben Konfiguration wie Theming
  src/
    app/
      layout.tsx             # Grundgerüst, Theming-Provider, Service-Worker-Registrierung
      page.tsx                # Chat-Hauptansicht ("/")
      chats/
        page.tsx                # Chat-Historie ("/chats")
      api/
        chat/route.ts            # Route Handler -> chat/ POST /v1/chat, setzt/liest Cookie
        auth/
          login/route.ts           # -> accounts/ POST /v1/accounts/login
          register/route.ts        # -> accounts/ POST /v1/accounts/register
          magic-link/
            request/route.ts        # -> accounts/ POST /v1/accounts/magic-link/request
            confirm/route.ts        # -> accounts/ POST /v1/accounts/magic-link/confirm
          google/
            login/route.ts          # -> accounts/ GET /v1/accounts/google/login (Redirect)
            callback/route.ts       # -> accounts/ GET /v1/accounts/google/callback
          session/route.ts         # -> accounts/ GET /v1/accounts/session (Sitzungsprüfung)
    components/
      chat/                    # Eingabe, Nachrichtenliste, Ladeindikator, Zitat-Chip
      auth/                    # Login-/Registrierungs-Dialog
      ui/                      # shadcn/ui-Komponenten (generiert, im Repo)
    lib/
      config.ts                # Theming-/White-Label-Konfiguration, zur Laufzeit gelesen
      backend-clients.ts       # server-seitige fetch-Wrapper für accounts/ und chat/
      i18n/
        provider.tsx              # React-Context, liest normly_locale-Cookie
        de.json
        en.json
    public/sw.ts oder service-worker.ts  # App-Shell-Caching, kein Push-Handler
  tests/
    unit/                    # Vitest + React Testing Library
    e2e/                      # Playwright, gegen echte chat/+accounts/-Prozesse
```

### Theming/White-Label-Konfiguration

`REQ-UI-001` verlangt, dass Farben, Typografie und Logo pro Instanz konfigurierbar sind, ohne
den Quellcode zu ändern. Umsetzung: eine zur Startzeit gelesene Konfigurationsdatei/
Umgebungsvariablen (nicht in den Build eingebrannt, da `output: "standalone"` ein einziges
Image für beliebig viele Instanzen liefern soll — ein Rebuild pro Instanz widerspräche dem
Auslieferungsprinzip aus ADR-010). CSS-Variablen (von Tailwind gelesen) plus ein Logo-Pfad
werden aus dieser Konfiguration in `layout.tsx` in die Seite injiziert.

### Internationalisierung (DE/EN)

Die UI-Beschriftung (Buttons, Labels, Fehlermeldungen, Dialogtexte) ist von Anfang an
zweisprachig (Deutsch/Englisch) — unabhängig von `chat/`s eigenem `language`-Parameter, der
nur steuert, in welcher Sprache das LLM *antwortet*. Beide hängen zusammen (die UI-Sprache
bestimmt sinnvollerweise den Startwert für `chat/`s `language`-Feld), sind aber zwei getrennte
Einstellungen: eine deutschsprachige Oberfläche kann trotzdem eine englische Chat-Antwort
anzeigen, wenn der Nutzer das im Chat explizit so wählt (falls Teilprojekt 1 eine
Sprachumschaltung für die Antwortsprache eigens im Chat anbietet — sonst folgt sie einfach der
UI-Sprache).

**Kein URL-Präfix** (`/de/...`, `/en/...`) — die Sprache ist ein Cookie-Wert
(`normly_locale`), keine Route. Das passt zum bestehenden Cookie-basierten Muster
(Sitzungs-Token) und vermeidet doppelte Routen für eine App, die größtenteils hinter
Cookie-/Login-Zustand läuft. Ein Umschalter im Header wechselt die Sprache ohne
Seiten-Neuladung; ohne gesetztes Cookie bestimmt der `Accept-Language`-Header des ersten
Requests den Startwert (Fallback Deutsch, wenn nicht eindeutig zuordenbar).

Übersetzungen liegen als einfache Schlüssel-Wert-Wörterbücher (`lib/i18n/de.json`,
`lib/i18n/en.json`) vor, gelesen über einen React-Context-Provider in `layout.tsx` — für zwei
Sprachen und reinen UI-Chrome-Text (keine komplexe Pluralisierung/Zahlenformatierung
absehbar) ist eine schwergewichtige i18n-Bibliothek (z. B. `next-intl` mit
Locale-Routing-Middleware) nicht nötig und würde vor allem Routing-Komplexität einführen, die
hier nicht gebraucht wird (siehe „Entschieden mit dem Auftraggeber" zum Verzicht auf
URL-Präfixe). Jede neue UI-Komponente führt ihre Strings über diesen Provider, nie als
hartkodierten String — Tests (Komponententests) decken ab, dass beide Sprachwörterbücher für
dieselbe Komponente vollständig sind (kein fehlender Schlüssel in einer der beiden Sprachen).

### Backend-Anbindung als BFF (Backend for Frontend)

Kein direkter Client-seitiger Aufruf von `accounts/`/`chat/`. Stattdessen: Next.js Route
Handler unter `/app/api/*` nehmen die Anfrage vom Browser entgegen, reichen sie server-seitig
an den jeweiligen Backend-Dienst weiter (per internem Netzwerk-Aufruf, adressiert über
Umgebungsvariablen wie `NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_CHAT_BASE_URL` — demselben Muster
wie `chat/`s eigene Anbindung an `api/`/`accounts/`), und übersetzen die Antwort in ein
httpOnly-Cookie (`normly_session` für die anonyme `chat_session`, `normly_account_session` für
die Konto-Sitzung — getrennt, da eine `chat_session` auch ohne Konto existiert). Folgeanfragen
lesen das Cookie server-seitig aus dem Request und hängen es als `session_token`/
`Authorization`-Header an den Backend-Aufruf an — der Browser handhabt nie einen Rohtoken.

Produktiv sitzen `frontend/`, `api/`, `accounts/`, `chat/` hinter einem gemeinsamen Reverse
Proxy unter Pfad-Prefixen — dieselbe Origin wie das Frontend, keine CORS-Konfiguration nötig.
In der Entwicklung/in Tests wird stattdessen direkt gegen die jeweiligen Dienst-Adressen
aufgelöst.

### Seiten- und Komponentenstruktur

- **`/` — Chat-Hauptansicht.** Texteingabe (Absenden per Button oder Enter, `REQ-UI-002`),
  Nachrichtenverlauf mit Rollen-Unterscheidung (Nutzer/Assistent), visueller Ladeindikator
  während der Antwort erwartet wird, je Antwort ein oder mehrere Zitat-Chips mit Link zur
  Originalfundstelle (frei) bzw. Bezugsquelle des Herausgebers (kostenpflichtig, `REQ-UI-003`).
- **`/chats` — Chat-Historie (`REQ-UI-005`).** Liste vergangener Sitzungen, sortiert nach
  Erstellungsdatum, ein Klick öffnet die Sitzung erneut (Fortsetzung im `/`-Chat mit
  geladenem Verlauf). Nur für angemeldete Konten sichtbar/nutzbar — eine rein anonyme,
  geräteseitige Sitzung hat keine geräteübergreifend abrufbare „Liste", nur die eine laufende
  Sitzung im Cookie. Das deckt sich mit `chat/`s Design (`account_id`-Verknüpfung ist
  Voraussetzung für „mehrere Sitzungen einsehen") und ist kein Widerspruch zu `REQ-ACC-001`,
  da Chat selbst weiterhin ohne Konto voll nutzbar bleibt — nur die Historienübersicht über
  mehrere Sitzungen hinweg setzt ein Konto voraus.
- **Login-/Registrierungs-Dialog** (Modal, keine eigene Seite) — erreichbar über einen
  Header-Button, Chat bleibt davor und danach voll nutzbar. Tabs/Umschalter für
  E-Mail+Passwort-Login, Registrierung, Magic-Link-Anfrage, „mit Google anmelden"-Button.

## Datenfluss

**Chat-Zyklus:**
```
Nutzer sendet Nachricht
-> POST /app/api/chat (Next.js Route Handler)
   liest normly_session-Cookie (falls vorhanden) und normly_account_session-Cookie
   (falls vorhanden, als Authorization: Bearer Header)
-> POST {CHAT_BASE_URL}/v1/chat mit {session_token, jurisdiction, language, message}
   + optionalem Authorization-Header
<- Antwort: {session_token, answer, answer_type, citations}
   Route Handler setzt/aktualisiert normly_session-Cookie aus der Antwort
-> Antwort ans UI: Nachricht anzeigen, Zitate zu Links auflösen
   (je Zitat ein Lese-Aufruf gegen GET {API_BASE_URL}/v1/documents/{id} -- liefert
   Herausgeber/Bezugsquelle für REQ-UI-003s Verlinkung)
```

**Login-Zyklus (E-Mail/Passwort, analog für Magic-Link):**
```
Nutzer sendet Login-Formular
-> POST /app/api/auth/login -> POST {ACCOUNTS_BASE_URL}/v1/accounts/login
<- {session_token, account} oder 401 (generisch, kein Enumeration-Leak)
   Route Handler setzt normly_account_session-Cookie
-> nächste Chat-Anfrage hängt diesen Token als Authorization-Header an
   chat/ verknüpft die laufende chat_session mit dem Konto (siehe chat/-Design,
   "Sitzungsidentität und Kontoverknüpfung") -- bisheriger Verlauf bleibt erhalten
```

**Google-OAuth-Zyklus:** Browser wird direkt (nicht über den Route Handler) zu
`/app/api/auth/google/login` umgeleitet, dieser leitet redirect-technisch zu
`accounts/`s eigenem `GET /v1/accounts/google/login` weiter (der wiederum zu Google
umleitet); der Rückweg landet auf `/app/api/auth/google/callback`, der die `accounts/`-Antwort
entgegennimmt, das Cookie setzt und zurück zur Chat-Ansicht umleitet.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| `chat/` nicht erreichbar (503) | Route Handler reicht 503 durch; UI zeigt Fehlermeldung mit Retry-Möglichkeit, kein stiller Ladehänger |
| Login/Registrierung mit ungültigen Daten (400/401) | Fehlermeldung aus der generischen `accounts/`-Antwort direkt im Dialog, keine technischen Details |
| Sitzungscookie abgelaufen/unbekannt während eines Chats | Kein Fehlerzustand — nächste Anfrage bekommt von `chat/` einfach eine neue anonyme Sitzung, entspricht `chat/`s eigenem Verhalten |
| Zitat-Auflösung (Dokumentabruf für Link) schlägt fehl | Antwort wird trotzdem angezeigt, nur ohne klickbaren Quellenlink — Degradation, kein Blockierer |
| Google-OAuth abgelehnt/fehlgeschlagen | `accounts/`s eigene 400-Antwort wird im Dialog als generische Fehlermeldung angezeigt |

## Testkonzept

- **Komponententests** (Vitest + React Testing Library): Chat-Interaktion (Eingabe, Senden,
  Ladezustand, Anzeige), Login-Dialog (alle vier Wege), Zitat-Verlinkung — gegen gemockte
  Route-Handler-Antworten, schnell und isoliert.
- **End-to-End-Test** (Playwright), konsistent mit der in den Backend-Teilprojekten etablierten
  Testphilosophie (echte Dienste statt Mocks, wo praktikabel): vollständiger Zyklus — Frage
  stellen, Antwort inkl. Quellenlink sehen, optional einloggen, Sitzung verlassen und über
  `/chats` fortsetzen — gegen echte, real laufende `chat/`- und `accounts/`-Prozesse (analog zu
  `chat/`s eigenem `test_structural_end_to_end.py`-Muster: kein Ollama nötig für den
  Login-/Historie-Teil des Tests, ein separater, Ollama-gated Test deckt den echten
  Synthese-Antwortpfad ab, wo verfügbar).
- **WCAG-Konformität** (`REQ-UI-004`): automatisierte Prüfung via `axe-core` im
  Playwright-Lauf, plus eine manuelle Tastatur-/Screenreader-Stichprobe vor Abschluss des
  Teilprojekts.
- **PWA-Installierbarkeit**: manueller Test — Manifest und Service Worker führen zu einem
  gültigen Lighthouse-PWA-Score bzw. tatsächlicher Installierbarkeit in einem Chromium-Browser.
- **Wörterbuch-Vollständigkeit** (DE/EN): ein Komponententest pro Wörterbuch prüft, dass
  `de.json` und `en.json` exakt dieselbe Schlüsselmenge enthalten — verhindert einen
  Sprachwechsel, der einzelne Strings unübersetzt lässt.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| `REQ-UI-001` | Eigenständige Chat-Oberfläche, Theming/Logo über Laufzeit-Konfiguration, ohne externe Abhängigkeiten lauffähig |
| `REQ-UI-002` | Texteingabe mit Enter/Button, Ladeindikator, vollständiger Frage-Antwort-Zyklus |
| `REQ-UI-003` | Zitat-Chips je Antwort, Verlinkung zu Originalfundstelle bzw. Bezugsquelle |
| `REQ-UI-004` | Tailwind + shadcn/ui (Radix-Basis) als strukturelle Grundlage, `axe-core`-Prüfung im E2E-Test |
| `REQ-UI-005` | `/chats`-Historie, Sortierung nach Datum, Fortsetzbarkeit, performant auch bei vielen Sitzungen (Pagination bei Bedarf — siehe Offene Punkte) |
| `REQ-ACC-001` | Chat vollständig ohne Konto nutzbar; Login ist ein optionaler Zusatz, keine Voraussetzung |
| `REQ-ACC-004` | „gespeicherte Verläufe" steht explizit auf der abschließenden Liste kontopflichtiger Funktionen — `/chats` auf angemeldete Konten zu beschränken ist damit spec-konform, keine bloße Auslegung |
| `REQ-MOB-001` | Web-App-Manifest + Service Worker für App-Shell-Caching, Installierbarkeit |
| `REQ-MOB-003` | Offline-/Caching-Zugriff ausschließlich über den Service Worker als Abstraktionsschicht, keine verstreuten direkten Storage-Zugriffe in der Anwendungslogik |
| ADR-010 (Auslieferung) | `output: "standalone"`, ein Image für beliebig viele Instanzen, Theming zur Laufzeit statt im Build |
| CLAUDE.md „Mehrsprachigkeit vorgesehen" | DE/EN-UI-Beschriftung von Anfang an, siehe „Internationalisierung (DE/EN)" — vorgezogen statt als Folgearbeit behandelt |

## Offene Punkte / Folgearbeiten

- **Push-Benachrichtigungen** — siehe „Entschieden mit dem Auftraggeber" Punkt 5. Der
  Zielkonflikt mit „keine US-Dienste" bleibt ungelöst und müsste bei Bedarf bewusst mit dem
  Auftraggeber abgewogen werden (z. B. als explizit dokumentierte Ausnahme), nicht stillschweigend
  umgangen werden.
- **Referenzgraph-Suche/-Browsing** (Teilprojekt 2) und **Profilverwaltung** (Teilprojekt 3,
  braucht voraussichtlich neue `accounts/`-Endpunkte) — beide eigene, folgende Teilprojekte.
- **Rate-Limiting/Kontingent für anonyme Nutzung** (`REQ-ACC-003`) — noch nicht gebaut, weder
  hier noch im Backend; die Chat-Oberfläche zeigt aktuell keine Kontingent-Anzeige, weil es
  keine Kontingentzählung gibt.
- **Pagination der Chat-Historie** — `REQ-UI-005` verlangt performante Nutzbarkeit auch bei
  vielen Sitzungen; die konkrete Paginierungs-/Ladestrategie ist hier nicht im Detail
  festgelegt und wird im Implementierungsplan konkretisiert.
- **Sprachen über DE/EN hinaus** — das Wörterbuch-Muster ist auf weitere Sprachen erweiterbar,
  aber nicht Teil dieses Teilprojekts.
