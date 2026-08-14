# Design: Datenmodell & Referenzgraph-Schema

**Datum:** 2026-08-11
**Status:** zur Durchsicht
**Teilprojekt:** erstes von mehreren zur Umsetzung des normly-MVP (freier Kern)

## Kontext

normly hat aktuell keine Code-Basis, nur Dokumentation (`docs/adr/`, `docs/srs/`). Das
volle SRS umfasst 78 Requirements über den gesamten Zielzustand — freier Kern und
kommerzielle Schicht, Partnerportal, DRM, native App, Third-Party-Integrationen. Das ist
kein Umfang für ein einzelnes Teilprojekt.

**Entschieden mit dem Auftraggeber:**

1. Nur der MVP-Umfang wird umgesetzt: freier Kern, eigenständige Webanwendung, Chat über
   ein Open-Source-LLM, Referenzgraph aus frei zugänglichen Quellen (Kategorie A/B). Keine
   Konten, kein Billing, kein DRM, keine native App.
2. Erstes Teilprojekt innerhalb des MVP: **Datenmodell & Referenzgraph-Schema**. API,
   Ingestion-Pipeline und Chat-Frontend setzen darauf auf und werden als eigene
   Teilprojekte mit eigenem Spec→Plan→Umsetzung-Zyklus behandelt.
3. Backend-Stack für dieses Teilprojekt: **Python**, SQLAlchemy, Alembic.

## Ziel dieses Teilprojekts

Ein PostgreSQL-Schema (mit pgvector, ADR-006) für den Normen-Referenzgraph, plus eine
Repository-Schicht, die die Fachlogik vollständig von der konkreten Speichertechnologie
trennt (REQ-GRAPH-004). Das Schema deckt ab: global eindeutige, sprachunabhängige
Knotenidentität (REQ-GRAPH-005), Kanten mit Rechtsraum- und Schichtungsattribut
(REQ-GRAPH-002/006), Rechteklassifikation als Verarbeitungstor (REQ-PIPE-004), und
lückenlose Abstammung jedes abgeleiteten Artefakts auf eine Quelllieferung
(REQ-PIPE-005/006).

## Nicht-Ziele

Bewusst nicht Teil dieses Teilprojekts — jeweils eigene spätere Teilprojekte:

- **Ingestion-Pipeline:** Ingest-Adapter, Identitätsauflösung, Struktur- und
  Verweisextraktion, Segmentierung, Einbettung (REQ-PIPE-001). Dieses Teilprojekt legt
  nur die Zieltabellen an, in die eine Pipeline später schreibt.
