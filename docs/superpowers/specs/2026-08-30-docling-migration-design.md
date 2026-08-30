# Design: Umstieg von pdfplumber auf Docling

## Kontext

Die Ingestion-Pipeline (`docs/superpowers/specs/2026-08-14-ingestion-pipeline-design.md`)
nutzt heute `pdfplumber` für PDF-Extraktion in genau zwei Adaptern:
`DguvAdapter` (reiner Volltext, regelbasierte §-Struktur-Erkennung per Regex)
und `EurLexAdapter` (reine Tabellenextraktion, keine Struktur). Beide rufen
pdfplumber direkt inline in `fetch()` auf — es existiert keine
Abstraktionsschicht dazwischen.

Kein ADR begründet die Wahl von pdfplumber; es gibt insofern keine
dokumentierte Vorentscheidung, die hier überstimmt werden müsste.

**Treiber für den Umstieg:** Zukunftssicherheit. DGUV und EUR-Lex laufen mit
pdfplumber heute zufriedenstellend, aber deutlich mehr Quellen werden folgen
— weitere Normungsorganisationen mit unbekannten, teils komplexeren
Layouts, möglicherweise gescannte/bildbasierte Dokumente. pdfplumber bietet
dafür kein Dokumentenverständnis, nur Text- und Tabellenzugriff.
[Docling](https://github.com/docling-project/docling) (MIT-lizenziert,
LF AI & Data Foundation, ursprünglich IBM Research) liefert ein
strukturiertes `DoclingDocument` mit erkannten Überschriften, Abschnitten
und Tabellen, basierend auf einem Layout-Erkennungsmodell und TableFormer
für Tabellenstruktur — beide Teil der Standard-Pipeline, nicht nur optionale
Extras.

**Empirisch geprüft, nicht nur angenommen:** Während der Design-Phase wurde
Docling (Version 2.123.1) tatsächlich gegen die beiden echten Fixture-PDFs
(`core/tests/fixtures/dguv_sample_vorschrift.pdf`,
`eur_lex_machinery_summary.pdf`) laufen lassen, um Annahmen über die
tatsächliche API und das tatsächliche Klassifikationsverhalten zu
verifizieren, statt sie zu erraten. Die konkreten Befunde prägen Architektur
und Nicht-Ziele unten direkt.

## Ziel dieses Teilprojekts

- pdfplumber vollständig durch Docling ersetzen — in beiden bestehenden
  Adaptern, nicht nur für künftige neue Quellen.
- Eine gemeinsame Docling-Extraktionsschicht einführen, die für beliebige
  künftige Adapter wiederverwendbar ist, ohne dass diese Docling-Konfiguration
  duplizieren müssen.
- DGUVs Struktur-Erkennung von manuellem `.splitlines()` auf rohem Text
  (mit allen Zeilenumbruch-Eigenheiten, die pdfplumber mitbringt) auf
  Doclings saubere Textsegmentierung umstellen — die Grenzerkennung selbst
  bleibt musterbasiert (siehe "Empirischer Befund" unter Architektur, der
  diese Entscheidung während der Design-Phase korrigiert hat).
- Ein dokumentiertes, wiederholbares Entscheidungsverfahren festhalten, mit
  dem jeder künftige Adapter selbst prüfen kann, ob Doclings native
  Element-Klassifikation (`SectionHeaderItem` etc.) für seine Quelle
  zuverlässig funktioniert, oder ob musterbasierte Grenzerkennung nötig ist
  — nicht nur für DGUV/EUR-Lex, sondern als wiederverwendbares Verfahren.
- Sicherstellen, dass Docling-Modellgewichte zur Laufzeit **nie** über das
  Netzwerk nachgeladen werden (STACKIT-only-Vorgabe aus `CLAUDE.md`) —
  Bezug einmalig beim Image-Build, nicht im Betrieb.

## Nicht-Ziele

- **Keine generische, konfigurierbare Struktur-Mapping-Schicht** zwischen
  `DoclingDocument` und den Domain-Objekten (`RawRecord`/`RawSection`). Bei
  aktuell zwei sehr unterschiedlichen Quellenformen (Fließtext-mit-
  Überschriften vs. reine Tabelle) wäre eine "universelle" Abbildung jetzt
  geraten, nicht abgeleitet — das Ingestion-Spec hat einen generischen,
  konfigurationsgetriebenen Adapter bereits einmal bewusst verworfen (YAGNI).
  Jeder Adapter bleibt für seine eigene, kleine Mapping-Logik zuständig.
