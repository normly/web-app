# Design: LLM-Chat mit anonymer und kontogebundener Sitzungshistorie (v1)

**Datum:** 2026-08-20 (Sitzungsidentität überarbeitet: 2026-08-21)
**Status:** genehmigt
**Teilprojekt:** fünftes von mehreren zur Umsetzung des normly-MVP (freier Kern)

> **Nachtrag 2026-08-21:** Diese Spec wurde ursprünglich mit rein anonymer Sitzungsidentität
> genehmigt, dann zurückgestellt, bis das inzwischen abgeschlossene Accounts-Teilprojekt
> (viertes Teilprojekt) echte Konten bereitstellt. Jetzt überarbeitet: Abschnitt „Entschieden
> mit dem Auftraggeber" Punkt 1, Nicht-Ziele, Datenmodell und Datenfluss tragen die optionale
> Kontoverknüpfung nach. Der Rest der Spec (Architektur, RAG-Ablauf, LLM-Betrieb,
> Rechte-Gate-Fragen) ist unverändert gültig.

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
   REQ-INT-002A), aber ohne Nutzer-Uploads. Sitzungsidentität primär über einen anonymen, vom
   Client gehaltenen Token — keine Kontopflicht, kein Login erzwungen (ADR-017/REQ-ACC-001;
   „Verläufe" steht zwar auf CLAUDE.mds abschließender Liste der Kontopflicht-Gründe, ist hier
   aber ausdrücklich optional, nicht verpflichtend). Seit der Überarbeitung vom 2026-08-21 kann
   eine `chat_session` zusätzlich optional mit einem echten Konto aus dem Accounts-Teilprojekt
   verknüpft werden — siehe „Sitzungsidentität und Kontoverknüpfung" unten.
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
- **Eigene Authentifizierungslogik in `chat/`.** `chat/` prüft ein mitgeschicktes
  Konto-Token nur bei `accounts/` (HTTP-Aufruf, wie `api/`) — kein eigenes Login, keine
  eigene Session-Verwaltung für Konten. Ob überhaupt ein Konto-Token mitgeschickt wird,
  bleibt vollständig dem Client überlassen; anonyme Sitzungen funktionieren unverändert ohne
  jede Berührung mit `accounts/`.
- **Rate-Limiting/Kontingent** (REQ-SEC-004, serverseitige Kontingentzählung) — wie im
  Backend-API-Teilprojekt eigene Infrastrukturentscheidung, nicht Teil dieses Teilprojekts.
- **Vollständige Faktenprüfung/Halluzinationserkennung.** REQ-FUNC-001 wird über
  kontextgebundenes Prompting (nur aus abgerufenen Segmenten antworten) angestrebt, nicht
  über eine nachgelagerte Verifikation der inhaltlichen Korrektheit — das wäre ein eigenes,
  größeres Forschungsthema.
- **Produktions-Deployment/Skalierung des Inferenz-Servers** (SKE, GPU-Provisionierung,
  Lastverteilung) — analog zu den vorigen Teilprojekten eine spätere
  Deployment-Entscheidung.
- **Sprachen über Deutsch/Englisch hinaus.** `language` ist von Anfang an `"de"`/`"en"`
  (siehe Architektur) — weitere Sprachen sind Folgearbeit, kein Übersetzungsdienst für
  beliebige Zielsprachen in diesem Teilprojekt.

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
| `chat_session` | `id` (PK), `session_token` (eindeutig, opak), `account_id` (FK auf `account`, **nullable**), `jurisdiction`, `language` (`de`/`en`), `created_at` | Sitzungsidentität — anonym (`account_id IS NULL`) oder kontoverknüpft |
| `chat_message` | `id` (PK), `session_id` (FK), `role` (`user`/`assistant`), `content`, `answer_type` (`structural`/`synthesis`/`fallback`), `created_at` | Chat-Verlauf |
| `chat_message_citation` | `message_id` (FK), `document_id` (FK), `segment_id` (FK, nullable) | Abstammung der Antwort — welches Dokument/Segment die Antwort stützt |

`session_token` ist ein zufälliger, ausreichend langer opaker String (kein JWT nötig — keine
eingebetteten Ansprüche, nur ein Nachschlage-Schlüssel). Der Client erhält ihn bei der ersten
Anfrage und schickt ihn bei Folgeanfragen mit; ein fehlender oder unbekannter Token startet
eine neue Sitzung, kein Fehler.

