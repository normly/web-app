# Design: Ingestion-Pipeline (EUR-Lex, DGUV)

**Datum:** 2026-08-14
**Status:** zur Durchsicht
**Teilprojekt:** zweites von mehreren zur Umsetzung des normly-MVP (freier Kern)

## Kontext

Das erste Teilprojekt (Datenmodell & Referenzgraph-Schema, siehe
`docs/superpowers/specs/2026-08-11-datenmodell-referenzgraph-schema-design.md`) hat das
PostgreSQL-Schema und die Repository-Schicht gebaut, aber bewusst ohne Ingestion-Logik und
ohne Segment-/Embedding-Tabellen. Der Graph ist leer.

REQ-PIPE-001 beschreibt eine achtstufige Verarbeitungskette: Quellenregister, Ingest-Adapter,
Identitätsauflösung, Rechteklassifikation, Strukturextraktion, Verweisextraktion,
Segmentierung und Einbettung, Ausspielung. Das ist zu groß für ein Teilprojekt.

**Entschieden mit dem Auftraggeber:**

1. Umfang: die volle Kette bis einschließlich Segmentierung/Einbettung, aber nur für zwei
   konkrete Quellen — **EUR-Lex** (Listen harmonisierter Normen, nur Metadaten/Verweise, kein
   Volltext) und **DGUV** (Vorschriften, echter Volltext). „Ausspielung" ist explizit nicht
   Teil dieses Teilprojekts. Für EUR-Lex konkret: die von der Kommission veröffentlichten
   „Summary list of harmonised standards"-PDFs je Richtlinie/Verordnung (z. B. für die
   Maschinenrichtlinie 2006/42/EC unter
   `single-market-economy.ec.europa.eu/.../harmonised-standards/machinery-md_en`) — recherchiert
   und verifiziert (echte, real abgerufene Beispieldatei), nicht das CELLAR/SPARQL-System, für
   das kein vergleichbar sauberes, dokumentiertes Schema für harmonisierte Normen gefunden
   wurde.
2. Nur DGUV durchläuft Strukturextraktion, Segmentierung und Einbettung — EUR-Lex hat keinen
   Volltext, speist nur Katalogeinträge und Graphkanten.
3. Rechteklassifikation für beide Quellen läuft automatisch nach quellenspezifischer Regel,
   kein manueller Freigabeschritt.
4. Die Prüfoberfläche aus REQ-PIPE-007 bleibt in diesem Teilprojekt Datenmodell + Repository
   (Warteschlange), keine Bedienoberfläche — die kommt mit dem Backend-API-Teilprojekt.
5. Embedding-Modell: `intfloat/multilingual-e5-large`, lokal über `sentence-transformers`,
   keine externe API. Tests nutzen konsequent das echte Modell, kein Stub.
6. Rohdateien werden inhaltsadressiert lokal auf der Festplatte abgelegt. STACKIT Object
   Storage ist eine spätere Deployment-Entscheidung.
7. Aufruf als CLI (`python -m normly_core.pipeline ingest <quelle>`), kein Scheduler.
8. `adapter.fetch()` liest für den Start aus einem konfigurierten lokalen Verzeichnis
   (dorthin werden EUR-Lex-/DGUV-Dateien vorerst manuell heruntergeladen), statt selbst
   über HTTP abzurufen. Grund: automatisiertes, wiederkehrendes Abrufen (Login-Session,
   Pagination, Ratenbegrenzung) ist ein eigenes, nicht-triviales Stück Arbeit, das von der
   eigentlich wertvollen Extraktions-/Parsing-Logik unabhängig ist — die Parsing-Logik selbst
   ist jetzt gegen echte, verifizierte Formate spezifiziert (siehe Punkt 1 und
   Architektur-Abschnitt), nur das automatisierte Abrufen bleibt Folgearbeit. Ein echter
   HTTP-Fetcher ersetzt später nur diese eine Stelle, ohne die Parsing-Logik anzufassen.

## Ziel dieses Teilprojekts

