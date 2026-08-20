# Design: Backend-API — deterministische Graph-Anfragen (v1)

**Datum:** 2026-08-20
**Status:** zur Durchsicht
**Teilprojekt:** drittes von mehreren zur Umsetzung des normly-MVP (freier Kern)

## Kontext

Die ersten beiden Teilprojekte (Datenmodell & Referenzgraph-Schema, Ingestion-Pipeline)
haben das PostgreSQL-Schema, die Repository-Schicht und einen befüllten Referenzgraph mit
echten Daten aus EUR-Lex und DGUV gebaut. Die Daten liegen in der Datenbank, aber es gibt
keinen Weg nach außen — kein HTTP-Zugriff, keine Dokumentation, kein Drittsystem kann sie
abfragen.

REQ-INT-001 beschreibt eine öffentliche, dokumentierte HTTP-API. SRS Kapitel 3.1 hängt
daran weitere, deutlich größere Anforderungen: nutzerbasierte Dokumenten-Uploads mit
Isolation und Ablauffrist (REQ-INT-002A/B/C), SSO (REQ-INT-003), eine LLM-Schnittstelle für
Chat-Antworten (REQ-INT-004, REQ-FUNC-001/002/003). Das ist zu groß für ein Teilprojekt.

**Entschieden mit dem Auftraggeber:**

1. Umfang: nur deterministische Graph-Anfragen (REQ-GRAPH-003) über den bereits befüllten
   freien Bestand — Suche/Lookup, Verweise/Beziehungen, Ersetzungs-/Gültigkeitsketten, sowie
   ein vollständiger Dump des freien Graphanteils (REQ-GRAPH-001). Kein LLM-Aufruf, keine
   Nutzer-Uploads, kein Login — passend zu ADR-017/REQ-ACC-001 (keine Kontopflicht für freie
   Inhalte).
2. Tech-Stack: FastAPI (Python), neues Top-Level-Paket `api/`, abhängig von `normly_core`.
   Erzeugt die OpenAPI-Spezifikation automatisch aus den Endpunkt-Signaturen (erfüllt
   REQ-INT-001s Akzeptanzkriterium direkt), eingebautes Swagger-UI erfüllt SRS 3.6.2s
   „Swagger Instanz... ist zwingend".
3. Die API ist rein lesend. Ingestion bleibt CLI-only (Ingestion-Pipeline-Teilprojekt).
4. Ratenbegrenzung/Kontingent (REQ-SEC-004, serverseitige Kontingentzählung für anonyme
   Nutzung) bewusst nicht Teil dieses Teilprojekts — eigene Infrastrukturentscheidung, siehe
   Offene Punkte.

## Ziel dieses Teilprojekts

Eine öffentliche, versionierte, vollständig als OpenAPI dokumentierte HTTP-API, über die ein
Drittsystem ohne Kenntnis der internen Implementierung Normen nachschlagen, ihre Verweise
und Beziehungen abfragen, ihren Gültigkeitsstatus prüfen, ihre Ursprungsquelle (Herausgeber
und Bezugs-URL) einsehen und den freien Graphanteil vollständig exportieren kann — alles
deterministisch aus dem Graph beantwortet, ohne Modellaufruf (REQ-GRAPH-003).

## Nicht-Ziele

- **Nutzer-Uploads, Isolation, Ablauffrist** (REQ-INT-002A/B/C) — eigenes, späteres
  Teilprojekt.
- **SSO-Authentifizierung** (REQ-INT-003) — nicht nötig, solange keine kontogebundenen
  Funktionen existieren.
- **LLM-Schnittstelle / Chat-Antworten** (REQ-INT-004, REQ-FUNC-001/002/003) — eigenes,
  späteres Teilprojekt; setzt vermutlich auf dieser API auf.
- **Ratenbegrenzung, Kontingente, Anomalieerkennung** (REQ-SEC-004) — eigene
  Infrastrukturentscheidung, siehe Offene Punkte.
- **Schreibende Endpunkte.** Ingestion bleibt CLI-only.
- **Kommerzielle Schicht** (SLA, Abschnittsebene-Verweise in lizenzierten Normen,
  Konfidenzangaben) — es gibt aktuell keine lizenzierten Bestände in der Datenbank
  (nur Kategorie-A-Quellen aus dem Ingestion-Pipeline-Teilprojekt).

