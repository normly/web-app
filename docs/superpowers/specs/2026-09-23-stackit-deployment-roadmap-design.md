# Design: STACKIT-Deployment-Roadmap (Übersicht, 4 Teilprojekte)

Stand: 2026-09-23 · Status: vom Nutzer freigegeben, Teilprojekte folgen je
mit eigenem Spec und Plan.

## Kontext

Die Anwendung läuft heute nur lokal aus Entwicklungs-Venvs. Im Repository
existiert kein Dockerfile, kein Compose-Setup und kein Deployment-Schritt;
die GitHub-CI (`.github/workflows/ci.yml`) testet nur. ADR-005 und ADR-010
verlangen signierte Container-Images plus ein lauffähiges Compose-Setup,
REQ-INST-001 den Betrieb ausschließlich auf STACKIT, REQ-INST-002/004
automatisiertes Deployment mit Rollback. Auf STACKIT existiert am
2026-09-23 noch keine Ressource für den Betrieb.

Ein erstes Brainstorming am 2026-09-11 hatte die Zerlegung in vier
Teilprojekte und „VM mit Compose, kein Kubernetes" festgehalten, brach aber
bei der LLM-Frage ab. Dieses Dokument schließt die Grundsatzfragen ab und
legt den Zuschnitt der Teilprojekte fest. Es ist bewusst eine Übersicht:
Details (Dockerfile-Aufbau, Compose-Struktur, Secrets-Fluss, Rollout-Skript)
entscheidet das jeweilige Teilprojekt in seinem eigenen Brainstorming.

## Laufzeitbedarf der Anwendung (aus dem Code abgelesen)

- `frontend` (Next.js, `standalone`-Output, BFF): braucht
  `NORMLY_API_BASE_URL`, `NORMLY_ACCOUNTS_BASE_URL`, `NORMLY_CHAT_BASE_URL`,
  `NORMLY_PUBLIC_BASE_URL`; Konfiguration wird zur Laufzeit gelesen, ein
  Image für alle Instanzen.
- `api`, `chat`, `accounts` (je FastAPI/uvicorn): eine gemeinsame
  PostgreSQL-Datenbank mit pgvector (`NORMLY_DATABASE_URL`).
- `api` und `chat` laden das Embedding-Modell `intfloat/multilingual-e5-large`
  lokal (`NORMLY_EMBEDDING_MODEL_PATH`); ohne gesetzten Pfad lädt
  `sentence-transformers` von huggingface.co nach — in Produktion verboten,
  siehe Docstring in `core/src/normly_core/pipeline/embeddings.py`.
- `chat` spricht heute ausschließlich die Ollama-REST-API
  (`chat/src/normly_chat/ollama_client.py`, `NORMLY_OLLAMA_BASE_URL`,
  Standardmodell `llama3.1:8b-instruct-q4_0`).
- `accounts` braucht SMTP (`NORMLY_SMTP_*`) für Magic Link, Verifizierung,
  Passwort-Reset, E-Mail-Wechsel; optional Google OAuth
  (`NORMLY_GOOGLE_CLIENT_ID/SECRET`, `NORMLY_GOOGLE_REDIRECT_URI` muss auf
  die Frontend-Callback-Route zeigen, siehe `frontend/README.md`).
- `core`: Alembic-Migrationen (`core/migrations`), Ingestion-CLI
  (`python -m normly_core.pipeline`) mit Docling/Torch (~6 GB
  Abhängigkeiten, `libgl1`), nur für den Datenimport, nicht im laufenden
  Betrieb.

## Grundsatzentscheidungen

Alle vom Nutzer in dieser Session bestätigt, sofern nicht anders datiert.

### E1 — Zielumgebung: eine STACKIT-VM mit Docker Compose (2026-09-11)

Bestätigt ADR-005. Kein SKE, kein Load Balancer. TLS terminiert Caddy auf
der VM per Let's Encrypt. Umzug auf SKE bleibt möglich, weil die Images
identisch sind, und ist ein eigenes späteres Projekt.

### E2 — LLM-Inferenz: STACKIT AI Model Serving, Startmodell Gemma 4 31B

Managed, GPU-gestützt, Abrechnung pro Token, Region eu01, OpenAI-kompatible
API unter `https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1`.
STACKIT betreibt ausschließlich Open-Weight-Modelle selbst; laut FAQ werden
Anfragen weder gespeichert noch zum Training verwendet, kein Datenaustausch
zwischen Kunden. Damit bleibt das Betriebsversprechen (CLAUDE.md,
REQ-INST-001) eingehalten: die Daten gehen an STACKIT, nicht an den
Modellhersteller.

Verworfen: Ollama auf der VM per CPU (Antwortzeiten von Sekunden bis
Minuten bei 8B-Modellen, für Nutzer untragbar); eigene GPU-VM mit Ollama
(laufend teuer ohne Last, kein Managed-Vorteil).