Ein befragbarer Referenzgraph mit echten Daten aus EUR-Lex und DGUV: Normknoten,
Rechtsakt-Knoten, Ersetzungs-/Verweiskanten, Rechteklassifikation je Knoten und Rechtsraum,
sowie für DGUV zusätzlich Volltext-Segmente mit Embeddings für die spätere RAG-Anbindung.
Die Adapter-Abstraktion muss REQ-PIPE-001s Abnahmekriterium erfüllen: eine neue Quelle wird
angebunden, ohne dass Schritte hinter dem Adapter angepasst werden müssen.

## Nicht-Ziele

- **Ausspielung / öffentliche API / Chat.** Konsumiert die hier entstehenden Daten über die
  Repository-Schicht, ist aber ein eigenes Teilprojekt.
- **Bedienoberfläche für die Prüf-Warteschlange.** Nur Datenmodell + Repository-Methoden in
  diesem Teilprojekt; eine echte UI kommt mit dem Backend-API-/Frontend-Teilprojekt.
- **Weitere Quellen** (BAuA, CEN/CENELEC-Arbeitsprogramme, ISO/IEC-Katalogdaten). Die
  Adapter-Abstraktion muss sie ohne Änderung an nachgelagerten Schritten aufnehmen können,
  aber ihre konkrete Anbindung ist Folgearbeit.
- **Perinorm-/Kategorie-C-Adapter.** Weiterhin an einen konkreten Vertrag gebunden
  (siehe Nicht-Ziele des vorigen Teilprojekts).
- **STACKIT Object Storage, Scheduler/Orchestrierung für den Produktivbetrieb.**
  Deployment-Entscheidungen, nicht Teil dieses Teilprojekts.
- **Echte HTTP-Anbindung an EUR-Lex/DGUV.** `adapter.fetch()` liest für den Start aus einem
  lokalen Verzeichnis (siehe Kontext, Punkt 8) — ein späterer HTTP-Fetcher ist Folgearbeit.
- **Allgemeine, konfigurierbare Struktur-/Verweisextraktion.** Für den Start
  quellenspezifisch, regelbasiert — kein generisches Dokumentenverständnis.

## Architektur

### Adapter-Abstraktion

Drei Ansätze wurden abgewogen:

1. **Protocol-basierter `SourceAdapter`**, Adapter liefern ein quellenneutrales `RawRecord`.
2. Adapter schreiben direkt in die Datenbank — verworfen, verletzt REQ-PIPE-001s Vorgabe,
   dass die Verarbeitung ab der Identitätsauflösung herkunftsunabhängig ist.
3. Ein generischer, konfigurierbarer Adapter (URL+Mapping ohne Code) — verworfen für zwei
   strukturell sehr unterschiedliche Quellen (EUR-Lex-Tabellen-PDF vs. DGUV-Fließtext-PDF); verfrühte
   Abstraktion.

**Entschieden: Ansatz 1.**

```python
@dataclass(frozen=True)
class RawRecord:
    source_id: uuid.UUID
    content_hash: str
    raw_designation: str
    raw_issuer: str | None
    raw_title: str | None
    full_text: str | None          # None bei EUR-Lex
    language: str | None           # "en" (EUR-Lex) / "de" (DGUV); Fallback "de" im Runner
    raw_references: list[RawReference]
    fetched_at: datetime

class SourceAdapter(Protocol):
    def fetch(self) -> Iterable[RawRecord]: ...
    def extract_structure(self, record: RawRecord) -> list[RawSection]: ...
    def classify_rights(self, record: RawRecord) -> RightsRule | None: ...
```

`classify_rights` gibt `None` zurück, wenn die Quelle den Fall nicht zuordnen kann — der
Runner legt dann keine Klassifikationszeile und keine abgeleiteten Artefakte an, sondern
reiht den Datensatz in `identity_resolution_case` ein (`reason="cannot_classify_rights"`).
Das ist der in der Fehlerbehandlung geforderte sichere Default; ursprünglich zwang die
Protocol-Signatur jeden Adapter zu einer Antwort, das wurde in der Abschluss-Review
korrigiert. Ebenso prüft der Runner `regel.may_process` vor jedem Schreibzugriff
(`reason="processing_not_permitted"` bei `False`) — beide Adapter liefern heute immer eine
erlaubende, vollständige Regel, die Fähigkeit ist aber jetzt im Typsystem vorhanden.
`SourceAdapter` lebt tatsächlich in `pipeline/domain.py` (nicht in einer eigenen
`adapters/base.py`, siehe korrigiertes Modullayout unten).

