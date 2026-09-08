# Design: Editions-bewusste Identitätsauflösung

## Kontext

Das gerade gemergte Sub-project "Editionswechsel-Erkennung in Ingestion-
Adaptern" (PR #14) hat EUR-Lex und DGUV beigebracht, echte `REPLACES`-
Kanten aus Signalen in ihren jeweiligen Quelldaten zu erzeugen. Während
dieser Arbeit wurde ein tieferliegender, vorher unerreichbarer Defekt in
`core/src/normly_core/pipeline/identity.py` entdeckt und provisorisch
über einen Guard in `references.py` entschärft (self-referenzielle Kante
verhindert), aber die eigentliche Ursache blieb bewusst offen: **`identity.
resolve()` ist editions-blind.**

Konkret: `resolve()` entscheidet rein über String-Gleichheit von
`(issuer, raw_designation)`, ob ein eingehendes Dokument dasselbe wie ein
bereits bekanntes ist. `record.content_hash` wird dabei nirgends gelesen —
Content-Hash-Vergleich passiert eine Ebene höher in `runner.py`, aber nur
um eine *byte-identische* Re-Lieferung derselben Datei zu überspringen.
Sobald die Bytes auch nur geringfügig abweichen (eine echte neue Edition),
entsteht eine neue `Delivery`, aber `resolve()` matched trotzdem auf
dieselbe `(issuer, designation)` und behandelt die neue Edition als
*Update* des bestehenden Dokuments — nicht als neues.

Das betrifft konkret DGUV: jede reale DGUV-Vorschrift trägt ein
"vom `<Datum>`"-Ausgabedatum, das der Adapter bereits per Regex parst
(`_ISSUE_DATE_PREFIX`) — aber nur, um es beim Titel-Zeilen-Heuristik-Check
wegzuschneiden, nie um es als eigenständigen Wert zu erfassen. `RawRecord`
hat aktuell kein `edition`-Feld, `runner.py` setzt
`add_designation(..., edition=None, ...)` für jeden Adapter fest verdrahtet.
Für Sub-project 4 (Watchlist/Notification) ist das ein echtes Problem: eine
neue DGUV-Vorschrift-Auflage — der Hauptfall, für den DGUV's eigene
Editionswechsel-Erkennung gebaut wurde — löst aktuell **keine** erkennbare
neue Edition aus. Das System schreibt die neue Auflage einfach als
zusätzliche, liefer-gebundene Segmentmenge auf dasselbe bestehende
`Document`.

`find_by_designation(issuer, designation)` — genutzt sowohl von
`identity.resolve()` als auch von `references.extract_references()` für
Kantenziel-Lookups — filtert ebenfalls nur auf
`DocumentDesignationORM.issuer`/`.designation`; `DocumentDesignationORM.
edition` und `DocumentORM.edition` werden komplett ignoriert. Ein
DB-weiter Unique-Constraint `uq_designation_issuer_designation` auf
`(issuer, designation)` (ohne Edition) würde zudem jeden Versuch, zwei
Editionen als separate `DocumentDesignation`-Zeilen zu führen, mit einem
`IntegrityError` verhindern, selbst wenn `resolve()` korrigiert würde.

EUR-Lex ist von diesem Problem praktisch nicht betroffen: seine
Designationen kodieren die Edition bereits in der Zeichenkette selbst
(`"EN ISO 12100:2003"` vs. `"EN ISO 12100:2010"` sind unterschiedliche
Strings, `(issuer, designation)`-Gleichheit unterscheidet sie also
automatisch). BAuA hat aktuell keine Editionswechsel-Erkennung und bleibt
hier bewusst außen vor.

## Ziel dieses Teilprojekts

1. DGUV's bereits geparstes Ausgabedatum tatsächlich als Edition erfassen
   und bis zur Datenbank durchreichen.
