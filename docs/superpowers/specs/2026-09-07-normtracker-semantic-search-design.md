# Design: Semantische Suche (Normtracker-Grundgerüst, Teil 2/5)

## Kontext

Sub-project 1 ([[docs/superpowers/specs/2026-09-06-normtracker-work-entity-design.md]],
gemerged) hat die `Work`-Entität eingeführt — eine logische Identität für ein
Regelwerk über mehrere Ausgaben und nationale Übernahmen hinweg. Dieses
Teilprojekt baut direkt darauf auf: die heutige Suche
(`api/src/normly_api/routers/search.py`,
`PostgresDocumentRepository.search_documents_for_jurisdiction`) ist reines
ILIKE-Textmatching auf `DocumentDesignation`/`DocumentTitle`, liefert eine
flache, pro-`Document`-Trefferliste und nutzt kein Embedding — obwohl
pgvector und ein lokales Embedding-Modell (`intfloat/multilingual-e5-large`,
1024-dim, `core/src/normly_core/pipeline/embeddings.py`) bereits für
Chat-Segmente im Einsatz sind.

Zwei Entscheidungen aus der Sub-project-1-Brainstorming-Session sind hier
umzusetzen: die Suche wird auf semantische (Embedding-basierte) Ähnlichkeit
umgestellt, und Treffer werden pro `Work` gruppiert statt pro `Document`.

## Ziel dieses Teilprojekts

1. Eine hybride Suche: exakte Textübereinstimmungen (wie heute, ILIKE) zuerst,
   ergänzt um semantisch ähnliche Treffer, die ILIKE nicht findet (Synonyme,
   Umschreibungen, thematische Nähe).
2. Treffer werden nach `Work` gruppiert — ein Suchergebnis pro Regelwerk,
   nicht pro Ausgabe/nationaler Fassung.
3. Ein neues, pro `Document` gepflegtes Embedding, erzeugt/aktualisiert
   während der Ingestion sowie nachträglich per Backfill für bereits
   vorhandene Documents.

## Nicht-Ziele

- Keine vollständige Editions-/Übernahmeliste im Suchergebnis — das ist
  Teilprojekt 3 (Dokument-Detail-Seite). Dieses Teilprojekt liefert nur
  einen Zähler ("+2 weitere Ausgaben").
- Keine Embeddings auf Volltext-/Segment-Ebene für die Dokumentensuche —
  das bestehende `Embedding`/`EmbeddingRepository` (segment-gebunden, für
  Chat) bleibt unverändert und unberührt.
- Kein neuer Such-Service, keine externe Suchmaschine — bleibt vollständig
  in `core`/`api`, gleiches pgvector-Setup wie beim Chat.
- Keine Änderung an der Rechteklassifikations-Gate-Logik — Suche filtert
  wie heute ausschließlich rechtsraum-sichtbare, `may_process=True`-Documents.

## Architektur

### Zwei-Stufen-Suche

**Tier 1 (exakt):** ILIKE auf `DocumentDesignation.designation` und
`DocumentTitle.title`, wie heute implementiert. Treffer bekommen Rang 0.

**Tier 2 (semantisch):** die Suchanfrage wird mit `EmbeddingModel.embed_query()`
(Query-Prefix, nicht `embed()`/Passage-Prefix — das e5-Modell unterscheidet
beide Rollen im selben Vektorraum) in einen Vektor übersetzt und per
pgvector-Kosinus-Distanz (`DocumentEmbedding.vector.cosine_distance(...)`)
gegen alle rechteklassifizierten Documents sortiert. Treffer bekommen Rang 1
mit aufsteigender Distanz als Sekundärsortierung.

Beide Tiers laufen gegen dieselbe rechteklassifizierte Dokumentenmenge
(identisches Gating wie die heutige `search_documents_for_jurisdiction`).
Die vereinigte, nach `(rang, distanz)` sortierte Trefferliste wird
anschließend per `DISTINCT ON (work_id)` auf einen Treffer pro `Work`
reduziert — das erstplatzierte Document je Work gewinnt.

