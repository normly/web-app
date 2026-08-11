# Sicherheitsrichtlinie

## Schwachstellen melden

**Bitte melde Sicherheitslücken nicht als öffentliches Issue.**

Meldung an: **security@normly.ai**

Hilfreich für uns:

- Betroffene Komponente und Version
- Beschreibung und mögliche Auswirkung
- Schritte zur Reproduktion
- Deine Einschätzung des Schweregrads

Verschlüsselte Meldung ist möglich; den öffentlichen Schlüssel findest du unter
`docs/security/pgp-key.asc` *(noch zu ergänzen)*.

## Was du erwarten kannst

| | |
|---|---|
| Eingangsbestätigung | innerhalb von **3 Werktagen** |
| Erste Einschätzung | innerhalb von **10 Werktagen** |
| Statusmeldung | mindestens alle **14 Tage** bis zur Klärung |

Wir arbeiten mit koordinierter Offenlegung: Nach der Behebung veröffentlichen
wir einen Hinweis und nennen dich als Finder:in, sofern du das möchtest.
Üblicherweise liegen zwischen Behebung und Veröffentlichung **90 Tage** — bei
aktiv ausgenutzten Lücken deutlich weniger.

## Umfang

**Im Umfang:** der Kern dieses Repositories, die öffentliche API, die
Verarbeitungskette, Authentifizierung und Autorisierung, die Container-Images
sowie die Build- und Auslieferungswege.

**Besonders relevant** sind Lücken, die eine der folgenden Zusagen brechen:

- Trennung lizenzierter Bestände zwischen Mandanten
- Unerreichbarkeit lizenzierter Inhalte über anonyme Zugänge
- Wirksamkeit der Rücknahme zurückgezogener Bestände
- Schutz vor systematischer Massenextraktion

**Nicht im Umfang:** Schwachstellen in Fremdabhängigkeiten (bitte dort melden;
ein Hinweis an uns ist trotzdem willkommen), Angriffe, die physischen Zugriff
oder ein bereits kompromittiertes Konto voraussetzen, sowie Berichte aus
automatisierten Scannern ohne belegte Auswirkung.

## Regeln für Sicherheitsforschung

Erlaubt und erwünscht, solange du auf einer **eigenen Instanz** testest, keine
fremden Daten abrufst, veränderst oder löschst, keine Verfügbarkeit
beeinträchtigst und Funde nicht vor der koordinierten Offenlegung
veröffentlichst.

Wer sich daran hält, muss von uns keine rechtlichen Schritte befürchten.

## Ein Bug-Bounty-Programm gibt es derzeit nicht.