`account_id` ist `NULL` für rein anonyme Sitzungen und bleibt es für die gesamte Lebensdauer
der Sitzung, solange kein gültiges Konto-Token mitgeschickt wird — siehe unten. Ein Konto kann
mehrere `chat_session`-Zeilen haben (ein Gerät/Browser = eine Sitzung, wie schon bisher); es
gibt keine automatische Zusammenführung mehrerer Geräte-Verläufe zu einer Sitzung.

### Sitzungsidentität und Kontoverknüpfung

`POST /v1/chat` akzeptiert optional einen `Authorization: Bearer <accounts-Sitzungstoken>`-
Header. `chat/` verifiziert einen mitgeschickten Konto-Token ausschließlich über einen
HTTP-Aufruf gegen `accounts/` (`GET /v1/accounts/session`) — derselbe „Dienst als
HTTP-Client"-Grundsatz wie bei `api/`, kein direkter Zugriff auf `accounts`-Tabellen. Drei
Fälle:

1. **Kein oder ungültiger Konto-Token.** Verhalten unverändert zur Ursprungsspec: rein
   anonyme Sitzung über `session_token`, keine Berührung mit `accounts/`.
2. **Gültiger Konto-Token, `chat_session` noch nicht verknüpft** (`account_id IS NULL`).
   Die Sitzung wird jetzt mit der Konto-ID verknüpft (`UPDATE chat_session SET account_id =
   ...`), der bisherige Nachrichtenverlauf bleibt vollständig erhalten und ist ab diesem
   Zeitpunkt auch von anderen, mit demselben Konto verknüpften Geräten aus sichtbar (über
   eine künftige „Sitzungen auflisten"-Fähigkeit, hier nicht Teil des Umfangs — siehe Offene
   Punkte).
3. **Gültiger Konto-Token, `chat_session` bereits an eine ANDERE Konto-ID gebunden.**
   Schutz vor Geräte-/Nutzerwechsel: statt die fremde Sitzung weiterzuverwenden, wird eine
   neue `chat_session` für dieses Konto angelegt und ein neuer `session_token`
   zurückgegeben (wie beim allerersten Request). Verhindert, dass die Nachrichten einer
   Person in den Verlauf einer anderen landen, nur weil beide dasselbe Gerät mit
   wiederverwendetem `session_token` benutzt haben.

Ein abgelaufener/unbekannter Konto-Token wird wie „kein Token" behandelt (Fall 1) — kein
Fehler, kein Detail-Leak, konsistent mit `accounts/`s eigenem Umgang mit `/session`.

`language` ist ein expliziter Client-Parameter (`"de"` oder `"en"`), kein automatisch
erkannter — dasselbe Muster wie `jurisdiction`: deterministisch, kein zusätzlicher
Erkennungs-Dienst/-Modell nötig. Er steuert (a) welche Textbausteine `structural.py` für
Strukturantworten verwendet (b) die Sprachanweisung im Synthese-Prompt an das LLM. Die
Ähnlichkeitssuche selbst ist davon unabhängig: `multilingual-e5-large` ist sprachübergreifend
— eine englische Frage findet auch deutsche DGUV-Segmente, das LLM formuliert die Antwort
dann trotzdem auf Englisch. `chat/`s Antwort (paraphrasiert) ist damit sprachlich unabhängig
von der Quellsprache der zitierten Segmente.

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

`POST /v1/chat` — `{session_token: str | None, jurisdiction: str, language: Literal["de", "en"], message: str}`,
optionaler Header `Authorization: Bearer <accounts-Sitzungstoken>`

