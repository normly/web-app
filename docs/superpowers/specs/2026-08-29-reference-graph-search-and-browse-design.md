# Referenzgraph-Suche/-Browsing — Design

Sub-Projekt 2 des Frontends. Sub-Projekt 1 (App-Grundgerüst + Chat) ist abgeschlossen und
in `main` gemergt. Dieses Dokument beschreibt Suche, Browsing nach Herausgeber und eine
klickbare Dokumentdetailseite über den bestehenden `api/`-Dienst — ohne Sprachmodell.

## Entschieden mit dem Auftraggeber

1. **Funktionsumfang:** Suche + Dokumentdetailseite mit Graph-Browsing (Verweise,
   Gültigkeitsstatus) + eigene Browse-Ansicht nach Herausgeber, unabhängig von einer
   Sucheingabe.
2. **Ratenbegrenzung:** Jetzt eine einfache serverseitige Ratenbegrenzung in `api/`
   mitbauen (Postgres-gestützt), statt sie weiter als offenen Punkt zu verschieben —
   die durchsuchbare Katalogansicht ist ein deutlich attraktiveres Ziel für
   automatisierte Massenabfragen als der bisherige Chat.
3. **Sitzungsmerkmal für die Ratenbegrenzung:** REQ-ACC-003 verlangt die Zählung
   "anhand eines vergebenen Sitzungsmerkmals in Verbindung mit der Herkunftsadresse"
   — nicht Herkunftsadresse allein. Statt das als offenen Punkt stehen zu lassen,
   vergibt das Frontend-BFF einen neuen, eigenständigen anonymen Identifier-Cookie
   (`normly_anon_id`, getrennt von Chat-/Konto-Sitzung, nur für Ratenbegrenzung
   gedacht), der bei jedem `api/`-Aufruf als Header mitgeschickt wird. `api/`s
   Ratenbegrenzung schlüsselt auf (Anon-Id + Herkunftsadresse) statt nur
   Herkunftsadresse.
4. **Jurisdiktion:** Wird app-weiter Zustand (neuer `normly_jurisdiction`-Cookie,
   analog zum bestehenden `normly_locale`), gilt für Chat **und** Suche/Browsing
   gemeinsam. Behebt nebenbei die bisher fest kodierte `"DE"`-Vorgabe im Chat-Aufruf.
   Start-Auswahl: DE (Default) und EU — beide bereits in vorhandenen Testdaten
   vertreten.

## Architektur

Zwei Bausteine: eine kleine Backend-Erweiterung in `api/` (neuer Such-/Browse-Endpunkt
plus Ratenbegrenzung) und neue Frontend-Seiten nach demselben BFF-Muster wie
Sub-Projekt 1 — kein direkter Client-Zugriff auf `api/`, jeder Aufruf läuft über einen
Next.js Route Handler unter `/api/*`.

### Backend (`api/`)

**Neuer Endpunkt `GET /v1/documents/search`** — deckt Volltextsuche und
Browse-nach-Herausgeber mit einem Endpunkt ab, statt zwei separate zu bauen:

- Query-Parameter: `jurisdiction` (Pflicht, wie bei allen bestehenden Endpunkten),
  `q` (optional, Freitext über `DocumentDesignation.designation` und
  `DocumentTitle.title`, `ILIKE`-basiert — kein Volltextindex nötig für den aktuellen
  Datenumfang), `issuer` (optional, exakter Filter auf `DocumentDesignation.issuer`),
  `limit` (Default 20, Obergrenze 100), `offset` (Default 0).
- Antwort: `{ results: list[DocumentResponse], total: int }` — Wiederverwendung des
  bestehenden `DocumentResponse`-Schemas statt eines neuen, fast identischen
  Summary-Typs (YAGNI).
- Rechtegate: dieselbe jurisdiktionsgebundene Sichtbarkeitsprüfung wie die
  bestehenden Endpunkte (`get_document_for_jurisdiction`-Äquivalent pro Treffer) —
  nur was der Einzelabruf ohnehin durchließe, taucht in der Trefferliste auf.
- Baut auf `DocumentRepository.list_documents_for_jurisdiction` auf — im Protokoll
  bereits als der sanktionierte Pfad für genau diesen Zweck dokumentiert, aber
  bislang an keinem Router verdrahtet. Die Repository-Schicht bekommt eine
  Erweiterung um `q`/`issuer`-Filter und Pagination — keine neue Abstraktion, kein
  Bruch von ADR-006 (Datenbankzugriff nur über die Repository-Schicht).

**Ratenbegrenzung** — deckt REQ-ACC-003 jetzt vollständig ab (Sitzungsmerkmal **und**
Herkunftsadresse gemeinsam), nicht nur einen Teilaspekt:

- Postgres-gestützter Zähler (kein Redis — nicht Teil des freigegebenen Stacks nach
  CLAUDE.md; Postgres ist ohnehin die gemeinsame Datenhaltung und funktioniert daher
  korrekt auch über mehrere `api/`-Replicas hinweg, anders als ein reiner
  In-Memory-Zähler pro Prozess).
