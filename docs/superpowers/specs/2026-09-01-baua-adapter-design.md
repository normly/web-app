# Design: BAuA-Adapter (TRGS/TRBS/TRBA)

## Kontext

REQ-PIPE-009 (Erstbestand aus frei zugänglichen Quellen) nennt neben den
Listen harmonisierter Normen (EUR-Lex, bereits als `EurLexAdapter` gebaut)
und den Regelwerksverzeichnissen von DGUV (bereits als `DguvAdapter` gebaut)
ausdrücklich auch die **Regelwerksverzeichnisse von BAuA**. Beide bestehenden
Adapter laufen seit der Docling-Migration
(`2026-08-30-docling-migration-design.md`) über die gemeinsame Schicht
`core/src/normly_core/pipeline/docling_extraction.py` und folgen demselben
Ingestion-Modell: kein Live-Scraping, ein Operator legt Quelldateien in ein
lokales Verzeichnis, die CLI (`python -m normly_core.pipeline ingest ...`)
liest von dort.

Diese Aufgabe wurde in Rücksprache mit dem Auftraggeber gegenüber zwei
Alternativen ausgewählt (Prüfoberfläche für unklare Identitätsauflösung nach
REQ-PIPE-007; Aufbau einer CI/CD-Pipeline nach REQ-BUILD-002/003) — als
direkte inhaltliche Fortsetzung der gerade abgeschlossenen Docling-Migration,
mit demselben Adapter-Muster und derselben Extraktionsschicht.

**BAuA veröffentlicht drei hier relevante Regelwerksreihen**, alle vom
selben Herausgeber, alle mit vergleichbarem Nummernschema und
Bekanntmachungsweg:

- **TRGS** — Technische Regeln für Gefahrstoffe, erarbeitet vom Ausschuss
  für Gefahrstoffe (AGS).
- **TRBS** — Technische Regeln für Betriebssicherheit, erarbeitet vom
  Ausschuss für Betriebssicherheit (ABS).
- **TRBA** — Technische Regeln für Biologische Arbeitsstoffe, erarbeitet vom
  Ausschuss für Biologische Arbeitsstoffe (ABAS).

Alle drei werden von der BAuA im Gemeinsamen Ministerialblatt (GMBl) bekannt
gemacht.

## Ziel dieses Teilprojekts

- Ein neuer `BauaAdapter`, der alle drei Reihen unter einem gemeinsamen
  Registereintrag (Herausgeber `"BAuA"`) einliest — analog zu `DguvAdapter`,
  der ebenfalls mehrere Publikationsreihen desselben Herausgebers
  (Vorschrift/Regel/Information/Grundsatz) unter einem Eintrag bündelt.
- Ein neuer Registereintrag in `sources.py`, Schlüssel `"baua"`,
  Rechtegrundlage Kategorie A.
- CLI-Verdrahtung (`build_adapter()` in `cli.py`) analog zu den bestehenden
  Quellen.
- Ein erster, bewusst einfacher Wurf der Volltext-Struktur (siehe
  "Entscheidung: Struktur-Tiefe Phase 1" unten) — keine Wiederholung der
  aufwändigen Überschriften-Regex-Iteration, die der DGUV-Adapter
  durchlaufen musste.

## Nicht-Ziele

- **Keine automatisierte Beschaffung von baua.de.** Die Seite liegt hinter
  einem JavaScript-basierten Bot-Schutz (Bunny Shield) — sowohl `WebFetch`
  als auch `curl` (mit realistischem Browser-User-Agent) lieferten für jede
  während des Designs getestete URL, einschließlich des direkten
  `TRBS-Bekanntmachungen.pdf`-Index-Links, HTTP 403. Ein Umgehungsversuch
  wurde bewusst nicht unternommen. Beschaffung bleibt manuell — deckungsgleich
  mit dem bestehenden Modell für DGUV und EUR-Lex, wo der Operator Dateien
  selbst in das Ingest-Verzeichnis legt.
