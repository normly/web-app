# normly — Arbeitsanweisungen

Plattform für Normen- und Regelwerkswissen. Open Core: freier Kern unter
AGPL-3.0, kommerzielle Dienste getrennt davon.

Ausführlicher Kontext: `docs/adr/` (Entscheidungen samt Begründung),
`docs/srs/` (Anforderungen, Einstieg über `docs/srs/README.md` mit dem
Requirement-Index). Diese Datei enthält nur, was bei **jeder** Aufgabe gilt.

## Nicht verhandelbar

Diese Regeln haben rechtliche oder strategische Gründe. Bei Konflikt mit einer
Aufgabe: nachfragen, nicht umgehen.

- **Keine US-Dienste für Betrieb, Nutzerdaten, Normen-Wissensbasis, Secrets
  oder Produktions-Deployment.** Das läuft ausschließlich auf STACKIT, ohne
  Ausnahme. **Ausnahme seit ADR-021 (2026-09-14):** Quellcode, CI/CD und
  Container-Registry des freien Kerns liegen auf GitHub
  (`github.com/normly/web-app`) — einfachere Kollaboration war der
  ausschlaggebende Grund. STACKIT Git (`jwokittel/normly-webapp`) wird
  dafür nicht mehr genutzt, ist für die Wissensbasis nicht mehr
  vorgesehen (ADR-025) und wird gelöscht; die Wissensbasis liegt als Dump
  im STACKIT Object Storage. → ADR-021 (löst ADR-019 ab)
- **Kein Scraping kommerziell verwerteter Katalogbestände** (DIN Media/Nautos
  und vergleichbare). Nur vertraglich beziehen. Gilt auch bei öffentlicher
  Zugänglichkeit. → ADR-012
- **Keine personalisierte Werbung**, keine Nutzerprofile zu Werbezwecken. →
  ADR-009
- **Keine urheberrechtlich geschützten Volltexte** in freien Exporten oder im
  öffentlichen Repository.
- **Keine DRM-, Offline-Schutz- oder Kennzeichnungslogik im freien Kern.**
  Offenliegender Schutzcode ist kein Schutz. Der Kern stellt nur Schnittstellen
  bereit. → ADR-015
- **Der Kern darf nicht von proprietären Bestandteilen abhängen.** Er muss ohne
  sie baubar, testbar und lauffähig sein.
- **Sprachmodelle nur als Open-Weight-Modelle mit OSI-Lizenz, betrieben auf
  STACKIT.** Keine Anfrage erreicht den Modellhersteller; europäische
  Herkunft ist Präferenz, nicht Pflicht. → ADR-022

## Bei jeder Codeänderung

- **Lizenzheader** in neuen Quelldateien: AGPL-3.0 (Kern), Apache-2.0 (SDKs,
  API-Spezifikation).
- **Commits** brauchen `Signed-off-by` (DCO). Conventional Commits, SemVer.
- **Kein direkter Push auf `main`** — Merge Request mit Review und grüner
  Pipeline.
- **Keine Secrets im Code**, auch nicht in Tests oder Beispielen.

## Arbeitsweise: Wann abstimmen, wann direkt umsetzen

Diese Regeln gelten in jedem Permission-Modus, auch in Auto-Mode. Auto-Mode betrifft
nur Werkzeugentscheidungen (Dateien lesen, Befehle ausführen), nicht die Frage,
ob ein Design abgestimmt wird.

### Zuerst `brainstorming`-Skill aufrufen und Rückfragen stellen, wenn mindestens eines zutrifft:
- eine neue Komponente, Seite, Route, Tabelle oder ein neuer Service entsteht
- sich eine Interaktion oder ein Verhalten für den Nutzer ändert (Ablauf, Zustand, Sichtbarkeit, Bedienung)
- mehr als zwei Dateien angefasst werden
- eine Schnittstelle, ein Datenmodell oder eine Migration betroffen ist
- die Anforderung mehr als eine sinnvolle Umsetzung zulässt

Erst nach bestätigtem Design wird implementiert. Keine Edits vorher.