- Schlüssel: die Kombination aus einem anonymen Sitzungsmerkmal (siehe unten) und der
  Herkunftsadresse, ausgelesen aus `X-Forwarded-For` (vom vorgeschalteten Reverse
  Proxy gesetzt) mit Fallback auf die direkte Verbindungsadresse.
- **Sitzungsmerkmal:** `api/` selbst bleibt bewusst zustandslos — die Vergabe eines
  Anonym-Identifiers passt konzeptionell an den Rand der Anwendung, nicht in den
  Kern-Datendienst. Das Frontend-BFF vergibt daher beim ersten Besuch einen neuen,
  eigenständigen Cookie `normly_anon_id` (httpOnly, zufälliger Wert, ~1 Jahr Laufzeit
  — getrennt von `normly_session`/`normly_account_session`, ausschließlich für
  Ratenbegrenzung, keine Verknüpfung zu Chat-Verlauf oder Konto) und reicht ihn bei
  jedem `api/`-Aufruf als Header `X-Normly-Anon-Id` durch. `api/`s
  Ratenbegrenzungs-Dependency liest diesen Header, falls vorhanden, und schlüsselt
  auf `(anon_id, Herkunftsadresse)`; fehlt der Header (z. B. ein hypothetischer
  künftiger Direktzugriff ohne das Frontend-BFF), fällt sie auf die Herkunftsadresse
  allein zurück, statt die Anfrage abzulehnen.
- Festes Zeitfenster (60 anonyme Anfragen/Minute je Schlüssel, über alle
  `api/`-Endpunkte hinweg, nicht nur die Suche) als wiederverwendbare
  FastAPI-Dependency.

### Frontend

**Anonym-Identifier für die Ratenbegrenzung:** Da Next.js Server Components während
des Renderns keine Cookies setzen können, übernimmt das eine neue, minimale
`middleware.ts` (bislang nicht vorhanden im Projekt) — läuft vor jeder Anfrage,
prüft auf `normly_anon_id` und setzt ihn bei Fehlen einmalig. Damit ist der Cookie
unabhängig davon gesetzt, welche Seite zuerst besucht wird, ohne dass jeder einzelne
BFF-Route-Handler diese Logik dupliziert.

**Neue Seiten:**
- `/search` — Sucheingabe + paginierte Trefferliste, Filter nach Herausgeber. Ohne
  Sucheingabe, nur mit gesetztem Herausgeber-Filter, deckt dieselbe Seite "Browse
  nach Herausgeber" ab — keine separate Seite dafür nötig.
- `/documents/[id]` — Detailseite: Bezeichnungen/Titel/Quelle (`GET
  /v1/documents/{id}`), Gültigkeitsstatus (`.../validity`) und ausgehende Verweise
  gruppiert nach Kantentyp (`.../edges`). Jeder Verweis verlinkt auf die jeweilige
  Ziel-Detailseite — der Referenzgraph wird klickbar durchquerbar, nicht nur
  strukturiert gespeichert.

**Neue BFF-Route-Handler** (gleiches Muster wie das bestehende
`api/documents/[id]/route.ts`, reine Proxys mit Statuscode-Durchreichung):
`GET /api/documents/search`, `GET /api/documents/[id]/edges`,
`GET /api/documents/[id]/validity`. Alle Pfad- und Query-Werte werden von Anfang an
mit `encodeURIComponent()` behandelt — Sub-Projekt 1 hatte hier eine reale
Path-Traversal-Lücke, die erst im Abschluss-Review gefunden wurde; dieses Mal wird
korrekt encodiert gebaut, nicht nachträglich gepatcht.

**Neue UI-Bausteine** (shadcn/ui-Stil, wie die bestehenden vier — Button/Input/
Dialog/Tabs): eine einfache Tabelle/Liste für Trefferlisten, eine
Pagination-Komponente, ein `Badge` für Kantentyp/Gültigkeitsstatus. Kein
Autocomplete/Command-Palette — zusätzlicher Scope ohne SRS-Vorgabe.

**`JurisdictionSwitcher`** im bestehenden `AppHeader`, analog zum `LocaleSwitcher`:
setzt einen `normly_jurisdiction`-Cookie (nicht httpOnly, wie `normly_locale` — reiner
UI-Zustand, kein Sicherheitsmerkmal), gelesen server-seitig in `layout.tsx`. Der
Chat-Aufruf in `home-page-content.tsx` liest ab jetzt diese Jurisdiktion statt der
fest kodierten `"DE"`.

**i18n:** neuer `search`-Namensraum in `de.json`/`en.json` für Sucheingabe,
Leerzustand, Paginierung, sowie menschenlesbare DE/EN-Bezeichnungen für die fünf
`EdgeType`-Werte (references/replaces/withdrawn_by/based_on_law/adopted_from) und die
drei `ValidityResponse`-Status (valid/replaced/withdrawn).

## Datenfluss