`fetch()` nimmt kein `since` entgegen: Ein Verzeichnis-Adapter listet bei jedem Lauf alle
konfigurierten Dateien auf (der Ordnerpfad kommt über den Adapter-Konstruktor, nicht über
`fetch()`); welche Lieferungen tatsächlich neu sind, entscheidet `find_delivery` anhand des
Inhalts-Hashes (REQ-PIPE-006) — nicht ein Zeitstempel-Filter beim Abruf.

### EUR-Lex-Quellformat: „Summary list of harmonised standards"

Recherchiert und mit einer echten, real abgerufenen Beispieldatei verifiziert (Kommissions-PDF
für die Maschinenrichtlinie 2006/42/EC, generiert 15.10.2021, abrufbar über
`single-market-economy.ec.europa.eu`). Konsistente Tabellenstruktur, eine Zeile je Norm:

| Spalte im PDF | Beispiel | Verwendung |
|---|---|---|
| Legislation reference | `2006/42/EC` | Adapter-Konfiguration (eine PDF-Datei je Rechtsakt), nicht pro Zeile — wird zur `based_on_law`-Kante |
| ESO | `CEN` | `raw_issuer` |
| Reference number of the standard | `EN ISO 12100:2010` | `raw_designation` |
| Title of the standard | „Safety of machinery - General principles for design..." | `raw_title` |
| Type | `A` / `B` | vorerst nicht modelliert (YAGNI) |
| Date of start of presumption of conformity | `08/04/2011` | vorerst nicht modelliert |
| OJ reference for publication in OJ | `OJ C 110 - 08/04/2011` | Beleg für die `based_on_law`-Kante (nicht als eigenes Feld gespeichert) |
| Restriction, Datum/OJ-Referenz für Restriction | meist `-` | vorerst nicht modelliert |
| Date of withdrawal from OJ | z. B. `03/09/2022` | vorerst nicht modelliert — die Tabelle nennt kein Nachfolgestandard, nur ein Rückzugsdatum; eine `withdrawn_by`-Kante bräuchte ein Zieldokument, das hieraus allein nicht sauber ableitbar ist. Bewusste Vereinfachung für den Start, siehe Offene Punkte. |

Pro Zeile entsteht: `document_designation` mit `(issuer="CEN", designation="EN ISO 12100:2010")`,
`document_title` mit dem Titel, und eine `RawReference(target_designation="2006/42/EC",
edge_type=EdgeType.BASED_ON_LAW)`. Der Rechtsakt selbst (`2006/42/EC`) wird beim ersten
Adapter-Lauf als eigener `document`-Knoten angelegt (Herausgeber „EU", Nummer „2006/42/EC").

Begleitende Hilfstypen (ebenfalls in `pipeline.domain`, keine SQLAlchemy-Abhängigkeit):

```python
@dataclass(frozen=True)
class RawReference:
    target_designation: str        # Bezeichnung des Zieldokuments, roh
    edge_type: EdgeType            # aus graph.domain, z. B. REFERENCES, REPLACES

@dataclass(frozen=True)
class RawSection:
    sequence_number: int
    heading: str | None
    text: str

@dataclass(frozen=True)
class RightsRule:
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str

@dataclass(frozen=True)
class IdentityResolution:
    document_id: uuid.UUID | None  # None, wenn neu anzulegen
    is_new: bool
    is_ambiguous: bool
    reason: str | None             # gesetzt, wenn is_ambiguous
```

`extract_structure` liefert für EUR-Lex immer eine leere Liste (kein Volltext).
`classify_rights` kapselt die quellenspezifische Rechteregel (siehe Datenfluss) — jeder
Adapter kennt seine eigene Rechtslage, die Pipeline selbst enthält keine quellenspezifische
Fallunterscheidung.