Eine leere Suchanfrage (`q=None`) überspringt Tier 2 vollständig (kein Text
zum Embedden) und verhält sich wie das heutige ungefilterte, paginierte
Listing.

### Datenmodell

```
DocumentEmbedding (neu)
  document_id: UUID (FK → document.id)
  model_name: str
  vector: Vector(1024)
  delivery_id: UUID (FK → delivery.id)   # Abstammung — welche Lieferung
                                          # den zugrundeliegenden Text erzeugt hat
  created_at: datetime
  UNIQUE(document_id, model_name)
```

Bewusst eine eigene Tabelle, nicht eine Erweiterung der bestehenden
`Embedding`-Tabelle (die an `segment_id` gebunden ist) — ein Document-
Identitäts-Embedding und ein Chat-Segment-Embedding sind fachlich
unterschiedliche Konzepte; eine gemeinsame Tabelle mit sich gegenseitig
ausschließenden Fremdschlüsseln wäre unsauberer als zwei kleine, fokussierte
Tabellen.

**Embedding-Inhalt:** ein Embedding pro `Document`, gebildet aus der
primären `DocumentDesignation` plus dem primären `DocumentTitle`
(`"<Designation> — <Titel>"`, z.B. `"EN ISO 9001:2018 — Qualitätsmanagement-
systeme"`). Nicht ein Embedding je Titel/Sprache — hält die Pflege auf ein
Embedding pro Document begrenzt.

Weder Designation noch Titel sind zum Ingestion-Zeitpunkt garantiert
vorhanden (`add_title` wird nur bei vorhandenem `raw_title` aufgerufen,
`add_designation` nur bei vorhandenem `raw_issuer`): fehlt der Titel, wird
nur die Designation embedded (`"<Designation>"` ohne Anhang); fehlt auch
die primäre Designation (kein `raw_issuer` in diesem Durchlauf), entfällt
die Embedding-Erzeugung für diesen Durchlauf vollständig — das Document
bleibt bis zu einem späteren Durchlauf mit Designation nur über Tier 1
(sofern dann Text vorhanden ist) bzw. gar nicht auffindbar, was konsistent
mit dem bestehenden Verhalten ist (ohne Designation ist ein Document auch
heute schon nicht über `find_by_designation` auffindbar).

### Ingestion & Backfill

In `core/src/normly_core/pipeline/runner.py`s `process()` wird nach dem
bestehenden Designation-/Titel-Schritt (für neue wie wiedergefundene
Documents gleichermaßen) der aktuelle primäre Designation- und Titeltext
gelesen, embedded und per Upsert (`ON CONFLICT (document_id, model_name) DO
UPDATE`) in `DocumentEmbedding` geschrieben — bei jedem Durchlauf, nicht nur
beim ersten. Das ist von Natur aus idempotent (gleicher Text ergibt
denselben Vektor) und hält das Embedding automatisch aktuell, falls ein
späterer Durchlauf den primären Titel ändert, ohne eigene
Änderungserkennung.

Für bereits vorhandene Documents ohne Embedding: ein neuer CLI-Subcommand
(`python -m normly_core.pipeline backfill-document-embeddings`, analog zum
bestehenden `ingest`-Subcommand in `core/src/normly_core/pipeline/cli.py`)
erzeugt Embeddings für alle Documents ohne `DocumentEmbedding` zum
aktuellen Modell. Bewusst **keine** Alembic-Migration (anders als der
Union-Find-Backfill in Teilprojekt 1) — das Laden und Aufrufen eines
ML-Modells gehört nicht in eine Migration (langsam, dateisystem-/
modellabhängig), sondern in Pipeline-Code wie jeder andere Ingestion-
Schritt auch.

### API-Response

```
WorkSearchResultResponse
  work_id: UUID
  best_match: DocumentResponse   # bestplatziertes Document dieses Works
  other_editions_count: int       # Anzahl weiterer Documents im selben Work
WorkSearchResponse
  results: list[WorkSearchResultResponse]
  total: int   # Anzahl DISTINCT Works, nicht Rohtreffer
```

