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

## Ziel dieses Teilprojekts

- pdfplumber vollständig durch Docling ersetzen — in beiden bestehenden
  Adaptern, nicht nur für künftige neue Quellen.
- Eine gemeinsame Docling-Extraktionsschicht einführen, die für beliebige
  künftige Adapter wiederverwendbar ist, ohne dass diese Docling-Konfiguration
  duplizieren müssen.
- DGUVs Struktur-Erkennung von Regex-auf-Rohtext auf Doclings native
  Überschriften-/Abschnittserkennung umstellen.
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

## Komponenten

| Datei | Änderung |
|---|---|
| `core/src/normly_core/pipeline/docling_extraction.py` | **Neu.** Kapselt `DocumentConverter`-Aufruf, Modellkonfiguration, einheitliche Fehlerklasse für defekte/unlesbare Dateien. |
| `core/src/normly_core/pipeline/adapters/dguv.py` | `fetch()` nutzt die neue Schicht statt `pdfplumber.open()`. `raw_designation`/`raw_title` aus der ersten erkannten Top-Level-Überschrift statt "erste/zweite Textzeile". `extract_structure()` läuft über Doclings Abschnittsgrenzen — die bisherige Regex-Logik entfällt vollständig. |
| `core/src/normly_core/pipeline/adapters/eur_lex.py` | `_fetch_file()` nutzt dieselbe Schicht, liest `DoclingDocument.tables` statt `page.extract_tables()`. Spaltenindex-Logik (`_COLUMN_ESO` etc.) bleibt im Prinzip bestehen, wird aber gegen echten Docling-Output neu verifiziert (siehe Testkonzept). |
| `core/pyproject.toml` | `pdfplumber` entfernt, `docling` als neue Abhängigkeit (Versionsbereich beim Implementieren gegen die zu diesem Zeitpunkt aktuelle stabile Version festlegen). |
| Build/CI (Dockerfile bzw. Pipeline-Definition) | Neuer Schritt: Docling-Modellgewichte einmalig beziehen (`docling-tools models download` oder Äquivalent) und ins Image backen. Kein Netzwerkzugriff auf Hugging Face zur Laufzeit. Modell-Updates laufen künftig über erneutes Ausführen dieses Schritts bei Docling-Versions-Updates, nicht automatisch. |
| `docs/adr/README.md` | Neuer Eintrag ADR-018 (siehe unten). |

## Datenfluss

- **DGUV:** Datei → `docling_extraction` → `DoclingDocument` → Adapter läuft
  über die erkannten Überschriftenknoten, baut `RawSection`-Objekte (Titel =
  Überschriftentext, Inhalt = zugehöriger Textblock bis zur nächsten
  Überschrift gleicher oder höherer Ebene). `raw_designation`/`raw_title`
  aus der ersten Top-Level-Überschrift.
- **EUR-Lex:** Datei → `docling_extraction` → `DoclingDocument` → Adapter
  iteriert `.tables`, liest Zellen weiterhin positionsbasiert, baut
  `RawRecord`s. `extract_structure()` bleibt `[]` (keine Struktur bei reinen
  Katalogdaten — unverändert gegenüber heute).

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
  Regressionsabsicherung für den Umstieg — Assertions bleiben so weit wie
  möglich unverändert, Abweichungen werden bewusst nachvollzogen, nicht
  stillschweigend angepasst.
- EUR-Lex' Spalten-/Zeilenumbruch-Eigenheit (`"ESO\n(B)"`, bisher per
  `.startswith("ESO")` gefiltert) muss gegen echten Docling-Output neu
  verifiziert werden. Verhält sich Docling anders, werden Filter/Assertions
  entsprechend angepasst — nicht Doclings Verhalten künstlich zurückgebogen.
- Die zur Laufzeit per `reportlab` erzeugte DGUV-Test-Fixture muss weiterhin
  durch Docling sauber lesbar sein. Falls Doclings Layout-Erkennung an
  minimalen synthetischen PDFs schlechter greift als pdfplumber, wird die
  Fixture-Erzeugung angepasst, nicht die Assertion verwässert.
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