```
Kein/unbekannter session_token? -> neue chat_session anlegen, neuen Token zurückgeben

Authorization-Header vorhanden?
    -> GET /v1/accounts/session bei accounts/ (HTTP-Aufruf)
    ungültig/abgelaufen? -> wie "kein Header" behandeln, weiter wie gehabt
    gültig, chat_session.account_id noch NULL?
        -> chat_session.account_id setzen, Verlauf bleibt erhalten
    gültig, chat_session.account_id bereits eine ANDERE Konto-ID?
        -> neue chat_session für dieses Konto anlegen, neuen session_token zurückgeben
    gültig, chat_session.account_id == diese Konto-ID?
        -> nichts zu tun, weiter wie gehabt

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
           keine Volltextwiedergabe, antworte auf {language}" (REQ-FUNC-001/002) +
           Segmenttexte + Frage
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
| Fehlender/ungültiger/abgelaufener Konto-Token im `Authorization`-Header | Kein Fehler — wie „kein Konto-Token" behandelt, Chat funktioniert anonym weiter |
| Strukturfrage, aber Dokument in `api/` nicht auffindbar (404) | Fallback-Antwort, kein Chat-Fehler |
| Synthesefrage ohne relevante Segmente | Fallback-Antwort, kein Modellaufruf |
| LLM-Antwort enthält 15+ aufeinanderfolgende Wörter aus einem zitierten Quellsegment | Antwort verworfen, Fallback-Antwort stattdessen, Vorfall geloggt |
| Ollama nicht erreichbar | 503, kein Detail-Leak |
| Datenbank- oder `api/`-/`accounts/`-Verbindung down | 503, kein Detail-Leak |

## Testkonzept

- Echtes Ollama mit echtem Llama 3.1 8B Instruct in den Tests (kein Mocking des Modells) —
  konsistent mit dem bisherigen Projektstil (echtes Embedding-Modell in der
  Ingestion-Pipeline, echtes Postgres überall). Die verfügbare 24-GB-GPU reicht dafür.
- `api/` und `accounts/` laufen als echte Prozesse in den Tests, `chat/` ruft sie wirklich
  über HTTP auf — kein Mocking, genau wie ein externes Drittsystem sie nutzen würde.
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
- Zweisprachigkeit: dieselbe Synthesefrage einmal mit `language="de"`, einmal mit
  `language="en"` gegen dieselben (deutschen) DGUV-Segmente — prüft, dass die
  Ähnlichkeitssuche in beiden Fällen dieselben Segmente findet (sprachübergreifendes
  Embedding-Modell) und die Antwort jeweils tatsächlich in der angeforderten Sprache
  formuliert ist.
- Sitzungs-Fortsetzung: zwei Anfragen mit demselben `session_token` landen in derselben
  `chat_session`, mit vollständiger `chat_message`-Historie in der richtigen Reihenfolge.
- Kontoverknüpfung: eine anonyme Sitzung mit bestehendem Verlauf, gefolgt von einer Anfrage
  mit demselben `session_token` plus gültigem Konto-Token — prüft, dass `account_id` gesetzt
  wird UND der bisherige Verlauf erhalten bleibt. Ein zweiter Test mit ungültigem/abgelaufenem
  Konto-Token prüft, dass die Sitzung anonym bleibt (kein Fehler). Ein dritter Test prüft den
  Konto-Wechsel-Schutz: `chat_session` bereits an Konto A gebunden, Anfrage mit gültigem Token
  für Konto B — muss eine neue `chat_session` mit neuem `session_token` erzeugen, ohne
  Konto As Sitzung zu berühren.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Abdeckung in diesem Design |
|---|---|
| REQ-FUNC-001 | Synthese-Antworten ausschließlich aus abgerufenen, rechtsraumsichtbaren Segmenten (Prompt-Bindung); Strukturantworten ausschließlich aus dem Graph |
| REQ-FUNC-002 | Paraphrasierungs-Anweisung im Prompt + Verbatim-Überlapp-Check als Nachkontrolle |
| REQ-FUNC-003 | Fallback-Antwort für jeden Fall ohne belastbare Grundlage (kein Treffer, kein Dokument, Plagiats-Verdacht) |
| REQ-INT-002A (nur Historie-Teil) | `chat_session`/`chat_message` erlauben „Chat erneut öffnen" über den `session_token`, ohne Konto — optional zusätzlich über ein verknüpftes Konto |
| REQ-INT-004 | Ollama als austauschbare Inferenz-Schicht hinter `synthesis.py`; Modellwechsel ohne Änderung an `chat/`s öffentlicher Schnittstelle |
| REQ-GRAPH-003 | Regelbasierte Klassifikation vor jedem Modellaufruf, Strukturfragen deterministisch über `api/` |
| ADR-005 | Selbst gehostetes LLM (Ollama/Llama 3.1) statt externer US-API |
| ADR-008 | Kein Modellaufruf für Routing, Strukturfragen oder Fallback-Fälle |
| ADR-017 / REQ-ACC-001 | Anonymer `session_token` bleibt der Normalfall — Chat funktioniert ohne Login; Kontoverknüpfung ist rein optional, nie Voraussetzung |

## Offene Punkte / Folgearbeiten

- **Nutzer-Uploads** (REQ-INT-002A/B/C, der Upload-Teil) — eigenes, späteres Teilprojekt.
- **„Sitzungen auflisten" für ein Konto.** Ein Konto kann mehrere `chat_session`-Zeilen
  haben (eine pro Gerät/Browser, das verknüpft wurde), aber dieses Teilprojekt liefert keinen
  Endpunkt, der einem eingeloggten Nutzer alle seine Sitzungen anzeigt oder zwischen ihnen
  wechseln lässt — nur die Verknüpfung selbst. Eigene Folgearbeit.
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