Löst die heutige `DocumentSearchResponse { results: list[DocumentResponse],
total }` ab. `GET /v1/documents/search` bleibt der Endpunkt-Pfad (kein
Wechsel auf `/v1/works/search` in diesem Teilprojekt — das Umbenennen auf
eine Work-zentrierte URL-Struktur ist eine Frontend-/API-Namensfrage, die
besser mit Teilprojekt 5 (Frontend) zusammen entschieden wird, nicht isoliert
hier).

## Fehlerbehandlung

- Leere Suchanfrage: kein ILIKE-Filter, kein Embedding berechnet, Tier 2
  entfällt, reines jurisdiction-/issuer-gefiltertes Listing (wie heute).
- Ein Document ohne (noch) vorhandenes `DocumentEmbedding` (z.B. Backfill
  noch nicht gelaufen) taucht in Tier 2 nicht auf, bleibt aber über Tier 1
  (ILIKE) auffindbar — bewusstes, unschädliches Degradieren.
- Fehler beim Laden/Aufrufen des Embedding-Modells: kein neuer
  Fallback-Pfad — verhält sich wie der bestehende Code für Chat-Embeddings
  (`EmbeddingModel`), keine Sonderbehandlung für die Suche.

## Testkonzept

- Unit: Hybrid-Merge-Logik (Tier 1 vor Tier 2, keine Duplikate zwischen den
  Tiers), `DISTINCT ON work_id`-Gruppierung liefert genau einen Treffer je
  Work.
- Integration: Pipeline erzeugt Documents + Embeddings, Repository-Suche
  liefert korrekt nach Work gruppierte, korrekt sortierte Treffer gegen
  eine echte Postgres/pgvector-Instanz.
- Backfill-CLI: Documents ohne Embedding bekommen eins; ein zweiter Lauf
  erzeugt nichts Neues (idempotent).
- Eigener Test, der nachweist, dass die Abfrage `embed_query()` (Query-
  Prefix) nutzt, nicht `embed()` (Passage-Prefix) — sonst liefert das
  Modell falsch orientierte Vektoren und die Ähnlichkeitssuche wird
  bedeutungslos, ohne dass ein anderer Test das sichtbar macht.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-GRAPH-005 | `Work`-Gruppierung der Suchergebnisse ist die erste nutzerseitig sichtbare Konsequenz der in Teilprojekt 1 eingeführten Work-Identität. |
| ADR-006 | pgvector bleibt die einzige Vektor-Infrastruktur (kein Neo4j, keine externe Suchmaschine) — dieses Teilprojekt fügt eine zweite pgvector-Nutzung (Document-Embeddings) neben der bestehenden (Segment-Embeddings) hinzu, ohne neue Technologie. |
| — | Es existiert aktuell kein REQ-SEARCH-*-Eintrag im SRS (`docs/srs/03-anforderungen.md`) für die Suche selbst — dieses Design füllt eine bislang unformalisierte Anforderung. Empfehlung als Folgearbeit: einen REQ-SEARCH-001 ergänzen, der die hybride Suche und die Work-Gruppierung als Abnahmekriterium festhält. |

## Offene Punkte / Folgearbeiten

- **REQ-SEARCH-001 ergänzen** (siehe oben) — Dokumentationsnachtrag, kein
  Codeimpakt.
- **Dokument-Detail-Seite** (Teilprojekt 3): liefert die volle
  Editions-/Übernahmeliste, die dieses Teilprojekt bewusst nur als Zähler
  ausweist.
- **URL-Struktur `/v1/works/...`**: ob der Suchendpunkt (und andere) auf
  eine Work-zentrierte Pfadbenennung wechseln, wird mit Teilprojekt 5
  (Frontend) entschieden, nicht hier.
- **Embedding-Modell-Versionierung**: `model_name` ist bereits Teil des
  Unique-Keys (wie bei `Embedding`), sodass ein Modellwechsel später ohne
  Datenverlust möglich ist — ein Migrationspfad für einen tatsächlichen
  Modellwechsel (Neuberechnung aller Vektoren) ist nicht Teil dieses
  Teilprojekts.
