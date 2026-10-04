# Design: Containerisierung (STACKIT-Deployment, Teilprojekt 1/4)

Stand: 2026-10-01, freigegeben 2026-10-04 · Status: freigegeben. Roadmap und
Grundsatzentscheidungen E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

## Ziel

Aus dem Repository entstehen fünf Container-Images und ein Compose-Setup,
das mit einem Aufruf eine lauffähige normly-Instanz startet (REQ-DIST-004,
ADR-010). Dasselbe Setup läuft mit anderer Konfiguration auf der
STACKIT-VM gegen PostgreSQL Flex und STACKIT AI Model Serving (E8:
verifiziert wird direkt dort). Dazu die eine Codeänderung, die der
Betrieb auf STACKIT verlangt: ein OpenAI-kompatibler LLM-Client im
Chat-Dienst.

Nicht Teil dieses Teilprojekts: Image-Build in der CI und Push in die GHCR
(TP2), DNS, Secrets Manager, cloud-init (TP3), Rollout-Skript, Rollback,
Datenstand-Import und -Export (TP4).

## Vorentscheidungen des Nutzers (aus der Roadmap, nicht neu verhandeln)

- `core` behält Docling und sentence-transformers als Pflichtabhängigkeit.
  Folge: ein gemeinsames Python-Basis-Image.
- Die Gewichte von `intfloat/multilingual-e5-large` werden beim Build in
  dieses Basis-Image eingebacken.
- Iteration auf der STACKIT-VM: Repository dort auschecken, Images dort
  bauen.

## Image-Aufbau

Fünf veröffentlichte Images plus ein internes Basis-Image. Alle laufen als
unprivilegierter Nutzer, alle Basis-Images sind per Tag gepinnt (Digest-
Pinning kommt mit der Signierung in TP2).

| Image | Basis | Inhalt | Prozess |
|---|---|---|---|
| `normly-python-base` (intern, nicht veröffentlicht) | `python:3.12-slim` | `libgl1`, `core` installiert (alle Abhängigkeiten), e5-Gewichte unter `/opt/models/multilingual-e5-large`, `ENV NORMLY_EMBEDDING_MODEL_PATH` darauf | — |
| `normly-api` | Basis | `api` installiert | `uvicorn normly_api.main:app --host 0.0.0.0 --port 8000` |
| `normly-chat` | Basis | `chat` installiert | `uvicorn normly_chat.main:app …` |
| `normly-accounts` | Basis | `accounts` installiert | `uvicorn normly_accounts.main:app …` |
| `normly-pipeline` | Basis | `core/alembic.ini` + `core/migrations`, Docling-Modelle unter `/opt/models/docling` (`docling-tools models download layout tableformer`), `ENV NORMLY_DOCLING_ARTIFACTS_PATH` | Entrypoint `python -m normly_core.pipeline`; Migrationen per `alembic upgrade head` |
| `normly-frontend` | `node:22-alpine` (Multi-Stage) | `npm ci`, `next build`; Laufzeit nur `.next/standalone`, `.next/static`, `public` | `node server.js`, Port 3000 |

Entscheidungen dazu:

- **Modellgewichte beim Build laden, nicht aus dem Hugging-Face-Cache
  kopieren.** Der Build-Schritt ruft `SentenceTransformer(MODEL_NAME).save(path)`
  auf. Das macht den Build reproduzierbar und unabhängig vom Rechner; es
  ist der einzige Moment, in dem huggingface.co kontaktiert wird. Für den
  Build auf der STACKIT-VM ist das zulässig: es ist ein Download öffentlicher
  Gewichte, keine Nutzerdaten verlassen das System. In TP2 übernimmt das die
  GitHub-Pipeline, dann berührt die VM huggingface.co gar nicht mehr.
- **Docling-Modelle nur im Pipeline-Image**, nicht in der Basis: `api`,
  `chat`, `accounts` brauchen sie nicht, und so bleibt die geteilte Schicht
  kleiner.
- **Build-Kontext ist die Repository-Wurzel** für alle Python-Images (sie
  brauchen `core/` und ihr eigenes Paket), `frontend/` für das Frontend.
  Eine `.dockerignore` an der Wurzel schließt `.venv`, `node_modules`,
  `tests`, `.git`, `docs`, `site` aus.