- **Keine OCR-Aktivierung** für gescannte/bildbasierte PDFs in diesem
  Teilprojekt. Weder DGUV noch EUR-Lex brauchen sie heute; wird erst
  spezifiziert, wenn eine konkrete künftige Quelle das tatsächlich braucht.
  **Wichtig, empirisch bestätigt:** Doclings Standard-Pipeline führt OCR
  automatisch aus, auch bei reinem Vektor-Text ohne jedes Bild — die
  `docling_extraction`-Schicht **muss** `PdfPipelineOptions(do_ocr=False)`
  setzen, sonst lädt Docling beim ersten Lauf zusätzliche OCR-Modelle von
  **modelscope.cn** nach (nicht Hugging Face — eine zweite, bisher nicht
  bedachte externe Modellquelle, die genauso wenig zur Laufzeit erreichbar
  sein darf).
- **Kein blindes Vertrauen in Doclings semantische Element-Klassifikation**
  ohne empirische Prüfung gegen eine echte Beispieldatei der jeweiligen
  Quelle. Siehe "Empirischer Befund" unter Architektur — die Klassifikation
  ist nachweislich nicht für jede Quelle zuverlässig.
- **Kein Umstieg auf Doclings VLM-Pipeline** (`granite_docling` o. Ä.). Das
  Standard-Layout-Modell plus TableFormer reicht für die heutigen
  Anforderungen; ein VLM wäre ein deutlich schwereres Abhängigkeits- und
  Betriebsprofil ohne aktuellen Bedarf.
- **Keine Änderung an ADR-008** (Graph-First-Anfrageverarbeitung, kein
  Sprachmodell zur Anfragezeit für Strukturfragen). Diese Entscheidung
  betrifft ausschließlich die Anfragezeit und bleibt unberührt — siehe
  ADR-018 unten für die Abgrenzung.

## Architektur

Neue, gemeinsame Schicht: `core/src/normly_core/pipeline/docling_extraction.py`.
Sie kapselt die Docling-Konfiguration (Modellpfad, `TableFormerMode`) an
einer Stelle und stellt eine Funktion bereit, die aus einem Dateipfad ein
`DoclingDocument` liefert — formatunabhängig, da Doclings
`DocumentConverter` das Quellformat selbst erkennt (PDF heute, DOCX/HTML/etc.
ohne Zusatzaufwand für künftige Quellen, die kein PDF sind).

Jeder Adapter bleibt dafür zuständig, das `DoclingDocument` in seine eigenen
Domain-Objekte zu übersetzen:

- **DGUV** läuft über die erkannten Abschnitts-/Überschriftenknoten.
- **EUR-Lex** liest `DoclingDocument.tables` positionsbasiert, wie bisher.

Das entspricht dem bestehenden Architekturprinzip aus dem Ingestion-Spec
("adapterspezifische Abhängigkeiten bleiben im jeweiligen Adapter"), hebt
aber die eigentliche Docling-Mechanik (Modellkonfiguration, Fehlerpfade) auf
eine wiederverwendbare Ebene — ein dritter, vierter, ... Adapter dupliziert
sie nicht erneut.

### Empirischer Befund: Doclings Element-Klassifikation ist nicht immer verlässlich

Während der Design-Phase wurde Docling (2.123.1) direkt gegen die echte
DGUV-Fixture laufen lassen, mit folgendem, reproduzierbarem Ergebnis:

```
[TextItem]        level=1 text='DGUV Vorschrift 1 Grundsätze der Prävention'
[ListItem]         level=2 text='§ 1 Geltungsbereich'
[TextItem]        level=1 text='Diese Vorschrift gilt für alle Unternehmen und Versicherte.'
[ListItem]         level=2 text='§ 2 Pflichten des Unternehmers'
...
```

