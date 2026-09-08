# Design: Watchlist/Notification (Normtracker-Grundgerüst, Teil 4/5)

## Kontext

Sub-projects 1–3 sowie zwei nachträglich eingefügte Voraussetzungs-
Teilprojekte (Editionswechsel-Erkennung, editions-bewusste Identitäts-
auflösung) sind gemergt. Damit erzeugen EUR-Lex und DGUV jetzt zuverlässig
echte `REPLACES`-Kanten mit korrekter Work-Zuordnung — der Haupt-Auslöser
für dieses Teilprojekt existiert und funktioniert, auch bei unsortierter
oder gebündelter Ingestion.

Aktuell existiert von Watchlist/Notification nichts: das Glockensymbol im
Header (`frontend/src/components/page-header.tsx`) ist rein dekorativ
(zeigt immer "keine Benachrichtigungen"), es gibt kein Favoriten-Konzept
irgendwo im Frontend, und Auth/E-Mail-Versand leben ausschließlich im
`accounts/`-Service — der Service, der Works/Documents/Edges/Rights
besitzt (`api/`), hat aktuell keine Auth. `accounts/` hat außerdem keine
eigenen Datenbank-Modelle: alle Tabellen (`Account`, `AccountSession`,
etc.) leben in `core/`'s gemeinsamer ORM-Schicht (`core/src/normly_core/
graph/postgres/orm.py`), und alle Services (`accounts/`, `api/`, `chat/`)
verbinden sich mit derselben physischen Postgres-Datenbank über dieselbe
Umgebungsvariable (`NORMLY_DATABASE_URL`). Eine neue Watchlist-Tabelle
kann also einen echten Foreign Key auf `work.id` haben.

Dieses Projekt hat bislang bewusst keinen Scheduler (Ingestion ist
CLI-only, Rate-Limit-Bucket-Aufräumen passiert opportunistisch statt über
einen Cron-Job) und keinen Event/Hook-Mechanismus im Graph. Ein
periodischer Erkennungs-Job braucht also einen neuen CLI-Subcommand,
extern getriggert — kein neuer Scheduler im Code selbst.

## Ziel dieses Teilprojekts

1. Nutzer können ein Work über ein Herz-Symbol auf der Dokument-Detail-
   Seite als Favorit markieren (= zur Watchlist hinzufügen).
2. Nutzer stellen in den Profileinstellungen ein, ob und wie sie über
   Änderungen an ihren favorisierten Works benachrichtigt werden wollen:
   gar nicht, nur in der Software, nur per E-Mail, oder beides.
3. Ein neuer, extern getriggerter CLI-Job erkennt drei Änderungsarten an
   einem beobachteten Work — neue Edition, neue nationale Fassung,
   Rechteklassifikations-Änderung — und erzeugt für jede echte, noch
   nicht verarbeitete Änderung eine Notification pro Beobachter.
4. Je nach Präferenz wird eine E-Mail verschickt und/oder die
   Notification erscheint im (bisher rein dekorativen) Glockensymbol im
   Header, das dafür erstmals echte Daten bekommt.

## Nicht-Ziele

- **Kein Retry/Queue für fehlgeschlagenen E-Mail-Versand.** Bleibt bei der
  bestehenden Fail-soft-Konvention (best-effort, `try/except`, kein
  erneuter Versuch) — dieselbe Konvention, die Magic-Link/Passwort-Reset
  schon heute nutzen.
- **Keine Push-Notifications** (Browser oder Mobile) — nur In-App-
  Popover und E-Mail.
- **Keine Digest-Zusammenfassung** ("wöchentliche Zusammenfassung mehrerer
  Änderungen in einer Mail"). Jede Änderung ist ihre eigene Notification
  und ihre eigene E-Mail.
- **Kein automatisches Aufräumen alter `Notification`-Einträge.** Bleibt
  für ein späteres Teilprojekt.

## Architektur

### Datenmodell (alles im gemeinsamen `core/`-ORM)

**`account.notification_preference`** — neue Spalte auf der bestehenden
`AccountORM`. Python-Enum `NotificationPreference` (`NONE`, `IN_APP`,
`EMAIL`, `BOTH`), abgebildet über `sa.Enum(..., native_enum=False,
create_constraint=True, values_callable=_enum_values)` — dasselbe Muster
wie `WorkStatus`/`LegalBasisCategory`. Default `NONE`: kein stiller Opt-in
in bestehende E-Mail-Zustellung.

**`WatchlistORM`** — neue Tabelle, die Favoriten-Liste:
```
id: uuid, primary key
account_id: uuid, FK account.id
work_id: uuid, FK work.id
created_at: datetime
UniqueConstraint(account_id, work_id)
```

**`NotificationORM`** — neue Tabelle, dient sowohl als Dedup-Log ("wurde
diese Änderung für diesen Beobachter schon verarbeitet?") als auch als
Datenquelle für den In-App-Feed:
```
id: uuid, primary key
account_id: uuid, FK account.id
work_id: uuid, FK work.id
trigger_type: enum (NEW_EDITION, NATIONAL_ADOPTION, RIGHTS_CHANGE)
trigger_edge_id: uuid | None, FK edge.id  -- gesetzt für NEW_EDITION/NATIONAL_ADOPTION
trigger_document_id: uuid | None, FK document.id  -- gesetzt für RIGHTS_CHANGE
trigger_jurisdiction: str | None  -- gesetzt für RIGHTS_CHANGE
created_at: datetime
read_at: datetime | None  -- In-App-Gelesen-Status, NULL = ungelesen
emailed_at: datetime | None  -- NULL = nicht per Mail zugestellt
UniqueConstraint(account_id, work_id, trigger_type, trigger_edge_id)
  -- für NEW_EDITION/NATIONAL_ADOPTION; RIGHTS_CHANGE nutzt eine separate
  -- Eindeutigkeits-Prüfung, siehe Trigger-Erkennung
