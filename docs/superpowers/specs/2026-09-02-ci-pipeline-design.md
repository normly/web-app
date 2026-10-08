# Design: CI/CD-Pipeline (Testausführung als Merge-Gate)

**Nachtrag 2026-09-05 (ADR-019):** Der Push-Mirror STACKIT→GitHub, den
dieser Spec unten als Ziel/Architektur/Aktivierungsschritt beschreibt, wird
**nicht** eingerichtet — GitHub entfällt als Ziel für jede künftige
Automatisierung. Die betroffenen Abschnitte bleiben unten stehen, um die
damalige Entscheidungsgrundlage nachvollziehbar zu halten, sind aber als
überholt zu lesen; siehe ADR-019 für die Begründung.

## Kontext

REQ-BUILD-002 verlangt STACKIT Pipelines (Forgejo Actions) als Build-/Test-
Infrastruktur, REQ-BUILD-003 verlangt automatisierte Qualitätssicherung als
Merge-Voraussetzung, REQ-GIT-004 verlangt eine erfolgreiche Pipeline als
Bedingung für jeden Merge Request. Bisher existiert im Repository **keine**
CI-Konfiguration — jedes der fünf Pakete (`accounts`, `api`, `chat`, `core`,
Python; `frontend`, Next.js) hat eine eigene, lokal laufende Testsuite, aber
nichts führt sie automatisiert aus. Mehrere frühere Design-Dokumente
(`2026-08-30-docling-migration-design.md`, "Offene Punkte") benennen das
bereits als Lücke: der einzige automatisierte Nachweis der
"kein Laufzeit-Netzwerkzugriff auf Modellquellen"-Vorgabe läuft mangels CI
nirgends.

Ausgewählt in Rücksprache mit dem Auftraggeber gegenüber zwei Alternativen
(REQ-PIPE-007 Identitätsauflösungs-Prüfoberfläche; eine weitere
BAuA-Folgeaufgabe) — als die am breitesten load-bearing Lücke: sie betrifft
jedes Paket und jeden künftigen Merge, nicht nur eine einzelne Quelle oder
einen einzelnen Anwendungsfall.

**Voraussetzung, während dieses Designs neu geschaffen:** Bis zu diesem
Zeitpunkt existierte für dieses Projekt keine erreichbare STACKIT-Git/
Forgejo-Instanz — nur der GitHub-Spiegel (`origin`). Der Auftraggeber hat
während der Brainstorming-Sitzung eine Organisation und ein Repository
angelegt (`https://normly.git.onstackit.cloud/jwokittel/normly-webapp`,
lokal als Remote `stackit` eingerichtet, HTTPS mit Personal-Access-Token
über einen Credential-Helper — SSH auf Port 22 zu dieser Instanz ist von der
Entwicklungsumgebung aus nicht erreichbar, obwohl SSH zu GitHub und HTTPS zur
Instanz funktionieren; vermutlich bietet das Managed-Forgejo-Angebot keinen
öffentlichen Git-über-SSH-Zugang, die offiziellen STACKIT-Docs zeigen nur
HTTPS-Klon-Beispiele). Ein Runner für Forgejo Actions ist laut Auftraggeber
bereits registriert. Details siehe `reference_stackit_git`-Notiz.

**REQ-GIT-001/002 sind damit aktuell nicht erfüllt** — STACKIT Git ist noch
nicht die führende Plattform (aktuell werden beide Remotes unabhängig von
Hand bespielt, kein automatischer Mirror in beide Richtungen). Auf
ausdrücklichen Wunsch des Auftraggebers holt dieses Teilprojekt den
zentralen technischen Teil davon bereits hier nach: einen automatisierten
Push-Mirror von STACKIT Git (führend) nach GitHub (Beitragsfassade) nach
jedem Merge — das konkrete Akzeptanzkriterium aus REQ-GIT-002. Was davon
bewusst *nicht* mit erledigt wird, steht unter Nicht-Ziele.

## Ziel dieses Teilprojekts

- Eine Forgejo-Actions-Pipeline (`.forgejo/workflows/ci.yml`), die bei jedem
  Pull Request gegen `main` und bei jedem Push die Testsuiten aller fünf
  Pakete ausführt.
- Jedes Paket als eigener, unabhängiger Job — eigener Status pro Paket in
  der MR-Ansicht, ein Fehlschlag blockt nicht die Rückmeldung der anderen.
- Live gegen die neue STACKIT-Instanz verifiziert (Test-Branch, echter
  Pipeline-Lauf) — nicht nur "blind" geschriebenes YAML.
