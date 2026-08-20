# Design: LLM-Chat mit anonymer Sitzungshistorie (v1)

**Datum:** 2026-08-20
**Status:** zur Durchsicht
**Teilprojekt:** viertes von mehreren zur Umsetzung des normly-MVP (freier Kern)

## Kontext

Die ersten drei Teilprojekte (Datenmodell & Referenzgraph-Schema, Ingestion-Pipeline,
Backend-API) haben einen befüllten Referenzgraph mit echten Daten aus EUR-Lex und DGUV sowie
eine öffentliche, lesende HTTP-API für deterministische Graph-Anfragen gebaut. Es gibt noch
keine Möglichkeit, Fragen in natürlicher Sprache zu stellen — REQ-FUNC-001/002/003 und
REQ-INT-004 beschreiben genau das.

SRS Kapitel 3.1/3.2 hängt an „Chat" weitere, teils deutlich größere Anforderungen:
nutzerbasierte Dokumenten-Uploads (REQ-INT-002A/B/C), SSO (REQ-INT-003). Das ist zu groß für
ein Teilprojekt.

**Entschieden mit dem Auftraggeber:**

1. Umfang: ein zustandsbehafteter Chat-Endpunkt inkl. Sitzungshistorie („erneut öffnen",
   REQ-INT-002A), aber ohne Nutzer-Uploads und ohne SSO. Sitzungsidentität über einen
   anonymen, vom Client gehaltenen Token — keine Kontopflicht, kein Login (ADR-017/
   REQ-ACC-001; „Verläufe" steht zwar auf CLAUDE.mds abschließender Liste der
   Kontopflicht-Gründe, wird hier aber bewusst ohne Konto realisiert, solange die Historie nur
   gerätegebunden sein muss).
2. LLM-Betrieb: selbst gehostet auf STACKIT-GPU-Infrastruktur, kein externer US-API-Anbieter —
   konsistent mit CLAUDE.mds „keine US-Dienste für Betrieb" und ADR-005s Feststellung, dass
   LLM-Inferenz „ohnehin nicht auf Serverless-Plattformen" läuft. Modell: Llama 3.1 8B
   Instruct (REQ-INT-004s eigenes Beispiel), Inferenz-Server: Ollama (einfacher zu
   containerisieren als vLLM, für die aktuelle Nutzungsgröße ausreichend; vLLMs
   Durchsatzvorteile wären hier verfrüht).
3. Klassifikation Strukturfrage vs. Synthesefrage: regelbasiert, kein Modellaufruf fürs
   Routing selbst (ADR-008, „ohne Tokenkosten").
4. Architektur: eigenes Top-Level-Paket `chat/`, ruft `api/` als gewöhnlicher HTTP-Client für
   Strukturfragen auf (wie ein externes Drittsystem) — hält `api/`s bereits geprüfte
   „rein lesend"-Eigenschaft intakt. Eigene, schreibende Tabellen (`chat_session`,
   `chat_message`, `chat_message_citation`) im bestehenden `core`-Schema.
