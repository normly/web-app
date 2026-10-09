# Lebenszyklus der Nutzerdaten (Teil B) — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anonyme Chats werden nicht mehr gespeichert, Fristen für Sitzungen/Tokens/Konten/Benachrichtigungen werden automatisch durchgesetzt, Verläufe lassen sich löschen, der Export ist vollständig, und Löschungen überstehen eine Wiederherstellung (Löschprotokoll, Wiederholung im Rollback).

**Architecture:** Neues Modul `normly_core/retention.py` (Fristen als Konstanten), neue Repository-Methoden und das Pipeline-Kommando `cleanup-user-data`; Migration 0035 (`deletion_log`); Änderungen im Chat-Dienst und im Frontend; Export im Accounts-Dienst vervollständigt; Kern-Kommandos `export-deletions`/`replay-deletions` und Erweiterung von `normly-deploy rollback`; Timer-Skript `scripts/normly-cleanup`. Spec: `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 Core/ORM, Alembic, pytest + testcontainers; Next.js/React (Vitest); Bash (Fake-Harness in `scripts/tests`), systemd.

**Voraussetzung:** PR #19 (Tombstone-Sicherung, ADR-026, Rollback-Vorlauf) ist in `main` gemergt; dieser Plan wird auf dem daraus entstehenden `main` umgesetzt.

## Global Constraints

- Fristen (verbindlich, benannte Konstanten in `normly_core/retention.py`, eine Stelle): `ACCOUNT_SESSION_GRACE = 7 Tage` nach `expires_at`; `ACCOUNT_TOKEN_GRACE = 24 Stunden` nach `expires_at` **oder** `used_at`; `UNVERIFIED_ACCOUNT_MAX_AGE = 30 Tage` nach `created_at` (nur `email_verified_at IS NULL`); `READ_NOTIFICATION_MAX_AGE = 60 Tage` (bisheriger Wert, `read_at` gesetzt); `UNREAD_NOTIFICATION_MAX_AGE = 365 Tage`; `DELETION_LOG_MAX_AGE = 90 Tage`. Anonyme Chats: jede `chat_session` ohne `account_id` wird gelöscht (Altbestand).
- Anonymer Chat: ohne gültige Konto-Identität **kein** Datenbankzugriff schreibender Art (keine Session, keine Nachricht, kein Zitat); Antwort ohne `session_token`; ein mitgeschicktes Chat-Token ohne gültige Konto-Identität wird ignoriert; mit gültigem Konto unverändertes Verhalten.
- Löschprotokoll: Tabelle `deletion_log(kind, entity_id, deleted_at)`, `kind ∈ {"account","chat_session"}`, Primärschlüssel `(kind, entity_id)`, **keine** Personendaten, geschrieben in derselben Transaktion wie jede Löschung (Kontolöschung inkl. Aufräumen nicht bestätigter Konten, Verlauf löschen); `ON CONFLICT DO NOTHING`; Teil von `USER_TABLES` (nach `notified_retirement`), erfasst vom Fail-closed-FK-Test; kein Fremdschlüssel (die Kennungen verweisen auf bereits gelöschte Zeilen).
- Rechteklassifikation bleibt das einzige Tor; kein SQL in `normly_core/exchange/`, `graph/domain.py` und in den Routern/Diensten (nur Repository-Schicht, ADR-006); neue Protocol-Methoden ohne `get_`/`list_`-Präfix, es sei denn sie nehmen `jurisdiction` (Guard in `core/tests/graph/test_architecture.py`; Ausnahmen mit Begründung nur wenn unvermeidbar).
- Idempotenz: jeder Aufräum- und Replay-Schritt ist wiederholbar ohne abweichendes Ergebnis. Aufräumbefehl und Replay geben nur Zähler/Kennungszahlen aus, nie Inhalte.
- Export: kein Passwort-Hash, keine Token (weder Konto-Sitzungs-, Chat-Sitzungs- noch Einmal-Token), keine Buchführungstabellen.
- Sprache: Code/Commits Englisch; ADRs/Spec/Plan/SRS/CLAUDE.md Deutsch; `docs/guide/*` Englisch (ADR-020). Lizenzheader AGPL-3.0-or-later in neuen Dateien. Keine Secrets/echten Namen in Tests.
- Commits: Conventional Commits, `git commit -s` (Signed-off-by des Menschen), Trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **nie** `git config`; kein Push/PR ohne Rückfrage. ShellCheck mit `koalaman/shellcheck:v0.9.0` (CI-Version). Der Rechner ist speicherbegrenzt: Testbefehle **einzeln nacheinander**, die komplette Core-Suite höchstens einmal je Task am Ende; Skript-Tests (`.venv/bin/pytest scripts/tests`) und Core-Tests nie in einem Lauf mischen.

## Dateiübersicht

| Datei | Änderung |
|---|---|
| `core/src/normly_core/retention.py` | neu: Fristen-Konstanten |
| `core/migrations/versions/0035_create_deletion_log.py`, `graph/postgres/orm.py`, `graph/domain.py`, `graph/postgres/repositories.py` | `deletion_log`, Protokoll-Schreiben, Aufräum- und Lösch-Methoden |
| `core/src/normly_core/exchange/tables.py` | `deletion_log` in `USER_TABLES` |
| `core/src/normly_core/pipeline/cli.py` | `cleanup-user-data` |
| `chat/src/normly_chat/routers/chat.py`, `routers/sessions.py`, `session_resolution.py`, `schemas.py` | anonym ohne Speicherung, DELETE-Endpunkte |
| `frontend/src/app/api/chat/**`, `components/chat/**`, `lib/session-cookies.ts` | kein Chat-Cookie für anonyme Chats, Löschknöpfe, BFF-Routen |
| `accounts/src/normly_accounts/routers/account_management.py`, `schemas.py` | Export vervollständigt |
| `core/src/normly_core/exchange/deletions.py`, `exchange/__main__.py` | `export-deletions`, `replay-deletions` |
| `scripts/normly-deploy`, `scripts/normly-cleanup`, `deploy/systemd/normly-cleanup.{service,timer}`, `docker/python.Dockerfile` | Rollback-Erweiterung, Timer, Image-Dateien |
| `docs/adr/README.md`, `docs/guide/operations.md`, `docs/guide/self-hosting.md`, Specs | ADR-027, Betrieb |

---

### Task 1: Kern — Fristen, Löschprotokoll, Aufräumbefehl

**Files:**
- Create: `core/src/normly_core/retention.py`, `core/migrations/versions/0035_create_deletion_log.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`DeletionLogORM`), `graph/domain.py` (Protocols), `graph/postgres/repositories.py`, `core/src/normly_core/exchange/tables.py`, `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/retention/test_cleanup_user_data.py` (neu), `core/tests/graph/test_deletion_log.py` (neu), ergänzende Tests in vorhandenen Dateien (`test_account_sessions_and_deletion.py`, `core/tests/exchange/test_tables.py`, `core/tests/pipeline/test_cli.py`)

**Interfaces:**
- Produces:
  - `retention` Konstanten (siehe Global Constraints) als `datetime.timedelta`.
  - `DeletionLogRepository` (Protocol + `PostgresDeletionLogRepository`): `record(*, kind: str, entity_id: uuid.UUID, deleted_at: datetime) -> None` (ON CONFLICT DO NOTHING), `entries_since(since: datetime) -> list[tuple[str, uuid.UUID, datetime]]` (**Achtung** `entries_since` beginnt nicht mit `get_`/`list_`), `delete_older_than(cutoff: datetime) -> int`.
  - Repository-Methoden (Namen frei wählbar, aber ohne `get_`/`list_`-Präfix; je mit `cutoff`/`now`-Parameter, Rückgabe: Anzahl gelöschter Zeilen): Sitzungen `delete_sessions_expired_before`, Tokens `delete_tokens_done_before`, nicht bestätigte Konten `delete_unverified_accounts_created_before` (nutzt dieselbe Kaskade wie `delete_account` und schreibt je Konto einen Protokolleintrag `account`), Benachrichtigungen `delete_unread_before` (zusätzlich zu `delete_read_before`), anonyme Chats `delete_anonymous_chat_sessions` (Kaskade Zitate → Nachrichten → Sitzung; **kein** Protokolleintrag, weil anonyme Daten nie zu einer Wiederherstellung gehören müssen? — doch: sie stehen in alten Sicherungen und tauchen nach einem Rollback wieder auf; schreibe also je gelöschter anonymer Sitzung einen Eintrag `chat_session`), Chat-Verlauf löschen `delete_chat_session(session_id, account_id) -> bool` (nur eigener; protokolliert) und `delete_chat_sessions_for_account(account_id) -> int` (protokolliert je Sitzung).
  - `delete_account(account_id)` schreibt zusätzlich `deletion_log(kind="account", entity_id=account_id)` in derselben Transaktion; sie löscht die Chats des Kontos wie bisher (die Chat-Sitzungen des Kontos erhalten **keinen** eigenen Eintrag, der `account`-Eintrag deckt sie ab).
  - CLI `python -m normly_core.pipeline cleanup-user-data`: führt alle Fristen mit `datetime.now(timezone.utc)` aus (inkl. `delete_read_before` mit `READ_NOTIFICATION_MAX_AGE`), committet am Ende, druckt eine Zeile `sessions=<n> tokens=<n> unverified_accounts=<n> notifications_read=<n> notifications_unread=<n> anonymous_chats=<n> deletion_log=<n>`; `cleanup-notifications` bleibt unverändert.
- Verhalten: Reihenfolge im Befehl: erst Löschungen, dann `deletion_log` bereinigen. Nicht bestätigte Konten: nur `email_verified_at IS NULL AND created_at < now - 30d`. Tokens: `expires_at < now - 24h OR used_at < now - 24h`. Sitzungen: `expires_at < now - 7d`. Benachrichtigungen ungelesen: `read_at IS NULL AND created_at < now - 365d`. Abstände strikt (`<`).

- [ ] **Step 1: Failing tests schreiben** (Fixtures wie in `core/tests/graph/test_account_sessions_and_deletion.py` und `core/tests/notifications/`; echte Signaturen der Repositories vor dem Schreiben mit grep prüfen und die Tests an die Parameter anpassen, nicht ihre Aussage): je Frist ein Test mit Zeilen knapp **vor** und knapp **nach** der Grenze (nur die alten verschwinden), Idempotenz (zweiter Lauf löscht 0), bestätigte Konten und Konten mit Bestätigung unberührt, Kaskade beim Löschen eines nicht bestätigten Kontos (Chats, Tokens, Sitzungen, Beobachtungen, Benachrichtigungen, Bookkeeping, Avatar) und Protokolleintrag `account`, Altbestand anonymer Chats (Sitzung ohne `account_id` samt Nachrichten und Zitaten gelöscht, Konto-Sitzungen bleiben, Protokolleintrag `chat_session`), `delete_chat_session` (eigener → True; fremder/unbekannter → False und nichts gelöscht; protokolliert), `delete_chat_sessions_for_account`, `delete_account` schreibt `deletion_log`, `PostgresDeletionLogRepository` (record idempotent, `entries_since` Zeitgrenze, `delete_older_than`), CLI-Ausgabezeile und Commit; `test_tables.py`: `deletion_log` in `USER_TABLES` und der Fail-closed-FK-Test bleibt grün; `test_architecture.py` grün; ORM↔Migration-Konsistenz und Determinismus grün.
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/retention tests/graph/test_deletion_log.py -q` — Expected: FAIL (fehlende Module/Methoden).
- [ ] **Step 3: Implementierung** wie oben. Migration `0035` (Stil und Revisions-IDs der Nachbarn, `revision = "0035"`, `down_revision = "0034"`): Tabelle `deletion_log` mit `kind` (String, CHECK `kind IN ('account','chat_session')`), `entity_id` (UUID), `deleted_at` (timestamptz, NOT NULL), Primärschlüssel `(kind, entity_id)`, Index auf `deleted_at`; `downgrade` löscht die Tabelle.
- [ ] **Step 4:** fokussierte Tests (`tests/retention tests/graph tests/exchange tests/pipeline -q`, einzeln), dann die komplette Core-Suite einmal (`cd core && ../.venv/bin/pytest tests -q`).
- [ ] **Step 5: Commit** `feat(retention): deletion log, retention constants and cleanup-user-data` (mit `-s` und Trailer).

### Task 2: Chat — anonym ohne Speicherung, Verläufe löschen

**Files:**
- Modify: `chat/src/normly_chat/routers/chat.py`, `routers/sessions.py`, `session_resolution.py`, `schemas.py`; `frontend/src/app/api/chat/route.ts`, `frontend/src/app/api/chat/sessions/route.ts` (+ neue Routen `frontend/src/app/api/chat/sessions/[id]/route.ts`), `frontend/src/lib/session-cookies.ts`, `frontend/src/components/chat/chat-history-sidebar.tsx`, `frontend/src/lib/i18n/{de,en}.json`
- Test: `chat/tests/…` (vorhandene Chat-Tests anpassen/ergänzen), `frontend/tests/unit/…` (Sidebar, Cookie-Logik, BFF-Routen)

**Interfaces:**
- Consumes: `delete_chat_session`, `delete_chat_sessions_for_account` aus Task 1.
- Produces: `POST /v1/chat` mit optionalem `session_token` in der Antwort (`None` für anonym); `DELETE /v1/chat/sessions/{session_id}` (Bearer-Konto-Token erforderlich; Antwort 204 bei Erfolg, 404 bei fremder/unbekannter ID, 401 ohne gültiges Konto); `DELETE /v1/chat/sessions` (alle eigenen; 200 mit `{"deleted": <n>}`); Frontend: `DELETE /api/chat/sessions/[id]` und `DELETE /api/chat/sessions`; Löschknopf je Verlauf mit Bestätigungsdialog und „Alle Verläufe löschen“ in der Seitenleiste; i18n-Schlüssel in de/en.

- [ ] **Step 1: Failing tests** — Chat-Dienst: anonyme Anfrage (kein `Authorization`) → Antwort 200 mit Antworttext, `session_token` ist `None`, in der Datenbank **keine** neuen Zeilen in `chat_session`, `chat_message`, `chat_message_citation`; anonyme Anfrage mit mitgeschicktem `session_token` einer Konto-Sitzung → kein Anhängen, keine Schreibzugriffe; Anfrage mit ungültigem Konto-Token verhält sich wie anonym; Anfrage mit gültigem Konto legt Session/Nachrichten/Zitate an wie bisher (bestehende Tests bleiben grün); `resolve_session`: kein `link_account` mehr für anonyme Sitzungen (der Test, der die Verknüpfung beim Anmelden prüfte, wird entfernt/ersetzt, mit Begründung im Bericht); DELETE-Endpunkte (eigener Verlauf gelöscht inkl. Nachrichten/Zitate und Protokolleintrag, fremder → 404 ohne Änderung, ohne Token → 401, „alle“ löscht nur eigene). Frontend (Vitest): `api/chat/route.ts` setzt bei Antwort ohne `session_token` **kein** Chat-Cookie und löscht ein vorhandenes (`maxAge: 0`), Sitzungs-Cookie-Verhalten für Konten unverändert; Seitenleiste: Löschknopf ruft die BFF-Route nach Bestätigung auf und entfernt den Eintrag; „Alle löschen“; Fehlerfall (Antwort nicht ok) lässt die Liste unverändert.
- [ ] **Step 2:** fokussiert ausführen (`cd chat && ../.venv/bin/pytest -q`; `cd frontend && npx vitest run tests/unit/<datei>` — falls `frontend/node_modules` fehlt zuerst `cd frontend && npm ci`; Befehle einzeln) — Expected: FAIL.
- [ ] **Step 3: Implementierung.** `chat.py`: Identität zuerst auflösen; ohne Identität weder `resolve_session` noch `create_message`/`add_citation` aufrufen, `ChatResponse.session_token = None`; `session_resolution.py` bleibt für Konten (ohne `link_account`-Zweig für `account_id is None`; wenn `session.account_id` nicht zur Identität passt → neue Sitzung wie bisher). `schemas.py`: `session_token: str | None`. Frontend: Cookie nur bei String-Token setzen, sonst löschen; `CHAT_COOKIE_MAX_AGE_SECONDS`-Kommentar anpassen (nur noch für Konten).
- [ ] **Step 4:** komplette Suiten einmal: `cd chat && ../.venv/bin/pytest -q`; `cd frontend && npx vitest run` und `npx tsc --noEmit`.
- [ ] **Step 5: Commit(s)** `feat(chat): do not store anonymous chats; let users delete their chat history` (mit `-s` und Trailer).

### Task 3: Export vervollständigen

**Files:**
- Modify: `accounts/src/normly_accounts/routers/account_management.py`, `accounts/src/normly_accounts/schemas.py`, Repository-Methoden in `core/src/normly_core/graph/postgres/repositories.py`/`graph/domain.py` (Lesemethoden für lesbare Kennungen und Zitate; Namen ohne `get_`/`list_`-Präfix, oder mit `jurisdiction` falls nötig und dann bewusst in `JURISDICTION_EXEMPT_READS` mit Begründung)
- Test: `accounts/tests/test_account_export.py` (bestehende Export-Tests anpassen und ergänzen)

**Interfaces:**
- Produces (Antwortform, verbindlich): `ExportChatSession`: `id` (UUID) statt `session_token`, `jurisdiction`, `language`, `created_at`, `messages`; `ExportChatMessage`: `role`, `content`, `answer_type: str | None`, `created_at`, `citations: list[ExportCitation]`; `ExportCitation`: `document: ExportDocumentRef`, `segment_id: UUID | None`; `ExportDocumentRef`: `id`, `origin_issuer`, `origin_number`, `edition`, `part`; `ExportWatchlistEntry`: `work_id`, `created_at`, `documents: list[ExportDocumentRef]` (alle Dokumente des Works inklusive zurückgezogener); `ExportNotification` unverändert. Kein `session_token`, keine Tokens, kein Hash.
- Die Lesemethoden sind **ungeprüft** (ohne Rechtetor), weil sie nur Kennungen (Herausgeber, Nummer, Ausgabe, Teil) der eigenen Daten liefern, nie Inhalt; im Docstring begründen.

- [ ] **Step 1: Failing tests** — Export enthält je Chat-Nachricht `answer_type` und Zitate mit lesbarer Dokumentreferenz (auch für ein zurückgezogenes Dokument/Tombstone: Kennung bleibt lesbar, `segment_id` ist `None` nach einer Rücknahme), die Beobachtungsliste nennt Dokumentreferenzen des Works, der Chat-Sitzungs-Token kommt nicht vor (Suche im serialisierten JSON nach dem Token-Wert), Fremdzugriff und fehlende Anmeldung (401) wie bisher, keine Passwort-Hash-/Token-Felder (Suche nach `password`, `token` in den Schlüsseln der Antwort), Export einer Person enthält keine Daten einer anderen.
- [ ] **Step 2:** `cd accounts && ../.venv/bin/pytest tests/test_account_export.py -q` — Expected: FAIL.
- [ ] **Step 3: Implementierung** wie oben. Das Frontend (`export-section.tsx`) bleibt unverändert (es serialisiert die Antwort 1:1); prüfen und im Bericht bestätigen.
- [ ] **Step 4:** `cd accounts && ../.venv/bin/pytest -q` (komplett), `cd core && ../.venv/bin/pytest tests/graph -q`.
- [ ] **Step 5: Commit** `feat(accounts): complete the personal data export` (mit `-s` und Trailer).

### Task 4: Wiederholung von Löschungen im Rollback, Aufräum-Timer

**Files:**
- Create: `core/src/normly_core/exchange/deletions.py`, `scripts/normly-cleanup`, `deploy/systemd/normly-cleanup.service`, `deploy/systemd/normly-cleanup.timer`, `core/tests/exchange/test_deletions.py`, `scripts/tests/test_cleanup.py`
- Modify: `core/src/normly_core/exchange/__main__.py` (`export-deletions`, `replay-deletions`), `scripts/normly-deploy`, `docker/python.Dockerfile` (COPY von `scripts/normly-cleanup`), `scripts/tests/conftest.py` (nur additiv), Rollback-Tests in `scripts/tests/`

**Interfaces:**
- Consumes: `PostgresDeletionLogRepository.entries_since`, `PostgresAccountRepository.delete_account`, `delete_chat_session` (Task 1).
- Produces:
  - `deletions.build_document(entries, *, created_at) -> str` / `parse_document(text) -> list[(kind, UUID)]`; JSON: `{"format": 1, "created_at": "<ISO UTC>", "entries": [{"kind": "account"|"chat_session", "entity_id": "<uuid>", "deleted_at": "<ISO UTC>"}, ...]}` sortiert nach `deleted_at`, `kind`, `entity_id`; `parse_document` wirft `ValueError` bei falscher Version/Struktur/unbekannter `kind`.
  - CLI: `python -m normly_core.exchange export-deletions --since <ISO-8601 mit Zeitzone>` → JSON auf stdout (nur das Dokument); `python -m normly_core.exchange replay-deletions` liest JSON von stdin, wendet jede Löschung an (Konto: `delete_account` falls vorhanden; Chat: `delete_chat_session` ohne Besitzerprüfung über eine interne Methode **nur für den Replay** `delete_chat_session_by_id`), schreibt dabei das Protokoll, committet, druckt `replayed deletions: <n> applied, <m> already gone`; ungültige Eingabe → Exit 1, nichts geändert; `replay-deletions --check` benötigt **keine** Datenbank, exit 0 (zeigt, dass das Image den Befehl kennt).
  - `scripts/normly-cleanup`: wie `normly-backup` (lädt `.env` über `normly-env.sh`, `NORMLY_COMPOSE` Standard `docker compose -f $NORMLY_DIR/current/compose.yaml --project-directory $NORMLY_DIR/current`) und ruft `$COMPOSE run --rm --no-deps -T pipeline cleanup-user-data` auf; Exit-Code des Befehls durchreichen; Timer täglich 04:00 UTC mit `Persistent=true`, Service `Type=oneshot`.
  - `normly-deploy rollback`: Im **Vorlauf** (nach dem Tombstone-Vorlauf, vor Banner und Bestätigung) mit dem **aktuellen** Release `export-deletions --since <Sicherungszeitpunkt>` ausführen (Zeitpunkt aus dem Basisnamen `YYYYMMDDTHHMMSSZ-...` in ISO-8601 UTC umrechnen; Fehler oder ungültiges Dokument → `die "... nothing was changed"`), Ergebnis in `$WORK/deletions.json`; mit dem **vorherigen** Release `replay-deletions --check` ausführen: unterstützt → nach `pg_restore` (und nach `import-tombstones`) `replay-deletions` mit `< "$WORK/deletions.json"` ausführen; nicht unterstützt und Liste nicht leer → Banner-Zeile mit Anzahl und Kennungen („previous release cannot replay deletions; re-delete these by hand after the rollback: …"), Rollback läuft nach Bestätigung weiter; Liste leer → nichts zu tun. Fehler beim Replay nach `DESTRUCTIVE=1` zählt wie jeder andere Fehler (Wiederherstellungshinweis, Lock frei, Zustand unverändert).

- [ ] **Step 1: Failing tests** — Kern: Export (Zeitgrenze: Eintrag genau am Zeitpunkt wird nicht ausgegeben, danach schon; Dokument gültig; nur stdout), Replay (Konto vorhanden → gelöscht und protokolliert; Konto fehlt → „already gone"; Chat-Sitzung; Idempotenz; ungültiges Dokument → Exit 1 ohne Änderung; `--check` ohne Datenbank), End-to-End-Rollback-Simulation (Szenario: Konto A mit Chat und Beobachtung wird nach dem Sicherungszeitpunkt gelöscht → Protokoll exportieren, Nutzerdaten auf den Stand der Sicherung zurücksetzen [Zeilen aus einer vor der Löschung gesicherten Kopie wieder einfügen], Replay → Konto A und seine Chats sind wieder gelöscht, das Protokoll enthält den Eintrag). Skripte (Fake-Harness): Reihenfolge im Rollback (`export-deletions` vor Banner/Prompt/`down`/DROP; Replay nach `pg_restore`, nach `import-tombstones`), Fehler beim Export bricht vor jeder Änderung ab, vorheriges Image ohne Befehl (`replay-deletions --check` schlägt fehl): Banner nennt die Kennungen und der Rollback läuft nach Bestätigung weiter, Liste leer: kein Replay-Aufruf, Replay-Fehler nach DROP: Wiederherstellungshinweis; `normly-cleanup`: Aufruf des Pipeline-Kommandos, Exit-Code-Weitergabe. Bestehende Tests grün (Harness nur additiv).
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_deletions.py -q`, danach im Repo-Root `.venv/bin/pytest scripts/tests -q` — Expected: FAIL.
- [ ] **Step 3: Implementierung** wie oben; ShellCheck `docker run --rm -v "$PWD":/mnt -w /mnt koalaman/shellcheck:v0.9.0 scripts/normly-deploy scripts/normly-backup scripts/normly-env.sh scripts/normly-cleanup` sauber; Dockerfile-COPY ergänzen und `docker buildx build --check --target pipeline -f docker/python.Dockerfile .` ohne Warnungen.
- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange tests/graph -q`; `.venv/bin/pytest scripts/tests -q`.
- [ ] **Step 5: Commit** `feat(rollback): replay deletions after a restore; add the cleanup timer` (mit `-s` und Trailer).

### Task 5: Dokumentation

**Files:** `docs/adr/README.md` (ADR-027, Register), `docs/guide/operations.md`, `docs/guide/self-hosting.md` (Aufräumbefehl), `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md` (Status), `docs/srs/…` (Verweise nur, wenn ein passender REQ existiert)

- [ ] **Step 1: ADR-027** „Lebenszyklus der Nutzerdaten“ (Deutsch, Format der Nachbar-ADRs): Kontext (Bestandsaufnahme), Entscheidung (Grundsatz, Datenverzeichnis als Tabelle je Tabelle mit Zweck, Personenbezug, Frist, Löschweg; anonymer Chat ohne Speicherung; Chats mit Konto bis zur Löschung; Fristen; Export; Löschprotokoll und Wiederholung), Begründung, Verworfen (Frist auch für Konto-Chats; anonyme Sitzungen mit Kurzfrist-Speicherung; kryptographisches Löschen je Konto in Sicherungen; asynchroner Export), Folgen/Offen (Nachwirkung in Sicherungen: Flex 30 Tage, eigene Sicherungen rund zwei Monate, Pre-Rollout bis zu drei Releases; Löschprotokoll 90 Tage; fachliche Prüfung der Fristen; Vorgängerrelease ohne Replay-Befehl braucht manuelles Nachlöschen; Verknüpfung „anonym → Konto beim Anmelden" entfällt bewusst; Tombstone-Aufbewahrung aus ADR-026 bleibt offen; Datenschutzerklärung außerhalb).
- [ ] **Step 2: `docs/guide/operations.md`** (Englisch): Aufräumen (Timer installieren/aktivieren, Fristentabelle, `cleanup-user-data` manuell), Rollback (Löschungen werden gelesen/erneut angewendet, Verhalten bei altem Image), Restore-Test (zusätzliche Schritte `export-deletions`/`replay-deletions`), Notfall-Wiederherstellung aus Flex (Anleitung: vor der Wiederherstellung das Löschprotokoll sichern/exportieren, danach `replay-deletions`), Hinweis auf maximale Nachwirkung in Sicherungen. `self-hosting.md`: Aufräumbefehl und Anonymverhalten kurz.
- [ ] **Step 3:** Spec-Status auf „umgesetzt" setzen, ADR-Register-Zeilen (offene Punkte) aktualisieren.
- [ ] **Step 4:** Docs-Build wie in CI (docker `python:3.12`, `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, `zensical build`, Zeile `3 issues found`; mit `--user "$(id -u):$(id -g)"`, beschreibbarem HOME und venv unter `/tmp`; danach `site/` und `.cache/` entfernen).
- [ ] **Step 5: Commit** `docs: ADR-027 user data lifecycle, operations guide` (mit `-s` und Trailer).

## Selbstprüfung gegen die Spec

| Spec-Abschnitt | Task |
|---|---|
| 1 Anonymer Chat ohne Speicherung | Task 2 (Chat, Frontend), Task 1 (Altbestand im Aufräumbefehl) |
| 2 Aufräumbefehl und Timer | Task 1 (Befehl), Task 4 (Skript, Timer) |
| 3 Verläufe löschen | Task 1 (Repository), Task 2 (Endpunkte, Oberfläche) |
| 4 Export vervollständigen | Task 3 |
| 5 Löschprotokoll | Task 1 (Tabelle, Schreiben, Bereinigung), Task 4 (Export/Replay) |
| 6 Rollback | Task 4 |
| ADR-027, Betriebsguide | Task 5 |

**Risiken:** Der Replay muss gegen das Schema des **vorherigen** Release laufen (deshalb Prüfung des Befehls im vorherigen Image); die Löschfunktionen des Kerns kennen ggf. Tabellen, die im älteren Schema fehlen — der Replay läuft im vorherigen Image mit dessen Code und Schema; Frontend-Tests brauchen `npm ci` (Speicher); echte `docker compose run -T` mit stdin/stdout bleibt Teil der Live-Abnahme.