- **Keine feingranulare Abschnittserkennung** (nummerierte Überschriften wie
  "1 Zielsetzung", "2.1 Begriffsbestimmungen") in diesem Durchgang — siehe
  Architektur. Bewusst als eigene Folgeaufgabe vertagt.
- **Keine erneute Prüfung nach REQ-PIPE-003** (Nutzungsvorbehalt). Dessen
  Wortlaut bindet die Prüfung an "automatisierte Erfassung frei zugänglicher
  Quellen" — hier liegt weder eine automatisierte Erfassung noch ein
  urheberrechtlich geschütztes Werk vor, an dem ein Nutzungsvorbehalt nach
  § 44b Abs. 3 UrhG überhaupt ansetzen könnte (siehe Rechtegrundlage unten).
- **Keine neue Abstraktion** zwischen `DoclingDocument` und den
  Domain-Objekten. Der Adapter bleibt, wie von der Docling-Migration
  festgelegt, selbst für seine kleine Mapping-Logik zuständig.

## Architektur

Neue Datei `core/src/normly_core/pipeline/adapters/baua.py`, Klasse
`BauaAdapter(directory, source_id)` — gleiche Form wie `DguvAdapter` und
`EurLexAdapter`. Nutzt dieselbe gemeinsame `docling_extraction.extract_document()`.

### Dateikonvention

Drei Datei-Präfixe für die drei Reihen, ein Adapter liest alle drei:

```python
_FILE_PATTERNS = ("baua_trgs_*.pdf", "baua_trbs_*.pdf", "baua_trba_*.pdf")
```

`fetch()` sammelt alle drei Globs sortiert zusammen und verarbeitet — wie
bei DGUV, anders als bei EUR-Lex — eine PDF als ein Dokument, nicht als
Zusammenfassungstabelle mit vielen Zeilen.

### Designation-Erkennung

Ein gemeinsames Muster für alle drei Reihen, da identisches Nummernschema
(Präfix + Zahl, optional "Teil N", z. B. "TRGS 500 Teil 1"):

```python
_DESIGNATION_PATTERN = re.compile(r"^(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)\s*(.*)$")
```

Wie bei DGUV/EUR-Lex empirisch bestätigt: Docling fasst visuell benachbarte
Zeilen (Designation- und Titelzeile) zu einem Textelement zusammen. Titel
wird daher aus dem Rest desselben ersten Elements nach dem
Designation-Treffer gebildet — anders als bei DGUV bewusst **ohne** dessen
Satzgrenzen-Heuristik (`_SENTENCE_OPENERS`, Wortlisten-Prüfung usw.). Das
ist ein akzeptiertes Risiko, keine Unachtsamkeit: bei einem stark
verschmolzenen Docling-Textblock kann der Titel Fließtext-Reste enthalten.
Kategorie desselben, bereits im DGUV-Adapter akzeptierten Restrisikos — dort
dokumentiert in dessen "Offene Punkte". `full_text` bleibt davon unberührt
und enthält in jedem Fall den vollständigen Text.

### Rechtegrundlage: Kategorie A

TRGS/TRBS/TRBA werden von BAuA-Fachausschüssen (AGS/ABS/ABAS) erarbeitet und
von der BAuA im GMBl bekannt gemacht. Anders als DGUV-Vorschriften sind sie
keine Rechtsnormen — Arbeitgeber, die die "vermutete" (nicht zwingende)
Konformität nicht über eine TRGS/TRBS/TRBA herstellen, müssen gleichwertigen
Schutz auf anderem Weg nachweisen ("Vermutungswirkung"). Das ändert nichts an
der Einordnung nach § 5 Abs. 1 UrhG: dessen "Bekanntmachungen"-Tatbestand
setzt keinen Rechtsnormcharakter des Inhalts voraus, sondern erfasst die
amtliche Bekanntmachung als solche — hier durch eine Bundesoberbehörde im
GMBl. Damit dieselbe Kategorie wie die bestehenden DGUV- und
EUR-Lex-Registereinträge:

```python
def classify_rights(self, record: RawRecord) -> RightsRule:
    return RightsRule(
        jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG — amtliche Bekanntmachung (TRGS/TRBS/TRBA, BAuA im GMBl)",
    )
```

Wie bei DGUV/EUR-Lex enger als das Protokoll (`RightsRule | None`): jeder
Record dieser Quelle ist klassifizierbar, es gibt keinen "kann nicht
klassifizieren"-Fall.

### Entscheidung: Struktur-Tiefe Phase 1

TRGS/TRBS/TRBA gliedern sich intern in nummerierte Abschnitte
("1 Zielsetzung", "2.1 Begriffsbestimmungen", ...), nicht in
§-Paragraphen wie DGUV. Eine robuste Grenzerkennung für dieses Schema
gegen reale Dokumentvarianz zu bauen ist vom selben Aufwand wie die
DGUV-Überschriftenerkennung, die fünf Iterationsrunden plus adversarielle
Re-Review brauchte und dabei ein akzeptiertes Restrisiko zurückließ (siehe
dortige "Offene Punkte"). Diese Iteration in diesem Durchgang zu wiederholen
— ohne die reale Dokumentvarianz zunächst wenigstens gegen ein einziges
echtes Exemplar geprüft zu haben, was `baua.de`s Bot-Schutz hier verhindert
— wurde mit dem Auftraggeber bewusst verworfen.

Stattdessen liefert `extract_structure()` in diesem ersten Wurf genau ein
Segment mit dem vollständigen Dokumenttext:

```python
def extract_structure(self, record: RawRecord) -> list[RawSection]:
    if record.full_text is None:
        return []
    return [RawSection(sequence_number=1, heading=None, text=record.full_text)]
```