5. Ein einfacher Verbatim-Überlapp-Check (REQ-FUNC-002s „Plagiatsprüfung ohne Treffer") ist
   Teil dieses Teilprojekts, nicht Folgearbeit.

## Ziel dieses Teilprojekts

Ein Chat-Endpunkt, der Nutzerfragen in natürlicher Sprache entgegennimmt, Strukturfragen
deterministisch aus dem Graph beantwortet (kein Modellaufruf), Synthesefragen über
Retrieval-Augmented Generation gegen echten DGUV-Volltext mit einem selbst gehosteten LLM
beantwortet — paraphrasiert, mit Zitaten, mit Plagiats-Schutz — und bei fehlender Grundlage
eine erklärende Fallback-Antwort liefert. Die Sitzung ist ohne Konto über einen anonymen
Token fortsetzbar.

## Nicht-Ziele

- **Nutzer-Uploads, Isolation, Ablauffrist** (REQ-INT-002A/B/C, der Upload-Teil) — eigenes,
  späteres Teilprojekt. Nur die Sitzungshistorie aus REQ-INT-002A wird hier umgesetzt, nicht
  die Dokumenten-Upload-Fähigkeit selbst.
- **SSO-Authentifizierung** (REQ-INT-003) — Sitzungen bleiben anonym/gerätegebunden.
- **Rate-Limiting/Kontingent** (REQ-SEC-004, serverseitige Kontingentzählung) — wie im
  Backend-API-Teilprojekt eigene Infrastrukturentscheidung, nicht Teil dieses Teilprojekts.
- **Vollständige Faktenprüfung/Halluzinationserkennung.** REQ-FUNC-001 wird über
  kontextgebundenes Prompting (nur aus abgerufenen Segmenten antworten) angestrebt, nicht
  über eine nachgelagerte Verifikation der inhaltlichen Korrektheit — das wäre ein eigenes,
  größeres Forschungsthema.
- **Produktions-Deployment/Skalierung des Inferenz-Servers** (SKE, GPU-Provisionierung,
  Lastverteilung) — analog zu den vorigen Teilprojekten eine spätere
  Deployment-Entscheidung.
- **Mehrsprachige Chat-Antworten.** Der Kern-Bestand (DGUV) ist deutsch; die Prompt-Sprache
  ist für den Start Deutsch, keine Übersetzungslogik.

## Architektur

### Paketstruktur

Drei Ansätze wurden abgewogen:

1. **Eigenes `chat/`-Verzeichnis, ruft `api/` als HTTP-Client für Strukturfragen.**
2. Chat-Endpunkte direkt in `api/` ergänzen — verworfen: bricht die bereits geprüfte
   Invariante „API ist rein lesend", vermischt zwei unterschiedliche Schutzbedürfnisse
   (öffentliche, anonyme Lese-API vs. sitzungsgebundene, schreibende Chat-Historie).
3. Chat-Logik direkt in `core/` statt eines eigenen Dienstes — verworfen: `core/` ist
   Bibliothek + CLI, kein Webdienst; würde FastAPI/LLM-Client-Abhängigkeiten in jede
   `core`-Installation ziehen, dasselbe Argument wie gegen Ansatz 2 im Backend-API-Design.

**Entschieden: Ansatz 1.**

```
chat/
  pyproject.toml        # eigenes Paket, hängt von normly_core ab
  src/normly_chat/
    main.py              # FastAPI-App, mountet /v1/chat
    dependencies.py       # DB-Session, HTTP-Client für api/, Ollama-Client
    schemas.py             # Pydantic-Request-/Response-Modelle
    classify.py             # regelbasierte Struktur-vs-Synthese-Erkennung
    structural.py            # baut Antworten aus api/-Aufrufen (kein LLM)
    synthesis.py              # RAG-Retrieval + Ollama-Aufruf + Paraphrasierungs-Prompt
                               # + Verbatim-Überlapp-Check
  tests/
```

`chat/` spricht mit `api/` ausschließlich über dessen öffentliche HTTP-Schnittstelle — wie
ein externes Drittsystem, kein direkter Python-Import der `api`-Router. Das ist bewusst
Dogfooding der eigenen öffentlichen API.

### Datenmodell (neue Tabellen im bestehenden `core`-Schema)

| Tabelle | Spalten | Zweck |
|---|---|---|
| `chat_session` | `id` (PK), `session_token` (eindeutig, opak), `jurisdiction`, `created_at` | Anonyme Sitzungsidentität |
| `chat_message` | `id` (PK), `session_id` (FK), `role` (`user`/`assistant`), `content`, `answer_type` (`structural`/`synthesis`/`fallback`), `created_at` | Chat-Verlauf |
| `chat_message_citation` | `message_id` (FK), `document_id` (FK), `segment_id` (FK, nullable) | Abstammung der Antwort — welches Dokument/Segment die Antwort stützt |

`session_token` ist ein zufälliger, ausreichend langer opaker String (kein JWT nötig — keine
eingebetteten Ansprüche, nur ein Nachschlage-Schlüssel). Der Client erhält ihn bei der ersten
Anfrage und schickt ihn bei Folgeanfragen mit; ein fehlender oder unbekannter Token startet
eine neue Sitzung, kein Fehler.

Repository-Zugriff nach demselben Muster wie überall im Projekt: `ChatRepository` (o. ä.) in
`core/src/normly_core/graph/postgres/repositories.py`, Protocol in `domain.py`,
Alembic-Migration für die drei Tabellen.

### Neue Repository-Fähigkeit: Ähnlichkeitssuche

`SegmentRepository.find_similar_segments_for_jurisdiction(query_vector: list[float],
jurisdiction: str, limit: int = 5) -> list[Segment]` — pgvector-Ähnlichkeitssuche
(`ORDER BY embedding.vector <=> :query_vector LIMIT :limit`), mit denselben
Rechte-Gate-Bedingungen wie das bestehende `list_segments_for_jurisdiction`
(`may_process`, `may_index_fulltext`, `revoked_at IS NULL`) — nur mit
Distanz-Sortierung statt Vollständigkeit. Kein zweiter Prüfpfad: dieselbe
Rechteklassifikations-Logik, nur eine andere Sortierung/Begrenzung.

`EmbeddingModel` (aus der Ingestion-Pipeline, `core/src/normly_core/pipeline/embeddings.py`)
bekommt eine neue Methode `embed_query(text: str) -> list[float]` (Präfix `"query: "` statt
`"passage: "`, e5-Konvention für Suchanfragen vs. Index-Inhalte) — die bestehende `embed()`
bleibt unverändert, keine Breaking Change für die Ingestion-Pipeline.

## Datenfluss

`POST /v1/chat` — `{session_token: str | None, jurisdiction: str, message: str}`

```
Kein/unbekannter session_token? -> neue chat_session anlegen, neuen Token zurückgeben

message klassifizieren (classify.py, regelbasiert, kein Modellaufruf):
    Muster wie "ersetzt", "gültig", "Verweis auf" + erkennbare Bezeichnung im Text
    -> STRUKTURFRAGE
    sonst -> SYNTHESEFRAGE

STRUKTURFRAGE:
    Bezeichnung aus dem Text extrahieren (Regex/Heuristik)
    -> HTTP-Aufruf gegen api/: GET /v1/documents (Suche), dann je nach erkanntem
       Fragetyp GET .../validity oder GET .../edges
    -> deterministischer, textuell zusammengesetzter Antwortsatz aus der
       strukturierten JSON-Antwort — KEIN Modellaufruf
    -> Zitat: das gefundene Dokument selbst
    -> Dokument nicht gefunden (404 von api/)? -> Fallback-Antwort

SYNTHESEFRAGE:
    EmbeddingModel.embed_query(message)
    -> SegmentRepository.find_similar_segments_for_jurisdiction(vector, jurisdiction, limit)
    kein Treffer? -> Fallback-Antwort (Textbaustein, kein Modellaufruf)
    Treffer vorhanden?
        -> Prompt: System-Anweisung "nur paraphrasieren, nur aus dem Kontext antworten,
           keine Volltextwiedergabe" (REQ-FUNC-001/002) + Segmenttexte + Frage
        -> Ollama-Aufruf (Llama 3.1 8B Instruct)
        -> Verbatim-Überlapp-Check der Antwort gegen die zitierten Segmenttexte
           (15+ aufeinanderfolgende Wörter überlappend? -> Antwort verwerfen, Fallback
           stattdessen, Vorfall geloggt)
        -> sonst: Antwort + Zitate (die verwendeten Segmente/Dokumente)

chat_message (Nutzerfrage) + chat_message (Antwort) + chat_message_citation(s) speichern
-> Response: {session_token, answer, answer_type, citations}
```

Kein LLM-Aufruf für Strukturfragen und für jeden Fallback-Fall — nur die eigentliche Synthese
ruft das Modell auf (ADR-008s „doppelter Gewinn": geringere Kosten und höhere Verlässlichkeit
genau dort, wo Fehler am teuersten wären).

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Fehlende/leere `message` oder `jurisdiction` | 400 |
| Unbekannter/fehlender `session_token` | Kein Fehler — neue Session wird angelegt |
| Strukturfrage, aber Dokument in `api/` nicht auffindbar (404) | Fallback-Antwort, kein Chat-Fehler |
| Synthesefrage ohne relevante Segmente | Fallback-Antwort, kein Modellaufruf |
| LLM-Antwort enthält 15+ aufeinanderfolgende Wörter aus einem zitierten Quellsegment | Antwort verworfen, Fallback-Antwort stattdessen, Vorfall geloggt |
| Ollama nicht erreichbar | 503, kein Detail-Leak |
| Datenbank- oder `api/`-Verbindung down | 503, kein Detail-Leak |

## Testkonzept

- Echtes Ollama mit echtem Llama 3.1 8B Instruct in den Tests (kein Mocking des Modells) —
  konsistent mit dem bisherigen Projektstil (echtes Embedding-Modell in der
  Ingestion-Pipeline, echtes Postgres überall). Die verfügbare 24-GB-GPU reicht dafür.
- `api/` läuft als echter Prozess in den Tests, `chat/` ruft es wirklich über HTTP auf — kein
  Mocking der Backend-API, genau wie ein externes Drittsystem sie nutzen würde.
- Klassifikation (`classify.py`) isoliert und ohne Modell/DB getestet — reine
  Funktionslogik, schnell.
- Strukturfrage-Pfad: End-to-End gegen echte DGUV-/EUR-Lex-Testdaten, prüft zusätzlich, dass
  kein Ollama-Aufruf stattfindet (Zähler/Spy auf dem Ollama-Client).
- Synthesefrage-Pfad: End-to-End mit echten DGUV-Segmenten, prüft Zitate und den
  Verbatim-Überlapp-Check — positiv (normale Paraphrase wird durchgelassen) und negativ (ein
  absichtlich Volltext-wiederholender Test-Prompt erzwingt den Fallback-Pfad).
- Rechteklassifikations-Asymmetrie: dieselbe Frage liefert für einen Rechtsraum ohne
  Klassifikation ausschließlich den Fallback (keine Segmente sichtbar) — analog zum
  bestehenden Muster aus den vorigen Teilprojekten.
- Sitzungs-Fortsetzung: zwei Anfragen mit demselben `session_token` landen in derselben
  `chat_session`, mit vollständiger `chat_message`-Historie in der richtigen Reihenfolge.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-FUNC-001 | Synthese-Antworten ausschließlich aus abgerufenen, rechtsraumsichtbaren Segmenten (Prompt-Bindung); Strukturantworten ausschließlich aus dem Graph |
| REQ-FUNC-002 | Paraphrasierungs-Anweisung im Prompt + Verbatim-Überlapp-Check als Nachkontrolle |
| REQ-FUNC-003 | Fallback-Antwort für jeden Fall ohne belastbare Grundlage (kein Treffer, kein Dokument, Plagiats-Verdacht) |
| REQ-INT-002A (nur Historie-Teil) | `chat_session`/`chat_message` erlauben „Chat erneut öffnen" über den `session_token`, ohne Konto |
| REQ-INT-004 | Ollama als austauschbare Inferenz-Schicht hinter `synthesis.py`; Modellwechsel ohne Änderung an `chat/`s öffentlicher Schnittstelle |
| REQ-GRAPH-003 | Regelbasierte Klassifikation vor jedem Modellaufruf, Strukturfragen deterministisch über `api/` |
| ADR-005 | Selbst gehostetes LLM (Ollama/Llama 3.1) statt externer US-API |
| ADR-008 | Kein Modellaufruf für Routing, Strukturfragen oder Fallback-Fälle |
| ADR-017 / REQ-ACC-001 | Anonymer `session_token` statt Konto — Chat funktioniert ohne Login |

## Offene Punkte / Folgearbeiten

- **Nutzer-Uploads** (REQ-INT-002A/B/C, der Upload-Teil), **SSO** (REQ-INT-003) — eigene,
  spätere Teilprojekte.
- **Rate-Limiting/Kontingent** (REQ-SEC-004) — eigene Infrastrukturentscheidung, wie im
  Backend-API-Teilprojekt.
- **Sitzungs-Ablauf/Bereinigung.** `chat_session`/`chat_message` haben aktuell keine
  automatische Löschfrist. REQ-INT-002C (7 Tage Default) gilt explizit für Uploads, nicht für
  Chat-Historie — ob eine analoge Frist für Chat-Sitzungen sinnvoll ist, ist hier nicht
  entschieden.
- **Zwei-Modell-Strategie** (ADR-008 erwähnt „kleines Modell für Routing, großes nur für
  komplexe Synthesen") — für den Start reicht ein Modell plus regelbasiertes Routing; ein
  zweites, kleineres Modell für unschärfere Klassifikationsfälle ist mit dem aktuellen
  Bestand nicht beobachtbar nötig.
- **Faktenprüfung/Halluzinationserkennung über reines Prompting hinaus** — siehe Nicht-Ziele,
  eigenes, größeres Thema.
- **Produktions-Deployment des Inferenz-Servers** (GPU-Provisionierung auf STACKIT,
  Skalierung, SKE-Anbindung) — spätere Deployment-Entscheidung, analog zu den vorigen
  Teilprojekten.
- **Mehrere gleichzeitige Chat-Anfragen/Warteschlange bei Ollama.** Mit einer einzelnen GPU
  und Ollamas Standard-Betrieb ist Parallelität begrenzt — für die aktuelle Nutzungsgröße
  unproblematisch, bei wachsendem Bestand zu prüfen (siehe auch die vLLM-Alternative aus der
  Architektur-Diskussion).
