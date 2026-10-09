# Design: Deployment-Automatisierung (STACKIT-Deployment, Teilprojekt 4/4)

Stand: 2026-10-09 · Status: umgesetzt bis auf die Live-Abnahme (Task 9). Roadmap und
Grundsatzentscheidungen E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.
Vorgänger: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`
(umgesetzt, Release `v0.1.0`).

## Ziel

Neue Versionen gelangen ohne Bau auf der VM und ohne STACKIT-Zugangsdaten
auf GitHub in Produktion, lassen sich zurücknehmen, und der freie
Wissensbestand wird getrennt vom Code versioniert ausgeliefert. Erfüllt
REQ-INST-002 (automatisiertes Deployment), REQ-INST-004 (Rollback),
REQ-DIST-004 und ADR-010 (Daten getrennt vom Image).

Heute baut die VM aus `/opt/normly/src` (Sync per `scripts/sync-to-vm.sh`),
es gibt keinen Rollback-Punkt, und der Wissensbestand entsteht per Ingestion
auf der VM. Das blockiert außerdem die Verkleinerung auf `g1a.2d` (TP1a).

## Zerlegung

Der Nutzer hat bewusst **eine** Spec für alle drei Teile gewählt (Option C
der Zerlegungsfrage; Empfehlung war, Rollout zuerst abzutrennen). Die Teile
sind deshalb getrennt abnehmbar gehalten und können im Plan in eigene
Abschnitte oder Pläne geschnitten werden:

1. Rollout und Rollback (`normly-deploy`)
2. Datenbanksicherung (`normly-backup`)
3. Wissensbestand-Dump (`normly-kb export` / `import`)

## Entscheidungen

| # | Frage | Entscheidung | Verworfen |
|---|---|---|---|
| D1 | Auslöser des Rollouts | Manueller Aufruf per SSH, Skript timerfähig gehalten | Timer mit Auto-Rollout (Migrationen liefen unbeaufsichtigt, braucht „höchster Tag“-Logik und Stabilitätsfenster) |
| D2 | Rollback und Migrationen | Rollback setzt Images **und** Daten auf den Stand vor dem Rollout zurück, mit Warnung und Bestätigung | Nur Images zurück (verlangt eine Expand/Contract-Disziplin für Migrationen, die es nicht gibt) |
| D3 | Sicherungsziel | `age`-verschlüsselt auf der VM, privater Bucket in STACKIT Object Storage, privater Schlüssel nie auf der VM | Nur serverseitige Verschlüsselung (Schlüssel beim Anbieter, neben den Daten); nur Pre-Rollout-Dumps |
| D4 | Dump-Format | Parquet je Tabelle plus signiertes Manifest, Import über die Repository-Schicht | `pg_dump` des Wissensbestands (siehe unten) |
| D5 | Verteilung | Öffentlich lesbarer Object-Storage-Bucket, Kalenderversion, signiertes Manifest | STACKIT-Git-Repository (große Binärdateien, anonymer Zugriff unhandlich); Git zusätzlich als Manifest-Verlauf (zweites System) |
| D6 | Sicherung nach Datenart | Nutzerdaten täglich gesichert, Wissensbestand nicht (ist über Dump rekonstruierbar), Flex-Sicherung als Betriebsnetz | Täglicher Gesamtdump (bei zweistelligen GB verschwendet) |

### Begründung D4: Parquet statt `pg_dump`

Der Nutzer hat B gegen die ursprüngliche Empfehlung (A, `pg_dump`) gewählt;
die Gründe, die ihn tragen:

- **ADR-006 / CLAUDE.md:** Datenbankzugriff läuft nur über die
  Repository-Schicht, damit die Speichertechnologie austauschbar bleibt.
  `pg_dump` ist ein Postgres-Artefakt und umgeht sie.
- **Der Dump ist ein öffentliches Produkt** (REQ-DIST-004), das Dritte
  einspielen. Ein Format ohne Bindung an unsere Alembic-Revision überlebt
  Schemaänderungen; bei `pg_dump` müsste jeder Selbsthoster die passende
  Anwendungsversion finden.
- **Abstammung:** Ein tabellenweiser Export mit Quelllieferung je Zeile
  hält die Rücknahme einer Lieferung auch im Dump nachvollziehbar.
- **Preis:** mehr Code (Export, Import, Austauschschema), langsamerer
  Import, Idempotenz selbst herzustellen. Parquet statt NDJSON, weil
  Einbettungen (1024 Floats, ~4 KB je Abschnitt) sonst unhandlich werden.

## Teil 1: Rollout und Rollback (`normly-deploy`)

Shell-Skript `scripts/normly-deploy`, läuft auf der VM ohne
Quellcode-Checkout mit einem schmalen Verzeichnis (`compose.yaml`, `.env`).
Es nutzt, was `compose.yaml` schon hat: den `migrate`-Dienst vor `api`,
`accounts` und `chat` und die Parametrisierung `NORMLY_IMAGE_TAG`.

**`normly-deploy deploy vX.Y.Z`**

0. Ein Tag, der dem aktuellen entspricht, wird abgelehnt. Ist ein
   fehlgeschlagener Rollout vermerkt (`state/failed_rollout`), startet kein
   neuer `deploy`, bis der Rollback gelaufen ist; der Operator kann das
   bewusst übergehen, indem er die Datei entfernt.
1. `cosign verify` für alle fünf Images gegen die GitHub-OIDC-Identität des
   Release-Workflows. Schlägt eine Prüfung fehl: Abbruch, nichts verändert.
   **Digest-Pinning:** Der geprüfte Digest (`docker-manifest-digest` aus der
   cosign-Ausgabe) wird festgehalten (`releases/<tag>/verified-digests`).
   Die Assets kommen aus `pipeline@<digest>`; nach `pull` muss der Digest
   jedes Images dem geprüften entsprechen, sonst Abbruch vor `up`. Ein
   zwischenzeitlich umgesetztes Tag umgeht die Prüfung so nicht.
2. Pre-Rollout-Sicherung nach Teil 2 (Nutzerdaten) samt aktuellem Tag und
   Dump-Version des Wissensbestands. Ohne bestätigten Upload kein Rollout.
   Lässt sich die Dump-Version des laufenden Releases nicht lesen, bricht
   der Rollout ab; `none` wird nur festgehalten, wenn `info` es meldet.
3. `docker compose pull` mit `NORMLY_IMAGE_TAG=vX.Y.Z`.
4. `migrate`, dann `up -d`.
5. Warten auf die `/health`-Endpunkte aller Dienste mit Timeout (von TP1 für
   TP4 vorgemerkt).
6. Bei Erfolg: Tag als `current`, vorheriger als `previous` festhalten. Bei
   Fehlschlag: klare Meldung, **kein** automatischer Rückweg; `previous` wird
   auf das bis dahin laufende Release gesetzt (Rollback-Ziel) und der
   fehlgeschlagene Tag in `failed_rollout` vermerkt.

**`normly-deploy rollback`:** prüft zuerst, bevor etwas verändert wird, ob
die Alembic-Revision aus `<backup>.meta.json` dem Alembic-Head des
**vorherigen** Images entspricht; bei Abweichung Abbruch (Dump und Schema
passen sonst nicht zusammen). Danach zeigt es, welche Daten verworfen werden (vom
Pre-Rollout-Dump bis jetzt), verlangt ausdrückliche Bestätigung und stellt
dann den Stand vor dem Rollout wieder her. Weil Alembic-Migrationen nur
vorwärts laufen, bleibt das neue Schema nach einem reinen Datenrestore
bestehen; der Rollback baut das Schema deshalb **neu auf**:

1. Dienste stoppen.
2. Alle Tabellen verwerfen (`DROP TABLE … CASCADE`; die Liste kommt aus der
   Datenbank selbst, nicht aus dem vorherigen Image, damit auch Tabellen des
   neueren Releases verschwinden; das Schema bleibt, damit pgvector erhalten
   bleibt) und mit dem `migrate`-Dienst des **vorherigen** Images auf dessen
   Alembic-Stand neu anlegen.
3. Wissensbestand in der damaligen Dump-Version importieren (stabile IDs,
   siehe Teil 3). Das muss **vor** den Nutzerdaten geschehen, denn diese
   verweisen per Fremdschlüssel auf Wissensbestand-Zeilen (`watchlist` →
   `work`, `notification` → `edge`/`document`, `chat_message_citation` →
   `document`/`segment`).
4. Nutzerdaten aus dem Pre-Rollout-Dump einspielen (`--data-only`; Schema und
   Dump stammen vom selben Alembic-Stand).
5. `previous` starten, Gesundheit prüfen.

Die Dauer von Schritt 3 steigt mit dem Bestand; das Skript nennt sie vorab.
Scheitert der Rollback nach dem Verwerfen, meldet das Skript, dass die
Datenbank unvollständig ist, `current_tag` unverändert bleibt und der
identische Aufruf gefahrlos wiederholt werden kann. Erfolgreich beendet,
löscht er `failed_rollout`.

**Fehlerfälle:** Läuft `migrate` halb durch, ist der Pre-Rollout-Dump der
Rettungsweg (das Skript sagt es). Eine Sperrdatei verhindert parallele Läufe.
Notweg bei Migrationen an Wissensbestand-Tabellen und großen Beständen: die
Flex-Wiederherstellung.

**Nicht enthalten:** Secrets per AppRole (TP3); das Skript liest
`/opt/normly/.env` wie heute. Kein Timer; die Schnittstelle erlaubt ihn
später ohne Umbau.

## Teil 2: Datenbanksicherung (`normly-backup`)

Aufgerufen vom Rollout und von einem täglichen systemd-Timer.

**Aufteilung nach Datenart (D6):**

| Daten | Eigenschaft | Sicherung |
|---|---|---|
| Nutzerdaten (Konten, Chats, Watchlists, Benachrichtigungen, Ratenbegrenzung) | klein, unersetzlich | täglich `pg_dump -Fc` nur dieser Tabellen, `age`-verschlüsselt, Object Storage |
| Wissensbestand | groß, reproduzierbar | kein eigener Dump; Stand = zuletzt importierte Dump-Version |
| Gesamtdatenbank | Betrieb | Flex-Sicherung (siehe Befund) |

Die Zuordnung ist als Allowlist im Code festgehalten
(`normly_core/exchange/tables.py`), mit einem Test, der jede ORM-Tabelle
genau einer Gruppe zuweist (neue Tabelle ohne Zuordnung lässt den Test
fehlschlagen). Es gibt drei Gruppen: **Wissensbestand** (`source`,
`delivery`, `work`, `document`, `document_designation`, `document_title`,
`rights_classification`, `edge`, `segment`, `embedding`,
`document_embedding`), **Nutzerdaten** (`account*`, `oauth_state`,
`watchlist`, `notification`, `rights_notification_baseline`,
`notified_edge`, `chat_*`, `rate_limit_bucket`) und **Pipeline-Zustand**
(`identity_resolution_case`: Prüfwarteschlange der lokalen Ingestion, in
Produktion leer, weder exportiert noch gesichert). Nutzerdaten verweisen per
Fremdschlüssel auf Wissensbestand-Zeilen; der Dump muss deshalb die
**IDs unverändert** erhalten (Voraussetzung für Rollback und Restore).

**Voraussetzung:** Der Wissensbestand in Produktion ändert sich **nur** durch
Dump-Import, nie durch Ingestion auf der VM. Das ist zugleich die
Voraussetzung für TP1a.

**Werkzeug für den Upload:** `rclone` (quelloffen, ein Binary, S3-kompatibel
gegen STACKIT Object Storage); kein US-Dienst, nur ein Client.

**Ablauf:** Dump → auf der VM mit dem öffentlichen `age`-Schlüssel
verschlüsseln (temporäre Datei in einem 0700-Verzeichnis, kein Klartext
danach) → Upload nach `backups/<UTC-Zeitstempel>-<art>.dump.age`
(`daily` oder `pre-<tag>`) → Prüfsumme daneben. Eine Sicherung gilt erst
nach bestätigtem Upload; Bereinigung läuft erst danach.

**Schlüssel:** Der private `age`-Schlüssel liegt im Secrets Manager und als
Offline-Kopie beim Betreiber, **nicht** auf der VM. Die VM kann schreiben,
nicht lesen. Restore und Rollback brauchen den Schlüssel kurzzeitig
(vom Betreiber bereitgestellt). Zugangsdaten für Object Storage kommen aus
`/opt/normly/.env`.

**Aufbewahrung (Stand, kann sich durch den Flex-Befund ändern):** 7 tägliche,
2 monatliche, 3 Pre-Rollout-Stände. Begründung: Nutzerdaten sind klein
(Megabytes), die Kosten sind nachrangig; 7 Tage decken das typische
Entdeckungsfenster einer Einzelinstanz, Monatsstände dienen als Anker für
spät erkannte Schäden. Wöchentliche Stände entfallen (Nutzen über 7 Tage
hinaus klein). Ob der Bucket eine Objektsperre bietet, wird beim Bau
geprüft und hier nachgetragen.

**Restore-Test:** Manuell und dokumentiert, einmal nach dem Bau, danach
monatliche Erinnerung. Ein automatischer Test bräuchte den privaten
Schlüssel auf einer Maschine und widerspräche dem Schlüsselkonzept.

### Befund Flex-Sicherung (2026-10-09, Screenshot des Portals)

- Tägliche Sicherung um 11:45 (UTC), Ablauf nach 30 Tagen (Start 08.10.,
  Ablauf 07.11.).
- Größe aktuell 3,66 MB; der Wissensbestand fehlt noch.
- **Nicht geprüft:** Punkt-in-Zeit-Wiederherstellung (PITR), Verschlüsselung
  der Flex-Sicherungen. Beides ist vor dem Bau in der STACKIT-Dokumentation zu
  klären; von PITR hängt ab, ob die täglichen Dumps noch kürzer ausfallen
  können (Richtwert 3).

## Teil 3: Wissensbestand-Dump

**Inhalt:** Nur freie Bestände (Kategorien A, B, D). Allowlist je Tabelle,
zusätzlich muss jede Zeile durch die Rechteklassifikation freigegeben sein
(einziges Tor); fehlende Klassifikation heißt nicht exportieren. Nutzerdaten
und lizenzierte Bestände sind nie enthalten.

**Format:** Parquet je Tabelle (große Tabellen in Teilen) und
`manifest.json` mit: Austauschschema-Version (unabhängig von Alembic),
Dump-Version (Kalender, z. B. `2026.10.1`) und Zeitpunkt, Einbettungsmodell
mit gepinnter Revision und Dimension, enthaltene Quelllieferungen mit
Herausgeber und Kategorie (die Rechtsgrundlage je Dokument steht in den
Zeilen von `rights_classification`), Prüfsumme und Zeilenzahl je Datei. Jede Zeile
führt ihre Quelllieferung (Abstammung).

**Export (`normly-kb export`):** lokal bei der Ingestion, über die
Repository-Schicht. Ergebnis ist ein hochladbares Verzeichnis; eine Version
ist unveränderlich und wird nie überschrieben.

**Verteilung (D5):** Öffentlich lesbarer STACKIT-Object-Storage-Bucket,
`kb/<version>/`, dazu `kb/latest`. Das Manifest ist mit einem
Maintainer-Schlüssel signiert (kein Keyless-Zertifikat möglich, weil der Dump
lokal entsteht, nicht in der CI); der öffentliche Schlüssel liegt im
Repository. **Werkzeug: Ed25519 in Python (`cryptography`), im Import
selbst geprüft.** Begründung: Der Import läuft im `pipeline`-Image und beim
Selbsthoster; ein zusätzliches Binary (cosign, minisign) würde das Image
vergrößern und eine zweite Installationshürde schaffen. Signaturformat und
Prüfung sind klein genug, um sie testbar im Kern zu halten. Die Prüfung der
Images mit cosign (Teil 1) bleibt davon unberührt.

**Import (`normly-kb import <version>`):**

1. Manifest laden, Signatur prüfen; sonst Abbruch.
2. Austauschschema-Version und Einbettungsmodell prüfen; bei Abweichung
   Abbruch mit klarer Meldung (keine stillen falschen Einbettungen).
3. Prüfsummen prüfen, über die Repository-Schicht einspielen.
4. **Idempotent:** Wiederholung derselben Version erzeugt keinen
   abweichenden Stand; Zeilen sind über stabile Schlüssel identifiziert,
   in der neuen Version fehlende Zeilen werden entfernt, in drei
   Durchgängen: (a) in umgekehrter Abhängigkeitsreihenfolge fehlende Zeilen
   löschen, die keine behaltene Zeile mehr referenziert; (b) in
   Abhängigkeitsreihenfolge einfügen oder aktualisieren (verschiebt
   Fremdschlüssel, z. B. `document.work_id` nach einem Work-Merge oder
   `rights_classification.delivery_id` auf eine neue Lieferung); (c) die in
   (a) zurückgestellten fehlenden Zeilen löschen. Reines „zuerst löschen"
   würde sonst fälschlich blockieren, obwohl keine Nutzerdaten beteiligt
   sind. Ein Work-Merge exportiert die zusammengeführte Work samt Ziel, damit
   die Weiterleitung beim Import erhalten bleibt. Der Austausch ist atomar, die
   Anwendung sieht nie einen halben Bestand. Verweist eine Nutzerdaten-Zeile
   noch auf eine zu löschende Wissensbestand-Zeile (z. B. eine beobachtete
   `work`, die die neue Version nicht mehr enthält), bricht der Import
   **ohne Änderung** ab und nennt die blockierenden Verweise; wie solche
   Fälle fachlich aufzulösen sind, ist eine spätere Entscheidung.
5. Die importierte Version wird in einer kleinen Tabelle festgehalten;
   Rollout und Rollback lesen sie dort.

**Erster Start von Selbsthostern:** Ein Werkzeugprofil in `compose.yaml`
führt `normly-kb import latest` aus (REQ-DIST-004: „beim ersten Start
bezogen“).

**Nicht enthalten:** Delta-Dumps. Das Format lässt sie offen, ohne sie zu
bauen.

## Dokumentation, die mitläuft

- **ADR-024** „Rollout, Rollback und Sicherung auf der Einzel-VM“: D1, D2,
  D3, D6 mit Begründung und Verworfenem.
- **ADR-025** „Wissensbestand-Dump als Austauschformat“: D4, D5.
- **ADR-021, Nachtrag:** Die Aussage, STACKIT Git sei für das künftige
  Hosting der Normen-Wissensbasis vorgesehen, entfällt; die Wissensbasis
  wird als Dump im Object Storage verteilt (ADR-025). Als datierter
  Nachtrag, nicht als stilles Überschreiben (Muster: ADR-020). Mitzuziehen:
  der Satz in `CLAUDE.md`, REQ-GIT-005 in `docs/srs/03-anforderungen.md` und
  das ADR-Register. Was mit dem STACKIT-Git-Repository `normly-webapp`
  geschieht (archivieren oder löschen), ist eine getrennte Entscheidung des
  Nutzers und nicht Teil dieser Spec.
- **SRS:** Verweise bei REQ-INST-002, REQ-INST-004, REQ-DIST-004.
- **`docs/guide/`** (Englisch, ADR-020): Betriebsabschnitt für Rollout,
  Rollback, Sicherung und Restore; `self-hosting.md` um Dump-Import ergänzen
  (der Satz „No versioned knowledge-base dump yet“ entfällt).

## Offene Punkte

- PITR und Verschlüsselung der Flex-Sicherungen klären (siehe Befund); kann
  die Aufbewahrung ändern.
- Objektsperre im Backup-Bucket: Verfügbarkeit prüfen.
- Kryptographisches Löschen bei Vertragsende (ADR-014): Der tägliche Dump
  enthält Nutzerdaten, aber keine lizenzierten Bestände. Sobald lizenzierte
  Bestände in Postgres liegen, müssen sie von Sicherungen ausgenommen oder
  je Herausgeber verschlüsselt werden (Aufgabe der kommerziellen Schicht).
- Größe und Dauer von Export und Import erst mit realem Bestand messbar;
  Rollback-Dauer (Neu-Import) wird dann in `normly-deploy` angezeigt.
- Zuordnung jeder Tabelle zu Wissensbestand oder Nutzerdaten (im Plan, mit
  Test gegen vergessene Tabellen).

## Nicht-Ziele

- Timer-gesteuerter Auto-Rollout, Blue/Green, Canary.
- Secrets per AppRole (TP3).
- Delta-Dumps, inkrementelle Sicherungen.
- Automatisierter Restore-Test.
- Entscheidung über das STACKIT-Git-Repository.