```

### Trigger-Erkennung: `notify-watchers` CLI-Subcommand

Neu registriert in `core/src/normly_core/pipeline/cli.py`, gleicher
`argparse`-Subcommand-Stil wie `ingest`/`backfill-document-embeddings`,
nutzt dieselbe bereits im `main()` aufgebaute Engine/Session. Extern per
Cron/systemd-Timer/STACKIT-Scheduler getriggert — kein neuer Scheduler im
Code.

Pro Lauf, für jeden `WatchlistORM`-Eintrag (ein Account, ein beobachtetes
Work):

1. **`NEW_EDITION`/`NATIONAL_ADOPTION`**: alle `REPLACES`/`WITHDRAWN_BY`-
   bzw. `ADOPTED_FROM`-Kanten, deren `to_document_id` zu einem Document
   dieses Works gehört. `EdgeORM.created_at` existiert bereits als
   Spalte, ist aber nicht auf der `Edge`-Domain-Dataclass exponiert —
   wird ergänzt, zusammen mit einer neuen `EdgeRepository`-Methode, die
   Kanten für ein Work seit einem Zeitpunkt (oder einfach alle, s.u.)
   auflistet. Für jede gefundene Kante: existiert bereits ein
   `Notification`-Eintrag mit exakt `(account_id, work_id, trigger_type,
   trigger_edge_id)`? Wenn nein → neuer Eintrag.
2. **`RIGHTS_CHANGE`**: `RightsClassificationORM.classified_at` wird bei
   *jeder* Neuklassifizierung neu gesetzt, auch ohne inhaltliche
   Änderung (die Upsert-Logik überschreibt das Feld immer). Ein reiner
   Zeitstempel-Vergleich würde also bei jeder Re-Ingestion mit
   unveränderten Werten eine falsche Benachrichtigung auslösen. Der Job
   vergleicht deshalb die tatsächlichen Rechte-Felder (`may_process`,
   `may_index_fulltext`, `may_cite_passages`, `may_export_free`) gegen
   die Werte, die beim letzten `Notification`-Eintrag für dieses
   `(account_id, work_id, trigger_document_id, trigger_jurisdiction)`
   festgehalten wurden (dafür werden die vier Bool-Werte als eigene
   Spalten mit auf `NotificationORM` gespeichert, nicht separat
   nachgeschlagen) — nur bei einer echten Abweichung wird ein neuer
   Eintrag erzeugt.
3. Für jeden neu erzeugten `Notification`-Eintrag: wenn
   `notification_preference` des Accounts `EMAIL` oder `BOTH` ist, wird
   eine E-Mail verschickt (siehe unten) und `emailed_at` gesetzt. Sonst
   bleibt `emailed_at` `NULL`. `read_at` ist bei Erzeugung immer `NULL`.
   Läuft eine Account-Präferenz auf `NONE`, wird für dieses Work
   überhaupt kein `Notification`-Eintrag erzeugt (kein Datenmüll für
   Nutzer, die nichts wollen).

Kein Bedarf für einen "seit wann"-Zeitstempel-Cutoff: der Job scannt bei
jedem Lauf alle aktuell relevanten Kanten/Klassifikationen pro
beobachtetem Work und verlässt sich auf die `Notification`-Tabelle selbst
für Dedup — robust gegen verpasste oder wiederholte Läufe, konsistent mit
dem Idempotenz-Prinzip dieses Projekts.

### E-Mail-Versand

`EmailSender`-Protokoll sowie `SmtpEmailSender`/`RecordingEmailSender`
(aktuell in `accounts/src/normly_accounts/email.py`) wandern nach `core/`
— reine Infrastruktur ohne accounts-spezifische Logik, und der neue
CLI-Job (der in `core/` lebt) darf nicht von `accounts/` abhängen.
`accounts/` importiert die Klassen ab sofort aus `core/` weiter; alle
bestehenden Aufrufstellen (`registration.py`, `magic_link.py`,
`password_reset.py`, `email_change.py`) bleiben unverändert, ihre
bestehenden Tests müssen unverändert grün bleiben.

Neue Notification-Mails folgen dem bestehenden Stil: schlichter Text auf
Deutsch, ein Link, kein Anhang, `try/except`-umschlossen (ein SMTP-Fehler
darf den Job nicht abbrechen — best effort, kein Retry).

### Frontend: Favorisieren + Profileinstellung

**Herz-Symbol** auf der Dokument-Detail-Seite (`frontend/src/app/
documents/[id]/document-detail-content.tsx`, aus Sub-project 3) — neuer
Toggle-Button, ruft einen neuen, authentifizierten `POST`/`DELETE
/v1/accounts/watchlist`-Endpunkt in `accounts/` auf (Body: `work_id`).
Zeigt gefüllt/leer je nachdem, ob das aktuelle Work bereits auf der
Watchlist des eingeloggten Nutzers steht (neuer `GET
/v1/accounts/watchlist/{work_id}`-Check oder Teil der Dokument-Detail-
Antwort — Detail bleibt der Implementierungsplan).

**Profileinstellung**: neue Sektion im bestehenden `profile-overlay.tsx`
(Dialog mit Tab-Navigation, `SECTIONS`-Liste), die `notification_
preference` über den bestehenden `PATCH /v1/accounts/profile`-Endpunkt
setzt (dessen `UpdateProfileRequest`/`AccountResponse` um das neue Feld
erweitert werden, gleiches `model_fields_set`-Partial-Update-Muster wie
bei `first_name`/`last_name`).

### Frontend: echte In-App-Benachrichtigungen

Neuer `useNotifications`-Hook (gleiches Muster wie der bestehende
`useAccountSession`-Hook: `fetch` auf Mount, `useState`, manuelle
Refresh-Funktion), backed von neuen `GET /v1/accounts/notifications`
(Liste) und `PATCH /v1/accounts/notifications/{id}`-Endpunkten (als
gelesen markieren, setzt `read_at`). Das bestehende Glockensymbol in
`page-header.tsx` (aktuell eine statische `Popover`-Hülle mit
`t("nav.noNotifications")`) rendert ab jetzt die echte Liste — kein neues
Design, nur echte Daten statt der statischen Zeile.

## Tests

- `core/`: Repository-Tests für `WatchlistRepository`/
  `NotificationRepository`; CLI-Job-Tests (echte Postgres via
  testcontainers) für alle drei Trigger-Typen, inklusive: kein
  False-Positive bei `RIGHTS_CHANGE`, wenn eine Re-Ingestion dieselben
  Rechte-Werte erneut klassifiziert; Dedup (ein zweiter Lauf über
  unveränderte Daten erzeugt keine doppelten `Notification`-Einträge);
  `notification_preference == NONE` erzeugt überhaupt keinen Eintrag.
  `SmtpEmailSender`/`RecordingEmailSender` nach dem Umzug getestet an
  ihrem neuen Ort in `core/`.
- `accounts/`: Endpunkt-Tests für Watchlist-Add/Remove, Profil-Update mit
  `notification_preference`, Notifications-Liste/Als-gelesen-markieren.
  Bestehende E-Mail-Tests (`registration.py` etc.) bleiben unverändert
  grün, da nur der Import-Pfad wechselt.
- `frontend/`: Herz-Symbol-Interaktion (Toggle, gefüllt/leer-Zustand),
  neue Profileinstellungs-Sektion, `useNotifications`-Hook plus
  Glocke-Popover mit echten (gemockten) Daten statt der statischen
  Zeile.