### Modullayout

Teil desselben `core`-Pakets, keine neue Top-Level-Komponente:

```
core/src/normly_core/pipeline/
  domain.py          # RawRecord, RawSection, RawReference, RightsRule,
                       # IdentityResolution, SourceAdapter Protocol
  sources.py           # Quellregister (Publisher -> Kategorie/Rechtsraum/Meta),
                       # resolve_source() legt fehlende Registereinträge idempotent an
  adapters/
    __init__.py
    eur_lex.py
    dguv.py
  identity.py         # Bezeichnung parsen + gegen document_designation abgleichen
  references.py       # RawReference -> edge (Layer aus RightsRule.may_export_free)
  embeddings.py        # EmbeddingModel-Wrapper um sentence-transformers,
                       # optionaler lokaler model_path (siehe unten)
  runner.py           # Orchestrierung (siehe Datenfluss)
  cli.py              # build_adapter(), main()
  __main__.py          # `python -m normly_core.pipeline ingest <quelle>`
```

Abweichung vom ursprünglichen Entwurf: `SourceAdapter` liegt in `domain.py` statt in einer
eigenen `adapters/base.py` (konsistent mit `graph.domain`, das ebenfalls seine Protocols
neben den Dataclasses führt). `cli.py` allein reicht für `python -m` nicht aus — `-m`
benötigt ein `__main__.py`, das war im ursprünglichen Modullayout nicht vorgesehen und wurde
bei der Umsetzung ergänzt.

**Quellregister (`sources.py`).** CLAUDE.md verlangt für jede Quelle einen Registereintrag
mit Kategorie. `resolve_source(publisher, session)` sucht per `SourceRepository.find_by_publisher`
nach einer bestehenden `source`-Zeile und legt sie sonst mit fest hinterlegten Metadaten an
(EUR-Lex: Kategorie A, Rechtsraum EU; DGUV: Kategorie A, Rechtsraum DE). Die Suche geht über
den bloßen `publisher`-Namen, nicht über den vollständigen Registereintrag (Kategorie/
Rechtsraum/Bezugspfad) — für die zwei aktuellen, fest verdrahteten Quellen unproblematisch,
aber eine spätere Härtung (eindeutiger Index über die volle Kombination) ist offen, siehe
Offene Punkte.

`pipeline.domain` bleibt frei von SQLAlchemy, wie `graph.domain` — dieselbe Grenze.
Adapter-spezifische Abhängigkeiten (HTTP-Client, `lxml`, PDF-Extraktion) sind auf die
jeweilige Adapter-Datei beschränkt.

### Testphilosophie

Wie im vorigen Teilprojekt: kein Mocking der Datenbank (echtes PostgreSQL mit `pgvector`
über Testcontainers) und kein Mocking des Embedding-Modells (echtes
`multilingual-e5-large`). Adapter-Tests laufen gegen einmalig aufgezeichnete, echte
Beispieldateien (die echte EUR-Lex-"Summary list"-PDF, ein DGUV-PDF), keine Live-Netzwerkaufrufe.

## Datenmodell-Erweiterung

### `segment` — Volltextabschnitt (nur DGUV)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `delivery_id` | UUID, FK → `delivery` | Abstammung |
| `sequence_number` | int | Reihenfolge im Dokument |
| `heading` | text, nullable | z. B. „§ 3 Grundpflichten" |
| `text` | text | |
| `language` | text | ISO 639-1 |
| `created_at` | timestamptz | |

Segmentgrenzen folgen den natürlichen Gliederungseinheiten der Quelle (§-Absätze bei
DGUV-Vorschriften) — keine separate Chunking-Stufe für den Start (YAGNI, siehe
Pipeline-Stufen).

