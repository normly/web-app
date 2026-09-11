# Design: Sprachregel-Korrektur — Dokumentation auf Englisch

## Kontext

CLAUDE.md schrieb bislang vor: „Dokumentation und Nutzeroberfläche auf
Deutsch, Mehrsprachigkeit vorgesehen." Auf dieser Grundlage wurde die neue
Zensical-Doku-Site (PR #30, siehe
`docs/superpowers/plans/2026-09-11-zensical-documentation-site.md`)
komplett auf Deutsch verfasst — inklusive einer finalen Review, die
Nav-Beschriftungen sogar extra von Englisch auf Deutsch korrigierte, weil
das damals die geltende Regel war.

Der Nutzer hat diese Regel korrigiert: Dokumentation muss zwingend
Englisch sein. Das ist eine Umkehr der bisherigen Vorgabe, kein
Missverständnis der alten Regel.

## Entscheidung

**Ab sofort wird neue Dokumentation auf Englisch verfasst.** Betrifft
`docs/`-Inhalte, Code-Referenz, Guides — nicht Code/Bezeichner/Commits
(die waren schon vorher Englisch, CLAUDE.md änderte sich hier nicht) und
nicht CLAUDE.md selbst (bleibt Deutsch als Arbeitsanweisung).

**Nur ab jetzt, nicht rückwirkend.** Bestehender deutscher Content wird in
diesem Projekt nicht angefasst. Das betrifft insbesondere:

- `README.md`
- `docs/adr/README.md` (ADR-001 bis ADR-019, komplett Deutsch)
- `docs/srs/*.md` (78 Requirements, komplett Deutsch)
- `CONTRIBUTING.md`, `SECURITY.md`, `GOVERNANCE.md`, `TRADEMARK.md`,
  `CODE_OF_CONDUCT.md`

Diese Migration ist ein eigenes, deutlich größeres Folgeprojekt und
ausdrücklich **nicht** Teil dieser Spec.

**Die Fachbegriffs-Ausnahme bleibt bestehen, sprachunabhängig.** CLAUDE.md
erlaubte schon vorher, deutsche Normenwesen-Begriffe zu behalten, wo es
keine etablierte Entsprechung gibt (`Normenausschuss` als Beispiel). Das
galt schon vorher unabhängig von der Sprache der umgebenden Doku und gilt
jetzt genauso in englischsprachigem Fließtext (z. B. "the
`Normenausschuss`" statt einer erfundenen Übersetzung).

**Die Nutzeroberfläche ist nicht betroffen.** Das Frontend hat bereits
eine echte de/en-Sprachumschaltung (`LocaleProvider`,
`frontend/src/lib/i18n/provider.tsx`) — die bleibt unverändert. Diese
Entscheidung betrifft nur Fließtext-Dokumentation, nicht die App-UI.

## Nicht-Ziele

- Keine rückwirkende Übersetzung von README/ADR/SRS/CONTRIBUTING/etc. —
  eigenes Folgeprojekt.
- Keine Änderung an CLAUDE.md's eigener Sprache (bleibt Deutsch).
- Keine Änderung an der App-Sprachumschaltung (de/en bleibt wie sie ist).

## Umsetzung

### 1. CLAUDE.md — Regeltext korrigieren

Im Abschnitt „Sprache" wird der Satz „Dokumentation und Nutzeroberfläche
auf Deutsch, Mehrsprachigkeit vorgesehen" ersetzt durch eine Regel, die
Dokumentation auf Englisch vorschreibt, die Fachbegriffs-Ausnahme
unverändert übernimmt, und klarstellt, dass sich das nicht auf die
bestehende App-Sprachumschaltung bezieht. CLAUDE.md selbst bleibt
komplett Deutsch — nur dieser eine Regel-Absatz beschreibt jetzt eine
andere Vorgabe als vorher.

### 2. ADR-020 — Entscheidung dokumentieren

Neuer Eintrag in `docs/adr/README.md`, nach ADR-019, mit Status
„beschlossen". **Auf Deutsch geschrieben**, übergangsweise — konsistent
mit ADR-001 bis ADR-019, bis diese Datei im späteren Migrationsprojekt
insgesamt übersetzt wird.

**Entscheidung:** Neue Dokumentation (docs/-Inhalte, Code-Referenz,
Guides) wird ab sofort auf Englisch verfasst statt auf Deutsch. Nicht
rückwirkend — bestehender deutscher Content wird nicht migriert, das ist
ein eigenes Folgeprojekt.

**Begründung:** Englisch ist der De-facto-Standard für
Open-Source-Dokumentation. Er ermöglicht internationalen Beitragenden
Teilnahme, unabhängig vom deutschsprachigen Kernteam — passend zum
Open-Core-Modell (ADR-001) und dem Anspruch, dass der freie Kern von
außen mitgetragen werden kann. Die ursprüngliche Regel (Dokumentation auf
Deutsch) stand dem im Weg.

**Nicht betroffen:** Code/Bezeichner/Commits waren schon vorher Englisch
(unverändert). Die App-eigene de/en-Sprachumschaltung
(`LocaleProvider`) ist eine Laufzeit-Funktion für Endnutzer, keine
Projektdokumentation, und bleibt unverändert. Die Fachbegriffs-Ausnahme
für Normenwesen-Begriffe ohne etablierte englische Entsprechung
(z. B. `Normenausschuss`) gilt unabhängig von der Sprache weiter.

### 3. PR #30 — Bestehenden Doku-Site-Content auf Englisch umschreiben

Der PR ist noch nicht gemerged — der komplette PR-Content zählt als „ab
jetzt", nicht als Bestandsschutz. Betroffene Dateien (Branch
`docs/zensical-documentation-site`):