## Architektur

### Paketstruktur

Drei Ansätze wurden abgewogen:

1. **Eigenes `api/`-Verzeichnis (FastAPI), abhängig von `normly_core`.**
2. FastAPI innerhalb von `core/` — verworfen: vermischt zwei Auslieferungsformen
   (Bibliothek+CLI vs. Webdienst), zieht Web-Framework-Abhängigkeiten in jede Installation,
   die nur die Bibliothek braucht.
3. GraphQL/RPC statt REST — verworfen: REQ-INT-001 verlangt explizit eine
   OpenAPI-dokumentierte HTTP-API; klassisches REST passt besser zu Drittsystem-Integration
   (CAD/ERP) als GraphQL. Verfrühte Abweichung vom Vorgabenweg.

**Entschieden: Ansatz 1.**

```
api/
  pyproject.toml        # eigenes Paket, hängt von normly_core ab
  src/normly_api/
    main.py             # FastAPI-App-Fabrik, mountet Router unter /v1
    dependencies.py      # DB-Session-Dependency (nutzt normly_core.graph.postgres)
    schemas.py            # Pydantic-Antwortmodelle
    routers/
      documents.py        # Suche, Detail
      edges.py             # Verweise/Beziehungen
      validity.py          # Ersetzungs-/Gültigkeitsstatus
      export.py            # Freier Dump
  tests/
```