Volltext ist damit ab Tag eins durchsuchbar und zitierfähig (`may_index_fulltext`
ist `True`, siehe Rechtegrundlage) — nur ohne granulare Abschnittsgrenzen.
Feinere Segmentierung ist eine bewusst vertagte Folgeaufgabe (siehe "Offene
Punkte"), keine vergessene.

## Komponenten

| Datei | Änderung |
|---|---|
| `core/src/normly_core/pipeline/adapters/baua.py` | **Neu.** `BauaAdapter` — `fetch()`, `extract_structure()` (Phase 1: ein Volltext-Segment), `classify_rights()` (Kategorie A, immer klassifizierbar). |
| `core/src/normly_core/pipeline/sources.py` | Neuer Eintrag `"baua"` in `SOURCE_REGISTRY`: Herausgeber `"BAuA"`, Kategorie A, Rechtsraum `"DE"`. |
| `core/src/normly_core/pipeline/cli.py` | `build_adapter()` um den `"baua"`-Zweig erweitert, `argparse`-Choices um `"baua"` ergänzt. |
| `core/tests/pipeline/test_baua_adapter.py` | **Neu.** Siehe Testkonzept. |
| `core/tests/fixtures/baua_trgs_sample.pdf`, `baua_trbs_sample.pdf`, `baua_trba_sample.pdf` | **Neu.** Synthetische, per `reportlab` zur Testzeit erzeugte Fixtures (wie bei DGUV) — nicht von der echten Seite kopiert. |

## Datenfluss

Datei → `docling_extraction.extract_document()` → `DoclingDocument` →
Adapter nimmt den Text des ersten Elements, trennt Designation und Titel per
`_DESIGNATION_PATTERN`, sammelt den gesamten übrigen Text unverändert als
`full_text` (kein Zeilenstruktur-Rebuild wie bei DGUV nötig — Phase 1 braucht
keine Zeilengrenzen, nur den vollständigen Text). `extract_structure()` baut
daraus das eine Segment; `classify_rights()` liefert immer dieselbe Kategorie-
A-Regel.

Der Rest des Datenflusses (Delivery-Deduplizierung über Content-Hash,
Identitätsauflösung, Segment-/Embedding-Erzeugung) läuft unverändert über
`runner.run_adapter()` — der Adapter selbst kennt keine dieser Stufen.

## Fehlerbehandlung

Identisch zu `DguvAdapter`/`EurLexAdapter`:

- Eine unlesbare/defekte PDF kostet nur diese Datei — `DocumentExtractionError`
  wird pro Datei gefangen, über `report_skipped_source()` protokolliert,
  `fetch()` liest die restlichen Dateien weiter.
- Eine `PipelineInitializationError` (fehlkonfigurierte Docling-Modelle) wird
  **nicht** gefangen — sie beträfe jede Datei gleichermaßen und soll den Lauf
  sichtbar abbrechen statt einen leeren "Erfolg" vorzutäuschen.

## Testkonzept

`core/tests/pipeline/test_baua_adapter.py`, mit drei per `reportlab`
generierten Fixtures (eine je Reihe), analog zum Vorgehen bei
`dguv_sample_vorschrift.pdf`. Fälle:

- `fetch()` liefert einen Record je Datei, über alle drei Datei-Präfixe
  hinweg gemeinsam.
- Designation/Titel werden korrekt getrennt, für alle drei Präfixe
  (TRGS/TRBS/TRBA) sowie für den "Teil N"-Suffix-Fall.
- `classify_rights()` liefert immer dieselbe Kategorie-A-Regel, nie `None`.
- `extract_structure()` liefert für einen Record mit `full_text` genau ein
  Segment mit dem vollständigen Text; für `full_text=None` eine leere Liste.
- Eine unlesbare Datei wird übersprungen, die übrigen werden trotzdem
  verarbeitet (wie beim bestehenden DGUV-Test).
- Eine `PipelineInitializationError` bricht den Lauf weiterhin ab, statt
  stillschweigend übersprungen zu werden (wie beim bestehenden DGUV-Test).

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-PIPE-009 | Direkt erfüllt — BAuA ist dort namentlich als Kategorie-A/B-Erstbestandsquelle genannt. |
| REQ-PIPE-002 | Neuer Registereintrag mit vollständigen Pflichtfeldern (Herausgeber, Abrufweg, Kategorie, Rechtsraum, Prüfdatum, verantwortliche Person). |
| REQ-PIPE-003 | Nicht einschlägig — siehe Nicht-Ziele. |
| REQ-PIPE-005 | Unberührt — Abstammung läuft über dieselbe `Delivery`-Mechanik wie bei den bestehenden Adaptern, adapterunabhängig. |
| ADR-018 (Docling-Migration) | Der neue Adapter baut von Beginn an auf der dort eingeführten `docling_extraction`-Schicht auf, dupliziert keine Docling-Konfiguration. |

## Offene Punkte / Folgearbeiten

- **Ungeprüft gegen ein echtes Dokument.** Weder Designation-Muster noch
  Titel-Extraktion noch die Annahme über Doclings Element-Zusammenfassung
  wurden gegen eine echte TRGS/TRBS/TRBA-PDF verifiziert — `baua.de`s
  Bot-Schutz verhinderte das während des Designs. Sobald der Operator die
  ersten echten Dateien beschafft, sollte der erste reale Ingestion-Lauf
  stichprobenartig geprüft werden, bevor größere Mengen eingelesen werden.
- **Feingranulare Abschnittserkennung** (nummerierte Überschriften) ist
  bewusst vertagt (siehe "Entscheidung: Struktur-Tiefe Phase 1"). Eigene
  Folgeaufgabe, sobald reale Dokumente zur Musterbildung vorliegen.
- **Datei-Namenskonvention** (`baua_trgs_*.pdf` usw.) ist eine Annahme dieses
  Designs, keine von BAuA vorgegebene Konvention — der Operator muss beim
  Ablegen der Dateien entsprechend benennen. Bei Bedarf leicht erweiterbar
  (z. B. weitere Präfixe für zukünftige Reihen), ohne Bruch der bestehenden.
