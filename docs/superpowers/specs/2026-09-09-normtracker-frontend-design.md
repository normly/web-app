# Design: Frontend (Normtracker-Grundgerüst, Teil 5/5)

## Kontext

Alle vier Backend-Teilprojekte des Normtracker-Grundgerüsts sind fertig und
gemergt: Work-Entität (PR #11), Semantische Suche (PR #12), Dokument-Detail
(PR #13) und Watchlist/Notification (PR #18), plus zwei eingefügte
Voraussetzungs-Teilprojekte (Editionswechsel-Erkennung PR #14,
editions-bewusste Identitätsauflösung PR #15). Die gesamte Backend-Oberfläche,
die dieses letzte Teilprojekt darstellen muss, existiert bereits: Work-
gruppierte hybride Suche (`search_works_for_jurisdiction`), eine
Dokument-Detail-Seite mit Editionshistorie/nationalen Fassungen/Referenzen/
Rechten, und die Watchlist/Notification-Oberfläche (Favoriten-Herz, Glocke,
Profileinstellung) — letztere bereits mit echten Daten verdrahtet, aber
bewusst ohne eigenes Design gebaut ("kein neues Design, nur echte Daten",
per eigener Teilprojekt-4-Festlegung).

Dieses Teilprojekt ist das letzte der 5-Teile-Roadmap und übernimmt die
Rolle der ursprünglich pausierten Plan 6 ("Suche & Dokument-Detail",
Retheme-only) aus dem separaten 6-Plan-shadcn-Redesign — mit größerem Umfang,
da seither drei weitere Backend-Teilprojekte reale Inhalte geschaffen haben,
die Plan 6 noch nicht kannte. Die Plans 1-5 dieses Redesigns (Theme-Fundament,
App-Shell, Chat-Seite, Profil-Overlay-Struktur, Auth-Seiten) sind bereits
fertig und liefern die Grundlage (shadcn-Default-Theme, Light/Dark, App-Shell
mit Sidebar, `PageHeader`-Muster, Profil-Overlay als Dialog). Für
Suche/Dokument-Detail/Watchlist-UI wurde damals **bewusst kein
Referenz-Block** festgelegt — das ist die zentrale, hier neu zu treffende
Entscheidung.

## Ziel dieses Teilprojekts

Drei bislang funktional fertige, aber optisch underdesignte Bereiche
bekommen einen echten Gestaltungsdurchgang, alle im selben Teilprojekt:

1. **Dokument-Detail-Seite** — zweispaltiges Layout statt einspaltiger
   nackter Flex-Abschnitte.
2. **Suche** — Ergebnisliste als echte Tabelle statt nackter `<ul>`.
3. **Watchlist/Notification-UI** — Glocken-Popover-Inhalt und
   Profil-Benachrichtigungssektion bekommen echte, gestylte Bausteine statt
   Rohkomponenten.

Alle drei Bereiche bauen ausschließlich auf bereits bestehenden
Backend-Endpunkten und -Datenformen auf — reines Frontend-Remapping.

## Nicht-Ziele

- **Keine neuen Backend-Endpunkte oder Datenmodell-Änderungen.** Jede
  Komponente bindet weiterhin exakt dieselben BFF-Routen/Response-Shapes an,
  die schon existieren.
- **Keine neuen Filter, Sortieroptionen oder Suchfunktionen.** Filterleiste
  (Freitext + Herausgeber) und Pagination bleiben strukturell unverändert.
- **Keine neue Notification-Trigger-Logik.** `notify-watchers` und die
  Rechte-/Editions-Erkennung bleiben unverändert; nur die Darstellung der
  bereits erzeugten Notifications ändert sich.
- **Keine Änderungen an App-Shell, `PageHeader`-Rahmen (nur dessen
  Glocken-Popover-*Inhalt*), Chat-Seite oder Auth-Seiten.** Diese sind aus
  Plans 1-5 bereits fertig und werden hier nicht angefasst.
- **Kein visueller Regressionstest (Playwright-Screenshots).** Es existiert
  bislang keine E2E-Test-Infrastruktur in dieser Roadmap; die bestehenden
  Vitest-Unit-Tests werden erweitert, kein neues Test-Tooling eingeführt.
- **Keine eigene Rechtsraum-/Sprachumschalter-Überarbeitung.**
  `JurisdictionSwitcher`/`LocaleSwitcher` bleiben unverändert.

## Architektur

### Dokument-Detail-Seite

Referenz-Block: **`resource3`** (zweispaltige Ressourcen-Seite mit
Breadcrumb und fixierter Seitenleiste), mit einer expliziten Abweichung: das
Favoriten-Herz sitzt **direkt neben dem Titel**, nicht in der Seitenleiste
(wie im Original-Block dessen Social-Share-Zeile).

- **Kopfbereich**: Breadcrumb (Start › aktuelles Dokument), Titel-Zeile mit
  primärer Bezeichnung, Favoriten-Herz-Toggle direkt daneben, darunter der
  Gültigkeits-Badge.
- **Hauptspalte** (links, Großteil der Breite): Editionshistorie und
  nationale Fassungen als gestylte Zeilen — jede Zeile: Status-Badge
  (gültig/ersetzt/zurückgezogen) + Bezeichnung als Link, angelehnt an das
  `changelog8`-Zeilenmuster (Badge + Text statt nackter `<li>`). Referenzen
  darunter im selben Zeilenstil, aber mit Kanten-Typ-Badge statt
  Status-Badge (wie heute).
- **Seitenleiste** (rechts, beim Scrollen fixiert — `md:sticky md:top-20`,
  Vorbild `resource3`): Rechte-Checkliste (✓/✗ pro Berechtigung
  `may_process`/`may_index_fulltext`/`may_cite_passages`/`may_export_free`,
  Vorbild `resource3`s "Key Features"-Checkliste mit `CheckCircle2`), darunter
  ein "Quelle öffnen"-Button, der auf `documentDetail.source.retrieval_path`
  verlinkt (ersetzt den heutigen nackten Link).
- Neue Registry-Abhängigkeiten: `breadcrumb`, `separator` (falls noch nicht
  installiert — prüfen, `avatar`/`button` sind bereits vorhanden).
- Alle bestehenden `data-testid`-Anker (`validity-badge`, `edition-history-
  list`, `national-adoptions-list`, `references-list`, `watchlist-toggle`)
  bleiben erhalten, damit bestehende Tests ohne Verhaltensänderung nur ihr
  Markup-Umfeld anpassen müssen, nicht ihre Kernaussage.

### Suche

Referenz-Block: **`list1`** ("Multi-column data table"), reduziert auf die
tatsächlich vorhandenen Daten. Das Original hat 6 Spalten (Icon, Kategorie,
Beschreibung, Jahr, Angebot, Segment) — unsere `WorkSearchHit`-Antwort hat
nur Herausgeber, Bezeichnung und `other_editions_count`. Übernommen wird die
**Tabellenstruktur** (`Table`/`TableHeader`/`TableBody`/`TableRow`/
`TableCell` aus shadcn/ui), nicht die Spaltenanzahl:

- Spalte 1: Herausgeber (`best_match.origin_issuer`).
- Spalte 2: Bezeichnung (primäre Designation, Link zur Dokument-Detail-Seite)
  plus Badge "+N Ausgaben" wenn `other_editions_count > 0`.
- **Keine Icon-Spalte** — im Original-Block vorhanden, für uns nicht
  relevant, bewusst weggelassen (explizite Nutzer-Entscheidung).
- Filterleiste (Freitext-Input, Herausgeber-Input, Suchen-Button) und
  `Pagination`-Komponente bleiben strukturell exakt wie heute — nur die
  Ergebnisliste selbst wird zur Tabelle.
- Leerer-Zustand: eigene, dezent gerahmte Karte statt reinem
  `<p>`-Absatz.
- Neue Registry-Abhängigkeit: `table` (shadcn/ui-Basiskomponente, nicht
  `@shadcnblocks`).

### Watchlist/Notification-UI

Zwei bereits funktionierende, aber underdesignte Bausteine bekommen echte
Gestaltung — keine neue Struktur, keine neue Logik:

**Glocken-Popover** (`page-header.tsx`): der `Popover`/`PopoverTrigger`/
`PopoverContent`-Rahmen bleibt exakt bestehen (Plans 1-5), nur der Inhalt von
`PopoverContent` wird zu echten Listen-Zeilen im Aktivitäts-Feed-Stil
(Vorbild `list-panel-list-activity-feed`, ohne Avatar/`ItemMedia` — stattdessen
ein kleines Icon je Trigger-Typ, analog zu den bestehenden Kanten-Typ-Icons
in der Dokument-Detail-Seite): Icon + Titel (aus dem bestehenden
`TRIGGER_TYPE_KEYS`-Mapping) + Zeitangabe (relative Zeit aus `createdAt`) +
blauer Punkt für ungelesen (`readAt === null`). Klick auf eine Zeile ruft
weiterhin `markRead` auf, exakt wie heute.

**Profil-Benachrichtigungssektion** (`notification-preference-section.tsx`):
komplett umgebaut auf **`settings-notifications2`** ("Simple Switch List").
Der Block nutzt unabhängige `Switch`-Toggles statt eines 4-Wege-Radios —
explizite Nutzer-Entscheidung, zwei unabhängige Kanal-Switches statt einer
Auswahl aus vier Optionen:

- Switch "In der Software" (`in_app` an/aus)
- Switch "Per E-Mail" (`email` an/aus)
- **Beide vollständig unabhängig voneinander schaltbar** (explizit
  bestätigt, kein Master-Schalter-Verhältnis).
- Clientseitige Zustands-Abbildung auf das bestehende 4-Werte-Backend-Enum
  (`NotificationPreference`), unverändert:
  - beide aus → `none`
  - nur "In der Software" an → `in_app`
  - nur "Per E-Mail" an → `email`
  - beide an → `both`
- Jeder Switch-Klick löst sofort ein `PATCH /api/account/profile` aus
  (gleiche Route, gleicher `response.ok`-geprüfter Fehlerpfad wie heute),
  mit dem aus beiden Switch-Zuständen berechneten `notification_preference`-
  Wert — kein separater "Speichern"-Button.
- Neue Registry-Abhängigkeit: `switch` (shadcn/ui-Basiskomponente).

**Favoriten-Herz** (`document-detail-content.tsx`): keine eigene
Block-Vorlage nötig (einfacher Icon-Button), aber neue Platzierung direkt
neben dem Titel (siehe Dokument-Detail-Abschnitt oben) statt in der
Rechte-Seitenleiste.

## Datenfluss

Keine neuen Backend-Endpunkte. Betroffene, unveränderte BFF-Routen:
`/api/documents/{id}`, `/api/documents/{id}/edges`, `/api/documents/{id}/
validity`, `/api/documents/{id}/work`, `/api/documents/{id}/rights`,
`/api/documents/search`, `/api/account/watchlist` (GET/POST/DELETE),
`/api/account/notifications` (GET/PATCH), `/api/account/profile` (PATCH).
Neue/geänderte shadcn/ui-Abhängigkeiten (`table`, `switch`, `breadcrumb`,
`separator`) werden über die shadcn-CLI installiert; die referenzierten
`@shadcnblocks`-Blöcke (`resource3`, `list1`, `settings-notifications2`)
über dieselbe CLI geholt und an unsere echten Daten/Routen angepasst
(Demo-Daten der Blöcke werden vollständig ersetzt, wie bei Plans 1-5).

## Fehlerbehandlung

Keine neue Fehlerbehandlung nötig — jede Komponente übernimmt exakt den
bestehenden Fehlerpfad ihrer jeweiligen Datenquelle unverändert (z. B.
`toggleWatch`s `response.ok`-Prüfung mit Fehlermeldung, Such-Ratenlimit-
Anzeige, Profil-Sektionen-Fehlermeldungen). Die Switch-basierte
Benachrichtigungssektion übernimmt das bestehende Fehlerverhalten der
`PATCH /api/account/profile`-Route 1:1 (Fehler-Text bei nicht-`ok`-Antwort,
kein optimistisches Umschalten bei Fehlschlag — gleiches Prinzip wie beim
Favoriten-Herz-Fix aus Teilprojekt 4).

## Testkonzept

Bestehende Vitest-Suiten werden erweitert, nicht ersetzt:

- `document-detail-page.test.tsx`: bestehende Assertions bleiben inhaltlich
  gleich (Editionshistorie/Fassungen/Referenzen/Rechte/Watchlist-Toggle
  vorhanden und funktional), nur Selektoren/Markup-Erwartungen an das neue
  zweispaltige Layout angepasst. Neue Assertion: Herz-Button sitzt im
  Titel-Bereich, nicht in der Seitenleiste.
- Such-Test(s): bestehende Assertions zu Treffern/Pagination/Leerzustand
  bleiben inhaltlich gleich, Selektoren auf die neue `Table`-Struktur
  angepasst (`role="table"`/`role="row"` statt `<ul>`/`<li>`).
- `page-header.test.tsx`: bestehende Assertions (leer/anonym/reale Liste/
  `markRead`) bleiben inhaltlich gleich, nur die gerenderten Zeilen-Elemente
  ändern sich entsprechend dem neuen Aktivitäts-Feed-Markup.
- `notification-preference-section.test.tsx`: komplett neu geschrieben für
  die zwei-Switches-Interaktion — beide Switches unabhängig umschaltbar,
  jede der vier Kombinationen sendet den korrekten `notification_preference`-
  Wert, Fehlerzustand bei nicht-`ok`-Antwort.

Kein visueller Regressionstest (siehe Nicht-Ziele).
