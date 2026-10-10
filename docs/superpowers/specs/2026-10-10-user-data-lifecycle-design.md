# Design: Lebenszyklus der Nutzerdaten (Teil B)

Stand: 2026-10-10 · Status: Entwurf, wartet auf Review. Folgt auf
`docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md` (Teil A:
Nutzerverweise beim Wissensbestand-Import). Setzt PR #19 (Tombstone-Sicherung
im Rollback) voraus.

## Ziel und Anlass

Personenbezogene Daten sollen nur gespeichert werden, wenn ein Konto sie braucht,
und nur so lange, wie der Zweck besteht (Datensparsamkeit, Speicherbegrenzung);
Betroffene sollen ihre Daten einsehen und löschen können; eine Löschung soll
auch eine Wiederherstellung aus Sicherungen überstehen. Die Bestandsaufnahme
(2026-10-10) zeigte Lücken:

- Anonyme Chats werden gespeichert (`chat_session`/`chat_message`, Cookie
  `normly_session` mit 90 Tagen Laufzeit) und nie gelöscht, obwohl der Server
  sie zum Antworten nicht braucht (jede Frage wird einzeln beantwortet).
- `account_session` und `account_token` werden nie gelöscht (die Ablaufzeit wird
  nur geprüft); verlassene Registrierungen bleiben ewig.
- Ungelesene Benachrichtigungen werden nie gelöscht.
- Es gibt keinen Weg, einzelne Chat-Verläufe zu löschen.
- Der Rollback stellt Nutzerdaten vom Sicherungszeitpunkt wieder her: Zwischenzeitlich
  gelöschte Konten und Verläufe tauchten wieder auf.
- Der bestehende Export (`GET /v1/accounts/export`) ist unvollständig: Die
  Beobachtungsliste nennt nur `work_id`, Zitate fehlen, und der Chat-Sitzungs-Token
  (ein Geheimnis) steht im Export.

Dieser Entwurf ist keine Rechtsberatung. Die Fristen sind Entscheidungen des
Projekts und sollten von einer Fachperson für Datenschutz geprüft werden.

## Entscheidungen (vom Nutzer gewählt)

| Daten | Regel |
|---|---|
| Anonyme Chats | werden serverseitig **nicht gespeichert** |
| Chats mit Konto | bis zur Löschung durch die Person (pro Verlauf oder alle) oder durch die Kontolöschung; keine automatische Frist |
| `account_session` | 7 Tage nach Ablauf gelöscht |
| `account_token` | 24 Stunden nach Ablauf oder Verwendung gelöscht |
| verlassene Registrierungen (`email_verified_at` leer, keine Google-Verknüpfung, keine Konto-Sitzung, auch keine abgelaufene) | 30 Tage nach Anlage samt Tokens und Chats gelöscht; Konten in Benutzung (Google, Passwort-Anmeldung) nie, auch ohne Bestätigung |
| `notification` gelesen / ungelesen | 60 Tage / 12 Monate nach Anlage |
| `notified_edge`, `notified_retirement`, `rights_notification_baseline` | bis zur Kontolöschung (verhindern Doppelmeldungen) |
| `oauth_state`, `rate_limit_bucket` | unverändert (1 Stunde / 10 Minuten) |
| Avatar | mit dem Konto oder beim Entfernen gelöscht |
| Auskunft | bestehender JSON-Export, vervollständigt (siehe unten) |
| Sicherungen | Nachwirkung begrenzt (Flex 30 Tage, eigene Sicherungen rund zwei Monate); ein Löschprotokoll wendet Löschungen nach einer Wiederherstellung erneut an |

## Umsetzung