### Direkt umsetzen, ohne Brainstorming:
- Bugfix mit klarer Ursache
- reine Optik ohne Verhaltensänderung (Farbe, Abstand, Text, Icon-Tausch)
- Änderungen an höchstens zwei Dateien, die genau eine Umsetzung zulassen

Im Zweifel gilt die erste Liste.

### Weitere Skills
- Fehlersuche immer mit `systematic-debugging`, nicht ad hoc.
- Vor „fertig" immer `verification-before-completion`.

## Architekturregeln

- **Datenbankzugriff nur über die Repository-Schicht.** Keine SQL- oder
  graphspezifischen Abfragen in der Fachlogik — die Speichertechnologie muss
  austauschbar bleiben. → ADR-006
- **Abstammung mitführen.** Jedes abgeleitete Artefakt (Abschnitt, Segment,
  Einbettung, Graphkante, Exportdatei) referenziert seine Quelllieferung. Ohne
  das ist die zugesagte Rücknahme nicht einlösbar. Nachträglich nicht
  herstellbar.
- **Graph zuerst, Modell nur bei Bedarf.** Strukturfragen (Ersetzung,
  Gültigkeit, Verweise) werden deterministisch aus dem Graph beantwortet, ohne
  LLM-Aufruf. → ADR-008
- **Rechteklassifikation ist das einzige Tor.** Kein zweiter Prüfpfad, keine
  verteilten Prüfungen. Fehlende Klassifikation heißt „nicht verarbeiten", nicht
  „vorläufig erlaubt".
- **Verarbeitungsschritte idempotent.** Wiederholung erzeugt kein abweichendes
  Ergebnis.
- **Lizenzierte Bestände getrennt je Herausgeber** — inklusive eigenem
  Datenschlüssel. Ermöglicht kryptographisches Löschen bei Vertragsende, auch in
  Backups. Berechtigungsprüfung bei jedem Zugriff. → ADR-014
- **Offline-Zugriff nur über die Abstraktionsschicht.** Keine direkten
  Speicherzugriffe (IndexedDB, Keychain, Keystore) in der Anwendungslogik —
  Browser- und native Ablage müssen austauschbar bleiben. → ADR-016
- **Alles Persistierte verschlüsselt:** Datenbank, Objektspeicher, Indizes,
  Protokolle, Sicherungen. Schlüssel nie neben den Daten.

## Neue Datenquellen

Jede Quelle braucht einen Registereintrag mit Kategorie:

| | Kategorie | Grundlage |
|---|---|---|
| A | Amtliche Werke, Rechtstexte | § 5 UrhG o. Ä. |
| B | Frei lizenzierte Regelwerke | Lizenz des Herausgebers |
| C | Vertraglich bezogen | Vertragsreferenz |
| D | Sonstige öffentlich zugänglich | Einzelfallprüfung + § 44b Abs. 3 |

Keine Kategorie zuordenbar → nicht erfassen. Kategorie D niemals für
kommerziell verwertete Kataloge.

## Technischer Rahmen

- **Datenhaltung:** PostgreSQL (Flex) mit pgvector — Graph und Embeddings in
  einer Datenbank. Kein Neo4j. → ADR-006
- **Auslieferung:** signierte Container-Images plus lauffähiges Compose-Setup.
  Der Wissensbestand liegt **nicht** im Image, sondern als eigenständig
  versionierter Dump. Code und Daten getrennt versioniert. → ADR-010
- **Registry:** GitHub Container Registry (GHCR) im Repository
  `normly/web-app`, führend für den freien Kern. → ADR-021
- **CI:** GitHub Actions im Repository `normly/web-app`. Der Port von
  `.forgejo/workflows/ci.yml` steht als Folgearbeit noch aus. → ADR-021
- **Frontend:** Next.js mit `standalone`-Output, zugleich installierbare PWA.
  Keine plattformspezifischen Primitive — alles muss im Container hinter
  beliebigem Reverse Proxy laufen.