Passt zum bereits sichtbaren Muster separater Top-Level-Komponenten mit eigenen
Container-Images (CLAUDE.md „Auslieferung: signierte Container-Images").

### Schema-Grenze

Die API antwortet mit eigenen Pydantic-Modellen, nicht mit den `normly_core.graph.domain`-
Dataclasses direkt. Das hält REQ-GRAPH-004s Vorgabe ein (Fachlogik/Speichertechnologie
bleibt hinter einer Abstraktion) und lässt die API-Version unabhängig vom Kern-Paket
weiterentwickeln:

```python
class DesignationResponse(BaseModel):
    issuer: str
    designation: str
    language: str
    is_primary: bool

class TitleResponse(BaseModel):
    language: str
    title: str

class SourceResponse(BaseModel):
    publisher: str
    retrieval_path: str        # Ursprungs-URL der Quelle
    legal_basis_category: str  # A/B/C/D, siehe Quellenregister
    jurisdiction: str

class DocumentResponse(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    designations: list[DesignationResponse]
    titles: list[TitleResponse]
    source: SourceResponse

class EdgeResponse(BaseModel):
    edge_type: str
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    jurisdiction: str | None
    layer: str

class ValidityResponse(BaseModel):
    document_id: uuid.UUID
    status: Literal["valid", "replaced", "withdrawn"]
    replaced_by: list[uuid.UUID]
    withdrawn_reference: str | None

class LicenseNotice(BaseModel):
    license_name: str          # "ODbL-1.0"
    license_url: str
    attribution: str

class ExportResponse(BaseModel):
    license: LicenseNotice
    schema_version: str
    jurisdiction: str
    generated_at: datetime
    documents: list[DocumentResponse]
    edges: list[EdgeResponse]
```

Jeder Endpunkt nimmt `jurisdiction` als Pflicht-Query-Parameter — die
Rechteklassifikation ist rechtsraumabhängig (REQ-GRAPH-006), und die bestehenden
Repository-Methoden sind bereits jurisdiction-scoped gebaut; die API reicht diesen
Parameter nur durch, keine eigene Klassifikationslogik.

**Das eine Tor — sechs Ausprägungen, ein Prinzip.** `DocumentRepository`s eigener Docstring
markiert `list_designations`, `list_titles`, `find_by_designation` und
`get_document_unchecked` explizit als *nicht* rechtsraumgefiltert und *nicht* für öffentliche
Lesepfade bestimmt (Ausnahme: `get_document_unchecked` als reine Existenzprüfung, siehe
unten) — nur die folgenden sechs Methoden filtern über die Rechteklassifikation und dürfen
das jeweilige Sichtbarkeitsergebnis bestimmen:

| Methode | Zusätzlich zu `may_process`/`revoked_at` | Verwendet von |
|---|---|---|
| `get_document_for_jurisdiction` | — | Suche, Detail, Validity (Existenz+Sichtbarkeit) |
| `list_documents_for_jurisdiction` | — | (intern/Pipeline, kein HTTP-Endpunkt) |
| `list_exportable_documents_for_jurisdiction` | `may_export_free=True` | `/v1/export` |
| `list_edges_for_jurisdiction` / `list_incoming_edges_for_jurisdiction` | — | (intern/Pipeline, kein HTTP-Endpunkt) |
| `list_free_layer_edges_for_jurisdiction` / `list_free_layer_incoming_edges_for_jurisdiction` | `layer=FREE` | `/v1/documents/{id}/edges`, `/v1/documents/{id}/validity` |
| `list_exportable_edges_for_jurisdiction` | `layer=FREE` **und** `may_export_free=True` (beide Seiten) | `/v1/export` |

Diese Tabelle ist in der Abschluss-Review nachträglich entstanden: der erste Umsetzungsstand
hatte `edges`/`validity` versehentlich an die *ungefilterten* Varianten angeschlossen —
`layer=COMMERCIAL`-Kanten wären über die anonyme, öffentliche API sichtbar gewesen, exakt der
Fehler, den die Abschluss-Review für `/v1/export` bereits einmal gefunden und behoben hatte,
nur in den beiden Geschwister-Endpunkten. `may_export_free` (Sichtbarkeit im Sammel-Export)
und `layer` (Zugehörigkeit zur freien vs. kommerziellen Schicht des Graphen selbst,
REQ-GRAPH-002) sind zwei getrennte Konzepte — die `free_layer_*`-Methoden prüfen nur `layer`,
nicht `may_export_free`, damit ein `may_process=True, may_export_free=False`-Dokument seine
freien Beziehungen weiterhin über die allgemeinen Lese-Endpunkte zeigen kann, ohne im
Sammel-Export zu erscheinen.

Jeder Endpunkt, der ein Dokument zurückgibt, muss zuerst durch eines der sechs Tore. Für
Suche/Detail/Validity heißt das: `get_document_for_jurisdiction(document_id, jurisdiction)`;
liefert das `None`, antwortet der Endpunkt mit 404 — unabhängig davon, ob das Dokument
existiert. Erst nach diesem einen Gate-Aufruf dürfen die ungated Methoden zur Anreicherung
(Bezeichnungen, Titel) für dasselbe, bereits autorisierte Dokument aufgerufen werden. Für die
Suche (`find_by_designation`) bedeutet das zweistufig: zuerst Identität auflösen
(`find_by_designation`, liefert nur eine `document_id`), dann das Gate prüfen
(`get_document_for_jurisdiction`) — das Suchergebnis kommt ausschließlich aus dem zweiten
Aufruf, `find_by_designation` dient nur der Identitätsauflösung, nie der Sichtbarkeitsprüfung.
`/v1/documents/{id}/edges` bildet bewusst eine Ausnahme: es nutzt `get_document_unchecked`
als reine Existenzprüfung (404 bei unbekannter `document_id`, ohne Rechte-Inhalte
preiszugeben), gefolgt vom eigentlichen Inhalts-Tor — siehe Fehlerbehandlung.

**Quellenauflösung.** `document.created_via_delivery_id` verweist auf die Lieferung, die das
Dokument ursprünglich angelegt hat; darüber `DeliveryRepository.get_delivery(...).source_id`
und `SourceRepository.get_source(...)` — beide Methoden existieren bereits, keine neue
Repository-Methode nötig. Das liefert die Quelle, die den Dokumentknoten erzeugt hat, nicht
notwendigerweise jede Quelle, die je Daten zu diesem Dokument beigetragen hat (ein Dokument
könnte im Prinzip über mehrere Lieferungen unterschiedlicher Quellen angereichert werden) —
für den aktuellen Bestand (EUR-Lex, DGUV) ist das gleichbedeutend, siehe Offene Punkte.

## Endpunkte (v1)

| Endpunkt | Zweck | Repository-Methode(n) |
|---|---|---|
| `GET /v1/documents?designation=&issuer=&jurisdiction=` | Suche/Lookup nach Bezeichnung | `find_by_designation` (Identität) + `get_document_for_jurisdiction` (Tor, siehe „Das eine Tor") |
| `GET /v1/documents/{id}?jurisdiction=` | Dokument-Detail (Bezeichnungen, Titel mehrsprachig, Ursprungsquelle inkl. URL) | `get_document_for_jurisdiction` (Tor) zuerst, danach `list_designations`/`list_titles` (Anreicherung), `get_delivery`/`get_source` über `document.created_via_delivery_id` |
| `GET /v1/documents/{id}/edges?jurisdiction=&edge_type=` | Verweise/Beziehungen (references, based_on_law, adopted_from) | `get_document_unchecked` (Existenz) + `list_free_layer_edges_for_jurisdiction` (Tor) |
| `GET /v1/documents/{id}/validity?jurisdiction=` | Abgeleiteter Gültigkeitsstatus | `get_document_for_jurisdiction` (Tor) zuerst, dann wertet `replaces`/`withdrawn_by`-Kanten aus `list_free_layer_incoming_edges_for_jurisdiction` aus |
| `GET /v1/export?jurisdiction=&format=json` | Vollständiger Dump des freien Graphanteils (REQ-GRAPH-001) | `list_exportable_documents_for_jurisdiction` + `list_exportable_edges_for_jurisdiction` |

`edge_type` ist als `EdgeType | None` typisiert (nicht als roher String) — ein ungültiger
Wert liefert 400 statt eine stillschweigend leere Liste.

Der `validity`-Endpunkt ist bewusst ein eigener, abgeleiteter Endpunkt statt „selbst aus den
Kanten ableiten" — REQ-INT-001 verlangt, dass ein Drittsystem ohne Kenntnis der internen
Implementierung anfragen kann; `replaces`/`withdrawn_by`-Semantik soll niemand außerhalb
dieses Repositories kennen müssen.

## Export-Format (`GET /v1/export`)

REQ-GRAPH-001 verlangt nur „offenes, dokumentiertes Format" mit maschinenlesbarem
Lizenzhinweis — schreibt kein konkretes Format vor. Entschieden: einfaches, dokumentiertes
JSON (kein JSON-LD/RDF — verfrühte Komplexität für den Start, YAGNI), mit eingebettetem
Lizenzblock (`LicenseNotice`, siehe oben). Bei den aktuell kleinen Beständen (nur
EUR-Lex/DGUV) reicht eine einzelne JSON-Antwort; Paginierung/Streaming ist YAGNI für den
Start, siehe Offene Punkte.

## Datenfluss

Beispiel `GET /v1/documents/{id}/edges`:

```
Router nimmt jurisdiction, edge_type (optional) entgegen
    -> get_document_unchecked(id) is None? -> 404
    -> EdgeRepository(session).list_free_layer_edges_for_jurisdiction(id, jurisdiction)
    -> Python-seitiger Filter auf edge_type, falls gesetzt (kein Repository-Parameter)
    -> Domain-Edges -> EdgeResponse-Liste gemappt
    -> 200 mit (ggf. leerer) Liste
```

`edge_type` wird NICHT an die Repository-Methode durchgereicht — `list_free_layer_edges_for_jurisdiction`
kennt keinen solchen Parameter, das Filtern passiert im Router auf der bereits geladenen Liste.

Kein Endpunkt schreibt.

## Fehlerbehandlung

Zwei unterschiedliche Verhaltensmuster, je nach Antwortform — beide bewusst, nicht
widersprüchlich:

- **Einzelressourcen** (`/v1/documents/{id}`, `/v1/documents/{id}/validity`, sowie die Suche):
  `get_document_for_jurisdiction` liefert `None` sowohl bei unbekannter `document_id` als auch
  bei fehlender Klassifikation — beide Fälle ergeben einheitlich 404, absichtlich nicht
  unterscheidbar (sonst ließe sich aus der Antwort ablesen, ob ein Dokument existiert, dem
  Anfragenden aber verborgen bleibt).
- **Listenressource** (`/v1/documents/{id}/edges`): eine unbekannte `document_id` ergibt 404
  (eigene Existenzprüfung über `get_document_unchecked`, die keine Rechte-Inhalte preisgibt),
  eine bekannte, aber im angefragten Rechtsraum nicht klassifizierte `document_id` ergibt 200
  mit leerer Liste — für eine Liste ist „keine sichtbaren Einträge" ein normales, kein
  fehlerhaftes Ergebnis.

| Fall | Verhalten |
|---|---|
| Unbekannte `document_id` (Einzelressource) | 404 mit strukturiertem Fehlerkörper (`ErrorResponse`), nicht von „existiert, aber nicht klassifiziert" unterscheidbar |
| Unbekannte `document_id` (`/edges`) | 404, eigene Existenzprüfung, siehe oben |
| `document_id` bekannt, aber `jurisdiction` ohne Klassifikation (`/edges`) | 200 mit leerem Ergebnis |
| Fehlender/ungültiger `jurisdiction`-Parameter | 400 — Pflichtparameter, kein stiller Default (sonst rutscht versehentlich der falsche Rechtsraum durch) |
| Ungültiger `edge_type`-Wert | 400 (Enum-Validierung durch FastAPI, kein stiller Leerlistenrückgabe mehr) |
| Datenbankverbindung down (SQLAlchemy/OS-Fehler) | 503, kein Detail-Leak |
| Unerwarteter interner Fehler (z. B. nicht auflösbare Herkunft) | 500 — bewusst NICHT als 503 maskiert; nur echte Infrastrukturfehler (Datenbank, Verbindung) ergeben 503, ein Programmfehler soll sichtbar bleiben statt einen Retry nahezulegen |
| `format`-Parameter bei `/v1/export` ungleich `json` | 400 — für den Start ist `json` der einzige gültige Wert, der Parameter existiert für spätere Formate (siehe Offene Punkte), ohne dass sich der Endpunkt-Pfad ändert |

Alle 400/404/503-Antworten sind über `ErrorResponse` (`{"detail": str}`) in der
OpenAPI-Spezifikation dokumentiert — sowohl global (400/503 über `include_router(...,
responses=...)`) als auch je Endpunkt für die 404-Fälle.

## Testkonzept

- FastAPI `TestClient`/`httpx` gegen die App direkt, keine echten Netzwerkaufrufe.
- Echtes PostgreSQL über denselben Testcontainer-Ansatz wie in `core/tests/conftest.py`
  (kein Mocking der Datenbank, konsistent mit dem bisherigen Projektstil).
- Testdaten werden über die Repository-Schicht direkt aufgebaut (nicht über Ingestion) —
  schnell, fokussiert auf API-Verhalten.
- Ein Test ruft `/openapi.json` ab und prüft, dass es ein valides OpenAPI-Dokument mit den
  erwarteten Pfaden ist — mechanische Abnahme von REQ-INT-001s „vollständig als
  OpenAPI-Spezifikation dokumentiert".
- Rechteklassifikations-Asymmetrie explizit getestet: derselbe Endpunkt liefert für
  Rechtsraum A Daten, für B nicht (analog zum bestehenden Muster aus den vorigen
  Teilprojekten).

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-INT-001 | Öffentliche, OpenAPI-dokumentierte, versionierte HTTP-API (`/v1/`) |
| REQ-GRAPH-001 | `/v1/export` — vollständiger Dump, offenes JSON-Format, maschinenlesbarer Lizenzhinweis |
| REQ-GRAPH-002 | Export UND die allgemeinen Lese-Endpunkte filtern auf `layer=FREE`; `/v1/export` zusätzlich auf `may_export_free`. In der Abschluss-Review korrigiert: die ursprüngliche Annahme „keine lizenzierten Bestände vorhanden, daher trivial erfüllt" war die Ursache eines echten Lecks (COMMERCIAL-Kanten waren über `/edges`/`/validity` öffentlich sichtbar) — die Erfüllung ist jetzt strukturell durch die layer-gefilterten Repository-Methoden erzwungen, nicht durch die zufällige Abwesenheit lizenzierter Testdaten |
| REQ-GRAPH-003 | Alle Endpunkte deterministisch aus dem Graph beantwortet, kein Modellaufruf |
| REQ-GRAPH-004 | Pydantic-Antwortmodelle statt direkter Domain-/ORM-Objekte — Speichertechnologie bleibt hinter der Repository-Schicht |
| REQ-GRAPH-006 | `jurisdiction`-Pflichtparameter auf jedem Endpunkt, rechtsraumgefilterte Repository-Methoden |
| ADR-017 / REQ-ACC-001 | Keine Kontopflicht — API funktioniert vollständig ohne Login |

## Offene Punkte / Folgearbeiten

- **Ratenbegrenzung/Kontingent** (REQ-SEC-004, serverseitige Kontingentzählung für anonyme
  Nutzung) — eigene Infrastrukturentscheidung (Zähl-Mechanismus ohne Cookies/Session), nicht
  Teil dieses Teilprojekts.
- **Nutzer-Uploads, SSO, LLM-Chat** (REQ-INT-002A/B/C, REQ-INT-003, REQ-INT-004,
  REQ-FUNC-001/002/003) — eigene, spätere Teilprojekte.
- **Paginierung/Streaming für `/v1/export`** — mit den aktuell kleinen Beständen (EUR-Lex,
  DGUV) nicht nötig; sobald weitere Adapter/Quellen hinzukommen, muss das nachgezogen
  werden.
- **Mehrere Quellen je Dokument.** `source` auf `DocumentResponse` zeigt aktuell nur die
  erzeugende Quelle (`created_via_delivery_id`). Sobald ein Dokument real über mehrere
  Quellen anreichert wird, braucht es entweder ein `sources: list[SourceResponse]`-Feld
  oder einen eigenen `/v1/documents/{id}/sources`-Endpunkt — mit dem aktuellen Bestand nicht
  beobachtbar, daher hier nicht spezifiziert.
- **Kommerzielle Schicht** (SLA, Abschnittsebene-Verweise, Konfidenzangaben,
  branchenspezifische Anreicherungen aus REQ-GRAPH-002) — es gibt aktuell keine lizenzierten
  Bestände; sobald welche über REQ-INT-002/REQ-PART-001 hinzukommen, braucht die API eigene,
  zugriffsgeschützte Endpunkte dafür.
- **Deployment/Reverse-Proxy-Konfiguration** — CLAUDE.md verlangt Betrieb hinter beliebigem
  Reverse Proxy im Container; konkrete STACKIT-Pipeline-Anbindung ist eine spätere
  Deployment-Entscheidung, analog zu den vorigen Teilprojekten.
- **OpenAPI dokumentiert einen 422, den es nie gibt.** FastAPI ergänzt automatisch einen
  422-Eintrag für jeden Endpunkt mit validierten Parametern; der `RequestValidationError`-Handler
  wandelt aber jeden solchen Fall zur Laufzeit in 400 um, sodass 422 nie tatsächlich
  zurückkommt — ein totes Schema-Element (eigenes `HTTPValidationError`-Komponentenschema,
  strukturell verschieden von `ErrorResponse`) für generierte Clients. Aus der Abschluss-Review,
  bewusst nicht behoben: bräuchte eine `app.openapi()`-Override zur Schema-Nachbearbeitung.
- **`/v1/documents/{id}/edges` und Einzelressourcen haben unterschiedliche
  404-vs-200-leer-Semantik**, siehe Fehlerbehandlung — bewusst, aber ein API-Konsument sollte
  das aus der Dokumentation lernen können, nicht nur aus dem Verhalten.
- **`/v1/documents` (Suche) liefert ein einzelnes Objekt, keine Liste**, obwohl der Pfad wie
  eine Kollektion aussieht. Solange „Suche" nur exakte Bezeichnung+Herausgeber unterstützt, ist
  das eindeutig; sobald unscharfe/mehrdeutige Suche hinzukommt, wäre `list[DocumentResponse]`
  eine brechende Änderung — property jetzt schon so anlegen, solange nichts davon abhängt, wäre
  eine Überlegung wert.
- **N+1-Anfragen im Export** — für jedes Dokument einzeln `list_exportable_edges_for_jurisdiction`
  aufgerufen. Mit den aktuell kleinen Beständen unproblematisch; bei wachsendem Bestand vor
  Paginierung (siehe oben) zu adressieren.
- **`SET TRANSACTION READ ONLY`** wäre eine strukturelle (statt nur durch Review erzwungene)
  Absicherung von „die API ist rein lesend" — aktuell hält kein Code-Pfad diese Eigenschaft
  technisch durch, nur die Abwesenheit schreibender Repository-Aufrufe im Quellcode.