- **Ein Perinorm/DIN-Media-Format-Adapter.** Herausgeber, die künftig Bestände in einem
  Perinorm-artigen Feldformat liefern, werden über einen eigenen Ingest-Adapter
  angebunden, der auf dieses generische Schema abbildet — aber erst, wenn ein
  Kategorie-C-Vertrag mit dem jeweiligen Herausgeber vorliegt (REQ-PIPE-002). Das
  Kernschema selbst bleibt herausgeber- und formatneutral: Es wird unter ODbL
  veröffentlicht (REQ-GRAPH-001), und eine Anlehnung an das lizenzrechtlich geschützte
  Perinorm-Feldschema (Annex 1 zum "Metadata License Agreement" von AFNOR/BSI/DIN) würde
  sowohl dessen Copyright-Vorbehalt ("no further processing without prior written
  approval") als auch ADR-012 (kein Nachbau kommerziell verwerteter Katalogbestände)
  berühren.
- **Segment- und Einbettungstabellen** für Volltextverarbeitung. ADR-006 sieht Graph und
  Embeddings in derselben Datenbank vor, aber die Population dieser Tabellen ist
  Pipeline-Arbeit. Das Schema ist so angelegt, dass sich eine Segment-/Embedding-Tabelle
  später ergänzen lässt, ohne das Kernschema zu ändern (gleiches Abstammungsmuster:
  eigene `delivery_id` je Zeile).
- **Öffentliche API und Chat-Kernlogik.** Konsumieren dieses Schemas über die
  Repository-Schnittstelle, sind aber ein eigenes Teilprojekt.

## Architektur

### Repository-Muster

Drei Ansätze wurden abgewogen:

1. SQLAlchemy Core ohne ORM, Repository-Interfaces als `Protocol`.
2. SQLAlchemy-ORM-Modelle direkt als Domänenmodelle.
3. **SQLAlchemy-ORM intern, an der Repository-Grenze auf einfache Domänen-Dataclasses
   gemappt.**

Entschieden: **Ansatz 3.** Er erfüllt das Abnahmekriterium von REQ-GRAPH-004 wörtlich
("Architektur-Review bestätigt, dass die Fachlogik keine Kenntnis der konkreten
Graphtechnologie besitzt"), behält Alembic-Autogenerate für Migrationen, und
unterstützt rekursive CTEs für Ersetzungsketten über SQLAlchemy direkt (laut ADR-006
für die vorliegende Kantentiefe ausreichend).

**Aufbau:**

- **Domänenschicht** (`normly_core.graph.domain`): reine Python-Dataclasses
  (`Document`, `DocumentDesignation`, `DocumentTitle`, `Edge`, `RightsClassification`,
  `Source`, `Delivery`) sowie Repository-Interfaces als `Protocol`
  (`DocumentRepository`, `EdgeRepository`, `RightsRepository`, `SourceRepository`,
  `DeliveryRepository`). Kein Import von SQLAlchemy.
- **Postgres-Adapter** (`normly_core.graph.postgres`): SQLAlchemy-ORM-Modelle (privat,
  nicht exportiert), Implementierung der Repository-Interfaces, Mapping-Funktionen
  ORM ↔ Dataclass, Alembic-Migrationsverzeichnis.
- Die Fachlogik (spätere Teilprojekte) importiert ausschließlich aus der
  Domänenschicht.

### Rechte-Gate als Teil der Schnittstelle, nicht als Aufrufer-Pflicht

Es gibt in `DocumentRepository` keine Methode, die Dokumente ohne Rechtsraum-Parameter
zurückgibt. Jede lesende Methode verlangt einen Rechtsraum und joint intern gegen
`rights_classification`. Damit ist REQ-PIPE-004 ("fehlende Klassifikation gilt nicht als
vorläufige Erlaubnis") strukturell erzwungen — es gibt keinen Aufrufpfad, der ihn
umgehen könnte, nicht nur eine Konvention, die man vergessen kann.

## Datenmodell

### `source` — Quellenregister (REQ-PIPE-002)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `publisher` | text | |
| `retrieval_path` | text | |
| `legal_basis_category` | enum(A,B,C,D) | |
| `jurisdiction` | text | ISO 3166-1 alpha-2 |
| `reviewed_at` | date | |
| `responsible_person` | text | |
| `commercial_catalog` | boolean | Default `false` |
| `contract_reference` | text, nullable | Pflicht bei Kategorie C (CHECK) |
| `tdm_opt_out_checked_at` | date, nullable | REQ-PIPE-003 |
| `tdm_opt_out_result` | enum(none_found, opt_out_present), nullable | |

CHECK-Constraints: `legal_basis_category = 'D' AND commercial_catalog` ist unzulässig
(REQ-PIPE-008/ADR-012 — technische Sperre, keine Richtlinie). Kategorie C ohne
`contract_reference` ist unzulässig.

### `delivery` — Lieferung/Ingest-Lauf (REQ-PIPE-006)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `source_id` | UUID, FK → `source` | |
| `content_hash` | text | Inhaltsadressierung; `UNIQUE(source_id, content_hash)` |
| `ingested_at` | timestamptz | |
| `withdrawn_at` | timestamptz, nullable | |

### `document` — Knoten, ein Regelwerk (REQ-GRAPH-005)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | interner, stabiler Identifikator |
| `origin_issuer` | text | Herausgeber der international führenden Bezeichnung |
| `origin_number` | text | |
| `edition` | text | Ausgabestand |
| `part` | text, nullable | Teilnummer |
| `created_via_delivery_id` | UUID, FK → `delivery` | erste Lieferung, aus der der Knoten entstand |
| `created_at` | timestamptz | |

### `document_designation` — nationale Übernahmen (REQ-GRAPH-005)

Nationale Übernahmen und Übersetzungen sind **keine eigenen Knoten**, sondern Zeilen an
einem Knoten — das entspricht dem Abnahmekriterium wörtlich ("ein Knoten mit
zugeordneten Übernahmen").

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `issuer` | text | z. B. DIN, BSI, AFNOR |
| `designation` | text | z. B. "DIN EN ISO 9001" |
| `language` | text | ISO 639-1 |
| `edition` | text, nullable | falls abweichend vom Knoten |
| `is_primary` | boolean | |
| `delivery_id` | UUID, FK → `delivery` | |
| `created_at` | timestamptz | |

`UNIQUE(issuer, designation)`.

### `document_title` — mehrsprachige Bezeichnungen (REQ-GRAPH-005)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `document` | |
| `language` | text | ISO 639-1 |
| `title` | text | |
| `delivery_id` | UUID, FK → `delivery` | |

### `edge` — Kanten (REQ-GRAPH-001/002)

| Spalte | Typ | Hinweis |
|---|---|---|
| `id` | UUID, PK | |
| `from_document_id` | UUID, FK → `document` | |
| `to_document_id` | UUID, FK → `document` | |
| `edge_type` | enum | `references`, `replaces`, `withdrawn_by`, `based_on_law`, `adopted_from` |
| `jurisdiction` | text, nullable | `NULL` = global gültig |
| `layer` | enum(free, commercial) | Default `free` (REQ-GRAPH-002) |
| `delivery_id` | UUID, FK → `delivery` | |
| `revoked_at` | timestamptz, nullable | |
| `created_at` | timestamptz | |

Partieller Unique-Index `(from_document_id, to_document_id, edge_type, jurisdiction)
WHERE revoked_at IS NULL` verhindert doppelte aktive Kanten.

`adopted_from` deckt den Fall ab, in dem die Identitätsauflösung zwei Dokumente als
verwandt, aber nicht identisch einstuft (z. B. internationale Basisnorm vs. regionale
Adoption mit inhaltlicher Abweichung) — im Unterschied zur reinen Attributbeziehung in
`document_designation`, wo beide Bezeichnungen dasselbe Dokument meinen. Die
Entscheidung, welcher Fall vorliegt, ist Aufgabe der Identitätsauflösung
(REQ-PIPE-007, außerhalb dieses Teilprojekts).

### `rights_classification` — Rechteklassifikation je Rechtsraum (REQ-GRAPH-006, REQ-PIPE-004)

| Spalte | Typ | Hinweis |
|---|---|---|
| `document_id` | UUID, FK → `document` | Teil des Composite-Keys |
| `jurisdiction` | text | Teil des Composite-Keys |
| `may_process` | boolean | |
| `may_index_fulltext` | boolean | |
| `may_cite_passages` | boolean | |
| `may_export_free` | boolean | |
| `legal_basis_reference` | text | |
| `classified_at` | timestamptz | |
| `classified_by` | text | |
| `delivery_id` | UUID, FK → `delivery` | |
| `revoked_at` | timestamptz, nullable | |

Fehlt die Zeile für `(document_id, jurisdiction)`, gilt der Knoten für diesen
Rechtsraum als gesperrt — durchgesetzt per Inner-Join im Repository (siehe
Architektur), nicht per Anwendungslogik-Check.

## Datenfluss: Abstammung & Rechte-Durchsetzung

**Schreibpfad.** Jede schreibende Repository-Methode verlangt `delivery_id` als
Pflichtparameter. Es gibt keinen Pfad, der einen Knoten, eine Kante, eine Bezeichnung
oder eine Klassifikation ohne Bezug auf eine Lieferung anlegt. Jede dieser Methoden
prüft zuerst, ob die Lieferung existiert und nicht zurückgezogen ist; andernfalls
bricht sie mit `WithdrawnDeliveryError` ab. Ohne diese Prüfung würde ein erneuter
Ingest-Lauf für eine zurückgezogene Lieferung die Rücknahme wieder aufheben.

**Lesepfad.** Jede für Anzeige, Zitierung oder Export bestimmte Leseoperation verlangt
einen Rechtsraum-Parameter und filtert intern über `rights_classification`. Im
öffentlichen Protokoll `DocumentRepository` gibt es keine Methode, die Dokumente
ungefiltert zurückgibt. Die konkrete Implementierung trägt daneben ungefilterte
Methoden (`get_document_unchecked`, `list_designations`, `list_titles`) für
Identitätsauflösung, Pipeline und Administration — sie sind bewusst nicht Teil des
Protokolls und kein Auslieferungspfad für Inhalte.

**Rücknahmepfad.** `revoke_delivery(delivery_id)` markiert `delivery.withdrawn_at`,
setzt `revoked_at` auf alle zugehörigen `edge`- und `rights_classification`-Zeilen und
löscht die zugehörigen `document_designation`- und `document_title`-Zeilen — alles in
einer Transaktion, vollständig und atomar. Einen eigenen Protokolleintrag schreibt der
Pfad heute **nicht**: ein Audit-Trail existiert in diesem Teilprojekt noch nicht (siehe
Offene Punkte). Ein `document`-Knoten ohne verbleibende aktive
Bezeichnung, Kante oder Klassifikation gilt als verwaist und wird aus Leseergebnissen
ausgeschlossen, aber nicht sofort gelöscht (Nachvollziehbarkeit). Bleiben andere
Lieferungen den Knoten weiter stützen, bleibt er unangetastet — Abstammung wirkt auf
Artefaktebene, nicht auf Knotenebene. Klassifiziert eine andere, weiterhin aktive
Lieferung dasselbe Dokument/denselben Rechtsraum später erneut, hebt das die vorherige
Rücknahme bewusst auf — das ist eine erneute, eigenständige Rechteprüfung (REQ-PIPE-004),
kein zweiter Prüfpfad um die Rücknahme herum. Unterbunden wird ausschließlich die
Wiederverwendung derselben, bereits zurückgezogenen Lieferung (`WithdrawnDeliveryError`,
siehe Schreibpfad).

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Schreiboperation ohne `delivery_id` | Typfehler zur Aufrufzeit (Pflichtparameter) |
| Schreiboperation auf eine unbekannte oder bereits zurückgezogene Lieferung | `WithdrawnDeliveryError` (Domänenfehler, kein SQL-Fehler) |
| Quelle Kategorie D mit `commercial_catalog=true` | DB-Constraint-Verletzung, als eigener Fehlertyp im Repository gefangen und weitergereicht |
| Quelle Kategorie C ohne `contract_reference` | DB-Constraint-Verletzung, ebenso |
| Lesezugriff ohne Klassifikation für den Rechtsraum | kein Fehler — leeres Ergebnis (Normalfall, kein Ausnahmezustand) |
| Rücknahme einer bereits zurückgezogenen Lieferung | idempotent, kein Fehler |

## Testkonzept

Migrationen und Repository-Implementierung laufen gegen einen echten PostgreSQL-Container
(lokal, Testcontainers — reine Testinfrastruktur, kein Betrieb, kein Konflikt mit der
STACKIT-Vorgabe). Testfälle bilden die Abnahmekriterien der betroffenen Requirements
direkt ab:

- Wiederholte Anwendung derselben Migrations-/Ingest-Fixture erzeugt kein abweichendes
  Ergebnis (REQ-PIPE-006).
- Ein Knoten mit drei nationalen Bezeichnungen wird als **ein** Knoten mit drei
  `document_designation`-Zeilen gelesen (REQ-GRAPH-005).
- Zwei Rechtsraum-Exporte desselben Bestands liefern nachweislich unterschiedliche
  Ergebnismengen (REQ-GRAPH-006).
- Rücknahme einer Lieferung entfernt/sperrt genau deren Artefakte; unabhängig
  gestützte Knoten bleiben unangetastet (REQ-PIPE-005).
- Ein Dokument ganz ohne Klassifikationszeile erscheint in keinem Leseergebnis
  (REQ-PIPE-004).
- Kategorie-D-Quelle mit `commercial_catalog=true` lässt sich nicht anlegen
  (REQ-PIPE-008).
- Architektur-Test (z. B. Import-Linting): Domänenschicht importiert kein
  `sqlalchemy` (REQ-GRAPH-004).

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-GRAPH-001 | Schema, ODbL-fähig, dokumentiert |
| REQ-GRAPH-002 | `edge.layer` |
| REQ-GRAPH-004 | Repository-Muster, Ansatz 3 |
| REQ-GRAPH-005 | `document`/`document_designation`/`document_title` |
| REQ-GRAPH-006 | `rights_classification`, Rechtsraum-Filterung im Lesepfad |
| REQ-PIPE-002 | `source` |
| REQ-PIPE-003 | `source.tdm_opt_out_*` |
| REQ-PIPE-004 | Rechte-Gate im Lesepfad |
| REQ-PIPE-005 | `delivery_id` an jedem abgeleiteten Artefakt, `revoke_delivery` |
| REQ-PIPE-006 | `delivery.content_hash`, Idempotenz-Tests |
| REQ-PIPE-008 | CHECK-Constraint auf `source` |
| REQ-PIPE-009 | Schema ist quellenagnostisch, kein Zwang zu Kategorie C/D |
| ADR-006 | PostgreSQL + pgvector, Repository-Kapselung |
| ADR-011 | globales Identifikatorschema, sprachunabhängige Knotenidentität |
| ADR-012 | technische Sperre für Kategorie D + kommerzielle Kataloge; kein Nachbau des Perinorm-Feldschemas im offenen Kern |

## Offene Punkte / Folgearbeiten

- **Audit-Trail für Rücknahmen.** Der Rücknahmepfad ist atomar und vollständig,
  hinterlässt aber keinen eigenen Nachweis: es gibt keine Audit-Tabelle, und die
  gelöschten `document_designation`- und `document_title`-Zeilen sind danach spurlos.
  Wer wann welche Lieferung zurückgezogen hat, ist aus dem Schema nicht rekonstruierbar.
  Das ist bewusst auf ein späteres, übergreifendes Observability-/Audit-Verfahren
  vertagt und nicht Teil dieses Teilprojekts.
- Konkretes Python-Modullayout und Paketname (Teil der Implementierungsplanung).
- Segment-/Embedding-Tabellen (folgt mit der Ingestion-Pipeline).
- Perinorm-/DIN-Media-Format-Adapter (folgt erst mit einem konkreten Kategorie-C-Vertrag).
- Rekursive-CTE-Abfragen für Ersetzungsketten sind hier nur als Repository-fähig
  vorgesehen, nicht im Detail spezifiziert — Teil der Implementierungsplanung.
- **`create_edge`-Wiederverwendung verwirft abweichende Attribute stillschweigend.**
  Erneutes Anlegen derselben aktiven Kante (`from`/`to`/`edge_type`/`jurisdiction`) gibt
  die bestehende Zeile zurück, ohne `layer` oder `delivery_id` gegen die neuen Werte zu
  prüfen — eine zweite Lieferung, die dieselbe Kante mit anderer Schicht bestätigt,
  gewinnt keine eigene Abstammung; zieht die erste Lieferung die Kante später zurück,
  wird auch der Beitrag der zweiten mitentfernt. Das schlägt in dieselbe, bewusst sichere
  Richtung wie die Deduplizierung bei `document_designation`/`document_title` (eher zu
  viel als zu wenig zurückgenommen), ist aber nicht weiter spezifiziert.
- **`_require_active_delivery` hat ein theoretisches TOCTOU-Fenster.** Die Prüfung liest
  den Lieferungsstatus ohne Zeilensperre; unter READ COMMITTED könnte eine gleichzeitig
  laufende `revoke_delivery`-Transaktion zwischen Prüfung und Schreiben committen. Bei der
  aktuell angenommenen Einzel-Schreiber-Pipeline nicht ausnutzbar; sobald ein
  nebenläufiger Ingest existiert, braucht die Prüfung `SELECT … FOR SHARE` oder eine
  gleichwertige Sperre.
