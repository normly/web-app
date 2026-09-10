# accounts/ Commit-Timing Sweep, Test Hardening, and Two Small Data Fixes — Design

## Kontext

Ein 10 Tage alter Memory-Eintrag aus dem "Profilverwaltung"-Teilprojekt
listete mehrere zurückgestellte Follow-ups auf. Direkte Neuprüfung gegen den
aktuellen Code (main @ 85a464fe) ergab: einer der Punkte ist bereits gelöst
(die Magic-Link-E-Mail hat seit 2026-09-08 eine echte URL und einen
funktionierenden Frontend-Consumer, verifiziert), einer ist größer als
gedacht (das "Response vor Commit"-Problem betrifft nicht nur zwei, sondern
17 Endpunkte), und einer braucht eine echte technische Entscheidung (wie ein
Regressionstest für Commit-Timing überhaupt funktionieren kann, gegeben die
bestehende Test-Fixture-Architektur). Dieser Spec bündelt die vier Punkte,
die sich als "mechanisch/risikoarm" einordnen ließen — größere,
design-bedürftige Punkte (Avatar-Neugestaltung, Notification-Cleanup-Policy,
Suche-Schwellwert/Index) werden bewusst NICHT hier behandelt, sondern
bekommen eigene, spätere Brainstorming-Runden.

## Das Kernproblem (Punkt 1 und 2 dieses Specs)

`accounts/src/normly_accounts/dependencies.py`s `get_session()`:
```python
def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()
```
Der `session.commit()` läuft erst, wenn FastAPI den Yield-Dependency-Generator
beim Abbau des `AsyncExitStack` fortsetzt — das passiert **nachdem** die
HTTP-Response bereits an den Client gesendet wurde. Ein Endpunkt ohne
eigenes, explizites `session.commit()` vor seinem `return` liefert also eine
Erfolgsantwort, bevor die Schreiboperation durchsetzungsfähig (durable) ist.
Ein Client, der sofort danach etwas abfragt, das von dieser Schreiboperation
abhängt, kann unter READ COMMITTED eine veraltete Antwort bekommen — genau
diese Race wurde bereits zweimal real gemessen und gefixt (Session-Erstellung
beim Login/Register/Magic-Link/Google-OAuth über `_create_session_response()`
in `login.py`, und Kontolöschung in `account_management.py`s
`delete_account`).

**Neuprüfung ergab: 17 weitere Endpunkte sind exakt derselben Gefahrenklasse
ausgesetzt**, nicht nur die zwei bereits gefixten:

| Datei | Endpunkt(e) | Zeile(n) |
|---|---|---|
| `email_verification.py` | `POST /verify-email/resend` | 49 |
| `email_verification.py` | `GET /verify-email` (schreibt via GET) | 35 |
| `password.py` | `POST /password` | 19 |
| `email_change.py` | `POST /email/change` | 37 |
| `email_change.py` | `GET /email/confirm` (schreibt via GET) | 81 |
| `login.py` | `POST /logout` | 91 |
| `notifications.py` | `PATCH /notifications/{id}` | 50 |
| `profile.py` | `PATCH /profile` | 37 |
| `profile.py` | `POST /avatar` | 59 |
| `profile.py` | `DELETE /avatar` | 104 |
| `watchlist.py` | `POST /watchlist` | 22 |
| `watchlist.py` | `DELETE /watchlist/{work_id}` | 42 |
| `magic_link.py` | `POST /magic-link/request` | 38 |
| `sessions.py` | `DELETE /sessions/{session_id}` | 43 |
| `password_reset.py` | `POST /password-reset/request` | 36 |
| `password_reset.py` | `POST /password-reset/confirm` | 72 |
| `google.py` | `GET /google/login` (schreibt den neuen `oauth_state`) | 40 |

Fix: ein explizites `session.commit()` vor jedem `return`, exakt das
bestehende Muster aus `_create_session_response()`/`delete_account`. Keine
Verhaltensänderung außer dem Zeitpunkt der Durchsetzbarkeit.

## Testhärtung (Punkt 3 dieses Specs)

