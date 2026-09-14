# Mitwirken an normly

Danke, dass du beitragen möchtest. Dieses Dokument beschreibt, wie das
praktisch abläuft.

Beiträge sind ausdrücklich **nicht nur Code**. Wer Verweise zwischen Regelwerken
korrigiert, eine falsche Ersetzungskette meldet oder eine Quelle vorschlägt,
trägt zum wertvollsten Teil des Projekts bei — Fachwissen aus der Praxis ist
hier oft nützlicher als ein Patch.

## Developer Certificate of Origin (DCO)

normly nutzt das **DCO** statt einer Contributor License Agreement. Du
überträgst keine Rechte; du bestätigst nur, dass du den Beitrag beisteuern
darfst. Der volle Text steht unter <https://developercertificate.org/>.

Jeder Commit braucht dafür eine `Signed-off-by`-Zeile:

```bash
git commit -s -m "fix: Ersetzungskette für DIN EN ISO 9001 korrigiert"
```

Das `-s` fügt automatisch an:

```
Signed-off-by: Vorname Nachname <mail@example.org>
```

Name und E-Mail müssen zu deiner Git-Konfiguration passen. Pseudonyme sind
nicht zulässig — das DCO setzt eine identifizierbare Person voraus.

Vergessen? Nachträglich signieren:

```bash
git commit --amend -s          # letzter Commit
git rebase --signoff main      # mehrere Commits
```

Die Prüfung läuft automatisiert; ohne Signatur wird nicht zusammengeführt.

**Bewusste Folge:** Weil die Rechte bei den Beitragenden bleiben, ist eine
spätere Umlizenzierung des Kerns dauerhaft ausgeschlossen. Das ist so gewollt —
siehe [ADR-003](docs/adr/).

## Ablauf

1. **Erst reden, dann bauen.** Für alles über eine Fehlerkorrektur hinaus:
   zuerst ein Issue. Das erspart dir Arbeit, die am Ende nicht passt.
2. **Branch** von `main`, sprechender Name (`feat/graph-export`,
   `fix/eurlex-parser`).
3. **Commits** nach [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
4. **Pull Request** mit Beschreibung, was und warum. Verweis auf das Issue.
5. **Review** durch mindestens eine maintainende Person, grüne Pipeline
   erforderlich.

## Bevor du einen PR öffnest

- [ ] Alle Commits mit `Signed-off-by`
- [ ] Tests laufen lokal durch
- [ ] Neue Quelldateien tragen den Lizenzheader
- [ ] Keine Zugangsdaten im Code, auch nicht in Tests oder Beispielen
- [ ] Bei Architekturentscheidungen: Entwurf für einen ADR-Eintrag beigelegt

## Lizenzheader

Neue Dateien im Kern:

```
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
```

In SDKs und der API-Spezifikation stattdessen `Apache-2.0`.

## Grenzen, die nicht verhandelbar sind

Diese Punkte haben rechtliche oder strategische Gründe. PRs, die dagegen
verstoßen, können wir nicht annehmen — auch wenn der Code gut ist. Frag lieber
vorher in einem Issue nach.

- **Keine US-Dienste** für Betrieb, Nutzerdaten, die Normen-Wissensbasis,
  Zugangsdaten oder Produktions-Deployment. Ausnahme seit ADR-021: Quellcode,
  CI/CD und Container-Registry des freien Kerns liegen auf GitHub.
- **Kein Scraping kommerziell verwerteter Katalogbestände.** Auch nicht, wenn
  sie öffentlich zugänglich sind. Neue Quellen brauchen einen Eintrag im
  Quellenregister mit zugeordneter Rechtsgrundlage.
- **Keine DRM- oder Schutzlogik im freien Kern.** Offenliegender Schutzcode ist
  kein Schutz; solche Komponenten liegen außerhalb dieses Repositories.
- **Keine Kontopflicht für freie Inhalte.**
- **Keine personalisierte Werbung**, keine Nutzerprofile zu Werbezwecken.
- **Kein proprietärer Bestandteil im Kern.** Er muss ohne Zusatzmodule baubar,
  testbar und lauffähig bleiben.
- **Kein direkter Datenbankzugriff** außerhalb der Repository-Schicht.

Ausführliche Begründungen: [docs/adr/](docs/adr/).

## Beiträge ohne Code

- **Fehler in den Daten** — falscher Verweis, veralteter Gültigkeitsstand,
  fehlende Ersetzung: Issue mit Fundstelle. Besonders willkommen.
- **Neue Quellen** — welches Regelwerk, welcher Herausgeber, welche
  Rechtsgrundlage für die Nutzung.
- **Übersetzungen und Terminologie** — normly soll langfristig weltweit
  funktionieren.
- **Dokumentation** — wenn etwas unverständlich war, war es unverständlich.

## Verhalten

Es gilt der [Verhaltenskodex](CODE_OF_CONDUCT.md).

## Fragen

Für alles Unklare: Issue aufmachen. Lieber eine Frage zu viel als ein Tag
vergebliche Arbeit.