Die `§ N ...`-Überschriften kommen als `ListItem` zurück, **nicht** als
`SectionHeaderItem` — reproduzierbar, auch mit `do_ocr=False`. Docling
stuft sie offenbar als nummerierte Listeneinträge ein, weil es keine
optischen Unterscheidungsmerkmale (größere Schrift, Fettdruck, Abstand)
gibt, an denen sein Layout-Modell eine echte Überschrift erkennen könnte.
Das ist plausibel kein Fixture-Artefakt, sondern reales Verhalten bei
schlicht formatierten deutschen Verwaltungs-/Rechtstexten — die ursprünglich
angenommene "Docling erkennt Struktur automatisch für jede künftige Quelle"
-Erwartung ist für diesen Dokumenttyp nicht einlösbar, unabhängig von der
Implementierung.

**Konsequenz für DGUV:** `extract_structure()` iteriert weiterhin über
Doclings segmentierte Text-Elemente (`document.iterate_items()`) — das ist
bereits ein echter Gewinn gegenüber pdfplumber, da Docling die
Zeilenzerlegung sauberer vornimmt als manuelles `.splitlines()` auf rohem
Text. Die Entscheidung "ist dieses Element eine Abschnittsgrenze" bleibt
aber musterbasiert (dieselbe `§ N`-Regex wie heute), angewendet pro Element
statt auf einem rohen Text-Blob — **nicht** Doclings semantische
Klassifikation (`SectionHeaderItem` vs. `ListItem` vs. `TextItem`).

### Entscheidungsverfahren für künftige Adapter

Damit dieser Befund nicht bei jeder neuen Quelle erneut mühsam entdeckt
werden muss, gilt für jeden künftigen Adapter dasselbe, dokumentierte
Verfahren:

1. **Docling gegen eine echte Beispieldatei der neuen Quelle laufen lassen**
   (nicht raten, nicht von DGUV/EUR-Lex extrapolieren) und
   `document.iterate_items()` inspizieren.
2. **Prüfen, ob die tatsächlichen Überschriften der Quelle zuverlässig als
   `SectionHeaderItem` zurückkommen:**
   - **Ja** — der Adapter kann direkt auf
     `isinstance(item, SectionHeaderItem)` aufbauen; Doclings automatische
     Struktur-Erkennung funktioniert für diese Quelle tatsächlich wie
     ursprünglich erhofft.
   - **Nein** (wie bei DGUV) — der Adapter iteriert trotzdem über Doclings
     segmentierte Elemente, entscheidet "ist das eine Grenze" aber über ein
     quellenspezifisches Textmuster, exakt nach demselben Muster wie
     `DguvAdapter.extract_structure()`.
3. **Dieses Verhalten wird durch einen Test gegen eine echte Fixture-Datei
   der neuen Quelle festgehalten**, nicht nur einmalig manuell geprüft —
   damit ein künftiger Docling-Versions-Wechsel, der das
   Klassifikationsverhalten ändert, im Test auffällt statt still in
   Produktion falsche (leere) Struktur zu erzeugen. Task-Vorlage: ein Test,
   der `document.iterate_items()` gegen die Fixture aufruft und explizit
   die erwartete Elementart der bekannten Überschriften assertiert — bricht
   der Test bei einem künftigen Docling-Update, ist das ein bewusstes
   Signal, keine stille Verhaltensänderung.

## Komponenten