**Suchzyklus:**
```
Eingabe /search → GET /api/documents/search?q=...&jurisdiction=<Cookie>
  → api/'s neuer Endpunkt (Ratenbegrenzung-Dependency zuerst)
  → Trefferliste (DocumentResponse[] + total)
Klick auf Treffer → /documents/[id]
  → drei parallele BFF-Aufrufe: Detail, Edges, Validity
  → Detailseite mit anklickbaren Verweisen zu weiteren Detailseiten
```

**Jurisdiktionswechsel:** `JurisdictionSwitcher` setzt Cookie clientseitig
(`document.cookie`, wie der bestehende `LocaleSwitcher`) → nächster Server-Request
(Seitenwechsel oder manueller Reload) liest den neuen Wert in `layout.tsx` →
sowohl Chat- als auch Such-/Browse-Aufrufe verwenden ihn.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Ratenbegrenzung überschritten | `api/` antwortet 429, BFF reicht durch, UI zeigt Meldung mit Verweis auf Anmeldung (REQ-ACC-003: "bei Erreichen des Kontingents wird auf die Anmeldung verwiesen") |
| Leere Trefferliste | Eigener Leerzustand, kein Fehler |
| Dokument nicht gefunden / nicht rechtefreigegeben | Wie bei der bestehenden Zitat-Auflösung: 404 wird nicht unterschieden (bewusstes Bestehendes Verhalten von `api/`, verhindert Rückschluss auf Existenz gesperrter Inhalte); UI zeigt generisches "nicht gefunden" |
| `api/` nicht erreichbar | Wie im Chat-BFF: Statuscode durchgereicht, UI zeigt generische Fehlermeldung |

## Testkonzept

- **`api/`:** Pytest für den neuen Such-Endpunkt (Treffer/Filter/Pagination/
  Rechtegate) und für die Ratenbegrenzung — inklusive eines Tests, der das
  Zeitfenster tatsächlich auslöst und den 429 verifiziert, sowie eines Tests, der
  bestätigt, dass zwei unterschiedliche `X-Normly-Anon-Id`-Werte von derselben
  Herkunftsadresse getrennt gezählt werden (nicht nur die Dependency-Verdrahtung).
- **`core/`:** Repository-Test für die erweiterte `list_documents_for_jurisdiction`
  (Filter- und Pagination-Verhalten), gleiches Muster wie die bestehenden
  Repository-Tests.
- **`frontend/`:** Test für die neue `middleware.ts` (`normly_anon_id` wird bei
  fehlendem Cookie gesetzt, bei vorhandenem Cookie unverändert gelassen),
  Vitest-Unit-Tests für die neuen BFF-Routen (inkl. eines Encoding-Tests nach dem
  Vorbild des in Sub-Projekt 1 gefundenen Path-Traversal-Fixes) und Komponenten,
  Playwright-Erweiterung der bestehenden E2E-Suite um einen Such-und-Detail-Durchlauf.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-ACC-001 (anonyme Basisnutzung) | Suche/Browsing/Referenzgraph-Abfrage funktionieren ohne Konto |
| REQ-ACC-003 (Kontingent anonyme Nutzung) | Ratenbegrenzung deckt Sitzungsmerkmal (`normly_anon_id`) **und** Herkunftsadresse gemeinsam ab, wie im Wortlaut gefordert |
| REQ-GRAPH-001/003/004 | Neuer Endpunkt bleibt hinter der Repository-Abstraktion, rein deterministisch, kein Modellaufruf |
| REQ-GRAPH-005 (Internationalisierung) | Jurisdiktions-Auswahl macht die von Anfang an mehrsprachig/mehrrechtsraum-fähige Graphmodellierung erstmals in der UI sichtbar |
| REQ-GRAPH-006 (rechtsraumabhängige Klassifikation) | Suchendpunkt filtert wie alle bestehenden Endpunkte strikt nach `jurisdiction` |
| REQ-SEC-004 (Schutz vor Massenextraktion) | Teilweise: Ratenbegrenzung ja, Anomalieerkennung/Protokollauswertung nein — offener Punkt |
| ADR-006 (Speichertechnologie austauschbar) | Suchfilterung bleibt in der Repository-Schicht, keine SQL-Fachlogik im Router |
| ADR-017 (anonyme Nutzung, gemeinsame Infrastruktur mit Ratenbegrenzung) | Die neue Dependency ist bewusst wiederverwendbar für weitere `api/`-Endpunkte angelegt, nicht nur für die Suche |

## Offene Punkte

- Volle Anomalieerkennung/protokollbasierte Auswertung je Herausgeber (REQ-SEC-004)
  — nur die Ratenbegrenzung ist Teil dieses Sub-Projekts.
- Weitere Rechtsräume über DE/EU hinaus — Auswahl ist als einfache, erweiterbare
  Liste angelegt, nicht dynamisch aus dem Backend ermittelt.
- Volltextindex (statt `ILIKE`) — für den aktuellen Datenumfang ausreichend; wird
  relevant, sobald der Katalog deutlich wächst.