- **Mobil:** PWA ist der einzige mobile Zugang bis Phase 2. Eine native App
  kommt erst mit lizenzierten Offline-Volltexten und gehört zur kommerziellen
  Schicht. Nicht an ein eigenes Sprachmodell gekoppelt. → ADR-016
- **Kommerzielle Schicht heißt nicht kostenpflichtiger Zugang.** Die native App
  ist kostenfrei, freie Inhalte sind darin ohne Konto abrufbar. Entgelt nur für
  lizenzierte Volltexte und deren geschützte Offline-Nutzung.
- **Keine Kontopflicht für freie Inhalte.** Suche, Referenzgraph und freie
  Regelwerke funktionieren ohne Anmeldung. Konto nur für: höhere Kontingente,
  Verläufe, Uploads, lizenzierte Inhalte, Offline-Nutzung, Bezahldienste — diese
  Liste ist abschließend. → ADR-017
- **SSO ist optional**, nie Voraussetzung für freie Inhalte. → REQ-INT-003
- **Kontingentzählung serverseitig**, nie über Cookies oder Browser-Speicher.
  Gleiche Infrastruktur wie die Ratenbegrenzung aus REQ-SEC-004.

## Identifikatoren

Von Anfang an weltweit gedacht — nachträglicher Umbau ist die teuerste Altlast.

- Global kollisionsfreies Schema, Herausgeber / Nummer / Ausgabestand /
  Teilnummer getrennt.
- **Ein Regelwerk = ein Knoten, sprachunabhängig.** DIN EN ISO 9001 und BS EN
  ISO 9001 sind dasselbe Dokument; nationale Übernahmen und Übersetzungen sind
  Beziehungen bzw. Attribute.
- **Lizenzklassifikation je Rechtsraum**, nicht global. § 5 UrhG gilt nur in
  Deutschland. → ADR-011

## Sprache

Code, Bezeichner und Commits auf Englisch. **Dokumentation ebenfalls auf
Englisch** (`docs/`-Inhalte, Code-Referenz, Guides) — internationale
Reichweite hat Vorrang. Fachbegriffe aus dem Normenwesen behalten ihren
deutschen Begriff, wo es keine etablierte Entsprechung gibt (z. B.
`Normenausschuss`), unabhängig von der Sprache der umgebenden Doku. Diese
Datei (CLAUDE.md) bleibt auf Deutsch. Die App-eigene Sprachumschaltung
(Deutsch/Englisch für Endnutzer) ist davon unberührt. → ADR-020

Teilweise migriert (2026-09-14): README.md, CONTRIBUTING.md, SECURITY.md
und CODE_OF_CONDUCT.md sind jetzt auf Englisch. Weiterhin auf Deutsch und
vorerst unverändert: docs/adr/, docs/srs/, GOVERNANCE.md, TRADEMARK.md —
deren Migration bleibt ein eigenes, späteres Projekt, siehe ADR-020-Nachtrag.
`docs/superpowers/` (interne Specs, Pläne, Ledger für die KI-gestützte
Entwicklung) ist davon unabhängig zu betrachten — das sind Arbeitsdokumente
für den Entwicklungsprozess, keine Dokumentation im Sinne dieser Regel, und
bleiben wie CLAUDE.md selbst auf Deutsch.

## Weitere Repository-Dateien

`CONTRIBUTING.md` (DCO-Ablauf), `SECURITY.md` (Meldeweg), `GOVERNANCE.md`
(Rollen und Entscheidungswege), `TRADEMARK.md` (Markennutzung),
`CODE_OF_CONDUCT.md`. Bei Änderungen an Ablauf oder Regeln diese Dateien
mitziehen — sie sind nach außen sichtbar und werden gelesen.

## Wenn etwas unklar ist

Bei Konflikt zwischen dieser Datei und einer Aufgabenstellung: nachfragen. Die
Regeln oben haben rechtliche oder strategische Gründe, die aus einer einzelnen
Aufgabe nicht ersichtlich sein müssen. Neue Architekturentscheidungen bekommen
einen eigenen Eintrag in `docs/adr/`.