2. `identity.resolve()` und `find_by_designation` editions-bewusst machen,
   sodass zwei Editionen derselben Designation als zwei getrennte
   `Document`s erkannt werden — ohne das bestehende Verhalten für
   Adapter/Aufrufer ohne Edition-Konzept (EUR-Lex, BAuA, unqualifizierte
   Vorgänger-Referenzen) zu verändern.
3. Beim Erkennen einer neuen Edition automatisch die richtige `work_id`
   übernehmen und eine `REPLACES`-Kante zur vorherigen Edition anlegen —
   damit eine neue DGUV-Auflage sofort ein echter, auffindbarer
   Editionswechsel ist, nicht nur ein neues, isoliertes Document.

## Nicht-Ziele

- **Kein Backfill** für bereits ingestierte Daten — nur Dev/Test-
  Datenbankstand, kein Produktivbestand zu berücksichtigen.
- **Keine Edition-Befüllung für EUR-Lex/BAuA.** EUR-Lex braucht sie nicht
  (Edition schon in der Designation kodiert); BAuA hat keine
  Editionswechsel-Erkennung und bleibt unverändert.
- **Kein genereller Fix für eine mögliche eigene Edition-Blindheit von
  BAuA** — BAuA ist von der gesamten Editionswechsel-Erkennung
  ausgeschlossen (siehe Vorprojekt-Spec), dieses Teilprojekt ändert daran
  nichts.
- **Keine Änderung an der bestehenden Inkrafttreten-Abschnitt-Erkennung**
  (`_extract_predecessor_reference`) — die läuft unverändert weiter für
  den Fall eines Vorgängers mit *anderer* Designation (Freitext-Alttitel
  oder moderne Designation eines anderen Regelwerks). Der neue
  Auto-REPLACES-Mechanismus in diesem Teilprojekt ist ein zusätzlicher,
  unabhängiger Pfad für den Fall *gleicher* Designation, andere Edition.

## Architektur

### 1. `RawRecord` bekommt ein neues Feld

`core/src/normly_core/pipeline/domain.py`, `RawRecord` (frozen dataclass):
neues optionales Feld `edition: str | None = None`. Generischer Kanal —
jeder Adapter kann ihn befüllen, nur DGUV tut es vorerst.

### 2. DGUV erfasst das Ausgabedatum wirklich

`core/src/normly_core/pipeline/adapters/dguv.py`: `_ISSUE_DATE_PREFIX`
bekommt eine Capture-Group um den Datumsteil. Diese wird in `_fetch_file`
(nicht nur in der bestehenden `_is_publication_title_line`-Heuristik)
angewendet, das gematchte Datum ISO-normalisiert (`"2013-11-01"`) und als
`RawRecord.edition` gesetzt. Fehlt das "vom `<Datum>`"-Muster (z. B. eine
Publikation ohne dieses Feld), bleibt `edition=None` — kein Fehler.

### 3. `find_by_designation` wird editions-bewusst

`DocumentRepository.find_by_designation` (Protocol in `domain.py`) bekommt
einen neuen optionalen Parameter: `edition: str | None = None`.

- Mit gesetzter `edition`: exaktes Matching auf
  `(issuer, designation, edition)`.
- Ohne `edition` (Default, deckt jeden bestehenden Aufrufer ab): liefert
  weiterhin `Document | None`, aber jetzt deterministisch — bei mehreren
  Editionen derselben Designation die **neueste** (nach `created_at`
  absteigend sortiert, `LIMIT 1`), statt eines unspezifizierten Treffers.
  Für Designationen mit nur einer Edition (der heutige Normalfall für
  EUR-Lex/BAuA und für DGUV vor diesem Teilprojekt) ändert sich nichts am
  Ergebnis.

Beide bestehenden Aufrufer (`identity.resolve()`, `references.
extract_references()`) rufen weiterhin ohne `edition`-Argument auf, außer
`identity.resolve()` selbst (siehe Punkt 4).

### 4. `identity.resolve()` erkennt Editionswechsel

