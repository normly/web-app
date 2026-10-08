# Design: Image-Pipeline (STACKIT-Deployment, Teilprojekt 2/4)

Stand: 2026-10-08 · Status: umgesetzt und live verifiziert (PR #14, Merge
ea70cc8, Release `v0.1.0`, 2026-10-08; Ergebnisse am Ende dieses Dokuments). Roadmap und Grundsatzentscheidungen E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.
Vorgänger: `docs/superpowers/specs/2026-10-01-tp1-containerisation-design.md`
(gemerged als PR #12, 2026-10-08).

## Ziel

Die fünf Container-Images aus TP1 werden nicht mehr nur auf der STACKIT-VM
gebaut, sondern zentral in GitHub Actions gebaut, signiert und mit
Versions-Tags in der GitHub Container Registry (GHCR) veröffentlicht
(REQ-DIST-004, REQ-GIT-005, ADR-010, ADR-021). Derselbe Git-Tag liefert
dasselbe Image: Abhängigkeiten, Basis-Images und Modellgewichte sind
festgeschrieben (REQ-BUILD-001).

Damit entsteht, was heute fehlt:

- **Rollback-Punkt.** Heute überschreibt jeder Build auf der VM
  `normly-api:local`; ein vorheriges Image gibt es nicht (REQ-INST-004
  verlangt es).
- **Self-Hosting ohne eigenen Build.** ADR-010 verspricht öffentlich
  beziehbare, signierte Images; `docs/guide/self-hosting.md` sagt heute
  „No published images yet".
- **Nachvollziehbarkeit.** Ein laufendes Image lässt sich Commit, Workflow
  und Signatur zuordnen.
- **Entlastung der VM.** Ein reiner Betriebsserver zieht fertige Images
  statt Quellcode, Build-Werkzeuge und rund 5 GB Build-Schicht vorzuhalten
  (Voraussetzung für die Verkleinerung aus TP1a).

Nicht Teil dieses Teilprojekts: die Umstellung der VM von „selbst bauen"
auf „Tag ziehen", Rollout- und Rollback-Skript, Signaturprüfung als
Pflichtschritt vor dem Start, Datenstand-Import (alles TP4). Das
Live-System auf `app.normly.ai` bleibt von TP2 unberührt.

## Entscheidungen des Nutzers (2026-10-08, nicht neu verhandeln)

### D1 — Signatur: cosign keyless über GitHub-OIDC

Jedes gepushte Image wird über seinen Digest mit cosign signiert. Der
Workflow erhält pro Lauf ein kurzlebiges Zertifikat von Sigstore (Fulcio),
die Signatur landet im Transparenzprotokoll (Rekor). Kein privater
Schlüssel wird je erzeugt, gespeichert oder rotiert. Das Zertifikat bindet
die Signatur an Repository, Workflow-Datei und Commit.

**Begründung des Nutzers:** Der Vertrauensanker — die öffentliche
Sigstore-Infrastruktur — wird von der **Linux Foundation betrieben, einer
Non-Profit-Organisation**. Das unterscheidet ihn qualitativ von den
kommerziellen US-Diensten in der Build-Kette, die ADR-021 für den freien
Kern erlaubt (GitHub Actions, GHCR). Eine weitere Abhängigkeit von einem
gemeinnützigen Betreiber wiegt leichter als die Schlüsselpflege der
Alternative.

**Verworfen:** eigenes cosign-Schlüsselpaar (privater Schlüssel als
GitHub-Secret, öffentlicher im Repo). Keine Sigstore-Abhängigkeit, dafür
Rotation, sichere Ablage außerhalb von GitHub und bei Schlüsselverlust
Neusignierung aller Images.

### D2 — Eine Version für alle fünf Images, Git-Tag als einzige Quelle

Ein Git-Tag `vX.Y.Z` erzeugt alle fünf Images aus demselben Commit mit
demselben Versions-Tag. Es gibt keine Version je Paket.

**Begründung des Nutzers:** Die Services sind nur in einer gemeinsamen
Kombination gegeneinander getestet; `api` und `chat` teilen sich sogar das
Basis-Image. Ein Rollback in TP4 heißt dann „alle Images auf 0.1.0", ein
Handgriff, und welche Kombination zusammen getestet wurde, ist am Tag
ablesbar. Die Versionsfelder in den vier `pyproject.toml` und in
`frontend/package.json` werden im Release-Commit von Hand auf denselben
Wert gesetzt; der Workflow bricht ab, wenn Tag und `core`-Version nicht
übereinstimmen.

**Verworfen:** eigene Version je Paket. Erlaubt, nur das Frontend neu zu
veröffentlichen, braucht aber je Release einen Tag je Paket, und die
getestete Kombination ist nicht mehr ablesbar.

**Erster Release-Tag:** `v0.1.0` auf den Stand nach dem Merge dieses
Teilprojekts, damit TP4 von Anfang an einen Rollback-Punkt hat.

### D3 — Gebaut wird nur bei Merge auf `main`, bei Release-Tags und manuell

Pull Requests lösen weiterhin nur die Test-Pipeline aus. Ein kaputtes
Dockerfile fällt erst nach dem Merge auf, aber laut und ohne Schaden:
`edge` bleibt auf dem letzten funktionierenden Stand, ein Release-Tag
schlägt sichtbar fehl.

**Begründung:** Zum Zeitpunkt der Entscheidung war das Repo privat, die
Organisation auf dem Free-Plan (2.000 Actions-Minuten im Monat); ein
voller Build dauert geschätzt 10 bis 15 Minuten. **Nachtrag 2026-10-08:**
Der Nutzer hat das Repository nach der Freigabe der Spec auf öffentlich
gestellt; Actions-Minuten sind damit unbegrenzt. Die Entscheidung bleibt
trotzdem bestehen: weniger Läufe heißt weniger Wartezeit je PR und
weniger Rauschen, und ein PR-Build ohne Push liefert ohnehin kein
Artefakt. Wiedervorlage, falls kaputte Dockerfiles auf `main` zum
wiederkehrenden Problem werden.

**Verworfen:** zusätzlicher Build ohne Push bei Pull Requests, die
Dockerfile, Compose oder Abhängigkeiten ändern. Fängt Build-Fehler vor dem
Merge, kostet aber je PR einen vollen Build, und ein Pfadfilter übersieht
Codeänderungen, die den Build trotzdem brechen.

### D4 — Reproduzierbarkeit vollständig in TP2

Alle drei aus TP1 übertragenen Punkte werden hier erledigt: Lock-Datei für
die Python-Abhängigkeiten, Torch nur aus dem CPU-Index, Modellgewichte mit
fester Revision in eigener Build-Stufe. Nicht vertagt.

## Bestandsaufnahme (2026-10-08, aus dem Repo abgelesen)

- `docker/python.Dockerfile`: eine Datei, Stufe `base` (python:3.12-slim,
  `core`-Abhängigkeiten per `pip install --extra-index-url` CPU-Torch,
  e5-Gewichte per `SentenceTransformer(...).save()`), darauf die Targets
  `api`, `chat`, `accounts`, `pipeline` (letzteres lädt zusätzlich die
  Docling-Modelle per `docling-tools models download`).
- `frontend/Dockerfile`: node:22-alpine, drei Stufen, `standalone`-Output.
- `compose.yaml`: alle Services mit `build:` und lokalem Tag
  (`normly-api:local` usw.); `migrate` und `pipeline` teilen sich
  `normly-pipeline:local`.
- `.github/workflows/ci.yml`: sechs Test-Jobs, je `pip install -e ../core
  -e .[dev]`; kein Image-Build.
- Kein Git-Tag im Repo; alle Pakete stehen auf `0.1.0`.
- Modellgewichte heute ohne feste Revision: e5 lädt `main`; Docling lädt
  das Layout-Modell `docling-project/docling-layout-heron` und dessen
  ONNX-Variante von `main`, die Tableformer-Modelle
  `docling-project/docling-models` per Tag `v2.3.0`. Die Download-CLI
  bietet keine Option zum Pinnen.
- Python-Abhängigkeiten nur als Bereiche in `pyproject.toml`; die drei
  Dienst-Pakete vermerken im Kommentar, dass die technische Absicherung
  gegen eine Auflösung von `normly-core` über einen Index noch aussteht.
- GitHub: Organisation auf dem Free-Plan. Repository seit 2026-10-08
  **öffentlich** (während des Brainstormings noch privat), damit
  Actions-Minuten unbegrenzt. GHCR-Speicher ist nur für öffentliche
  Pakete kostenlos; ein privates Paket mit rund 5 GB je Python-Image
  läge sofort über dem Freikontingent. Die Roadmap-Entscheidung „Paket
  öffentlich" ist damit Voraussetzung, nicht nur Komfort. Der Nutzer hat
  bestätigt, dass die Organisation öffentliche Pakete zulässt.

## Build-Pipeline

### Workflow `.github/workflows/images.yml`

Getrennt von `ci.yml`. Auslöser: `push` auf `main`, `push` eines Tags
`v*`, `workflow_dispatch`. Berechtigungen auf Job-Ebene: `contents: read`,
`packages: write` (GHCR), `id-token: write` (keyless Signatur). Alles über
das eingebaute `GITHUB_TOKEN`, kein PAT.

Ein Job, Ablauf:

1. Checkout.
2. Bei Tag-Auslöser: Version aus dem Tag lesen (`v0.1.0` → `0.1.0`) und
   gegen `core/pyproject.toml` prüfen; bei Abweichung abbrechen (D2).
3. Plattenplatz schaffen: nicht benötigte vorinstallierte Werkzeuge des
   Runners entfernen (Android-SDK, .NET, Haskell, CodeQL-Bundles). Der
   GitHub-Runner hat rund 14 GB frei, die Basisschicht allein ist rund
   5 GB, dazu kommt der Cache-Export.
4. Buildx-Builder anlegen, Login an GHCR mit `GITHUB_TOKEN`.
5. Tag-Liste berechnen (siehe Tagging) und als Bake-Variable übergeben.
6. `docker buildx bake --push` über `docker-bake.hcl`.
7. Signatur: für jedes der fünf Images `cosign sign --yes <image>@<digest>`
   mit dem Digest aus dem Bake-Metadaten-Output. Signiert wird der Digest,
   nie ein beweglicher Tag.
8. Zusammenfassung im Job-Summary: Image-Digests, Tags, Laufzeit.

Marketplace-Actions nur dort, wo sie Arbeit sparen und von Docker,
Sigstore oder GitHub selbst stammen: `actions/checkout`,
`docker/setup-buildx-action`, `docker/login-action`, `docker/bake-action`,
`sigstore/cosign-installer`. Alle per Major-Tag mit Kommentar, welche
Version beim Schreiben galt.

### `docker-bake.hcl` im Repo-Root

Eine Bake-Datei definiert die fünf Targets und ist die einzige
Build-Definition für die CI. `compose.yaml` behält seine `build:`-Blöcke
für den lokalen Build; beide zeigen auf dieselben Dockerfiles und Targets.

- Gruppe `default` = `api`, `chat`, `accounts`, `pipeline`, `frontend`.
- Die vier Python-Targets teilen Kontext (Repo-Root) und Dockerfile; ein
  einziger Bake-Aufruf baut sie in einer BuildKit-Sitzung, die identische
  Stufen dedupliziert. Die Basisschicht wird also einmal gebaut und einmal
  hochgeladen, die Registry speichert sie einmal.
- Nur `linux/amd64`. Die VM ist x86_64; Multi-Arch wäre doppelte Build-Zeit
  ohne Abnehmer. Wiedervorlage, sobald ein ARM-Betreiber auftaucht.
- Variablen: `REGISTRY` (Standard `ghcr.io/normly/web-app`) und `TAGS`
  (Liste, von der CI gesetzt; lokal Standard `local`). Die
  Modellrevisionen sind keine Bake-Variablen, sie stehen als
  `ARG`-Vorgaben im Dockerfile (siehe Reproduzierbarkeit).
- Layer-Cache in der Registry: je Target `cache-from`/`cache-to` vom Typ
  `registry` unter `ghcr.io/normly/web-app/cache:<target>` mit `mode=max`.
  Nicht der GitHub-Actions-Cache: der ist auf 10 GB je Repository
  begrenzt. Ein Folge-Build, der nur Anwendungscode ändert, überspringt
  damit Torch-Installation und Modell-Download.
- Attestationen: BuildKit erzeugt je Image eine SLSA-Provenance und eine
  SBOM (`attest` mit `type=provenance,mode=max` und `type=sbom`) und
  schiebt sie neben das Image. REQ-GIT-005 verlangt beides je Release;
  mit Buildx kostet es eine Zeile.

### Tagging

Image-Namen: `ghcr.io/normly/web-app/api`, `.../chat`, `.../accounts`,
`.../pipeline`, `.../frontend`.

| Auslöser | Tags |
|---|---|
| Push auf `main` | `edge`, `sha-<7 Zeichen>` |
| Git-Tag `vX.Y.Z` | `X.Y.Z`, `X.Y`, `latest`, `sha-<7 Zeichen>` |
| `workflow_dispatch` | wie der Branch bzw. Tag, auf dem er gestartet wird |

`latest` zeigt immer auf das jüngste Release, nie auf `edge`. `X.Y`
wandert mit dem jüngsten Patch-Release der Minor-Linie. Der Betreiber
entscheidet, wie beweglich sein Pin sein soll.

### Signaturprüfung durch Betreiber

Ein Betreiber prüft ohne GitHub-Konto:

```bash
cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/api:0.1.0
```

Der Aufruf steht wörtlich in `docs/guide/self-hosting.md`. Die Prüfung als
Pflichtschritt vor dem Start auf der VM (Abnahmekriterium REQ-GIT-005:
unsigniertes Artefakt wird abgewiesen) gehört zum Rollout-Skript aus TP4.

### Öffentliche Pakete

Nach dem ersten erfolgreichen Push müssen sechs Pakete (fünf Images, ein
Cache-Paket) in den GitHub-Paketeinstellungen von Hand auf öffentlich
gestellt werden. Falls die Organisation das Anlegen öffentlicher Pakete
nicht erlaubt, ist das vorher in den Org-Einstellungen unter Packages
freizuschalten. Beides geht nur im Portal, nicht aus dem Workflow; beides
steht als Pflichtschritt in der Verifikation und in
`docs/guide/releasing.md`.

## Compose-Anbindung

`compose.yaml` behält die `build:`-Blöcke. Die Image-Namen wechseln:

| heute | neu |
|---|---|
| `normly-api:local` | `ghcr.io/normly/web-app/api:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-chat:local` | `ghcr.io/normly/web-app/chat:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-accounts:local` | `ghcr.io/normly/web-app/accounts:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-pipeline:local` (migrate, pipeline) | `ghcr.io/normly/web-app/pipeline:${NORMLY_IMAGE_TAG:-edge}` |
| `normly-frontend:local` | `ghcr.io/normly/web-app/frontend:${NORMLY_IMAGE_TAG:-edge}` |

Wirkung: `docker compose up -d` zieht die veröffentlichten Images, wenn
sie lokal fehlen; `docker compose pull` aktualisiert sie; `docker compose
up -d --build` baut weiter lokal und tagt das Ergebnis unter demselben
Namen (harmlos, der lokale Build gewinnt dann bis zum nächsten `pull`).
Keine zweite Compose-Datei, kein Override.

`.env.example` bekommt `NORMLY_IMAGE_TAG` mit Erklärung der Tag-Familien.
`compose.yaml` erhält im Kopfkommentar den Hinweis, dass `docker-bake.hcl`
die CI-Build-Definition ist und beide Dateien dieselben Targets benennen.

Die VM läuft weiter aus `/opt/normly/src` mit lokalem Build, bis TP4 sie
auf `pull` umstellt. Der Wechsel der Image-Namen in `compose.yaml` ändert
dort erst etwas, wenn der nächste `git pull` plus `up -d --build` läuft;
auch dann baut die VM lokal unter dem neuen Namen weiter.

## Reproduzierbare Builds

### Lock-Datei mit uv

Ein `pyproject.toml` im Repo-Root erklärt die vier Python-Pakete zum
uv-Workspace:

```toml
[tool.uv.workspace]
members = ["core", "api", "chat", "accounts"]

[tool.uv.sources]
normly-core = { workspace = true }
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

Dazu eine einzige `uv.lock` im Repo-Root, versioniert. Wirkung:

- `normly-core` wird ausdrücklich aus dem Checkout aufgelöst, nie von
  einem Index. Das schließt die Typosquat-Lücke, die
  `api/pyproject.toml`, `chat/pyproject.toml` und
  `accounts/pyproject.toml` heute im Kommentar als offen vermerken; die
  Kommentare werden entsprechend gekürzt.
- Torch (transitiv über sentence-transformers) kommt ausschließlich aus
  dem CPU-Index, alle anderen Pakete ausschließlich von PyPI. Heute gilt
  `--extra-index-url` für jedes Paket.
- Eine Lock-Datei statt vier; Auflösung in Sekunden.
- `[project] version` in den vier Paketen bleibt die Quelle für die
  Versionsprüfung des Workflows (D2). Das Root-`pyproject.toml` hat
  keinen `[project]`-Abschnitt, es ist ein rein virtueller
  Workspace-Anker und wird nie als Paket gebaut oder installiert.

**Verworfen:** pip-tools mit `requirements.txt` je Paket. Hält die
Per-Paket-Venvs, erzeugt aber vier Lock-Dateien, deren Auflösungen
auseinanderlaufen können, und löst weder die Index-Trennung für Torch noch
die `normly-core`-Auflösung sauber.

### Folgen für Entwicklung und CI

- **Eine Entwicklungsumgebung** im Repo-Root (`.venv`), eingerichtet mit
  `uv sync --all-packages --all-extras`. Die bisherigen `.venv` je Paket
  bleiben lokal liegen, werden aber nicht mehr gepflegt; `.gitignore`
  kennt beide. `CONTRIBUTING.md` beschreibt den neuen Weg (uv installieren,
  `uv sync`, `uv run pytest` im jeweiligen Paket).
- **`ci.yml`:** die vier Python-Jobs wechseln von `pip install -e ../core
  -e .[dev]` auf `uv sync --locked --package normly-<name> --extra dev`
  und `uv run --package normly-<name> pytest`. `--locked` schlägt fehl,
  wenn `uv.lock` nicht zu den `pyproject.toml` passt (Korrektur nach
  Gesamtdurchsicht 2026-10-08: `--frozen` prüft nicht, `--locked` prüft) — damit ist die
  Lock-Datei in jedem PR geprüft, ohne eigenen Job. uv kommt per
  `astral-sh/setup-uv` mit gepinnter uv-Version; `test-core` behält den
  `libgl1`-Schritt und seine bekannte rote DGUV-Signatur (nicht Teil
  dieses Teilprojekts).
- **Chat-End-to-End-Tests** (`chat/tests/conftest.py`, heute per
  `api/.venv/bin/uvicorn` und `accounts/.venv/bin/uvicorn`): starten die
  Nachbardienste über `sys.executable -m uvicorn` aus der gemeinsamen
  Umgebung. Damit entfällt der Grund für ihren Ausschluss in der CI
  (`--ignore=tests/test_structural_end_to_end.py`); der Ausschluss wird
  aufgehoben, falls die vier Tests in der CI grün laufen, sonst bleibt er
  mit aktualisiertem Kommentar.
- Die frontend-Seite ist mit `package-lock.json` und `npm ci` bereits
  gelockt; dort ändert sich nichts.

### Dockerfile

`docker/python.Dockerfile`, neue Stufenfolge:

1. `deps`: `python:3.12-slim` per Digest gepinnt; uv per `COPY --from`
   aus `ghcr.io/astral-sh/uv:<version>` (ebenfalls per Digest). Kopiert
   nur `pyproject.toml`, `uv.lock` und die vier Paket-`pyproject.toml`,
   dann `uv sync --locked --no-dev --no-install-workspace --package
   normly-core` in `/app/.venv`. Diese Schicht ändert sich nur, wenn die
   Lock-Datei sich ändert.
2. `weights`: lädt die Modellgewichte mit `huggingface_hub.snapshot_download`
   bei fester Revision (siehe Tabelle) nach `/opt/models`, in Doclings
   Ordnerkonvention (`<repo_id mit / → -->`), und ersetzt damit sowohl den
   `SentenceTransformer(...).save()`-Aufruf als auch `docling-tools models
   download`. Für e5 wird nur das Nötige geladen (`ignore_patterns` für
   `onnx/`, `openvino/` und die `.bin`-Duplikate der safetensors-Gewichte);
   das Repo liegt im sentence-transformers-Format, `SentenceTransformer`
   liest es direkt vom Pfad. Eigene Stufe, damit ein Wechsel der
   Lock-Datei die Gewichte nicht neu lädt und umgekehrt.
3. `base`: `deps` plus `COPY --from=weights /opt/models /opt/models` plus
   `core`-Quellcode, installiert mit `uv sync --locked --no-dev --package
   normly-core`. Benutzer `normly` wie bisher.
4. `api`, `chat`, `accounts`, `pipeline`: wie bisher, nur mit `uv sync
   --locked --no-dev --package normly-<name>` statt `pip install`.
   `pipeline` lädt keine Modelle mehr selbst; `NORMLY_DOCLING_ARTIFACTS_PATH`
   zeigt auf `/opt/models/docling` aus der `weights`-Stufe.

uv bleibt als einzelne statische Binärdatei (rund 40 MB) in den Images
liegen, weil jede Target-Stufe es für ihren `uv sync` braucht und eine
eigene Laufzeit-Stufe je Target die Dockerfile-Struktur aus TP1
verdoppeln würde. Bewusst in Kauf genommen.

`frontend/Dockerfile`: `node:22-alpine` per Digest gepinnt; sonst
unverändert.

### Modellgewichte mit fester Revision

| Modell | Hugging-Face-Repo | heute | neu |
|---|---|---|---|
| Embedding e5 | `intfloat/multilingual-e5-large` | `main` | Commit-SHA |
| Docling Layout | `docling-project/docling-layout-heron` | `main` | Commit-SHA |
| Docling Layout ONNX | `docling-project/docling-layout-heron-onnx` | `main` | Commit-SHA |
| Docling Tableformer | `docling-project/docling-models` | Tag `v2.3.0` | Commit-SHA |

Die vier Revisionen stehen an genau einer Stelle: als `ARG`-Vorgaben mit
Datumskommentar in `docker/python.Dockerfile`, direkt vor der
`weights`-Stufe. Weder `docker-bake.hcl` noch `compose.yaml` überschreiben
sie, beide Build-Wege laden damit dieselben Gewichte. Die konkreten SHAs
ermittelt der Implementierungsplan zum Zeitpunkt des Schreibens (jeweils
der Commit, auf den `main` bzw. `v2.3.0` an dem Tag zeigt).

Wirkung: ein Wechsel der Gewichte ist ein bewusster Commit mit sichtbarem
Diff. Derselbe Git-Tag liefert dieselben Embeddings, die Voraussetzung
dafür, dass der versionierte Datenstand aus TP4 zum Image passt.

Die Docstring-Anleitung in `core/src/normly_core/pipeline/docling_extraction.py`
(„docling-tools models download …") wird auf den neuen Bezug per
`snapshot_download` mit Revision angepasst; `tests/pipeline/test_docling_offline.py`
bleibt der Nachweis, dass zur Laufzeit kein Netzwerkzugriff stattfindet.

## Dokumentation

- **ADR-023 „Image-Veröffentlichung: GHCR, keyless Signatur, eine Version,
  Lock-Datei"** in `docs/adr/README.md`. Status beschlossen (2026-10-08).
  Entscheidung: D1–D4 in Kurzform. Begründung: Linux Foundation als
  Non-Profit-Betreiber des Vertrauensankers; Monorepo-Kombination als
  Testeinheit; sparsame Build-Auslöser; Reproduzierbarkeit als
  Voraussetzung für den Datenstand-Abgleich. Verworfen: eigener Schlüssel,
  Version je Paket, PR-Builds, pip-tools. Konsequenz: Verweise aus
  REQ-BUILD-001, REQ-DIST-004, REQ-GIT-005.
- **`docs/srs/03-anforderungen.md`:** REQ-BUILD-001 und REQ-DIST-004
  erhalten unter „Weitere Informationen" den Verweis auf ADR-023.
  REQ-GIT-005 nennt im Akzeptanzkriterium noch die STACKIT Container
  Registry; der Satz wird auf GHCR (ADR-021) umgestellt und bekommt den
  Hinweis, dass die Prüfung als Pflichtschritt vor dem Start Teil von TP4
  ist.
- **`docs/guide/self-hosting.md`:** Pull-Weg wird Standard
  (`docker compose pull && docker compose up -d`), lokaler Build die
  Alternative. Anforderungen: der Hinweis auf 45 GB Build-Cache gilt nur
  noch für den lokalen Build. Neuer Abschnitt „Verifying image signatures"
  mit dem `cosign verify`-Aufruf und einem Satz zu Provenance und SBOM.
  „Known gaps" verliert den Punkt „No published images yet".
- **`docs/guide/releasing.md`** (neu, Englisch, in der Zensical-Navigation
  nach Self-Hosting): Versionsfelder anheben (vier `pyproject.toml`,
  `package.json`, `package-lock.json`), Release-Commit, annotierten Tag
  setzen, Tag pushen, Lauf beobachten, beim ersten Mal Pakete öffentlich
  stellen; Modellrevisionen ändern; was `edge`, `X.Y` und `latest`
  bedeuten.
- **`CONTRIBUTING.md`:** Abschnitt zur Entwicklungsumgebung mit uv.
- **`README.md`:** ein Satz, dass Images auf GHCR liegen, mit Link auf
  Self-Hosting.
- **Roadmap-Spec:** TP2-Abschnitt bekommt einen Verweis auf diese Spec und
  den Vermerk „umgesetzt“ nach der Verifikation.

## Verifikation

Nichts gilt als fertig, bevor es nicht einmal echt gelaufen ist. Jeder
Push, der einen Workflow auslöst, wird vorher mit dem Nutzer abgestimmt
(gewohnte Regel aus den STACKIT-Zeiten; Minuten sind seit der
Veröffentlichung des Repos zwar frei, Läufe auf `main` wirken aber nach
außen sichtbar).

1. **Lokal, vor dem PR:** `uv lock` erzeugt die Lock-Datei; `uv sync
   --all-packages --all-extras`; alle vier Python-Testsuiten und
   `npm test` grün; `docker buildx bake` baut alle fünf Images lokal;
   `docker compose up -d --build` startet den Stack wie in TP1 verifiziert
   (bundled-Profil); die Chat-End-to-End-Tests laufen aus der gemeinsamen
   Umgebung.
2. **Erster `main`-Lauf nach dem Merge:** pusht `edge` und `sha-…` für
   alle fünf Images, Signaturen und Attestationen. Aus dem Protokoll
   notieren: Gesamtlaufzeit, freier Plattenplatz vor dem Build, Größe der
   gepushten Images. Pakete öffentlich stellen.
3. **Signaturprüfung von außen:** `cosign verify` wie in der Doku, ohne
   GitHub-Anmeldung, gegen ein öffentliches Paket; zusätzlich
   `docker buildx imagetools inspect` zeigt Provenance und SBOM.
4. **Pull-Weg:** auf einem Rechner mit leerem Image-Cache
   `NORMLY_IMAGE_TAG=edge`, `docker compose pull`, `docker compose up -d`,
   Stack läuft ohne lokalen Build.
5. **Release:** Versionsfelder auf `0.1.0` (stehen bereits so), Tag
   `v0.1.0`, Push des Tags. Der Lauf liefert `0.1.0`, `0.1`, `latest`;
   die Versionsprüfung (D2) hat durchgelassen. Laufzeit mit Lauf 2
   vergleichen: der Registry-Cache muss greifen.
6. **Negativprobe der Versionsprüfung:** ein Tag `v9.9.9` auf denselben
   Commit lässt den Lauf im zweiten Schritt abbrechen, bevor ein Build
   beginnt (unter einer Minute); Tag danach lokal und auf GitHub löschen.

## Risiken und offene Punkte

- **Plattenplatz auf dem Runner.** Reicht der freigeräumte Platz nicht,
  ist die Rückfallebene, die Python-Targets und das Frontend in zwei Jobs
  zu trennen oder den Cache-Export auf `mode=min` zu setzen. Entscheidet
  der erste echte Lauf.
- **Org-Einstellung für öffentliche Pakete.** Vom Nutzer am 2026-10-08
  bestätigt: erlaubt. Bleibt als Pflichtschritt nach dem ersten Push
  (Sichtbarkeit je Paket umstellen).
- **Hugging-Face-Verfügbarkeit beim Build.** Nur zur Build-Zeit kontaktiert
  (wie bisher); mit festen Revisionen reagiert der Build auf ein
  gelöschtes Repo mit einem klaren Fehler statt stillschweigend anderen
  Gewichten. Spiegelung in STACKIT Object Storage bleibt eine Option für
  TP4.
- **Zwei Build-Definitionen** (`compose.yaml`, `docker-bake.hcl`) für
  dieselben Targets. Bewusst in Kauf genommen: beide sind kurz, und ein
  Bake-Overlay über die Compose-Datei hätte das Doppel-Target
  `migrate`/`pipeline` und die Profile-Logik mitgeschleppt.
- **Drift der Versionsfelder.** Der Workflow prüft nur `core`; die drei
  anderen `pyproject.toml` und `package.json` könnten abweichen.
  Akzeptiert, `releasing.md` nennt alle fünf Stellen; eine Prüfung aller
  fünf ist eine Zeile mehr und kann im Plan ergänzt werden.

## Übertrag an spätere Teilprojekte

- **TP4:** VM auf `docker compose pull` umstellen, Rollout-/Rollback-Skript
  mit `NORMLY_IMAGE_TAG`, `cosign verify` als Pflichtschritt vor dem Start
  (Abnahmekriterium REQ-GIT-005), Datenstand-Dump mit Verweis auf die
  Modellrevision des erzeugenden Images.
- **TP1a:** profitiert von der Entlastung der VM; unabhängig von TP2
  baubar.
- **Wartung:** `uv lock --upgrade` als wiederkehrende Aufgabe; die sieben
  npm-Funde aus TP1 bleiben ein eigener Wartungs-PR.

## Verifikation 2026-10-08 (Task 8, nach dem Merge von PR #14)

Alle Schritte des Verifikationsplans sind gelaufen; gemessen, nicht angenommen.

| Schritt | Ergebnis |
|---|---|
| PR #14, Test-Pipeline | fünf Jobs grün; `test-core` rot mit den bekannten vier DGUV-Tests (vgl. CI-Spec 2026-09-02); `uv sync --locked` in allen Jobs ohne Lock-Fehler (147 Pakete aufgelöst, 135 installiert) |
| Erster `Images`-Lauf auf `main` (Merge ea70cc8) | erfolgreich, **9 min 25 s**, kalt (kein Registry-Cache); Runner hatte nach dem Aufräumen 110 GB frei, Plattenplatz ist kein Engpass |
| Zweiter Lauf auf `main` (README-Commit 9937b92, kurz danach) | wartete dank Concurrency-Gruppe auf den ersten, dann **5 min 09 s** mit Registry-Cache |
| Öffentliche Pakete | alle sechs (`api`, `chat`, `accounts`, `pipeline`, `frontend`, `cache`) waren **ohne manuellen Schritt** anonym lesbar (HTTP 200 auf das Manifest): GitHub verknüpft Pakete über das `org.opencontainers.image.source`-Label mit dem öffentlichen Repo und übernimmt dessen Sichtbarkeit. Der Handgriff aus `releasing.md` bleibt als Rückfallebene dokumentiert |
| Signaturprüfung von außen | `cosign verify` (v3.1.3, ohne GitHub-Anmeldung) bestätigt `api:edge`: Zertifikat vom Workflow `images.yml`, Eintrag im Transparenzprotokoll; SBOM (SPDX, syft 1.51.0) und SLSA-Provenance am Image vorhanden |
| Pull-Weg | lokal: `docker compose pull` zieht fünf Images (Python-Images je 7,5 GB auf Platte, Frontend 337 MB); `docker compose up -d` mit `NORMLY_IMAGE_TAG=edge`: `migrate` Exit 0, api/accounts/chat healthy, Frontend HTTP 200, ohne lokalen Build |
| Release `v0.1.0` (annotierter Tag auf ea70cc8) | erfolgreich, **4 min 32 s**; Versionsprüfung aller fünf Felder bestanden; `0.1.0`, `0.1`, `latest`, `sha-ea70cc8` zeigen auf denselben Digest (`api`: `sha256:e67d62a7…`) |
| Negativprobe `v9.9.9` | Lauf bricht nach **7 s** im Schritt "Check that a release tag matches the package versions" ab, eine `::error::`-Zeile je Versionsfeld, kein Build; Tag lokal und auf GitHub gelöscht |

**Befunde:**

- Das Release-Image aus ea70cc8 hat einen anderen Digest als das `edge`-Image
  aus demselben Commit (`sha256:96d067d4…` vs. `sha256:e67d62a7…`). Bestätigt
  den offenen Punkt aus ADR-023 und REQ-BUILD-001: gleiche Eingaben, aber
  keine bit-identischen Images (Zeitstempel in Schichten, apt-Pakete).
- Die Concurrency-Gruppe aus der Gesamtdurchsicht hat sich am ersten Abend
  bewährt: zwei Pushes auf `main` innerhalb von zwei Minuten liefen seriell.
- Die Runner-Plattenplatz-Bereinigung war mit 145 GB Root-Volume nicht
  nötig, schadet aber nicht; bleibt drin.

**Folgearbeiten (nicht Teil von TP2):**

- `test-core` rot: mit den jetzt gepinnten Docling-Modellen prüfen, ob die
  vier DGUV-Tests im `pipeline`-Image bestehen; falls ja, die CI auf
  dieselben Modellrevisionen umstellen statt auf den jeweils neuesten Stand.
- Gewichte-Stufe auf ein schlankes Eltern-Image umstellen (Lock-Änderung
  lädt heute die Gewichte neu); `api`/`chat`/`accounts` ohne Docling-Modelle;
  `uv` aus den Laufzeit-Images; SBOM-Scanner-Image pinnen; `latest` nur
  setzen, wenn der Tag der höchste ist.
- TP4: VM auf `docker compose pull` umstellen, `cosign verify` als
  Pflichtschritt vor dem Start.