| Datei | Änderung |
|---|---|
| `core/src/normly_core/pipeline/docling_extraction.py` | **Neu.** Kapselt `DocumentConverter`-Aufruf mit `do_ocr=False` und lokalem `artifacts_path`, einheitliche Fehlerklasse für defekte/unlesbare Dateien. |
| `core/src/normly_core/pipeline/adapters/dguv.py` | `fetch()` nutzt die neue Schicht statt `pdfplumber.open()`, iteriert `document.iterate_items()` statt `page.extract_text()` + `.splitlines()`. `raw_designation`/`raw_title` per Muster aus dem ersten Element getrennt (siehe Datenfluss). `extract_structure()` läuft weiterhin musterbasiert (`§ N`-Regex) — jetzt angewendet pro Docling-Element statt auf rohem Text-Blob (siehe "Empirischer Befund" unter Architektur: Doclings `SectionHeaderItem`-Klassifikation ist für diesen Dokumenttyp nicht zuverlässig, `§ N`-Zeilen kommen als `ListItem` zurück). |
| `core/src/normly_core/pipeline/adapters/eur_lex.py` | `_fetch_file()` nutzt dieselbe Schicht, liest `table.data.grid` (2D-Liste von `TableCell`, `.text`-Attribut pro Zelle) statt `page.extract_tables()`. Spaltenindex-Logik (`_COLUMN_ESO` etc.) bleibt unverändert — empirisch bestätigt identische Spaltenreihenfolge. Die `.startswith("ESO")`-Umgehung für eingebettete Zeilenumbrüche entfällt: Doclings Zellen enthalten keinen Zeilenumbruch (`"ESO (B)"` statt pdfplumbers `"ESO\n(B)"`), einfacher Vergleich reicht. |
| `core/pyproject.toml` | `pdfplumber` entfernt, `docling` als neue Abhängigkeit (Versionsbereich beim Implementieren gegen die zu diesem Zeitpunkt aktuelle stabile Version festlegen). |
| Build/CI (Dockerfile bzw. Pipeline-Definition) | Neuer Schritt: Docling-Modellgewichte einmalig beziehen (`docling-tools models download` oder Äquivalent) und ins Image backen. Kein Netzwerkzugriff auf Hugging Face zur Laufzeit. Modell-Updates laufen künftig über erneutes Ausführen dieses Schritts bei Docling-Versions-Updates, nicht automatisch. |
| `docs/adr/README.md` | Neuer Eintrag ADR-018 (siehe unten). |

## Datenfluss