Eindeutigkeit über `(document_id, delivery_id, sequence_number)`, nicht nur
`(document_id, sequence_number)` — Letzteres hätte bei einer erneuten Lieferung desselben
Dokuments (z. B. einer geänderten DGUV-PDF) die neuen Abschnittstexte stillschweigend
verworfen und die Zeile der ersten Lieferung zurückgegeben, mit denselben Folgen für die
kaskadierende Rücknahme wie bei `document_designation`/`document_title` im vorigen
Teilprojekt. In der Abschluss-Review korrigiert (Migration `0012`). Lesezugriffe filtern
noch nicht nach der jeweils aktiven Lieferung — bei einer zweiten, noch nicht
zurückgezogenen Lieferung desselben Dokuments würden beide Zeilenmengen zusammen
zurückgegeben. Offener Punkt, siehe unten.

### `embedding` — Vektorrepräsentation eines Segments

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `segment_id` | UUID, FK → `segment` | |
| `delivery_id` | UUID, FK → `delivery` | Abstammung |
| `model_name` | text | z. B. „intfloat/multilingual-e5-large" |
| `vector` | `vector(1024)` (pgvector) | |
| `created_at` | timestamptz | |

`UNIQUE(segment_id, model_name)` — ein Segment kann mehrere Embeddings verschiedener
Modellversionen haben, ohne dass der Text erneut extrahiert werden muss.

Beide Tabellen erhalten dieselbe Idempotenz- (`_require_active_delivery`,
Select-vor-Insert-mit-`IntegrityError`-Wiederherstellung) und Rücknahme-Behandlung
(kaskadierende Sperrung/Löschung bei `revoke_delivery`) wie die bestehenden Tabellen. Der
Drift-Schutztest aus dem vorigen Teilprojekt muss um diese beiden Tabellen erweitert werden
— er schlägt bewusst fehl, bis das geschieht.

**Neue Repository-Schnittstellen:** `SegmentRepository` (`add_segment`,
`list_segments_for_jurisdiction` — rechte-gegatet nach demselben Muster wie
`list_documents_for_jurisdiction`) und `EmbeddingRepository` (`add_embedding`,
`get_embedding`).

**Kleine, nicht-brechende Erweiterung an `DeliveryRepository`:** eine neue Methode
`find_delivery(source_id, content_hash) -> Delivery | None`, die die Pipeline vor
`record_delivery` aufruft, um unveränderte Lieferungen ohne teure Weiterverarbeitung zu
überspringen (REQ-PIPE-006). `record_delivery` selbst bleibt unverändert — kein Eingriff in
bereits abgenommenen, gemergten Code.

### `identity_resolution_case` — Prüf-Warteschlange (REQ-PIPE-007)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `delivery_id` | UUID, FK → `delivery` | |
| `raw_designation` | text | |
| `raw_issuer` | text, nullable | |
| `reason` | text | z. B. „unparseable_designation" |
| `status` | enum(pending, resolved, rejected) | |
| `resolved_document_id` | UUID, FK → `document`, nullable | |
| `resolved_at` | timestamptz, nullable | |
| `resolved_by` | text, nullable | |
| `created_at` | timestamptz | |

Kein Rechte-Gate nötig — interner Verwaltungsvorgang, keine Inhaltsauslieferung. Neue
Repository-Schnittstelle `IdentityResolutionRepository` (`enqueue_case`,
`list_pending_cases`, `resolve_case`, `reject_case`).

## Pipeline-Stufen

**Identitätsauflösung.** Eingehende Bezeichnung wird in Herausgeber/Nummer/Ausgabestand
geparst und gegen `document_designation` exakt abgeglichen (`(issuer, designation)`).
Treffer → vorhandener Knoten. Kein Treffer → neuer Knoten. Nicht parsbar → Fall in
`identity_resolution_case`, restlicher Bestand läuft unbeeinflusst weiter.

**Rechteklassifikation.** Automatisch, aber quellenspezifisch, nicht pauschal nach
Kategorie: EUR-Lex-Normknoten (kein Volltext bekannt) erhalten `may_process=true`,
`may_export_free=true`, aber `may_index_fulltext=false`, `may_cite_passages=false`.
DGUV-Dokumente (echter, freier Volltext, § 5 UrhG) erhalten alle vier Flags `true`.

