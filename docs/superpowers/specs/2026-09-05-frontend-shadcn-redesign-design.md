# Design: Frontend-Redesign auf shadcn-Default-Theme

## Kontext

Das Frontend ist funktional fertig (Chat, Suche, Dokument-Detail, Account-
Verwaltung, Auth-Modal), aber visuell unfertig: nur sieben rohe
shadcn-Basiskomponenten (`avatar`, `badge`, `button`, `dialog`, `input`,
`pagination`, `tabs`) im Slate-Default-Stil, keine durchgängige
Theming-Entscheidung, kein Light/Dark-Umschalter. Ein Sandbox-Testlauf
dieser Session (Screenshots) zeigt das deutlich: funktionierende, aber
komplett ungestylte Seiten.

Das Projekt hat bereits Zugang zu `@shadcnblocks` (Premium-Registry,
`SHADCNBLOCKS_API_KEY` gesetzt, in `frontend/components.json` konfiguriert)
und zum shadcn-MCP-Server für Komponenten-Discovery. Der Auftraggeber hat
für jeden Bereich der App konkrete Referenz-Blöcke aus dieser Registry
sowie ein externes Referenz-Layout (shadcnuikit.com's `ai-chat-v2`, nur als
visuelle Vorlage für den Chatverlauf, keine eigene registrierte Registry)
vorgegeben.

## Ziel dieses Teilprojekts

1. Umstellung auf das shadcn-Default-Theme (Light/Dark) als alleiniges
   Farbsystem, keine Mandanten-Branding-Farbe.
2. Neue App-Shell mit einklappbarer Sidebar (`application-shell2`),
   Hauptpunkte Chat und Suche.