`accounts/tests/test_account_management.py`s bestehender
`test_deleting_an_account_commits_before_the_response_is_returned` kann
strukturell nicht beweisen, was er behauptet: `accounts/tests/conftest.py`s
`client`-Fixture überschreibt `get_session` mit `lambda: db_session` —
Test und App teilen sich also dasselbe `Session`-Objekt. Der echte
`get_session()`-Codepfad (inkl. `session.commit()`) läuft dabei gar nicht;
die Rücklese-Prüfung des Tests sieht die Löschung unabhängig davon, ob
committed wurde, weil beide durch dieselbe offene Transaktion schauen.

**Bestätigter, existierender Ausweg**: `accounts/tests/conftest.py` hat
bereits eine session-weite, rohe `migrated_engine`-Fixture (ein echtes
`sqlalchemy.Engine`, unabhängig von der Savepoint-umwickelten `db_session`),
gebaut gegen einen echten Postgres-Testcontainer. `core/tests/pipeline/test_cli.py`s
`committed_db`-Fixture zeigt bereits das richtige Muster im Repo: den echten
Code committen lassen, dann über eine **zweite, unabhängige** Verbindung
zurücklesen.

**Wichtige Korrektur gegenüber der ursprünglichen Fassung dieser Spec**: Ein
`TestClient`-Aufruf führt den kompletten Request-Zyklus — inklusive
`get_session()`s eigenem, verzögertem `session.commit()` beim
Dependency-Teardown — **synchron ab, bevor die Testfunktion weiterläuft**.
Es gibt innerhalb eines einzelnen `TestClient`-Aufrufs kein Zeitfenster, in
dem eine zweite Verbindung zwischen "Response gesendet" und "Commit
ausgeführt" dazwischenfunken könnte — das echte Produktions-Race brauchte
einen echten laufenden Server mit zwei parallelen HTTP-Verbindungen. Ein
"zweite Verbindung, kein Override"-Test kann diese Race-Eigenschaft also
**nicht** beweisen, und würde identisch bestehen, ob Punkt 1's Fix
angewendet wurde oder nicht.

**Was der Test stattdessen beweist, ehrlich umgedeutet (User-Entscheidung)**:
nicht "Commit passiert vor der Response", sondern "der Schreibvorgang landet
wirklich durable in der echten Datenbank, sichtbar über eine wirklich
unabhängige zweite Verbindung" — eine schwächere, aber immer noch echte und
wertvolle Garantie. Sie ist strikt besser als der aktuelle kaputte Test (der
bestünde sogar, wenn `commit()` nirgendwo je aufgerufen würde, weil Test und
App dieselbe Session teilen) und schützt real gegen z. B. eine künftige
Änderung, die `get_session()`s eigenen Teardown-Commit kaputt macht oder
einen Endpunkt versehentlich über eine nie committende Session laufen lässt.

Fix-Design:
- Eine neue Fixture in `accounts/tests/conftest.py`, die einen `TestClient`
  baut, der `get_session` **nicht** überschreibt — die App konstruiert dann
  ihr eigenes echtes Engine (`accounts/src/normly_accounts/main.py:34-36`
  liest `NORMLY_DATABASE_URL` und setzt `app.state.engine`, genau die vom
  `client`-Fixture bereits per `monkeypatch.setenv` gesetzte URL), sodass der
  echte `get_session()`-Codepfad inklusive `session.commit()` tatsächlich
  läuft.
- Zwei Tests bekommen dieses Muster (User-Entscheidung: nicht nur der
  Delete-Test, auch Passwort-Änderung, da "sofort neu einloggen" explizit als
  plausible Race genannt wurde): nach dem jeweiligen Request wird über
  `migrated_engine.connect()` (eine zweite, unabhängige Verbindung) zurück-
  gelesen. Beide Tests sind selbstreinigend — Kontolöschung entfernt alles
  kaskadierend, und die Passwort-Änderung hinterlässt nur den erwarteten
  geänderten Zustand des ohnehin für den Test erstellten Kontos, kein Leck
  in andere Tests.
