# Design: Dokumentations-Site mit Zensical

## Kontext

Ein funktionierendes mkdocs + mkdocstrings + Material-Theme-Setup für die
Code-Referenzdokumentation existiert bereits auf dem Branch
`claude/normly-documentation-structure-3zs7i0` (Commit `7f8a1ea`,
27.08.2026) — lokal und auf GitHub, aber bewusst nicht gemergt. Der Branch
ist gegen aktuelles `main` ca. 27.9k Zeilen im Rückstand (er kennt z. B.
`frontend/tests/` noch nicht) und war laut eigenem Commit selbst
unvollständig (OpenAPI-Referenzgenerierung und STACKIT/Forgejo-
Pipeline-Anbindung fehlten).

Zwischenzeitlich hat das mkdocs-material-Team [Zensical](https://zensical.org/)
als Nachfolgeprojekt angekündigt; Material for MkDocs ist seit Anfang 2026
im Wartungsmodus, neue Feature-Arbeit fließt in Zensical. Der
mkdocstrings-Autor ist Teil des Zensical-Teams; Zensical unterstützt
mkdocstrings bereits. Zensical hat zusätzlich eine Kompatibilitätsschicht,
die bestehende `mkdocs.yml`-Konfigurationen einliest — die ist aber für die
Migration *bestehender* mkdocs-Projekte gedacht. Da hier neu aufgebaut
wird, nutzt dieses Projekt die native `zensical.toml`-Konfiguration statt
der Kompatibilitätsschicht.

**Entscheidung (bereits getroffen, 01.09.2026):** Der alte Branch wird
nicht reaktiviert, gemergt oder rebased. Stattdessen wird die
Dokumentations-Site frisch gegen aktuelles `main` mit Zensical aufgebaut.
Der alte Branch dient nur als Ideen- und Textquelle.

Auf `docs/adr/` und `docs/srs/` liegen bereits aktuelle, gepflegte Inhalte
(ein konsolidiertes ADR-Dokument statt nummerierter Einzeldateien wie im
alten Branch; die SRS-Kapitel 01–06 einzeln). Diese müssen nicht neu
geschrieben werden, nur in die Site-Navigation eingehängt werden.

Auf der Website (separates Repo `normly-website`) verweisen die
"Dokumentation"/"API-Referenz"-Links auf der Startseite aktuell auf
Platzhalter — dieses Projekt löst diese Platzhalter ein.

## Ziel dieses Projekts

1. Eine mit Zensical gebaute, statische Dokumentations-Site mit derselben
   Struktur wie der alte Branch: Home, Guide, Concepts, Architecture
   decisions, Requirements (SRS), Code-Referenz, Glossar.
2. Guide- und Concepts-Texte aus dem alten Branch als Basis übernommen,
   aber Zeile für Zeile gegen aktuelles `main` (README.md, CLAUDE.md,
   `docs/adr/README.md`) geprüft und korrigiert.
3. `docs/adr/` und `docs/srs/` unverändert in die Nav eingehängt.
4. Code-Referenz per mkdocstrings aus den Docstrings von `core`, `api`,
   `accounts`, `chat` generiert — eine Seite pro Package, wie im alten
   Branch.
5. Ein neuer CI-Job (`test-docs` in `.forgejo/workflows/ci.yml`), der die
   Site im Strict-Modus baut, damit kaputte Querverweise oder fehlende
   Docstring-Ziele den Job fehlschlagen lassen statt unbemerkt zu bleiben.
6. Ein als Entwurf markierter, nicht in CI eingebundener Dockerfile-Vorschlag
   als Anhang dieser Spec, für ein späteres eigenständiges
   Container/Deployment-Teilprojekt.

## Nicht-Ziele

- **Kein Container-Image, kein Registry-Push, keine Signierung.** Im Repo
  existiert aktuell für keinen Service ein Dockerfile — das wäre
  Infrastrukturarbeit, die über dieses Projekt hinausgeht und eigene
  Entscheidungen braucht (Basis-Image, Signierung, Versionierung des
  Doku-Standes analog ADR-010). Der CI-Job dieses Projekts baut die Site
  nur und prüft sie; er veröffentlicht nichts.
- **Keine Mehrsprachigkeit.** CLAUDE.md sieht sie langfristig vor, aber
  die Site startet einsprachig Deutsch, wie der alte Branch.
- **Kein OpenAPI-Referenz-Rendering.** War schon im alten Branch
  Folgearbeit und bleibt es.
- **Keine neuen ADR-/SRS-Inhalte.** Nur Verlinkung des Bestehenden.

## Architektur

Root-level `zensical.toml` mit `docs_dir = "docs"`. Das ist bewusst
derselbe Ordner, in dem `docs/adr/` und `docs/srs/` bereits liegen — kein
Kopieren nötig.

```
docs/
  index.md                    # neu (Basis: alter Branch, geprüft)
  guide/
    getting-started.md        # neu (Basis: alter Branch, geprüft)
    self-hosting.md           # neu (Basis: alter Branch, geprüft)
  concepts/
    normen-graph.md           # neu (Basis: alter Branch, geprüft)
    lizenzmodell.md           # neu (Basis: alter Branch, geprüft)
  reference/
    core.md                    # neu, mkdocstrings-Stub: ::: normly_core
    api.md                     # neu, mkdocstrings-Stub: ::: normly_api
    accounts.md                # neu, mkdocstrings-Stub: ::: normly_accounts
    chat.md                    # neu, mkdocstrings-Stub: ::: normly_chat
  glossary.md                 # neu (Basis: alter Branch, geprüft)
  adr/README.md               # bereits vorhanden, unverändert
  srs/*.md                    # bereits vorhanden, unverändert
  superpowers/                # bereits vorhanden, von der Nav ausgeschlossen
zensical.toml                 # neu, root-level
```

`docs/superpowers/` (interne Pläne/Specs, inkl. dieser Datei) wird nicht in
`nav` eingetragen. Zensical hat aktuell **keine** Exclude-Option (laut
eigener Kompatibilitätsliste sind `exclude_docs`, `not_in_nav` und
`draft_docs` "not yet supported") — ob nicht in `nav` gelistete Dateien
unter `docs_dir` trotzdem mitgebaut und unter ihrer Pfad-URL erreichbar
sind, wird in der ersten Implementierungsaufgabe per Build-Probe geklärt.
Falls ja: bewusst akzeptiert, kein Workaround (z. B. `docs_dir` auf einen
Unterordner verengen und `adr/`/`srs/` dorthin duplizieren) — das gesamte
Repository inklusive `docs/superpowers/` ist über STACKIT Git ohnehin
öffentlich einsehbar, eine zusätzliche unverlinkte Seite auf der Doku-Site
ist kein neues Datenschutz- oder Geheimhaltungsproblem, nur potenziell
unaufgeräumt. Wird nur zum Thema, wenn es tatsächlich stört.

### Code-Referenz

Eine Seite pro Package mit `show_submodules: true`, wie im alten Branch.
Nach dem bekannten mkdocstrings-Zensical-Format:

```toml
[project.plugins.mkdocstrings.handlers.python]
paths = ["core/src", "api/src", "accounts/src", "chat/src"]

[project.plugins.mkdocstrings.handlers.python.options]
show_submodules = true
show_source = true
docstring_style = "google"
```

Keine feinere Granularität (eine Seite pro Modul) — bei der aktuellen
Package-Größe unnötige Komplexität (YAGNI). Kann nachgezogen werden, wenn
einzelne Package-Seiten unübersichtlich werden.

mkdocstrings' Python-Handler **importiert** die Module tatsächlich, um
Docstrings zu extrahieren (reines Pfad-Referenzieren reicht nicht). Das
heißt, alle vier Packages müssen zur Build-Zeit installiert sein, samt
ihrer Laufzeitabhängigkeiten (SQLAlchemy, FastAPI, Docling,
sentence-transformers, …).

### Fonts: kein Google Fonts

Das Material-Theme lädt standardmäßig Web-Fonts von Google Fonts — auch
beim Build ein Aufruf an einen US-Dienst, verboten laut CLAUDE.md ("Keine
US-Dienste für Betrieb, **Build**, Daten, Secrets oder Deployment"). Der
genaue Theme-Schlüssel zum Abschalten ist zum Zeitpunkt dieser Spec nicht
verifiziert; verbindlich ist das Ergebnis, nicht der Weg dahin: der
gebaute `site/`-Ordner darf **keine** Referenz auf `fonts.googleapis.com`
oder `fonts.gstatic.com` enthalten (per Grep geprüft, siehe Plan). System-
Font-Stack verwenden — konsistent mit dem Frontend, das aus demselben
Grund ebenfalls keine Google Fonts lädt.

## Inhalte im Detail

| Seite | Vorgehen |
|---|---|
| `index.md` | Text aus altem Branch übernehmen, dann gegen `README.md` prüfen. **Muss korrigiert werden:** GitHub-Link (`github.com/sn4kez/normly-app`) raus — ADR-019 friert die GitHub-Fassade ein, keine neuen Verweise darauf. |
| `guide/getting-started.md` | Text aus altem Branch übernehmen, gegen aktuellen Stand prüfen. Ehrlich bleiben: weiterhin keine lauffähige Version, kein Public-Access — Platzhalter-Charakter wo zutreffend beibehalten. |
| `guide/self-hosting.md` | Text aus altem Branch übernehmen, gegen aktuelle Compose-/Deployment-Doku prüfen (`ADR-010`). |
| `concepts/normen-graph.md` | Gegen ADR-008 ("Graph zuerst") in `docs/adr/README.md` prüfen. |
| `concepts/lizenzmodell.md` | Gegen ADR-002/-011/-014 und die aktuelle Kategorien-Tabelle (A–D) aus CLAUDE.md prüfen. |
| `glossary.md` | Text aus altem Branch übernehmen, auf neue Begriffe seit 27.08. prüfen (z. B. Normtracker-Begriffe). |
| `adr/README.md`, `srs/*.md` | Unverändert, nur in `nav:` eintragen. |

## CI

Neuer Job `test-docs` in `.forgejo/workflows/ci.yml`, analog zu den
bestehenden Jobs:

```yaml
test-docs:
  runs-on: stackit-docker
  container: python:3.12
  timeout-minutes: 30
  steps:
    - run: |
        # (Checkout wie in den anderen Jobs)
    - run: apt-get update && apt-get install -y --no-install-recommends libgl1 && rm -rf /var/lib/apt/lists/*
    - run: pip install -e core -e api -e accounts -e chat zensical
    - run: zensical build --strict
```

`libgl1` wird gebraucht, weil das Importieren von `normly_core` Docling
mitzieht (siehe `test-core`-Job). `--strict` lässt den Job fehlschlagen bei
kaputten internen Links, fehlenden Docstring-Zielen oder Warnungen — Doku-
Rot fällt so beim nächsten PR auf, nicht erst wenn jemand die Site liest.

Paketname (`pip install zensical`) und Befehl (`zensical build --strict`)
sind recherchiert (siehe [zensical.org/docs/get-started](https://zensical.org/docs/get-started/)),
aber nicht in diesem Repo getestet — die erste Implementierungsaufgabe
verifiziert das gegen die dann aktuelle Zensical-Version, bevor der Rest
des Projekts darauf aufbaut.

## Fehlerbehandlung

- `--strict`-Build in CI (siehe oben) ist die einzige Prüfung. Keine
  weiteren automatisierten Tests nötig — eine Doku-Site hat kein
  Laufzeitverhalten jenseits von "baut sie fehlerfrei".
- Kein Linting von Prosa-Inhalten (Rechtschreibung o. Ä.) — außerhalb des
  Scopes.

## Anhang: Dockerfile-Entwurf (nicht Teil dieses Projekts)

Unverifizierter Vorschlag für ein späteres, eigenständiges
Container/Deployment-Teilprojekt. Nicht gebaut, nicht getestet, nicht in
CI eingebunden — dient nur als Startpunkt für diese Folgearbeit.

```dockerfile
# ENTWURF -- nicht verifiziert, nicht in CI eingebunden.
# Folgearbeit: Basis-Image-Wahl, Signierung, Versionierung klären (ADR-010).

FROM python:3.12-slim AS build
WORKDIR /site
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 \
    && rm -rf /var/lib/apt/lists/*
COPY core api accounts chat docs zensical.toml .
RUN pip install --no-cache-dir -e core -e api -e accounts -e chat zensical \
    && zensical build --strict --site-dir /site/dist

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY --from=build /site/dist /usr/share/nginx/html
```

Offene Fragen für den Folge-Task: Basis-Image über STACKIT-eigene
Spiegelung statt Docker Hub beziehen (nginxinc-Image liegt auf Docker Hub
— US-Dienst, gegen CLAUDE.md), Image-Signierung, Push-Ziel in der STACKIT
Container Registry, Versionierung des Doku-Standes.