- **Erwartete Größen:** Basis ca. 5 GB Abhängigkeiten plus 2,2 GB Gewichte;
  die drei Dienst-Images legen je unter 50 MB darauf; Pipeline plus ca.
  1 GB Docling-Modelle; Frontend unter 300 MB.

## Compose-Aufbau

Eine Datei `compose.yaml` an der Repository-Wurzel, Dienste über Profile
zuschaltbar, Konfiguration über `.env` (Vorlage `.env.example` im Repo,
ohne Secrets).

| Dienst | Profil | Image | Zweck |
|---|---|---|---|
| `postgres` | `bundled` | `pgvector/pgvector:pg17` | Datenbank für Self-Hosting und Entwicklung |
| `ollama` | `bundled` | `ollama/ollama` | LLM für Self-Hosting und Entwicklung |
| `ollama-pull` | `bundled` | `ollama/ollama` | Einmal-Dienst, zieht das konfigurierte Modell, dann beendet |
| `mailpit` | `bundled` | `axllent/mailpit` | Mail-Fänger, SMTP 1025, Oberfläche 8025 |
| `migrate` | immer | `normly-pipeline` | Einmal-Dienst `alembic upgrade head`, idempotent |
| `api`, `chat`, `accounts` | immer | je eigenes Image | `depends_on: migrate: condition: service_completed_successfully` |
| `frontend` | immer | `normly-frontend` | einziger nach außen sichtbarer Dienst |
| `caddy` | `edge` | `caddy:2` | TLS per Let's Encrypt, `reverse_proxy frontend:3000` |
| `pipeline` | manuell (`docker compose run --rm pipeline ingest …`) | `normly-pipeline` | Ingestion auf der VM, Rohdaten aus einem Volume |

Entscheidungen dazu:

- **Profile statt mehrerer Compose-Dateien.** Ein Override kann Dienste
  nicht entfernen, nur ändern; Profile können es. `.env.example` setzt
  `COMPOSE_PROFILES=bundled`, damit `docker compose up` für Self-Hoster ohne
  weiteren Parameter alles startet (REQ-DIST-004: „ein Aufruf"). Die
  Produktions-`.env` auf der VM setzt `COMPOSE_PROFILES=edge` und zeigt
  `NORMLY_DATABASE_URL` auf Postgres Flex sowie den LLM auf AI Model
  Serving.
- **Nur das Frontend ist erreichbar**, Backends hängen in einem internen
  Netz. Das Frontend ist als BFF gebaut (`frontend/README.md`): der Browser
  spricht ausschließlich mit Next.js-Route-Handlern, nie mit `api`, `chat`
  oder `accounts` direkt. Das ist zu verifizieren, bevor die Ports
  geschlossen werden; falls eine Route doch direkt auf ein Backend zeigt,
  wird sie durch den BFF geführt, nicht das Backend geöffnet.
- **Migrationen als Einmal-Dienst vor dem Start**, nicht im Entrypoint der
  Dienste. So läuft Alembic genau einmal pro `up`, nicht dreimal
  gleichzeitig aus drei Containern.
- **Healthchecks** gegen `GET /openapi.json` je Backend und `GET /` am
  Frontend, Postgres per `pg_isready`. Eigene `/health`-Endpunkte mit
  DB-Prüfung wären besser, sind aber eine Codeänderung in drei Diensten und
  werden als Folgearbeit für TP4 notiert, wo Rollback-Entscheidungen davon
  abhängen.
- **Ollama-Modell für Entwicklung und Self-Hosting:** die kleinste
  Gemma-Variante, die die Ollama-Bibliothek zum Implementierungszeitpunkt
  anbietet (Tag beim Implementieren prüfen und in `.env.example`
  eintragen). Gemma-Familie wegen E2/E3; klein, weil auf CPU gerechnet
  wird. Die Antwortqualität ist dann unter Produktionsniveau, das ist für
  Self-Hoster dokumentiert und akzeptiert.
- **Ingestion läuft auf der VM** im Pipeline-Image; Rohdateien werden in
  ein Volume unter `/data/raw/<quelle>` gelegt. Export und Import des
  Datenstands als versionierter Dump sind TP4.

## Codeänderung: LLM-Client im Chat-Dienst

Heute: `OllamaClient(base_url, model).chat(messages) -> str`
(`chat/src/normly_chat/ollama_client.py`), erzeugt in `main.py`,
durchgereicht über `dependencies.get_ollama_client`, genutzt in
`routers/chat.py` und `synthesis._is_faithful`.

Neu:

- Ein Protokoll `LlmClient` mit `chat(messages: list[dict]) -> str`.
- `OpenAiCompatibleClient(base_url, model, api_key)` ruft
  `POST {base_url}/chat/completions` mit `Authorization: Bearer` auf und
  gibt `choices[0].message.content` zurück. Wie `OllamaClient` ein dünner
  httpx-Aufruf, keine SDK-Abhängigkeit.
- Auswahl in `main.py` über `NORMLY_LLM_PROVIDER` (`ollama` | `openai-compatible`),
  `NORMLY_LLM_BASE_URL`, `NORMLY_LLM_MODEL`, `NORMLY_LLM_API_KEY` (nur beim
  zweiten Provider). Die alten Namen `NORMLY_OLLAMA_BASE_URL` /
  `NORMLY_OLLAMA_MODEL` entfallen; sie sind nur in `main.py`, Tests und
  Doku referenziert, es gibt kein Deployment, das sie noch bräuchte.
- Produktionswerte: `openai-compatible`,
  `https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1`,
  `google/gemma-4-31B-it`, Token aus der `.env` (TP3: aus dem Secrets
  Manager).
- `get_ollama_client` wird zu `get_llm_client`; Typannotationen auf das
  Protokoll.

Tests: Unit-Tests für `OpenAiCompatibleClient` mit gemocktem httpx-Transport
(Erfolg, HTTP-Fehler, Request-Form), ein Test für die Provider-Auswahl in
`main.py`. Bestehende Tests, die `OllamaClient` stubben, bleiben über das
Protokoll gültig.

## Dokumentation

- **ADR-022 „Betriebsumgebung Phase 1"** in `docs/adr/README.md`: E1–E8
  mit Begründung und Verworfenem; Modellherkunftsregel mit Wiedervorlage
  „europäisches Modell"; befristete Abweichung von REQ-DIST-001. Der
  offene Punkt „Öffentlicher Lesezugriff auf STACKIT Container Registry"
  im Register wird als durch ADR-021 erledigt gestrichen.
- **CLAUDE.md**, Abschnitt „Nicht verhandelbar": ein Satz zur
  Modellherkunft (Open-Weight, OSI-Lizenz, Betrieb nur auf STACKIT, keine
  Daten an den Modellhersteller) mit Verweis auf ADR-022.
- **SRS** `docs/srs/03-anforderungen.md`: REQ-DIST-001 (Abweichung mit
  Verweis), Kapitel 3.5 Fließtext (Modellherkunft). REQ-INST-003
  (Secrets-Fluss) erst in TP3, wenn der Weg feststeht.
- **`docs/guide/self-hosting.md`**: Platzhalter ersetzen durch den
  tatsächlichen Weg: Voraussetzungen, `cp .env.example .env`,
  `docker compose up`, erster Aufruf, wo Mails landen, wie das Modell
  gewechselt wird. Hinweis, dass das Datenstand-Dump-Verfahren folgt (TP4).
- **`frontend/README.md`** und die README-Tabellen der Dienste: neue
  `NORMLY_LLM_*`-Variablen.

## Verifikation (auf der STACKIT-VM, E8)

1. **Self-Hosting-Pfad:** `COMPOSE_PROFILES=bundled docker compose up`
   startet ohne Nacharbeit; Migrationen laufen durch; Frontend antwortet
   auf Port 3000; Registrierung erzeugt eine Mail in Mailpit; eine
   Chat-Anfrage liefert eine Antwort aus Ollama.
2. **Produktionspfad:** `.env` mit Postgres Flex, AI Model Serving und
   Profil `edge`; `docker compose up`; `https://app.normly.ai` antwortet mit
   gültigem Zertifikat, sobald DNS steht (bis dahin über die IP mit
   Caddy im HTTP-Modus); Chat-Antwort kommt aus Gemma 4; kein Container
   außer `caddy` hat einen veröffentlichten Port.
3. **Idempotenz:** zweites `docker compose up` ändert nichts; `migrate`
   endet mit „nothing to upgrade".
4. **Kein Laufzeit-Download:** Netzzugriff der Dienst-Container auf
   huggingface.co ist zur Laufzeit nicht nötig (Prüfung: Start mit
   gesperrtem ausgehenden Zugriff außer Postgres und Model Serving).
5. Bestehende Testsuiten aller Pakete grün; neue Tests für den
   LLM-Client grün; `test-docs` auf der 3-Issue-Baseline.

## Durchsicht (2026-10-04, Nutzer): freigegeben

- Postgres-Version im `bundled`-Profil: **17**, passend zur gebuchten
  Flex-Instanz (Version 17), damit Dumps austauschbar bleiben.
- Caddy nur im `edge`-Profil; Self-Hoster ohne eigene Domain starten ohne
  TLS-Terminierung, der Self-Hosting-Guide beschreibt, wie das Profil
  zugeschaltet wird.
- Healthchecks über `/openapi.json`; eigene `/health`-Endpunkte mit
  DB-Prüfung als Folgearbeit für TP4 notiert.

Zielumgebung am 2026-10-04 verifiziert: VM `normly-prod` (Ubuntu 26.04 LTS,
`g1a.4d`, Public IP `213.17.23.196`, SSH als `ubuntu`), `/opt/normly/.env`
vorhanden (600), Postgres Flex per TCP erreichbar (ACL auf die VM-IP),
AI Model Serving antwortet mit dem Token und listet `google/gemma-4-31B-it`.
Docker ist auf der VM noch nicht installiert; das ist der erste
Implementierungsschritt.

## Verifikation 2026-10-04

Geprüft auf der STACKIT-VM (Docker 29, Compose 2.40; Versionen laut Task 3), Images dort gebaut.

**Image-Größen:** python-base 6,59 GB; api 6,62 GB; chat 6,62 GB; accounts 6,65 GB; pipeline 7,94 GB; frontend 336 MB. Die Python-Images sind groß, weil Torch und die Embedding-Gewichte (multilingual-e5-large) im Image liegen.

**Self-Hosting-Pfad (Profil bundled, eigene Postgres, Ollama gemma3:4b; 2026-10-04: Default-Modell jetzt gemma4:e4b, Apache-2.0; gemma3 fiel unter die Gemma Terms of Use):** `up -d --build` mit gecachten Layern (beobachtet); nach rund 2 Minuten alle Dienste healthy, `migrate` Exit 0 mit `migrations: at head` (Revision 0031), `ollama-pull` Exit 0. Frontend und /search liefern 200, Registrierung 200 mit genau einer Mail in Mailpit, Chat 200 mit Fallback-Antwort (leere Datenbank); die Ollama-Inferenz selbst wurde auf dem Bundled-Pfad dadurch nicht geprüft, als Beleg für das gebündelte LLM dienen nur der erfolgreiche `ollama-pull` und der Health-Check. Ein zweites `up -d` erzeugt keine Container, `migrate` bleibt `at head`. Die Gewichte stammen aus dem Image; die „huggingface"-Treffer in den Logs sind nur der URL-Text einer Tokenizer-Warnung.

**Produktionspfad (Postgres Flex, Model Serving, Caddy):** Der erste Start scheiterte, weil die Datenbank `normly` auf der Flex-Instanz noch nicht angelegt war (Verbindung und Anmeldung funktionierten). Nach dem Anlegen: `migrate` Exit 0 `at head`; api, accounts, chat, frontend healthy; caddy Up; Zeit bis healthy nicht gemessen (beim Check nach 90 s waren alle Dienste healthy). Ports: nur caddy auf 80/443, frontend auf 127.0.0.1:3000; kein postgres, ollama, mailpit.

**TLS und Ende-zu-Ende:** `https://app.normly.ai/` liefert 200 mit gültigem Let's-Encrypt-Zertifikat (ssl_verify_result 0); HTTP leitet mit 308 auf HTTPS um. Chat über die öffentliche Adresse: 200, Fallback-Antwort, keine Fehler in den Chat-Logs. Die Fallback-Antwort braucht ohne Segmente kein Modell; deshalb wurde der Aufruf separat belegt: Der Model-Serving-Aufruf wurde aus dem Chat-Container heraus bestätigt (`OpenAiCompatibleClient`, google/gemma-4-31B-it, Antwort `'Test'` erhalten).

**Firewall:** Von außen sind 8000, 3000, 5432, 11434 und 8025 geschlossen, 80 und 443 offen.

**Auffälligkeiten:** Das Tokenizer-Warning (`fix_mistral_regex`) beim Laden des Embedding-Modells ist harmlos, sollte aber bei einem späteren Modell-Update beobachtet werden. Container haben ausgehenden Internetzugang; „offline" ist durch die Image-Gewichte belegt, nicht durch eine Netzsperre.