**1. Anonymer Chat ohne Speicherung.** `POST /v1/chat` ohne gültiges Konto-Token
schreibt nichts in die Datenbank, antwortet ohne `session_token` (Feld wird
optional), das Frontend setzt kein Chat-Cookie mehr und entfernt ein vorhandenes;
die Unterhaltung lebt nur im Browser-Tab. Mit gültigem Konto bleibt das Verhalten
wie bisher. Die Verknüpfung „anonyme Sitzung beim Anmelden ans Konto hängen“
(`resolve_session`) entfällt; ein Chat-Token ohne gültiges Konto wird ignoriert
(heute würde er an eine Konto-Sitzung anhängen, auch bei abgemeldeter Person).
Vorhandene anonyme Verläufe löscht der Aufräumbefehl: jede `chat_session` ohne
`account_id`.

**2. Aufräumbefehl `cleanup-user-data`.** Neues Pipeline-Kommando
(`python -m normly_core.pipeline cleanup-user-data`), das die Fristen der Tabelle
über Repository-Methoden durchsetzt (inklusive der bisherigen 60 Tage für gelesene
Benachrichtigungen), idempotent ist und nur Zähler ausgibt. Fristen stehen als
benannte Konstanten an einer Stelle (`normly_core/retention.py`). Ein kleines Skript
`scripts/normly-cleanup` und ein systemd-Timer (täglich) führen ihn auf der VM aus,
wie bei der Sicherung. `cleanup-notifications` bleibt als Befehl bestehen.

**3. Verläufe löschen.** `DELETE /v1/chat/sessions/{id}` (nur eigene; fremde oder
unbekannte ID gibt 404) und `DELETE /v1/chat/sessions` (alle eigenen); Löschknopf
und „Alle löschen“ in der Seitenleiste mit Bestätigung; BFF-Routen im Frontend.

**4. Export vervollständigen.** `GET /v1/accounts/export` bekommt: lesbare
Kennungen zur Beobachtungsliste (Herausgeber, Nummer, Ausgabe, auch bei
zurückgezogenen Dokumenten aus dem Tombstone), Zitate je Chat-Nachricht (Dokument
lesbar bezeichnet) und `answer_type`; der `session_token` der Chat-Sitzungen
entfällt (Geheimnis, kein Datum der Person) und wird durch die Sitzungs-ID ersetzt.
Passwort-Hash, Tokens und Buchführung bleiben ausgeschlossen.

**5. Löschprotokoll.** Tabelle `deletion_log` (Art `account` oder `chat_session`,
Kennung, Zeitpunkt; **keine** personenbezogenen Daten, nur Kennungen;
Primärschlüssel Art+Kennung). Geschrieben in derselben Transaktion wie jede
Löschung (Kontolöschung, Verlauf löschen, Aufräumen verlassener Registrierungen);
bereinigt nach 90 Tagen (länger als die längste Sicherungsfrist). Teil der
Nutzerdaten-Sicherung (`USER_TABLES`). Kommandos im Kern (`python -m
normly_core.exchange`): `export-deletions --since <ISO-Zeitpunkt>` schreibt die
Einträge als JSON auf stdout; `replay-deletions` liest sie von stdin und wendet sie
über die normalen Löschfunktionen an (idempotent; schreibt dabei wieder ins
Protokoll); `replay-deletions --check` prüft ohne Datenbank, ob das Image den Befehl
kennt.