`core/src/normly_core/pipeline/identity.py`: wenn `record.edition` gesetzt
ist, ruft `resolve()` zuerst `find_by_designation(issuer, designation,
edition=record.edition)` auf:

- Treffer → wie heute, `is_new=False` (exakte Re-Ingestion derselben
  Edition).
- Kein Treffer, aber `find_by_designation(issuer, designation)` (ohne
  Edition, liefert die neueste vorhandene Edition) findet trotzdem etwas
  → **neue Edition erkannt**: `is_new=True`, plus ein neues Feld auf
  `IdentityResolution`: `previous_edition_document_id: uuid.UUID | None`,
  gesetzt auf das gefundene (jetzt vorherige) Document.
- Kein Treffer überhaupt → `is_new=True`,
  `previous_edition_document_id=None` (echtes Erstauftreten dieser
  Designation, wie heute).

Ist `record.edition` nicht gesetzt (EUR-Lex, BAuA, DGUV-Publikationen
ohne erkennbares Datum), verhält sich `resolve()` exakt wie heute —
keine Verhaltensänderung für diese Fälle.

### 5. Runner: Work-Übernahme + Auto-REPLACES-Kante

`core/src/normly_core/pipeline/runner.py`: wenn
`result.previous_edition_document_id` gesetzt ist,

- wird das neue Document direkt mit `work_id` der vorherigen Edition
  angelegt (nicht über die RawReference-basierte
  `work_assignment.determine_work_assignment`-Maschinerie — die
  Editionskette *ist* per Definition dasselbe Regelwerk, kein
  Mehrdeutigkeitsfall),
- wird zusätzlich eine echte `REPLACES`-Kante vom neuen zum vorherigen
  Document über `edge_repo.create_edge(...)` angelegt (derselbe
  Mechanismus, den `references.py` für RawReference-basierte Kanten
  nutzt; `create_edge`s bestehende Dedup-Logik verhindert doppelte Kanten,
  falls die Inkrafttreten-Erkennung dieselbe Verbindung zusätzlich findet).

Dieser Pfad läuft unabhängig von, und zusätzlich zu, der bestehenden
`_extract_predecessor_reference`/`references.extract_references`-Kette.

### 6. DB-Migration

Neue Alembic-Migration: Unique-Constraint
`uq_designation_issuer_designation` auf `DocumentDesignationORM` von
`(issuer, designation)` auf `(issuer, designation, edition)` erweitert.
Reine Schema-Änderung ohne Backfill (nur Dev/Test-Stand, per
Nutzerentscheidung bestätigt).

## Tests

- `identity.py`: neuer Test für "gleiche `(issuer, designation)`, andere
  Edition, anderer `content_hash`" → `is_new=True`,
  `previous_edition_document_id` korrekt gesetzt. Bestehender Test für
  "keine Edition" bleibt unverändert grün (Regressionsschutz).
- `find_by_designation`: neuer Test für "mehrere Editionen, kein
  Edition-Parameter → liefert neueste"; bestehende edition-lose Aufrufe
  bleiben unverändert grün.
- DGUV-Adapter: neuer Test, dass das "vom `<Datum>`"-Datum korrekt als
  ISO-normalisiertes `RawRecord.edition` ankommt; Grenzfall ohne
  erkennbares Datum → `edition=None`, kein Fehler.
- End-to-End: zwei DGUV-PDFs mit identischer Designation, unterschiedlicher
  Edition, real durch die Pipeline — prüft neues Document, `work_id`
  identisch zur vorherigen Edition, echte `REPLACES`-Kante zwischen
  beiden.
- Migrationstest: bestätigt, dass der erweiterte Constraint zwei
  Editionen derselben Designation als getrennte `DocumentDesignation`-
  Zeilen zulässt.
- Kein Regressionsrisiko für EUR-Lex/BAuA-Tests — deren Aufrufe bleiben
  edition-los, ihr beobachtbares Verhalten ändert sich nicht.