3. Chat-Seite bekommt eine zweite, verschachtelte Sidebar für den
   datumsgruppierten Verlauf samt "Neuer Chat"-Button (Vorbild
   shadcnuikit's `ai-chat-v2`), ersetzt die bisherige eigenständige
   `/chats`-Seite.
4. Einheitliches Seiten-Header-Muster (Vorbild `dashboard9`): Titel/
   Untertitel links, Dark/Light-Toggle und Benachrichtigungs-Glocke
   (Platzhalter) rechts.
5. Profilverwaltung als geblurrtes Overlay-Dialog (Vorbild
   `settings-profile4`-Struktur, Claude-artige Darstellung statt
   Vollseite), mit echten Konto-Abschnitten statt der Block-Demofelder.
6. Fünf eigene Auth-Vollseiten (`/login`, `/signup`, `/magic-link`,
   `/reset-password`, `/verify-email`) nach den Blöcken `signup2`,
   `magic-link2`, `reset-password2`, `verify-email2`, lösen das bisherige
   Auth-Modal ab.
7. Suche und Dokument-Detail bekommen kein neues Layout, nur die neuen
   Theme-Farben/-Komponenten, und laufen künftig innerhalb der App-Shell.

## Nicht-Ziele

- **Keine Mandanten-Branding-Farbe.** `NORMLY_BRAND_COLOR_HSL` und die
  zugehörige Logik in `frontend/src/lib/config.ts` bleiben unangetastet im
  Code (eigene Anforderung, REQ-DIST-003), werden aber in diesem
  Teilprojekt nirgends in die neuen Farb-Tokens eingebunden. Reine
  shadcn-Standardpalette.
- **Keine neuen Backend-Endpunkte oder Auth-Flow-Änderungen.** Insbesondere
  bleibt E-Mail-Verifizierung token-link-basiert (siehe unten,
  Abweichung bei `verify-email2`).
- **Keine echte Notification-Funktion.** Die Glocke im Header ist reines
  UI-Element ohne Datenquelle.
- **Kein neues Blocklayout für Suche/Dokument-Detail.** Nur
  Farb-/Komponenten-Anpassung an das neue Theme.
- **Keine der Demo-Navigationspunkte aus den Referenz-Templates**
  (Dashboard, Tasks, Team, Workspace, Kanban, Mail, Hotel etc. aus
  `application-shell2`/`dashboard9`/shadcnuikit) — die sind Beiwerk der
  Vorlagen, nicht Teil dieser App.

## Architektur

### Theme-Fundament

- `@shadcnblocks/theme/shadcnblocks` liefert die Standard-shadcn-CSS-
  Variablen (`--primary`, `--secondary`, `--accent`, `--muted`,
  `--destructive`, `--sidebar-*`, `--chart-1..5`, `--radius-*`,
  `--shadow-*`) für Light und Dark in `src/app/globals.css`.
- `next-themes` wird neu eingeführt (`ThemeProvider` um das Root-Layout),
  liefert den Light/Dark-Zustand für den Toggle im Header.
- `tailwind.config.ts` wird um die neuen Farb-Utilities ergänzt
  (`primary`, `secondary`, `sidebar`, `chart-*` usw.), die bestehenden
  `brand`/`brand-foreground`-Mappings bleiben bestehen, werden aber von
  keiner neuen Komponente mehr referenziert.

### App-Shell

- `application-shell2` liefert Grundstruktur: einklappbare
  (icon-only-fähige) Sidebar, Inhaltsbereich (`SidebarInset`).
  Registry-Abhängigkeiten, die neu installiert werden müssen: `sidebar`,
  `collapsible`, `dropdown-menu`, `scroll-area`, `separator` (Avatar ist
  schon vorhanden).
- Nav-Gruppen der Demo (Overview/Projects/Team/Workspace) werden ersetzt
  durch genau zwei Hauptpunkte: **Chat**, **Suche**.
- User-Footer (`NavUser`-Muster aus dem Block) bleibt strukturell:
  Avatar + Name/E-Mail, Dropdown mit "Account" (öffnet das
  Profil-Overlay, siehe unten) und "Abmelden".
- Diese Shell umschließt künftig alle Seiten (Chat, Suche,
  Dokument-Detail) — ersetzt den aktuellen einfachen Top-Nav-Header.

### Chat-Seite (verschachtelte Sidebar)

- Zweite, innere Sidebar **nur auf der Chat-Seite**: Chatverlauf nach
  Erstellungsdatum gruppiert (Buckets "Heute", "Gestern", "Vor 7 Tagen",
  älter analog), "Neuer Chat"-Button oben, Vorbild ai-chat-v2 (nur
  Struktur/Layout, keine Fremd-Registry-Abhängigkeit — wird als eigene
  Komponente gebaut, nicht importiert).
- Datenquelle: bestehende `/api/chat/sessions`-BFF-Route (existiert
  bereits) — Gruppierung passiert clientseitig anhand des
  Sitzungs-Erstellungsdatums.
- Die bisherige eigenständige `/chats`-Verlaufsseite entfällt; der
  Top-Nav-Link "Verlauf" verschwindet, der Verlauf lebt nur noch in dieser
  inneren Sidebar, erreichbar über den Chat-Menüpunkt der äußeren Sidebar.
- Chat-Fenster selbst wird mit shadcn-Komponenten neu gebaut
  (Nachrichtenliste, Eingabefeld unten statt wie bisher oben) — bestehende
  Quellenangaben ("Quelle"-Links unter jeder Antwort) bleiben funktional
  unverändert, nur visuell neu.

### Header-Muster

- Gemeinsame Layout-Komponente (`PageHeader` o. ä.): Titel + Untertitel
  links (z. B. "Chat", "Suche" — zeigt den aktuellen Bereich), rechts ein
  Dark/Light-Toggle-Button (`next-themes`) und ein Glocken-Icon-Button
  (Popover mit statischem "Keine neuen Benachrichtigungen"-Inhalt, keine
  echte Datenquelle).
- Wird von jeder Seite unterhalb der App-Shell verwendet.

### Profil-Overlay

- Struktur aus `settings-profile4` übernommen (interne
  Abschnitts-Navigation links, Inhalt rechts, "Speichern"-Leiste), aber:
  - **Als Dialog/Overlay**, nicht Vollseite: geblurrter Hintergrund
    (`backdrop-blur`), Dialog nimmt nicht die volle Breite ein
    (Claude-artig), ähnlich dem bisherigen Auth-Modal, nur größer.
  - **Abschnitte an echte Kontodaten angepasst**, nicht an die
    Block-Demofelder (Name/Bio/Social-Links/Timezone entfallen). Echte
    Abschnitte: Profil (Name, Avatar), E-Mail, Passwort, Sitzungen (mit
    Widerruf), Konto & Daten (Export, Löschen), plus
    Google-Verknüpfungsstatus falls vorhanden — entspricht 1:1 den
    bereits gebauten Abschnitten der bisherigen `/account`-Seite,
    einschließlich der bestehenden BFF-Routen
    (`/api/account/profile`, `/api/account/email`,
    `/api/account/password`, `/api/account/sessions`,
    `/api/account/export`, `/api/account/delete`,
    `/api/account/avatar`) — reines UI-Remapping, keine neue Logik.
  - Genaue Abschnitts-Reihenfolge/-Bezeichnung sowie der exakte
    Öffnungs-Mechanismus (Client-State vs. Intercepting Route vs.
    Query-Parameter für Deep-Links) sind Implementierungsdetails, kein
    Design-Punkt.
  - Löst die bisherige eigenständige `/account`-Seite ab.

### Auth-Seiten

Fünf neue Vollseiten-Routen ersetzen das bisherige Auth-Modal auf der
Startseite (Chat bleibt anonym nutzbar, "Anmelden" im User-Bereich der
App-Shell verlinkt jetzt auf `/login` statt ein Modal zu öffnen):

| Route | Block-Vorlage | Anmerkung |
|---|---|---|
| `/login` | Split mit Foto (wie `magic-link2`/`reset-password2`) | E-Mail+Passwort, Links zu Passwort-vergessen/Magic-Link, "Mit Google anmelden" |
| `/signup` | `signup2` (zentriert, Logo) | E-Mail+Passwort, Link zu Login |
| `/magic-link` | `magic-link2` (Split mit Foto) | nur E-Mail-Feld |
| `/reset-password` | `reset-password2` (Split mit Foto) | neues Passwort setzen, ersetzt den bestehenden Route-Ordner |
| `/verify-email` | `verify-email2`-Layout, **Inhalt abweichend** | siehe unten |

**Abweichung `verify-email2`:** Der Block ist für einen manuell
eingetippten 6-stelligen Code gebaut. Das Backend arbeitet aber
token-link-basiert (`GET /v1/accounts/verify-email?token=...`, automatisch
beim Öffnen eines E-Mail-Links eingelöst). Übernommen wird nur das
visuelle Split-Layout; statt des Code-Eingabefelds zeigt die Seite einen
Status (wird bestätigt… / bestätigt / ungültiger Link + erneut senden).
Das Backend wird dafür nicht geändert.

Alle Formulare verwenden weiterhin die bereits vorhandenen
Auth-BFF-Routen (`/api/auth/login`, `/api/auth/register`,
`/api/auth/magic-link/request` + `/confirm`,
`/api/auth/password-reset/request` + `/confirm`,
`/api/auth/google/login` + `/callback`) — keine neue Backend-Logik.

### Suche & Dokument-Detail

Bestehende Struktur/Logik bleibt unverändert. Nur die verwendeten
Komponenten (Input, Button, Card, Pagination, Badge) und Farben wechseln
auf das neue Theme, und beide Seiten laufen künftig innerhalb der neuen
App-Shell statt freistehend.

## Datenfluss

Keine neuen Backend-Endpunkte. Neue/geänderte shadcn/ui-Abhängigkeiten
(`sidebar`, `collapsible`, `dropdown-menu`, `scroll-area`, `separator`,
`label`, `select`, `textarea`, `popover`, ggf. `card`) werden über die
shadcn-CLI installiert, die referenzierten `@shadcnblocks`-Blöcke über
dieselbe CLI geholt und danach an unsere echten Daten/Routen angepasst
(Demo-Daten der Blöcke werden vollständig ersetzt).

## Fehlerbehandlung

- Auth-Seiten: Formularvalidierung via `zod` (bereits Teil der Blöcke),
  bestehende BFF-Fehlerantworten werden inline angezeigt (Muster aus der
  bisherigen Account-Seite wiederverwendet).
- `/verify-email`: fehlender/ungültiger/abgelaufener Token zeigt einen
  expliziten Fehlerzustand mit "Erneut senden"-Option statt eines stillen
  Fehlschlags.
- Profil-Overlay: bestehende Fehlerbehandlung je Abschnitt (z. B.
  Sessions-Liste, Export) wird unverändert übernommen, nur neu gestylt.

## Testkonzept

- Bestehende Playwright-E2E-Suite (`npm run test:e2e`) muss für neue
  Routen (Auth-Vollseiten statt Modal, `/account` → Overlay,
  `/chats` entfällt) aktualisiert werden.
- Visueller Smoke-Test je neu gestalteter Seite nach der Umsetzung
  (Playwright-Screenshot, wie in dieser Session bereits gegen die
  laufende App demonstriert), inklusive einmal Light- und einmal
  Dark-Mode.
- Toggle-Test: Light/Dark-Umschalter tatsächlich einmal betätigen und
  Persistenz über einen Reload prüfen (next-themes-Standardverhalten).

## Bezug zu Requirements und ADRs

| Requirement | Bezug |
|---|---|
| REQ-UI-001/002 | Chat-Oberfläche bleibt eigenständige Webanwendung, chat-basierte Interaktion unverändert funktional, nur neu gestaltet. |
| REQ-UI-003 | Quellenanzeige/-Verlinkung im Chat bleibt erhalten, nur visuell neu. |
| REQ-ACC-* | Chat/Suche bleiben ohne Konto nutzbar; Auth wird nur zugänglicher (eigene Seiten statt Modal), keine neue Kontopflicht. |
| REQ-DIST-003 | Mandanten-Branding-Infrastruktur bleibt bestehen, wird in diesem Teilprojekt nicht verdrahtet — siehe Offene Punkte. |

## Offene Punkte / Folgearbeiten

- **Mandanten-Branding-Wiederanbindung.** Falls REQ-DIST-003 später aktiv
  gebraucht wird, muss `NORMLY_BRAND_COLOR_HSL` auf die neuen
  `--primary`/`--primary-foreground`-Variablen umgezogen werden — bewusst
  nicht Teil dieses Teilprojekts.
- **Suche/Dokument-Detail eigenes Blocklayout.** Aktuell nur
  Theme-Anpassung; ein eigener Gestaltungsdurchgang für diese beiden
  Seiten ist eine spätere, separate Aufgabe.
- **Echte Notification-Funktion.** Die Glocke im Header ist heute reiner
  Platzhalter.
- **Exakter Öffnungs-Mechanismus des Profil-Overlays** (Client-State,
  Intercepting Route oder Query-Parameter für Deep-Links) wird beim
  Schreiben des Implementierungsplans entschieden, nicht hier.
- **Exakte Abschnitts-Reihenfolge/-Bezeichnung im Profil-Overlay** ebenso
  Implementierungsdetail.