**6. Rollback.** `normly-deploy rollback`: Im Vorlauf (vor Banner, Bestätigung,
Stopp) werden mit dem Image des **Releases, dessen Daten verworfen werden** (`$from`:
bei einem fehlgeschlagenen Rollout dieser, sonst der aktuelle) die Löschungen seit dem
Sicherungszeitpunkt gelesen (erster Export; Fehler → Abbruch ohne Änderung; Format
vom gemeinsamen Prüfer `normly_check_deletions` geprüft). Der Zeitpunkt ist der
Zeitstempel aus dem Basisnamen **minus eine Stunde** (Sicherheitsrand im Skript; der
Kernbefehl behält seine strikte „später als“-Bedeutung): eine doppelt angewendete
Löschung ist harmlos, weil die Entität schon fehlt und UUIDs nie wiederverwendet
werden. Fehlt die Tabelle `deletion_log` (Release vor diesem Feature), wird ohne
Image-Aufruf eine leere Liste angenommen. Der erste Export speist Banner, die
Entscheidung über `replay-deletions --check` und die frühe Prüfung. Nach dem Stopp
der Dienste und vor dem DROP folgt ein **zweiter Export** (gleiches Image, gleicher
Zeitpunkt, gleicher Prüfer); schlägt er fehl, bricht der Rollback ab, die Dienste
sind gestoppt, die Datenbank unverändert. **Dieses zweite Dokument** wendet nach
`pg_restore` (und nach der Tombstone-Wiederherstellung) das **vorherige** Image an
(`replay-deletions`). Das `--check` gilt nur bei Exitcode 2 (unbekannter Befehl) als
„nicht unterstützt“, jeder andere Fehler bricht vor Banner und Bestätigung ab. Kennt
das vorherige Image den Befehl nicht (Release vor diesem Feature), meldet das Banner
Anzahl und die ersten 20 Kennungen; die vollständige Liste liegt danach in
`$STATE/rollback-pending-deletions.json` (0600, überlebt das Aufräumen von `$WORK`)
und muss von Hand erneut gelöscht werden (die Bestätigung bleibt Pflicht). Dasselbe
gilt im Restore-Test und für eine Notfall-Wiederherstellung aus der Flex-Sicherung
(Betriebsguide). `normly-cleanup` überspringt seinen Lauf, solange
`state/deploy.lock` existiert.

## Absicherung

- Tests: Anonymer Chat schreibt nichts (Datenbank unverändert, kein `session_token`,
  kein Cookie); Konto-Chat wie bisher; Chat-Token ohne Konto wird ignoriert;
  Aufräumbefehl je Frist (Grenzen, Idempotenz, alte anonyme Verläufe, bestätigte
  Konten unberührt, Kaskade beim Löschen eines Kontos); Verlauf löschen (eigener,
  fremder, alle; schreibt Protokoll); Export (Inhalte, Ausschlüsse, Fremdzugriff,
  Tombstone-Kennungen); `deletion_log` bei `delete_account`; Protokoll-Export/-Replay
  (Zeitgrenze, Idempotenz, Format); Rollback-Skript (Reihenfolge: Protokoll vor dem
  Löschen, Replay nach der Wiederherstellung; Fehlerfälle; vorheriges Image ohne
  Befehl); Frontend (Chat ohne Cookie, Löschknöpfe, Export).
- Migration `0035`: `deletion_log` (Nutzerdaten-Gruppe, vom Fail-closed-Test erfasst).
- Dokumentation: ADR-027 (Datenverzeichnis je Tabelle mit Zweck, Personenbezug,
  Frist, Löschweg; Wirkung in Sicherungen mit den tatsächlichen Höchstfristen;
  Hinweis auf fachliche Prüfung), Betriebsguide (Timer, Aufräumen, Rollback-Schritt,
  Restore, Notfall-Wiederherstellung), Spec-Status.

## Nicht-Ziele

- Datenschutzerklärung und Verzeichnis der Verarbeitungstätigkeiten als Rechtstext.
- Löschen inaktiver Konten nach Frist (mit Vorwarnung per E-Mail).
- Asynchroner Export per E-Mail-Link, Verwaltungsoberfläche für Betreiber.
- Kryptographisches Löschen je Konto in Sicherungen.

## Offene Punkte

- Fachliche Prüfung der Fristen (Datenschutz).
- Sitzungs-Metadaten (`account_session`): enthält heute keine IP/User-Agent; ändert
  sich das, muss das Datenverzeichnis und die Frist neu bewertet werden.
- Aufbewahrung der Tombstones (aus Teil A) bleibt offen und gehört hierher, sobald
  entschieden ist, ob Kennungen zurückgezogener Dokumente zeitlich begrenzt werden.
