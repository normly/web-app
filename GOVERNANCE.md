# Governance

## Grundgedanke

Der freie Kern von normly soll unabhängig von den wirtschaftlichen Interessen
einzelner Beteiligter bestehen können. Deshalb sind Trägerschaft und
kommerzielle Verwertung getrennt.

## Struktur

**Trägerorganisation** — hält Marke, offene Daten und Quellcode, verantwortet
den freien Kern und die Beziehungen zu Herausgebern und Community.

**Kommerzielle Gesellschaft** *(geplant, noch nicht gegründet)* — betreibt
kostenpflichtige Dienste: Managed Hosting, Compliance-Instanzen,
Integrationen, lizenzierte Bestände. Sie lizenziert von der Trägerorganisation
zu marktüblichen Konditionen.

Diese Trennung ist der Grund, warum der Kern keine Abhängigkeit auf proprietäre
Bestandteile haben darf: Der freie Kern muss auch ohne die kommerzielle Seite
weiterexistieren können.

## Rollen

**Beitragende** — alle, die etwas einbringen: Code, Daten, Korrekturen,
Dokumentation, Übersetzungen. Keine formale Voraussetzung außer der
DCO-Signatur.

**Maintainende** — dürfen zusammenführen und tragen Verantwortung für einen
Bereich. Aufnahme durch bestehende Maintainende nach nachhaltigem Beitrag über
einen längeren Zeitraum. Die aktuelle Liste steht in `MAINTAINERS.md`.

**Technische Leitung** — entscheidet, wenn im Maintainer-Kreis keine Einigung
zustande kommt, und verantwortet die Einhaltung der Architekturgrundsätze.

## Entscheidungen

Im Regelfall im Konsens innerhalb des betroffenen Bereichs. Was keinen Konsens
findet, wird im Maintainer-Kreis besprochen; bleibt es strittig, entscheidet
die technische Leitung.

**Architekturentscheidungen** werden als ADR in [docs/adr/](docs/adr/)
dokumentiert — mit Begründung und den verworfenen Alternativen. Eine
Entscheidung ohne dokumentierte Begründung ist keine getroffene Entscheidung.

Wesentliche Änderungen werden vor der Umsetzung als Issue zur Diskussion
gestellt.

## Was nicht zur Disposition steht

Einige Festlegungen sind Bedingung dafür, dass das Projekt seinen Zweck
erfüllt. Sie können nicht durch einen einzelnen Pull Request geändert werden,
sondern nur durch einen ADR mit ausdrücklicher Zustimmung der
Trägerorganisation:

- Lizenzmodell (AGPL-3.0 Kern, Apache-2.0 SDKs, ODbL Daten)
- DCO als Beitragsmodell
- Unabhängigkeit des Kerns von proprietären Bestandteilen
- Freier Zugang zu frei lizenzierbaren Inhalten ohne Konto
- Ausschluss personalisierter Werbung
- Datenhaltung und Betrieb in Europa

## Änderungen an diesem Dokument

Über einen Pull Request, mit Zustimmung der Mehrheit der Maintainenden und der
Trägerorganisation.