| Datei | Vorgehen |
|---|---|
| `zensical.toml` | `site_description` und alle `nav`-Beschriftungen von Deutsch auf Englisch (zurück — waren in der finalen Review kurz zuvor extra auf Deutsch korrigiert worden, das war zu dem Zeitpunkt richtig). |
| `docs/index.md` | Übersetzen, Struktur/Links unverändert. |
| `docs/guide/getting-started.md` | Übersetzen. |
| `docs/guide/self-hosting.md` | Übersetzen, ADR-010-Link-Ziel bleibt unverändert (verlinkt weiterhin die deutsche ADR-Seite — das ist in Ordnung, ADR-Migration ist nicht Teil dieser Spec). |
| `docs/concepts/normen-graph.md` | Übersetzen. |
| `docs/concepts/lizenzmodell.md` | Übersetzen, inkl. der Kategorien-Tabelle (A–D) und des neuen ADR-014-Absatzes. |
| `docs/glossary.md` | Übersetzen — der **Titel bleibt „Glossar"→"Glossary"**, aber Fachbegriffe wie `Normenausschuss`, `Referenzgraph` (letzteres hat keine etablierte englische Entsprechung im Projekt, bleibt als Terminus erhalten mit englischer Erklärung) folgen der Fachbegriffs-Ausnahme aus CLAUDE.md. |
| `docs/reference/*.md` | **Keine Änderung** — bereits Englisch (`# normly-core`, `Reference graph data model...`, `::: normly_core`). |

Nach der Übersetzung: Build erneut verifizieren (`zensical build`, die
bekannten 3 Warnungen aus `docs/superpowers/specs/*.md` bleiben
unverändert bestehen, keine neuen Warnungen durch die Übersetzung). Die
zuvor verifizierten Anker-Links (ADR-008, ADR-006, ADR-002, ADR-007,
ADR-012, ADR-011, ADR-014, ADR-010) ändern sich durch die Übersetzung
nicht, da sie auf die (weiterhin deutsche) `docs/adr/README.md` zeigen —
trotzdem nach der Übersetzung erneut prüfen, falls sich durch
Textänderungen um die Links herum etwas verschoben hat.

## Fehlerbehandlung

Kein neues Fehlerverhalten — dieselbe Verifikationsmethode wie beim
ursprünglichen Aufbau (Build-Check + gezielte Grep-/Anker-Prüfungen pro
Seite, siehe Originalplan). Kein `--strict` (unverändert aus dem
Originalprojekt übernommen, dortige Begründung gilt weiter).