**Strukturextraktion (nur DGUV).** PDF-Text wird extrahiert und anhand der üblichen
DGUV-Gliederung (§-Absätze, nummerierte Abschnitte) in Segmente zerlegt — regelbasiert,
kein generisches Layout-Verständnis.

**Verweisextraktion.** EUR-Lex: Rechtsakt-Knoten (ebenfalls ein `document`, Kategorie A)
erhält `based_on_law`-Kanten zu gelisteten Normknoten. DGUV: zitierte Normen/Gesetze ergeben
`references`-Kanten, Versionshistorie ergibt `replaces`/`withdrawn_by`.

**Segmentierung und Einbettung (nur DGUV).** Jedes extrahierte Segment wird über
`multilingual-e5-large` eingebettet und als `embedding`-Zeile gespeichert.

## Datenfluss

```
für jeden RawRecord aus adapter.fetch():
    wenn delivery_repo.find_delivery(source_id, content_hash) vorhanden: weiter  # REQ-PIPE-006
    versuche (in einem Savepoint, siehe Fehlerbehandlung):
        delivery = delivery_repo.record_delivery(source_id, content_hash, ingested_at)

        regel = adapter.classify_rights(raw_record)
        wenn regel ist None ODER regel.may_process ist False:
            identity_resolution_repo.enqueue_case(delivery_id, raw_designation, raw_issuer, reason)
            Savepoint erfolgreich beenden, nächster Datensatz  # keine Artefakte angelegt

        ergebnis = identity.resolve(raw_record)
        wenn ergebnis uneindeutig:
            identity_resolution_repo.enqueue_case(delivery_id, raw_designation, raw_issuer, reason)
            Savepoint erfolgreich beenden, nächster Datensatz

        document = ergebnis.document ODER document_repo.create_document(..., delivery_id)
        document_repo.add_designation(document.id, ..., sprache=raw_record.language, delivery_id)

        rights_repo.classify(document.id, regel.jurisdiction, regel.may_process, ..., delivery_id)

        für jede RawReference in raw_record.raw_references:
            references.extract(raw_record, document, regel, delivery_id)  # Layer aus regel.may_export_free

        wenn raw_record.full_text ist nicht None:
            für jeden RawSection in adapter.extract_structure(raw_record):
                segment = segment_repo.add_segment(document.id, delivery_id, ..., abschnitt)
                vektor = embeddings.embed(segment.text)
                embedding_repo.add_embedding(segment.id, delivery_id, modell_name, vektor)
    außer Exception:
        Savepoint zurückrollen (inkl. der `delivery`-Zeile — sonst gilt der Datensatz beim
        nächsten Lauf fälschlich als bereits verarbeitet), records_failed zählen, weiter
```

Jeder Schreibaufruf mit `delivery_id` läuft durch den bereits bestehenden
`_require_active_delivery`-Schutz — keine Änderung an dessen Semantik nötig, die neuen
Repository-Methoden reihen sich nur ein.

Der ursprüngliche Entwurf sah keine Fehlerisolation je Datensatz vor (`record_delivery` lag
außerhalb jeder Transaktionsgrenze). In der Abschluss-Review korrigiert: die gesamte
Verarbeitung eines Datensatzes — inklusive `record_delivery` selbst — läuft in einem
`session.begin_nested()`-Savepoint, damit ein Fehler nirgendwo im Datensatz eine
halb-angelegte `delivery`-Zeile hinterlässt, die den Datensatz beim nächsten Lauf
fälschlich als „bereits verarbeitet" erscheinen ließe.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| `adapter.fetch()` schlägt fehl (Netzwerk/API) | Lauf bricht für diese Quelle ab, keine Teil-Ergebnisse; nächster Lauf versucht erneut |
| Ein einzelner Datensatz löst eine Ausnahme aus (beliebige Ursache) | Savepoint für diesen Datensatz rollt vollständig zurück (inkl. `delivery`), `records_failed` gezählt, Lauf setzt mit dem nächsten Datensatz fort — echte Wiederholbarkeit beim nächsten Lauf |
| Bezeichnung nicht parsbar / Identität uneindeutig | `identity_resolution_case`, blockiert nur dieses Dokument |
| Struktur-/Verweisextraktion schlägt für einen Datensatz fehl | Gleiche Warteschlange, gleiche Isolation |
| Automatische Rechteklassifikation kann Fall nicht zuordnen (`classify_rights` liefert `None`) | Keine Klassifikationszeile, keine abgeleiteten Artefakte — `identity_resolution_case` mit `reason="cannot_classify_rights"`, Dokument bleibt gesperrt (sicherer Default) |
| `regel.may_process` ist `False` | Gleiche Warteschlange, `reason="processing_not_permitted"` |
| Embedding schlägt für ein Segment fehl | Segment ohne Embedding, Fehler geloggt, nächster Lauf holt es nach (`add_embedding` idempotent über `(segment_id, model_name)`) |
| Schreiboperation auf zurückgezogene Lieferung | `WithdrawnDeliveryError` (bestehender Mechanismus) |