Das Produktionsmodell ist per Konfiguration wählbar; Standardwert
`google/gemma-4-31B-it` (Apache-2.0). Ollama bleibt für lokale Entwicklung
und Self-Hosting, dort ebenfalls mit einem Gemma-Modell derselben Familie,
damit Prompts sich nicht unterschiedlich verhalten.

### E3 — Modellherkunftsregel (neu, wird ADR-022 und CLAUDE.md-Satz)

Bisher ungeregelt; der heutige Llama-Standard ist selbst ein Meta-Modell.
Festgelegt:

- Nur Open-Weight-Modelle unter OSI-anerkannter Lizenz (Apache-2.0, MIT,
  …). Damit zulässig im STACKIT-Katalog vom 2026-09-23: Gemma 4 31B
  (Apache-2.0), gpt-oss 20B/120B (MIT), Qwen3-VL-235B (Apache-2.0). Nicht
  zulässig: Llama 3.3 (Llama-Lizenz), Qwen3.8 (Qwen-Lizenz).
- Betrieb ausschließlich auf STACKIT-Infrastruktur; keine Anfrage erreicht
  den Modellhersteller.
- Europäische Herkunft ist Präferenz, nicht Pflicht — im aktuellen Katalog
  gibt es kein europäisches Chat-Modell (Mistral nur als englisches
  Embedding-Modell). Wiedervorlage im ADR: sobald STACKIT ein europäisches
  Modell in passender Größe anbietet, wird der Wechsel geprüft.

Verworfen: europäische Herkunft als Pflicht (hätte nur die eigene GPU-VM
übrig gelassen, kauft ein Marketingargument ohne Datenschutzgewinn).

### E4 — DNS: gesamte Zone `normly.ai` zu STACKIT DNS

Registrar bleibt Strato (deutsches Unternehmen, sieht keinen Verkehr). Die
Nameserver werden bei Strato auf `ns1.stackit.cloud` und `ns2.stackit.zone`
umgestellt; vorher werden alle Records — inklusive der Website-Einträge —
in der STACKIT-Zone angelegt. Cloudflare (US) entfällt vollständig, damit
auch Proxy/CDN für die Website; für eine statische Website ohne
Lastspitzen ist das verschmerzbar. App-Hostname: `app.normly.ai`.

Verworfen: nur `app.normly.ai` als Subzone delegieren (Cloudflare bliebe
autoritativ für die Apex-Zone und damit in der Auflösungskette); alles bei
Cloudflare lassen (Bruch der Regel, die das Verkaufsargument ist).

### E5 — Mailversand: IONOS Business (SMTP mit Authentifizierung)

Deutsches Unternehmen, Postfach wie `noreply@normly.ai`, SPF und DKIM als
Records in der STACKIT-Zone. Verworfen: Strato-Mailpaket (Drosselung),
eigener Postfix auf der VM (Zustellbarkeit einer frischen Cloud-IP).

### E6 — Images: GHCR per GitHub Actions (ADR-021, bestätigt)

Paket öffentlich lesbar (Nutzerentscheidung vom 2026-09-14). Signierung
läuft in der GitHub-Pipeline und ist durch die ADR-021-Ausnahme gedeckt.

### E7 — Nur Produktion auf STACKIT, Staging lokal

REQ-DIST-001 verlangt getrennte Umgebungen mit eigener Datenbank. Bewusste
Vereinfachung für Phase 1: eine Produktionsumgebung auf STACKIT; das lokale
Compose-Setup aus Teilprojekt 1 übernimmt die Rolle der Staging-Umgebung.
Eine echte Staging-Umgebung (zweite VM, zweite Datenbank) kommt, sobald es
Nutzer gibt, die ein fehlerhaftes Deployment treffen würde. Wird im ADR-022
als bewusste, befristete Abweichung festgehalten.

## Zu buchende STACKIT-Produkte

Listenpreise aus der STACKIT-Preisliste (PDF, Version 18), Region EU01,
netto pro Monat bei 720 h. Preise dienen der Einordnung, verbindlich ist
das Portal.

| Produkt | Ausprägung | ca. €/Monat | Zweck |
|---|---|---|---|
| Projekt | eigenes Projekt für den Betrieb, getrennt vom Git-Projekt | 0 | Trennung Betrieb / Datenprojekt |
| Compute Engine | `g1a.4d` (4 vCPU, 16 GB, AMD), Ubuntu LTS, Variante ohne Suffix `-m` | 142 | alle Container per Compose |
| Block Storage (VM) | 80 GB, Premium-Performance 2 | ca. 20 | OS, Images, Modellgewichte |
| Public IP (IPv4) | eine | 3 | Eingang für Caddy |
| PostgreSQL Flex | `2.4` Single (2 vCPU, 4 GB), 20 GB Premium-Capacity, neueste PG-Version; Extension `vector` | 92 | eine DB für alle Dienste |
| DNS | Zone `normly.ai`, Tarif DNS-100 | 2 | siehe E4 |
| Secrets Manager | eine Instanz, AppRole-Auth (Public Preview seit 2026-08-31) | < 1 | REQ-INST-003 |
| Object Storage | ein Bucket, Standard, AES-256 at rest per Default | 0,03/GB | Datenstand-Dumps, DB-Sicherungen, Modellgewichte |
| AI Model Serving | ein Token, Modell `google/gemma-4-31B-it` | pro Token | siehe E2 |