- Die übrigen 16 der 17 Endpunkt-Fixes bekommen KEINEN eigenen neuen
  "zweite Verbindung"-Test — sie werden durch ihre bestehende funktionale
  Testsuite (unverändertes Verhalten, nur anderer Commit-Zeitpunkt) und durch
  Code-Review abgedeckt, nicht durch 16 weitere aufwendige Durability-Tests.

## Zwei kleine, unabhängige Datenfixe (Punkt 4 und 5 dieses Specs)

**`find_previous_edition`s Edition-String-Vergleich** (`core/src/normly_core/graph/postgres/repositories.py:635-661`):
aktuell ein reiner `edition < before_edition`-Stringvergleich, der nur
funktioniert, weil der einzige Erzeuger dieses Felds (der DGUV-Adapter)
immer ISO-8601-Daten liefert. Keine Absicherung gegen ein künftiges Format.
**Entscheidung: nur dokumentieren**, kein Laufzeit-Guard — bei aktuell genau
einem Erzeuger wäre eine Validierung für ein hypothetisches künftiges
Adapter-Format verfrühtes YAGNI. Fix: ein klarer Docstring-Zusatz an
`find_previous_edition` UND am `edition`-Feld der `DocumentDesignation`-
Domain-Klasse (`core/src/normly_core/graph/domain.py`), der die Annahme
explizit macht — jeder künftige Adapter, der `edition` setzt, muss dort
draufstoßen.

**`rights_notification_baseline.updated_at` ohne `onupdate`**
(`core/src/normly_core/graph/postgres/orm.py:629-631`): die Spalte bekommt
nur beim INSERT einen Wert, nie bei nachfolgenden Upserts (das Modell wird
per Merge-on-Conflict aktualisiert, siehe Klassen-Docstring). Fix: ein
`onupdate=sa.func.now()`-Zusatz zur bestehenden `mapped_column`-Definition,
keine Migration nötig (kein Schema-Wechsel, nur ein anderes
Anwendungsverhalten beim UPDATE).

## Testing

- Alle 17 Commit-Timing-Fixes: bestehende funktionale Tests jedes
  betroffenen Endpunkts laufen unverändert durch (Verhalten ändert sich
  nicht sichtbar).
- Zwei neue "echte zweite Verbindung"-Tests (Kontolöschung — Ersatz für den
  bestehenden, unwirksamen Test; Passwort-Änderung — neu) beweisen echte
  Durability über eine unabhängige Verbindung (nicht die ursprüngliche
  Timing-Race-Eigenschaft, die nur ein Live-Server-Setup zeigen könnte —
  siehe Korrektur oben).
- Der Edition-Docstring-Fix: keine neue Testpflicht (reine Dokumentation),
  aber die bestehende Testsuite für `find_previous_edition` muss weiter
  grün bleiben.
- Der `updated_at`-Fix: ein neuer, kleiner Test, der zwei Upserts hintereinander
  durchführt und bestätigt, dass sich `updated_at` beim zweiten wirklich
  ändert (nicht nur `created_at`).

## Globale Leitplanken

- DCO `Signed-off-by` (`git commit -s`), Conventional Commits, separater
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`-Trailer.
- Keine Verhaltensänderung außer dem Commit-Zeitpunkt bei den 17
  Endpunkt-Fixes — keine neuen Features, keine API-Vertragsänderungen.
- `accounts/` für die Commit-Timing-Fixes und die Testhärtung; `core/` für
  die zwei kleinen Datenfixe — unabhängige Bereiche, ein gemeinsamer Plan,
  da alle vier Punkte gleich risikoarm/mechanisch sind.
- Kein Push/PR/Merge ohne explizite Rückfrage vorher (STACKIT-CI-Läufe sind
  kostenpflichtig, kein funktionierendes Cancel). Direkter Push auf `main`
  ist ausgeschlossen — auch nicht als lokaler Merge, der anschließend
  gepusht wird (siehe die entsprechende Lektion aus dem vorherigen
  Teilprojekt dieser Session).
