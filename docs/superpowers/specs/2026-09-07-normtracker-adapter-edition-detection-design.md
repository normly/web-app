# Design: Editionswechsel-Erkennung in Ingestion-Adaptern

## Kontext

Sub-project 1 hat die `Work`-Entität gebracht: mehrere `Document`-Zeilen
teilen sich ein `Work`, sobald eine `REPLACES`-, `WITHDRAWN_BY`- oder
`ADOPTED_FROM`-Kante zwischen ihnen entsteht — der Mechanismus dafür ist
fertig, getestet, gemergt (`core/src/normly_core/pipeline/references.py`,
`create_edge`, das automatische Work-Merge). Sub-project 3 baut die
Editionshistorie/nationale-Fassungen-Anzeige genau darauf auf.

Bislang emittiert aber **kein** Ingestion-Adapter jemals eine dieser drei
Kantentypen auf echten Daten. Der einzige Adapter, der überhaupt
`raw_references` setzt, ist `eur_lex.py`, und der immer nur mit
`EdgeType.BASED_ON_LAW` (Norm → zugrundeliegender Rechtsakt) — eine Kante,
die per Definition nie Work-Zugehörigkeit auslöst. Auf echten Daten bekommt
heute also jedes ingestierte Dokument sein eigenes 1:1-`Work`. Für den als
Sub-project 4 geplanten Watchlist/Notification-Baustein ("Nachricht bei
neuer Edition") ist das der Haupt-Auslöser — ohne ihn hätte dieses Feature
auf echten Daten praktisch keine Auslöser. Dieses Teilprojekt schließt genau
diese Lücke, als Voraussetzung für Sub-project 4.

## Recherche-Ergebnis: welche Adapter sind geeignete Kandidaten?

Drei Adapter existieren: `eur_lex.py`, `baua.py`, `dguv.py` (alle in
`core/src/normly_core/pipeline/adapters/`). Für jeden wurde geprüft, ob
seine **tatsächlich eingelesene Quelle** (nicht eine separate, nicht
angebundene Publikation) ein strukturell erkennbares Signal für
Editionswechsel enthält:

- **EUR-Lex — ja, bestätigt.** Die von der Kommission veröffentlichte
  "Summary of references of harmonised standards"-Tabelle (Docling-Tabelle,
  aktuell werden nur Spalten 1–3 gelesen) enthält in Spalte 10/11 ein
  Widerrufsdatum plus die OJ-Referenz des Widerrufs, und in Spalte 6 die
  OJ-Referenz der eigenen Veröffentlichung. Am echten Fixture-PDF
  verifiziert: `EN ISO 12100-1:2003`/`-2:2003` tragen in Spalte 11 exakt die
  OJ-Referenz, die `EN ISO 12100:2010` (eine andere Zeile derselben Tabelle)
  in Spalte 6 als eigene Veröffentlichungsreferenz trägt — ein direkter,
  strukturell verlässlicher Join.
- **DGUV — ja, bestätigt (mit Einschränkung, siehe unten).** Jede reale
  DGUV-Vorschrift endet mit einem eigenen §-Abschnitt "Inkrafttreten/
  Außerkrafttreten", der den Vorgänger explizit benennt. Verifiziert am
  echten PDF der DGUV Vorschrift 38 ("Bauarbeiten", Nov. 2019):
  > "Diese Unfallverhütungsvorschrift tritt am ersten Tag des auf die
  > Veröffentlichung folgenden Monats in Kraft. Gleichzeitig tritt die
  > Unfallverhütungsvorschrift „Bauarbeiten" vom September 1976 in der
  > Fassung vom Januar 1997 außer Kraft."

  `dguv.py` spaltet den Fließtext bereits heute in §-nummerierte Abschnitte
  auf — dieser Abschnitt liegt beim Parsen also schon isoliert vor.
- **BAuA/TRGS — nein, verworfen.** Die offizielle Bekanntmachung einer
  neuen TRGS-Fassung enthält zwar die Formulierung "ersetzt die TRGS 905
  Ausgabe März 2014" — aber nur in der separaten GMBl-Veröffentlichung.
  Verifiziert an einer echten TRGS-905-PDF (der Quelle, die `baua.py`
  tatsächlich einliest): sie enthält **keinen** Ersetzungshinweis, nur
  "Ausgabe: &lt;Datum&gt;". Eine neue Quelle (GMBl) anzubinden wäre ein
  eigenständiges Projekt, kein Adapter-Fix — bleibt hier außen vor.

## Ziel dieses Teilprojekts

`eur_lex.py` und `dguv.py` erweitern, sodass sie beim Erkennen eines
Editionswechsel-Signals in ihrer jeweiligen Quelle eine zusätzliche
`RawReference` mit `EdgeType.REPLACES` emittieren — zeigt vom neuen
(nachfolgenden) Dokument auf das alte (abgelöste), analog zur bestehenden
Richtungskonvention. `references.py`, `create_edge` und die
Work-Merge-Logik sind bereits generisch genug (dispatchen nur auf
`RawReference.edge_type`) und brauchen keine Änderung.

## Nicht-Ziele

- **Kein BAuA/TRGS-Fix.** Signal existiert nachweislich nicht im
  eingelesenen Dokument (siehe oben).
- **Keine neue Quelle.** Weder das GMBl noch sonst eine bislang nicht
  angebundene Publikation wird in diesem Teilprojekt angeschlossen.
- **Kein Backfill-Mechanismus.** Erneutes Ausführen der Ingestion ist laut
  CLAUDE.md idempotent — ein erneuter `ingest`-Lauf über bereits vorhandene
  PDFs erzeugt die neuen Kanten retroaktiv über den bestehenden
  `create_edge`/Work-Merge-Mechanismus. Kein eigenes Skript nötig.
- **Kein Watchlist/Notification-Code.** Bleibt das eigentliche nächste
  Sub-project — dieses hier ist nur dessen Voraussetzung.
- **Keine Änderung an `references.py`, `create_edge`, Work-Merge.** Bereits
  generisch, unverändert wiederverwendet.

## Architektur: EUR-Lex

`_fetch_file` liest heute Spalten 1 (ESO), 2 (Nummer), 3 (Titel) und baut
pro Zeile eine `BASED_ON_LAW`-Referenz. Erweiterung:

1. Zwei neue Spalten-Konstanten: Spalte 6 ("OJ reference for publication in
   OJ") und Spalte 11 ("OJ reference for withdrawal from OJ") — Indizes
   gegen das echte Fixture-PDF verifizieren, analog zur bestehenden
   Verifikation von Spalte 1–3.
2. **Zwei Durchläufe** über `document.tables` statt einem: der erste baut
   eine Map `OJ-Referenz (Spalte 6) → (designation, eso)` über **alle**
   Tabellen/Zeilen hinweg (ein Nachfolger kann auf einer anderen Seite/
   Tabelle stehen als sein Vorgänger). Der zweite (der bestehende
   Yield-Loop) prüft je Zeile: steht ihre eigene Spalte-6-Referenz als
   Schlüssel in dieser Map? Wenn ja, ist diese Zeile der Nachfolger des
   Eintrags, der exakt diese OJ-Referenz in Spalte 11 als seine
   Widerrufs-Referenz trägt — die Zeile bekommt zusätzlich zur
   bestehenden `BASED_ON_LAW`-Referenz eine
   `RawReference(target_issuer=<alter eso>, target_designation=<alte
   designation>, edge_type=EdgeType.REPLACES)`.
3. Kein Match innerhalb der aktuell geladenen Tabelle(n) → keine Referenz
   erzeugen. Kein Rätselraten; bleibt offen, bis ein späterer Ingestion-Lauf
   den Nachfolger mit-erfasst.
4. Leere/`"-"`-Zellen in Spalte 6/11 gelten als "kein Wert", nicht als
   Match-Kandidat.

## Architektur: DGUV

`_fetch_file` baut `lines`/`full_text` über die bestehende
`_logical_lines`/`_HEADING_PATTERN`-Maschinerie, bevor der (unveränderliche)
`RawRecord` konstruiert wird. `extract_structure` — die die §-Aufteilung in
`RawSection`s vornimmt — wird vom Runner erst danach, separat, aufgerufen;
`raw_references` muss aber schon beim Konstruieren des `RawRecord` gesetzt
sein. Erweiterung:

1. Nach dem Aufbau von `lines`, vor dem Konstruieren des `RawRecord`: finde
   die Zeile, deren Heading `§ N Inkrafttreten/Außerkrafttreten` entspricht
   (gleiche `_HEADING_PATTERN`-Erkennung, hier vorgezogen), und nimm ihren
   Fließtext bis zur nächsten Heading-Zeile.
2. Zwei Regex-Varianten auf diesem Abschnittstext, je nach Form des
   genannten Vorgängers:
   - **Moderne Referenz** (selten, aber real — z. B. eine neue "DGUV
     Vorschrift 2" löst eine ältere, ebenfalls schon modern nummerierte
     "DGUV Vorschrift 2" ab): Text nach "außer Kraft" enthält ein
     `_DESIGNATION_PATTERN`-konformes Muster → `target_designation` =
     genau dieses Muster.
   - **Freitext-Alttitel** (häufiger — Vorgänger stammt aus der Zeit vor
     der DGUV-Nummernreform, z. B. „Bauarbeiten" vom September 1976):
     Muster `„<Titel>" vom <Datum>[ in der Fassung vom <Datum>]` →
     `target_designation` = der Titel-String, `target_issuer` = `"DGUV"`.
3. In beiden Fällen: `RawReference(target_issuer=..., target_designation=...,
   edge_type=EdgeType.REPLACES)`, angehängt an den `RawRecord` des
   Dokuments, das den Abschnitt selbst enthält (das neue, ablösende
   Dokument) — die Kantenrichtung stimmt damit automatisch (zeigt vom
   Nachfolger zum Vorgänger).
4. Kein erkennbares Muster im Abschnitt (z. B. Erstausgabe ohne Vorgänger,
   oder unbekannte Formulierung) → keine Referenz, kein Fehler.

**Bewusst in Kauf genommene Eigenschaft, kein Defekt:** die
Freitext-Alttitel-Variante wird auf echten Daten überwiegend NICHT über
`find_by_designation` auflösen, weil das ursprünglich referenzierte
Alt-Dokument nie unter diesem Titel (statt unter seiner damaligen
BGV-/GUV-V-Kennung) in dieses System eingelesen wurde. Das ist kein
Rückschlag: `references.py`s bestehender `reference_target_not_found`-Pfad
fängt das bereits ab (Kurator-Fall statt Fehler oder Rätselraten) — der
Signalwert entsteht daraus, dass ein Editionswechsel-Ereignis überhaupt
sichtbar wird, auch wenn seine Zielauflösung (noch) nicht automatisch
gelingt. Moderne DGUV-Vorschrift-zu-DGUV-Vorschrift-Nachfolgen (der
Normalfall, sobald dieses System über Jahre neu erscheinende Editionen
bereits bekannter Vorschriften nachträgt) lösen dagegen normal auf.

## Tests

- **EUR-Lex:** die bestehende Fixture (oder eine neue) um ein
  Withdrawal/Successor-Zeilenpaar erweitern, wie im echten PDF gefunden
  (`EN ISO 12100-1/-2:2003` → `EN ISO 12100:2010`). Test prüft: genau die
  Nachfolger-Zeile trägt zusätzlich zur `BASED_ON_LAW`-Referenz eine
  `REPLACES`-`RawReference` mit der korrekten `target_designation`; die
  beiden withdrawn-Zeilen selbst bekommen keine zusätzliche Referenz.
  End-to-End-Test (wie die bestehenden `test_eur_lex_adapter.py`-Tests)
  bestätigt: bei vorhandenem Zieldokument entsteht eine echte
  `REPLACES`-Kante über `create_edge`, und beide Dokumente landen im
  selben `Work`.
- **DGUV:** neue synthetische reportlab-Fixture (konsistent mit den
  bestehenden BAuA-Fixtures, kein Copyright-Risiko) mit einem "§ N
  Inkrafttreten/Außerkrafttreten"-Abschnitt in beiden Varianten — echter
  Wortlaut wie im realen DGUV-Vorschrift-38-PDF gefunden, einmal mit
  modernem, einmal mit Freitext-Alttitel-Vorgänger. End-to-End-Test
  bestätigt: die moderne Referenz erzeugt bei vorhandenem Zieldokument eine
  echte `REPLACES`-Kante und Work-Zusammenführung; die Freitext-Referenz
  landet als Kurator-Fall (kein Fehler, keine falsche Kante).
- Kein Regressionsrisiko für `references.py`/`create_edge`/Work-Merge — die
  bleiben unverändert, ihre bestehenden Tests laufen unangetastet mit.
- Kein Regressionsrisiko für `baua.py` — unverändert.