Grundlast rund 260 €/Monat plus Tokens. LLM-Preisstufen laut Liste:
Standard 0,15 € Eingabe / 0,25 € Ausgabe je Mio. Tokens, Plus 0,45 / 0,65,
Premium 1,50 / 1,75. Die Zuordnung der Modelle zu Stufen zeigt nur das
Portal.

Begründung der VM-Größe: `api` und `chat` halten je ~3 GB RAM für das
Embedding-Modell mit Torch, dazu Frontend, Accounts, Caddy; die Ingestion
braucht bei Bedarf weitere 6–8 GB. Mit 8 GB (`g1a.2d`) wäre die Ingestion
auf der VM nicht mehr möglich.

Begründung Postgres Single: die 3-Knoten-Variante (142 €) bringt
Hochverfügbarkeit, die vor dem ersten Nutzer nichts wert ist; Flavor-Wechsel
geht laut Doku ohne Ausfall, Backups macht Flex selbst.

Nicht gebucht: SKE, Load Balancer, STACKIT Container Registry.

**Buchungszeitpunkt:** Projekt, DNS-Zone (Propagation dauert), AI-Token und
Secrets Manager sofort (< 5 €/Monat). VM, Public IP, Postgres Flex und
Object Storage erst, wenn Teilprojekt 1 abgeschlossen ist — sonst laufen
Wochen Kosten für leere Ressourcen.

## Teilprojekte

Reihenfolge strikt 1 → 4; jedes braucht das vorherige. Jedes Teilprojekt
bekommt ein eigenes Brainstorming, einen eigenen Spec, Plan und PR.

### TP1 — Containerisierung (rein lokal verifizierbar)

**Umfang:**
- Dockerfiles für `frontend`, `api`, `chat`, `accounts` und ein
  Pipeline-Image aus `core` (Migrationen und Ingestion, mit Docling).
- Ein Compose-Setup, das mit einem Aufruf startet: PostgreSQL mit pgvector,
  Ollama (lokale Entwicklung / Self-Hosting), ein Mail-Fänger, alle vier
  Dienste; Migrationen laufen vor dem App-Start; das Embedding-Modell wird
  ohne Laufzeit-Download bereitgestellt.
- Die eine Codeänderung: ein OpenAI-kompatibler LLM-Client in `chat` hinter
  derselben Schnittstelle wie `OllamaClient`, per Konfiguration wählbar;
  Wechsel des Ollama-Standardmodells von Llama auf ein Gemma-Modell (E3).
- Verankerung der Modellherkunftsregel: ADR-022, CLAUDE.md-Satz.

**Ergebnis:** Self-Hosting-Zusage aus ADR-010 / REQ-DIST-004 eingelöst;
`docs/guide/self-hosting.md` verliert den Platzhalter.

**Offen für das TP1-Brainstorming:** Modellgewichte im Image oder als
Volume aus Object Storage; Aufteilung Compose-Basis vs. Overrides für
Produktion; Ingestion-Ort (lokal mit Dump-Export vs. auf der VM); wie die
CI die Images baut, ohne die Testjobs zu verlangsamen.

### TP2 — Image-Pipeline

**Umfang:** GitHub-Actions-Job, der die fünf Images baut, signiert und in
die GHCR (`ghcr.io/normly/web-app/...`) schiebt — bei Merge auf `main` als
Vorabversion, bei Git-Tag `vX.Y.Z` als Release. `permissions: packages:
write` mit `GITHUB_TOKEN`, kein PAT. Paket beim ersten Push auf öffentlich
stellen (manuell in den GitHub-Paketeinstellungen, nicht vergessen).

**Ergebnis:** Images sind öffentlich beziehbar und signiert
(REQ-DIST-004, REQ-GIT-005).

**Offen:** Signaturverfahren (cosign keyless per GitHub-OIDC vs. eigener
Schlüssel); Tagging-Schema; ob Multi-Arch nötig ist (VM ist x86_64).

### TP3 — Zielumgebung auf STACKIT

**Umfang:**
1. DNS-Umzug nach E4 als erster Schritt (Zone anlegen, Records
   übernehmen, Nameserver bei Strato umstellen, Propagation abwarten).