- **DGUV:** Datei → `docling_extraction` → `DoclingDocument` → Adapter
  iteriert `document.iterate_items()`, sammelt Elementtexte, wendet die
  `§ N`-Regex pro Element an, um Abschnittsgrenzen zu erkennen (musterbasiert,
  nicht Doclings Elementtyp-Klassifikation — siehe Architektur). Baut daraus
  `RawSection`-Objekte (Titel = Text des grenzsetzenden Elements, Inhalt =
  Text der folgenden Elemente bis zur nächsten Grenze).
  **Empirisch bestätigte weitere Abweichung:** Docling fasst visuell
  benachbarte Zeilen zu einem Block zusammen — Designation- und
  Titel-Zeile der Fixture ("DGUV Vorschrift 1" / "Grundsätze der
  Prävention", im PDF zwei separate Zeilen) kommen als **ein** Element
  zurück, nicht als zwei. `raw_designation`/`raw_title` werden daher aus
  dem ersten Element per Muster getrennt (`^(DGUV Vorschrift \d+)\s*(.*)$`),
  nicht per Index-Zugriff auf zwei separate Elemente.
- **EUR-Lex:** Datei → `docling_extraction` → `DoclingDocument` → Adapter
  iteriert `.tables`, liest Zellen über `table.data.grid` weiterhin
  positionsbasiert, baut `RawRecord`s. `extract_structure()` bleibt `[]`
  (keine Struktur bei reinen Katalogdaten — unverändert gegenüber heute).

## Fehlerbehandlung

- Defekte/unlesbare Datei: Docling wirft eigene Exceptions. Die
  `docling_extraction`-Schicht fängt diese und wirft eine normly-eigene,
  adapterunabhängige Fehlerklasse — beide heutigen und alle künftigen
  Adapter behandeln denselben Fehlerpfad einheitlich, statt
  Docling-Exceptions direkt durchzureichen.
- Fehlende Modellgewichte zur Laufzeit (sollte durch Image-Baking nicht
  vorkommen, aber defensiv abzusichern): klarer, sofortiger Fehler statt
  eines stillen Versuchs, Modelle nachzuladen. Docling darf im Betrieb nie
  einen Netzwerkzugriff auf ein Modell-Repository versuchen.

## Testkonzept

- Bestehende Fixture-Tests (`test_dguv_adapter.py`, `test_eur_lex_adapter.py`)
  laufen unverändert gegen dieselben Fixture-PDFs. Da sie auf Adapter-Output
  prüfen (nicht auf pdfplumber-Internals), sind sie eine echte
  Regressionsabsicherung für den Umstieg — Assertions bleiben unverändert,
  da der Adapter-Output (Designation, Titel, Abschnittsgrenzen) bei
  gleichem musterbasiertem Vorgehen gleich bleibt.
- EUR-Lex' Spalten-/Zeilenumbruch-Eigenheit ist **empirisch aufgelöst**:
  Doclings Zellen enthalten keinen eingebetteten Zeilenumbruch mehr
  (`"ESO (B)"` statt pdfplumbers `"ESO\n(B)"`), Spaltenindizes sind
  identisch geblieben (gegen die echte Fixture verifiziert). Die
  `.startswith("ESO")`-Umgehung kann vereinfacht werden, sobald das gegen
  den finalen Adapter-Code bestätigt ist.
- Die zur Laufzeit per `reportlab` erzeugte DGUV-Test-Fixture ist
  **empirisch bestätigt** durch Docling korrekt lesbar (Konversion
  `ConversionStatus.SUCCESS`, alle Textzeilen kommen an) — die
  Überschriften kommen nur mit anderem Elementtyp zurück als ursprünglich
  angenommen (siehe Architektur), keine Lesbarkeitsprobleme.
- **Neuer Test pro Adapter (Teil des Entscheidungsverfahrens oben):** ruft
  `document.iterate_items()` gegen die echte Fixture auf und assertiert
  explizit die tatsächliche Elementart der bekannten Überschriften (für
  DGUV: `ListItem`, nicht `SectionHeaderItem` — das ist eine bewusste,
  dokumentierte Assertion, kein Zufallsbefund). Bricht dieser Test bei
  einem künftigen Docling-Versions-Update, ist das ein bewusstes Signal,
  dass sich das Klassifikationsverhalten geändert hat und die
  Grenzerkennungs-Strategie neu bewertet werden muss — nicht eine stille
  Verhaltensänderung, die erst an leeren Abschnittslisten in Produktion
  auffällt.
- Neuer Test, analog zum bestehenden Architektur-Drift-Test
  (`test_pipeline_domain_does_not_import_sqlalchemy` in
  `test_architecture.py`): sichert ab, dass Docling im Testlauf nicht
  versucht, Modelle über das Netzwerk nachzuladen (z. B. durch eine
  Netzwerksperre im Testkontext) — hält die "kein Laufzeit-Fetch"-Vorgabe
  dauerhaft nach.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-PIPE-001 | Pipeline-Stufen unverändert; nur die Extraktions-Engine innerhalb der Struktur-/Referenzextraktion-Stufe wechselt. |
| ADR-006 | Unberührt — Datenhaltung/Repository-Schicht ändert sich nicht. |
| ADR-008 | Unberührt in seinem eigentlichen Geltungsbereich (kein Sprachmodell zur Anfragezeit). Siehe ADR-018 zur Abgrenzung: Docling ist ein deterministisches, diskriminatives Layout-/Tabellenmodell zur **Ingestion**-Zeit, kein generatives Sprachmodell zur Anfragezeit — die Anfrage selbst bleibt weiterhin ausschließlich graphbasiert beantwortet. |
| **ADR-018 (neu)** | Dokumentiert die Entscheidung, ML-basierte Struktur-Erkennung in die Ingestion-Pipeline aufzunehmen — kehrt den bisher im Ingestion-Spec explizit festgehaltenen Nicht-Ziel-Punkt ("kein generisches Dokumentenverständnis") um. |
| CLAUDE.md, "Keine US-Dienste für Betrieb, Build, Daten, Secrets oder Deployment" | Docling-Modellgewichte werden einmalig bezogen und ins Image gebacken; kein Laufzeit-Zugriff auf Hugging Face. Der einmalige Bezug beim Build ist eine bewusste, dokumentierte Ausnahme für den Build-Vorgang selbst (vergleichbar mit dem Bezug von PyPI-Paketen beim Build) — Betrieb bleibt frei von US-Diensten. |

## Offene Punkte / Folgearbeiten

- Exakter Docling-Versionsbereich für `core/pyproject.toml` wird beim
  Implementieren gegen die dann aktuelle stabile Version festgelegt.
- OCR-Aktivierung für künftige gescannte/bildbasierte Quellen — bewusst
  zurückgestellt, bis eine konkrete Quelle das braucht (siehe Nicht-Ziele).
- Sollte sich in Zukunft eine dritte, vierte Quelle mit ähnlicher Struktur
  wie DGUV oder EUR-Lex zeigen, kann geprüft werden, ob sich aus den dann
  mehreren Beispielen eine echte, abgeleitete (nicht geratene)
  Mapping-Abstraktion lohnt — bewusst nicht vorweggenommen (siehe Nicht-Ziele).