## Testkonzept

- Testcontainer wechselt auf ein pgvector-fähiges PostgreSQL-Image; neue Migration
  aktiviert die `vector`-Extension und legt `segment`, `embedding`,
  `identity_resolution_case` an.
- Adapter-Tests gegen echte, eingecheckte Beispieldateien (echte EUR-Lex-"Summary list"-PDF,
  DGUV-PDF) — beides amtliche Kategorie-A-Werke, unproblematisch einzuchecken.
- Identitätsauflösung isoliert getestet: sauberer Treffer, neuer Knoten, nicht parsbar.
- End-to-End-Test: volle Pipeline gegen beide Beispieldateien, prüft die
  Rechte-Gate-Asymmetrie direkt (EUR-Lex-Knoten nicht volltext-indexiert, DGUV-Knoten mit
  echten Embedding-Vektoren) sowie `find_delivery`s Skip-Verhalten bei wiederholtem Lauf.
- Kaskadierende Rücknahme erweitert auf Segmente/Embeddings getestet, gleiches Muster wie
  der bestehende `revoke_delivery`-Test.
- Embedding-Tests nutzen durchgängig das echte Modell, kein Stub (Entscheidung mit dem
  Auftraggeber, siehe Kontext) — Testlaufzeit ist entsprechend höher als im vorigen
  Teilprojekt.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-PIPE-001 | Adapter-Abstraktion, herkunftsunabhängige Verarbeitung ab Identitätsauflösung |
| REQ-PIPE-002 | `source`-Einträge für EUR-Lex/DGUV (bereits im Schema, hier befüllt) |
| REQ-PIPE-003 | TDM-Vorbehaltsprüfung bei Quellregistrierung dokumentiert (Feld bereits vorhanden) |
| REQ-PIPE-004 | Automatische, quellenspezifische Rechteklassifikation je Dokument/Rechtsraum |
| REQ-PIPE-005 | `delivery_id` an `segment`/`embedding`, kaskadierende Rücknahme erweitert |
| REQ-PIPE-006 | `find_delivery`-Skip, idempotente `add_segment`/`add_embedding` |
| REQ-PIPE-007 | `identity_resolution_case`-Warteschlange, isolierte Blockade je Dokument |
| REQ-PIPE-009 | EUR-Lex und DGUV sind beide Kategorie A/B, kein Kategorie-C/D-Zugriff |
| REQ-GRAPH-001 | Rechtsakte als eigene `document`-Knoten, `based_on_law`-Kanten |
| ADR-006 | pgvector in derselben Datenbank wie der Graph |
| ADR-008 | Struktur-/Verweisdaten fließen in den Graph, kein LLM-Aufruf für Ersetzungs-/Verweisfragen |
| ADR-012 | Weder EUR-Lex noch DGUV sind kommerziell verwertete Kataloge — unproblematisch |

## Offene Punkte / Folgearbeiten

- **Weitere Adapter** (BAuA, CEN/CENELEC, ISO/IEC-Katalogdaten) — Abstraktion ist darauf
  ausgelegt, aber nicht Teil dieses Teilprojekts.