2. Buchungen laut Tabelle.
3. VM-Einrichtung per cloud-init (Docker, Compose, Caddy, Firewall nur
   80/443/SSH), Compose-Overrides für Produktion.
4. Secrets-Fluss: Zugangsdaten liegen im Secrets Manager; die VM bezieht
   sie per AppRole beim Start, nicht dauerhaft in Umgebungsvariablen
   (REQ-INST-003).
5. IONOS-SMTP (E5) samt SPF-/DKIM-Records; AI-Model-Serving-Token (E2);
   Google-OAuth-Redirect-URI auf `https://app.normly.ai/api/auth/google/callback`.

**Ergebnis:** `app.normly.ai` antwortet mit einem manuell gestarteten
Stand; Datenbank läuft auf Postgres Flex; kein Secret im Repo oder auf
GitHub.

**Offen:** Terraform (STACKIT-Provider) vs. Portal plus cloud-init für die
VM; wie genau der AppRole-Secret-ID-Bootstrap auf die VM kommt; ob
Postgres-Flex-ACL auf die VM-IP beschränkt wird (ja, Standardannahme).

### TP4 — Deployment-Automatisierung

**Umfang:** Rollout neuer Images auf die VM ohne STACKIT-Zugangsdaten auf
GitHub — also pull-basiert von der VM aus (Skript, das einen Tag zieht,
Migrationen ausführt, Dienste neu startet). Rollback auf den vorherigen
Tag. Import des versionierten Datenstands aus Object Storage; Sicherung der
Datenbank nach Object Storage.

**Ergebnis:** REQ-INST-002 (automatisiert), REQ-INST-004 (Rollback),
ADR-010 (Daten getrennt vom Image) erfüllt.

**Offen:** Auslöser des Rollouts (manueller Aufruf per SSH vs. Timer, der
GHCR abfragt); Dump-Format und Versionierung des Datenstands;
Aufbewahrungsfrist der Sicherungen (offener Punkt aus dem ADR-Register).

## Dokumentation, die mitläuft

- **ADR-022 „Betriebsumgebung Phase 1"**: E1–E7 mit Begründung und
  Verworfenem; Wiedervorlage europäisches Modell; befristete Abweichung von
  REQ-DIST-001. Geschrieben in TP1, weil die Modellherkunftsregel dort
  Code berührt.
- **CLAUDE.md**: ein Satz zur Modellherkunft unter „Nicht verhandelbar".
- **SRS**: REQ-INST-003 (Secrets-Fluss per AppRole), REQ-DIST-001
  (Staging-Abweichung mit Verweis auf ADR-022), Kapitel 3.5 Fließtext
  (Modellherkunft), REQ-GIT-005 (Abnahmekriterium nennt noch die STACKIT
  Container Registry, seit ADR-021 ist es die GHCR; in TP2 korrigieren).
- **`docs/guide/self-hosting.md`**: in TP1 mit dem tatsächlichen
  Compose-Weg füllen.
- **ADR-Register „Offene Punkte"**: „Öffentlicher Lesezugriff auf STACKIT
  Container Registry" ist durch ADR-021 gegenstandslos und wird
  gestrichen.

## Nicht-Ziele

- Kubernetes/SKE, Load Balancer, Multi-Region.
- Echte Staging-Umgebung auf STACKIT (siehe E7).
- Native App, lizenzierte Volltexte, kommerzielle Schicht.
- Wechsel des Embedding-Modells auf STACKIT-Model-Serving-Embeddings
  (würde Neu-Einbettung des gesamten Bestands bedeuten; `e5-mistral-7b`
  ist englisch-fokussiert, `Qwen3-VL-Embedding-8B` hat andere
  Dimensionen). Bleibt lokal in `api`/`chat`.

## Im Portal noch zu prüfen (kann von hier nicht geklärt werden)

- Preisstufe von Gemma 4 31B bei AI Model Serving und Ratenlimits je Modell.
- Auftragsverarbeitungsvertrag / AGB für AI Model Serving (Protokollierung,
  Aufbewahrung).
- Bedeutung des Flavor-Suffix `-m` (doppelter Preis, in der Doku nicht
  erklärt) — Variante ohne Suffix nehmen.
- Ob Postgres Flex bei Single → Replica ohne Neuanlage wechseln kann.

## Quellen

- STACKIT AI Model Serving: Katalog
  (`docs.stackit.cloud/de/products/data-and-ai/ai-model-serving/basics/available-shared-models/`),
  FAQ, „Use the models".
- STACKIT Machine Types EU01, PostgreSQL Flex Flavors und Supported
  Extensions, DNS FAQ, Secrets Manager FAQ, Object Storage Core Features.
- STACKIT-Preisliste PDF Version 18 (`stackit.com/en/asset/download/37788/file/STACKIT_price_list.pdf?version=18`).