- Dokumentierte Anleitung zur einmaligen Aktivierung des Branch-Schutzes auf
  `main`, damit die Pipeline tatsächlich zum Merge-Gate wird (REQ-GIT-004).
- Ein automatisierter Push-Mirror von STACKIT Git nach GitHub, sodass
  STACKIT Git nach jedem Merge auf `main` den GitHub-Spiegel selbstständig
  aktuell hält (REQ-GIT-001/002) — kein manuelles Doppel-Pushen mehr wie
  während dieser Brainstorming-Sitzung.

## Nicht-Ziele

- **Keine Beitragsfassaden-Automatisierung und keine DCO-Prüfung auf
  GitHub-Seite** (Teil von REQ-GIT-002, aber nicht dessen Mirror-
  Akzeptanzkriterium). Der Weg "externer Pull Request auf GitHub → landet
  geprüft in der STACKIT-Pipeline" (REQ-GIT-002-Abnahmekriterium) bleibt
  offen — dieses Teilprojekt baut nur die *ausgehende* Spiegelung
  STACKIT→GitHub, nicht die Rückführung eingehender externer Beiträge.
  Eigene, spätere Aufgabe.
- **Kein Linting, kein Security-Scanning.** REQ-BUILD-003 verlangt beides,
  aber aktuell ist in keinem Paket ein Linter oder Scan-Tool konfiguriert.
  Werkzeugwahl und das Bereinigen bestehender Verstöße sind eigene
  Entscheidungen, die nicht nebenbei beim Verdrahten der Pipeline getroffen
  werden sollen (bewusst mit dem Auftraggeber so entschieden). Folgeaufgabe.
- **Keine Playwright-E2E-Tests in dieser Pipeline.** Die bräuchten eine
  laufende Anwendung samt Datenbank und Browser-Binaries — deutlich
  schwerere Einrichtung als die vorhandenen Unit-/Integrationstests. Nur
  `npm test` (Vitest) läuft für `frontend`.
- **Kein Docker-Image-Build, keine Auslieferung.** Es existiert noch kein
  einziges `Dockerfile` im Repository — REQ-DIST-004 (signierte,
  versionierte Images) ist ein eigenes, nachgelagertes Teilprojekt, das
  zuerst Dockerfiles je Service braucht.
- **Kein Dependency-Caching in v1.** Marketplace-Actions wie
  `actions/cache@vX` laden ihren eigenen Code standardmäßig von GitHub
  nach — dieselbe Kategorie Risiko wie unten unter "Architektur"
  beschrieben. Ob die STACKIT-Instanz einen Actions-Marketplace-Mirror
  betreibt, wurde nicht geprüft. Bis das geklärt ist, bleibt jeder
  Pipeline-Lauf ein kalter Dependency-Install — korrekt, aber langsam
  (insbesondere `core` mit Docling/Torch, ca. 5,6 GB installierte
  Abhängigkeiten). Optimierung ist eine spätere, bewusst nachgelagerte
  Aufgabe.
- **Keine automatisierte Branch-Schutz-Konfiguration.** Das Aktivieren
  (Pull-Request-Pflicht, Pflicht-Status-Checks) ist ein einmaliger Klick in
  den Forgejo-Repo-Einstellungen, kein wiederkehrender Vorgang — wird als
  Anleitung dokumentiert, nicht als Automatisierung gebaut.

## Architektur

### Entscheidung: keine GitHub-Actions-Marketplace-Actions

Forgejo Actions ist weitgehend GitHub-Actions-kompatibel (`uses: owner/repo@ref`
funktioniert syntaktisch identisch) — genau das macht es riskant für die
"keine US-Dienste im Betrieb"-Vorgabe aus CLAUDE.md: `uses: actions/checkout@v4`
lädt den referenzierten Code standardmäßig zur Laufzeit von `github.com`
nach, sofern die Forgejo-Instanz keinen eigenen Actions-Mirror/-Proxy
betreibt. Ob STACKITs Managed-Forgejo-Angebot das tut, wurde für dieses
Design nicht geprüft (kein Login möglich, keine Dokumentation dazu
gefunden). Statt das stillschweigend anzunehmen, verzichtet diese Pipeline
komplett auf `uses:`-Schritte: jeder Job läuft in einem vorgegebenen
Container-Image (`python:3.12` bzw. `node:20`) und besteht ausschließlich
aus `run:`-Shell-Schritten (`git checkout` ist bei Forgejo Actions ohnehin
implizit vorhanden, kein separater Checkout-Schritt nötig — zu verifizieren
beim ersten echten Lauf, siehe Testkonzept). Das einzige verbleibende
Laufzeit-Netzwerk ist PyPI/npm — bereits heute akzeptierter Teil jedes
Build-Vorgangs, keine neue Kategorie.

