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
und Beziehungen abfragen, ihren Gültigkeitsstatus prüfen und den freien Graphanteil
vollständig exportieren kann — alles deterministisch aus dem Graph beantwortet, ohne
Modellaufruf (REQ-GRAPH-003).

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

class DocumentResponse(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    designations: list[DesignationResponse]
    titles: list[TitleResponse]

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

## Endpunkte (v1)

| Endpunkt | Zweck | Repository-Methode(n) |
|---|---|---|
| `GET /v1/documents?designation=&issuer=&jurisdiction=` | Suche/Lookup nach Bezeichnung | `find_by_designation` |
| `GET /v1/documents/{id}?jurisdiction=` | Dokument-Detail (Bezeichnungen, Titel mehrsprachig) | `list_designations`, `list_titles` (rechtsraumgefiltert) |
| `GET /v1/documents/{id}/edges?jurisdiction=&edge_type=` | Verweise/Beziehungen (references, based_on_law, adopted_from) | `list_edges_for_jurisdiction` |
| `GET /v1/documents/{id}/validity?jurisdiction=` | Abgeleiteter Gültigkeitsstatus | wertet `replaces`/`withdrawn_by`-Kanten aus `list_edges_for_jurisdiction` aus |
| `GET /v1/export?jurisdiction=&format=json` | Vollständiger Dump des freien Graphanteils (REQ-GRAPH-001) | `list_documents_for_jurisdiction` + zugehörige Kanten |

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
    -> EdgeRepository(session).list_edges_for_jurisdiction(id, jurisdiction, edge_type)
    -> Domain-Edges -> EdgeResponse-Liste gemappt
    -> 200 mit Liste, oder 404 wenn document_id unbekannt
```

Kein Endpunkt schreibt.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Unbekannte `document_id` | 404 mit strukturiertem Fehlerkörper |
| Fehlender/ungültiger `jurisdiction`-Parameter | 400 — Pflichtparameter, kein stiller Default (sonst rutscht versehentlich der falsche Rechtsraum durch) |
| `jurisdiction` ohne Klassifikation für dieses Dokument | 200 mit leerem Ergebnis (deckt sich mit dem bestehenden „fehlende Klassifikation = nicht sichtbar"-Verhalten der Repository-Schicht) |
| Datenbankverbindung down | 503, kein Detail-Leak |
| `format`-Parameter bei `/v1/export` ungleich `json` | 400 — für den Start ist `json` der einzige gültige Wert, der Parameter existiert für spätere Formate (siehe Offene Punkte), ohne dass sich der Endpunkt-Pfad ändert |

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
| REQ-GRAPH-002 | Export enthält nur den freien Graphanteil — keine lizenzierten Bestände vorhanden, daher trivial erfüllt |
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
- **Kommerzielle Schicht** (SLA, Abschnittsebene-Verweise, Konfidenzangaben,
  branchenspezifische Anreicherungen aus REQ-GRAPH-002) — es gibt aktuell keine lizenzierten
  Bestände; sobald welche über REQ-INT-002/REQ-PART-001 hinzukommen, braucht die API eigene,
  zugriffsgeschützte Endpunkte dafür.
- **Deployment/Reverse-Proxy-Konfiguration** — CLAUDE.md verlangt Betrieb hinter beliebigem
  Reverse Proxy im Container; konkrete STACKIT-Pipeline-Anbindung ist eine spätere
  Deployment-Entscheidung, analog zu den vorigen Teilprojekten.