- **Chunking über Gliederungsgrenzen hinaus**, falls einzelne DGUV-Abschnitte für sinnvolle
  Embeddings zu lang sind — mit den zwei gewählten Quellen noch nicht beobachtbar, daher
  hier nicht spezifiziert.
- **Bedienoberfläche für `identity_resolution_case`** — Backend-API-/Frontend-Teilprojekt.
- **Scheduler/Automatisierung des CLI-Laufs** — Deployment-Entscheidung, nicht Teil dieses
  Teilprojekts.
- **STACKIT Object Storage für Rohdateien** statt lokaler Festplattenablage — ebenfalls eine
  spätere Deployment-Entscheidung, analog zur Datenbank-Frage aus dem vorigen Teilprojekt.
- **EUR-Lex-Rückzugsdatum ohne Nachfolgestandard.** Die „Summary list"-Tabelle nennt für
  zurückgezogene Normen nur ein Datum und eine OJ-Referenz, keinen Nachfolgestandard — eine
  `withdrawn_by`-Kante bräuchte aber ein Zieldokument. Für den Start wird das Rückzugsdatum
  nicht modelliert; eine spätere Verfeinerung könnte die referenzierte Entscheidung
  (OJ-Referenz) selbst als Knoten führen.
- **Echter HTTP-Fetch für EUR-Lex/DGUV** — die Parsing-Formate sind jetzt verifiziert (siehe
  Architektur), das automatisierte Abrufen selbst (Login/Pagination/Ratenbegrenzung) bleibt
  Folgearbeit.
- **Embedding-Modell-Beschaffung berührt eine US-Dienst-Frage.** `EmbeddingModel` lädt das
  Modell standardmäßig von `huggingface.co` (Inferenz selbst läuft lokal, wie von
  CLAUDE.md gefordert — nur die einmalige Gewichte-Beschaffung nicht). In der
  Abschluss-Review um einen optionalen `model_path`/`NORMLY_EMBEDDING_MODEL_PATH` ergänzt:
  ein STACKIT-Betrieb muss die Gewichte vorab bereitstellen (z. B. im Container-Image oder
  über STACKIT Object Storage) und niemals zur Laufzeit von Hugging Face laden. Die
  eigentliche Bereitstellungs-Pipeline dafür ist nicht Teil dieses Teilprojekts.
- **`resolve_source` matcht nur auf `publisher`**, nicht auf den vollständigen
  Registereintrag (Kategorie/Rechtsraum/Bezugspfad). Für die zwei aktuellen, im Code fest
  hinterlegten Quellen unproblematisch; sobald ein Herausgeber mehrere, unterschiedlich
  klassifizierte Registereinträge haben kann, braucht es einen eindeutigen Index über die
  volle Kombination statt der bloßen Publisher-Zeichenkette.
- **`list_segments_for_jurisdiction` filtert nicht nach der jeweils aktiven Lieferung.**
  Seit Migration `0012` kann ein Dokument bei zwei aktiven, nicht zurückgezogenen
  Lieferungen (z. B. einer korrigierten Neulieferung) Segmente aus beiden Lieferungen
  gleichzeitig zurückgeben. Vor einer produktiven API auf dieser Lesemethode braucht es
  entweder einen „letzte aktive Lieferung"-Filter oder einen expliziten
  Rücknahme-Schritt für die vorige Lieferung bei einer Neulieferung desselben Dokuments.
- **Der Architektur-Drifttest für den Rechtsraum-Zwang** (`test_architecture.py`) prüft nur
  `get_*`/`list_*`-Methoden auf den Repository-Protocols, nicht `find_*` — sowohl das
  bestehende `DocumentRepository.find_by_designation` als auch das neue
  `SourceRepository.find_by_publisher` sind ungated und entgehen dem Test dadurch. Sollte
  bei nächster Gelegenheit im Testcode selbst nachgezogen werden.
- **`RunSummary.records_processed` zählt auch später fehlgeschlagene Datensätze** (der
  Zähler wird vor dem eigentlichen Verarbeitungsversuch erhöht) — `processed` und `failed`
  aus der CLI-Ausgabe addieren sich dadurch nicht sauber zur Gesamtzahl auf.