### Jobs

Fünf unabhängige Jobs in einer Datei, `.forgejo/workflows/ci.yml`:

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:

jobs:
  test-accounts:
    runs-on: docker  # Label gegen die echte Runner-Registrierung prüfen, siehe Offene Punkte
    container: python:3.12
    steps:
      - run: cd accounts && pip install -e .[dev] && pytest

  test-api:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd api && pip install -e .[dev] && pytest

  test-chat:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd chat && pip install -e .[dev] && pytest

  test-core:
    runs-on: docker
    container: python:3.12
    steps:
      - run: cd core && pip install -e .[dev] && pytest

  test-frontend:
    runs-on: docker
    container: node:20
    steps:
      - run: cd frontend && npm ci && npm test
```

(Illustrativ — die exakte Syntax für den impliziten Checkout und das
`container:`-Schlüsselwort wird beim ersten echten Lauf gegen die Instanz
verifiziert, siehe Testkonzept; falls Forgejo Actions hier von der
GitHub-Actions-Syntax abweicht, wird das YAML entsprechend angepasst, ohne
an der Architekturentscheidung "keine Marketplace-Actions" zu rütteln.)

### STACKIT Git als führende Plattform: Push-Mirror nach GitHub

Für REQ-GIT-002s Akzeptanzkriterium "automatisierter Push-Mirror nach jedem
Merge" braucht es **keinen** Forgejo-Actions-Job. Forgejo bietet dafür eine
eingebaute Repo-Funktion: unter Settings → Repository → Mirror Settings →
Push Mirror lässt sich ein Ziel-Repository (die GitHub-URL) samt
Zugangsdaten (ein GitHub Personal Access Token mit Schreibrecht nur auf
dieses Repo) hinterlegen. Verifiziert gegen die Forgejo-Dokumentation:
Forgejo synchronisiert danach automatisch bei jedem Push auf das
STACKIT-Repo, nicht nur auf einem Zeitintervall — genau das geforderte
Verhalten, ganz ohne eigene Pipeline-Logik. Das Token wird von Forgejos
eigener Zugangsdaten-Verwaltung gehalten, taucht nirgends im Repository oder
in `ci.yml` auf — passt zu REQ-INST-003 ("Zugangsdaten... ausschließlich im
[Secrets Manager]").

Praktisch bedeutet das: `main` auf STACKIT Git wird ab Einrichtung dieses
Mirrors zur einzigen Stelle, an der tatsächlich gemergt werden muss —
GitHub `main` wird ab dann ausschließlich per Mirror beschrieben, nie mehr
von Hand gepusht (der direkte GitHub-Push während dieser Sitzung war eine
bewusste, einmalige Ausnahme vor Einrichtung dieses Mirrors, siehe
Gesprächsverlauf, nicht der künftige Normalfall).

### Voraussetzung: Docker-in-Docker auf dem Runner

Alle vier Python-Pakete nutzen `testcontainers[postgres]` — die Tests
starten selbst einen echten Postgres-Container. Der registrierte Runner
muss also Zugriff auf einen Docker-Daemon haben (vom Auftraggeber
bestätigt). Ohne das schlägt jeder Python-Job beim ersten
`testcontainers`-Aufruf fehl — ein klarer, sofort sichtbarer Fehler, kein
Sonderfall, den diese Pipeline gesondert behandeln müsste.

## Komponenten

| Datei | Änderung |
|---|---|
| `.forgejo/workflows/ci.yml` | **Neu.** Fünf Jobs wie oben beschrieben. |

Keine weiteren Dateien — diese Pipeline führt ausschließlich bereits
vorhandene Testbefehle aus, ohne bestehenden Code zu ändern.

## Datenfluss

Push oder Pull Request gegen `main` auf der STACKIT-Instanz → Forgejo
Actions löst `ci.yml` aus → fünf Jobs starten parallel auf dem registrierten
Runner, jeder in seinem eigenen Container → jeder Job installiert sein
Paket frisch (`pip install -e .[dev]` bzw. `npm ci`) und führt dessen
Testsuite aus → Erfolg/Fehlschlag jedes Jobs erscheint als eigener Status-
Check am Pull Request.

## Fehlerbehandlung

- Ein fehlschlagendes Paket blockt nur seinen eigenen Status-Check — die
  anderen vier Jobs laufen unabhängig durch (kein `needs:`-Verkettung
  zwischen ihnen, da die Pakete keine Build-Reihenfolge-Abhängigkeit
  zueinander haben, die die Pipeline abbilden müsste).
- Fehlender Docker-Zugriff auf dem Runner äußert sich als sofortiger,
  eindeutiger `testcontainers`-Fehler in den betroffenen vier Python-Jobs —
  keine gesonderte Behandlung nötig, das ist ein Infrastruktur-
  Voraussetzungsfehler, kein Pipeline-Logikfehler.

## Testkonzept

- Nach dem Schreiben der `ci.yml`: ein Test-Branch auf die STACKIT-Instanz
  pushen, einen Merge Request gegen `main` dort öffnen, den echten
  Pipeline-Lauf beobachten. Das ist der eigentliche Nachweis — nicht nur,
  dass die YAML-Syntax plausibel aussieht, sondern dass sie auf dem
  konkreten Runner tatsächlich läuft (Container-Start, impliziter Checkout,
  `testcontainers`-Postgres-Start, alle fünf Testsuiten grün).
- Bewusst zunächst nur ein Smoke-Test-Lauf mit unverändertem Code (alle
  Suiten sollten grün sein, siehe letzter bekannter Stand: 250 passed, 1
  skipped in `core`, entsprechend für die anderen Pakete) — kein
  künstlicher Fehlerfall nötig, um zu zeigen, dass ein roter Job den
  Gesamtstatus rot färbt: das ist Forgejo-Actions-Standardverhalten, kein
  selbst gebautes Feature dieser Pipeline.

## Bezug zu Requirements und ADRs

| Requirement | Bezug |
|---|---|
| REQ-BUILD-002 | Pipeline läuft auf STACKIT Pipelines (Forgejo Actions), keine US-SaaS-CI, keine Marketplace-Action-Nachladung von GitHub zur Laufzeit. |
| REQ-BUILD-003 | Fehlgeschlagene Tests verhindern (nach Aktivierung des Branch-Schutzes) den Merge — Linting/Security-Anteil bewusst als Folgeaufgabe vertagt, siehe Nicht-Ziele. |
| REQ-GIT-004 | Wird durch diese Pipeline erst *erfüllbar* (technische Voraussetzung); die eigentliche Durchsetzung (Merge-Blockade bei rotem Status) ist der dokumentierte manuelle Aktivierungsschritt unten. |
| REQ-GIT-001 | Erfüllt — STACKIT Git ist mit dieser Pipeline die führende Plattform für Build/Test. |
| REQ-GIT-002 | **Entfällt (ADR-019, 2026-09-05).** Push-Mirror wird nicht eingerichtet; kein GitHub als Beitragsfassade mehr. Requirement in `docs/srs/03-anforderungen.md` entsprechend als überholt markiert. |
| REQ-INST-002, REQ-DIST-004 | Unberührt — kein Deployment, kein Image-Build in diesem Teilprojekt. |

## Aktivierungsschritte nach Implementierung (manuell, einmalig)

**Überholt durch ADR-019 (2026-09-05):** Schritt 1 (Push-Mirror) entfällt —
GitHub wird nicht mehr automatisiert bespielt. Nur noch eine
Repo-Einstellung auf STACKIT Git bleibt offen:

1. **Branch-Schutz für `main`** — Pull Request erforderlich, direkte Pushes
   unterbunden, **nur die vier grünen Checks** (`test-accounts`, `test-api`,
   `test-chat`, `test-frontend`) als Pflicht-Checks markiert. **`test-core`
   bewusst NICHT als Pflicht-Check**, solange die weiter unten dokumentierte
   Docling-Kaltstart-Fehlfunktion nicht behoben ist — siehe "Offene Punkte".
   Erst danach ist REQ-GIT-004 tatsächlich durchgesetzt, nicht nur technisch
   möglich. Sollte erst erfolgen, nachdem die Pipeline (Testkonzept)
   nachweislich grün läuft (bis auf das akzeptierte `test-core`) — sonst
   blockiert der eigene erste Merge sich selbst.

## Offene Punkte / Folgearbeiten

- **Exaktes Runner-Label ungeklärt.** `runs-on: docker` oben ist ein
  Platzhalter — welches Label der registrierte Runner tatsächlich trägt,
  wird beim ersten echten Pipeline-Lauf sichtbar (bzw. der Auftraggeber
  kann es vorab in den Runner-Einstellungen nachsehen) und vor dem
  finalen Commit korrigiert.
- **Actions-Marketplace-Mirror-Status ungeklärt.** Falls sich herausstellt,
  dass die STACKIT-Instanz tatsächlich einen eigenen Mirror/Proxy für
  gängige Actions betreibt, kann diese Entscheidung (kein `uses:`) in einer
  späteren Iteration bewusst gelockert werden — nicht in diesem Durchgang,
  da unverifiziert.
- ~~**Externe Beitragsannahme über GitHub**~~ — **hinfällig (ADR-019).**
  REQ-GIT-002 entfällt; keine Beitragsfassade auf GitHub mehr geplant.
- **Linting, Security-Scanning, Dependency-Caching, Docker-Image-Build,
  Playwright-E2E** — alle bewusst vertagt, siehe jeweils Nicht-Ziele.
- **`test-core` wird auf jedem Lauf rot und ist bewusst akzeptiert (nicht
  verborgen, ignoriert oder übersprungen).** Grund: Docling's DGUV/BAuA-
  Titelerkennung (`raw_title` wird `None` statt echter Titel) ist fragil
  gegenüber einem *frischen* HuggingFace-Modell-Download — reproduzierbar
  via `docker run python:3.12` mit völlig frischer pip-Installation und
  keinem vorgefertigten Modell-Cache. Tests passen lokal in dieser
  Projektausgabe nur, weil diesen Checkout gecachte HF-Modelle aus
  früherer Arbeit hat, daher wird ein echtes Kalt-Start-Extraction nie
  tatsächlich geübt. Jede wirklich frische Umgebung (neue Dev-Maschine,
  neugebauter CI-Runner, frischer Produktions-Container) wird
  wahrscheinlich denselben Fehlschlag treffen. Reparatur ist eigene
  Folgeaufgabe (Docling-Modellversion-Sensibilität in `DguvAdapter` /
  `BauaAdapter` debuggen), nicht Teil dieses CI-Teilprojekts. `test-core`
  wird bewusst sichtbar/rot gehalten und ist *nicht* als erforderlicher
  Branch-Schutz-Check markiert, bis das gesondert untersucht und behoben
  ist.
  **Nachtrag 2026-10-08: geklärt und behoben.** Ursache war nicht die
  Modellversion, sondern fehlende Systemschriften im Container: die
  Fixture bettet Helvetica nicht ein, pdfium rendert die Seite für das
  Layout-Modell mit einer Ersatzschrift, und das Modell stuft die
  Titelzeile als `page_header` (FURNITURE) ein. `fonts-liberation` im
  `test-core`-Job und im Python-Image behebt es; Nachweis und
  Einzelvariablen-Tests in der TP2-Spec
  (`2026-10-08-tp2-image-pipeline-design.md`, Folgearbeiten).
- **`tests/test_structural_end_to_end.py` in `chat` ist von CI ausgeschlossen
  (nicht fehlerhaft, aber Fixture-Abhängigkeit mit CI inkompatibel).** Diese
  4 Tests spawnen Sibling-Pakete (`api`, `accounts`) via deren lokal-
  dev-only `.venv/bin/uvicorn`-Konvention (siehe
  `chat/tests/conftest.py:98-121`), die im frischen CI-Container nicht
  existiert (dort werden keine per-Package-venvs gebaut, nur frische
  pip-Installation). Folgeaufgabe: Das Fixture-Setup abstrahieren, um
  CI-native Alternativen (z. B. TestClient-Übergabe statt prozess-
  Spawning) zu unterstützen.
- **Behoben (2026-09-05, finale Whole-Branch-Review):** `on: push:` hatte
  keinen Branch-Filter — ein Push auf einen Branch mit offenem Pull Request
  löste dadurch gleichzeitig einen `push`- und einen `pull_request`-Lauf auf
  demselben geteilten Runner aus (empirisch als Ursache eines
  `test-chat`-Fehlschlags durch Ressourcen-Konkurrenz bestätigt, kein echter
  Regressionsfehler). Jetzt `push: branches: [main]` — ein Feature-Branch
  löst nur noch den `pull_request`-Lauf aus. Zusätzlich `timeout-minutes: 30`
  auf jedem Job, damit ein hängender Job nicht die gesamte Runner-Kapazität
  bis zum Runner-Standard-Timeout blockiert.
