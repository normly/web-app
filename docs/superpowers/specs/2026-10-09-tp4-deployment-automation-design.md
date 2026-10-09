# Design: Deployment-Automatisierung (STACKIT-Deployment, Teilprojekt 4/4)

Stand: 2026-10-09 · Status: Entwurf, wartet auf Review. Roadmap und
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

1. `cosign verify` für alle fünf Images gegen die GitHub-OIDC-Identität des
   Release-Workflows. Schlägt eine Prüfung fehl: Abbruch, nichts verändert.
2. Pre-Rollout-Sicherung nach Teil 2 (Nutzerdaten) samt aktuellem Tag und
   Dump-Version des Wissensbestands. Ohne bestätigten Upload kein Rollout.
3. `docker compose pull` mit `NORMLY_IMAGE_TAG=vX.Y.Z`.
4. `migrate`, dann `up -d`.
5. Warten auf die `/health`-Endpunkte aller Dienste mit Timeout (von TP1 für
   TP4 vorgemerkt).
6. Bei Erfolg: Tag als `current`, vorheriger als `previous` festhalten. Bei
   Fehlschlag: klare Meldung, **kein** automatischer Rückweg.

**`normly-deploy rollback`:** zeigt, welche Daten verworfen werden (vom
Pre-Rollout-Dump bis jetzt) und welche Dauer der Neu-Import des
Wissensbestands erwartet, verlangt ausdrückliche Bestätigung. Dann: Dienste
stoppen, Nutzerdaten aus dem Pre-Rollout-Dump zurückspielen, Wissensbestand
in der damaligen Dump-Version neu importieren, `previous` starten,
Gesundheit prüfen.

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

Die genaue Tabellenzuordnung wird beim Bau aus den Migrationen abgeleitet
und als Allowlist im Code festgehalten, mit einem Test, der jede
Tabelle genau einer Gruppe zuweist (neue Tabelle ohne Zuordnung lässt den
Test fehlschlagen).

**Voraussetzung:** Der Wissensbestand in Produktion ändert sich **nur** durch
Dump-Import, nie durch Ingestion auf der VM. Das ist zugleich die
Voraussetzung für TP1a.

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
  Ablauf 07.11.). Ein zusätzlicher Eintrag am 08.10. um 23:56 stammt aus
  unbekanntem Anlass (vermutlich Änderung an der Instanz) — offen.
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
Kategorie und Rechtsgrundlage, Prüfsumme und Zeilenzahl je Datei. Jede Zeile
führt ihre Quelllieferung (Abstammung).

**Export (`normly-kb export`):** lokal bei der Ingestion, über die
Repository-Schicht. Ergebnis ist ein hochladbares Verzeichnis; eine Version
ist unveränderlich und wird nie überschrieben.

**Verteilung (D5):** Öffentlich lesbarer STACKIT-Object-Storage-Bucket,
`kb/<version>/`, dazu `kb/latest`. Das Manifest ist mit einem
Maintainer-Schlüssel signiert (kein Keyless-Zertifikat möglich, weil der Dump
lokal entsteht, nicht in der CI); der öffentliche Schlüssel liegt im
Repository. Werkzeugwahl (cosign mit Schlüsselpaar oder minisign) fällt im
Plan und wird dort begründet.

**Import (`normly-kb import <version>`):**

1. Manifest laden, Signatur prüfen; sonst Abbruch.
2. Austauschschema-Version und Einbettungsmodell prüfen; bei Abweichung
   Abbruch mit klarer Meldung (keine stillen falschen Einbettungen).
3. Prüfsummen prüfen, über die Repository-Schicht einspielen.
4. **Idempotent:** Wiederholung derselben Version erzeugt keinen
   abweichenden Stand; Zeilen sind über stabile Schlüssel identifiziert,
   in der neuen Version fehlende Zeilen werden entfernt. Der Austausch ist
   atomar, die Anwendung sieht nie einen halben Bestand.
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
- Anlass des zweiten Flex-Sicherungseintrags am 08.10. um 23:56.
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
