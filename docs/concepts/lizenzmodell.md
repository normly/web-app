# Lizenzmodell

normly folgt einem Open-Core-Modell — die Trennlinie verläuft am **Inhalt**,
nicht am Zugangsweg.

| Bestandteil | Lizenz |
|---|---|
| Kern (Server, Anwendung) | AGPL-3.0 |
| Client-SDKs, API-Spezifikation | Apache-2.0 |
| Daten und Referenzgraph | ODbL |

Die AGPL greift, wenn jemand den Server selbst verändert und betreibt. Ein
Drittsystem, das über die HTTP-API mit einer normly-Instanz spricht, ist
ein getrenntes Programm und nicht betroffen — Integrationen sind
ausdrücklich erwünscht.

Begründung der Lizenzwahl: [ADR-002](../adr/README.md#adr-002-lizenzmodell-agpl-30-apache-20-odbl).
Warum der Graph trotz Lizenzierung offen bleibt:
[ADR-007](../adr/README.md#adr-007-referenzgraph-bleibt-offen).

## Rechteklassifikation nach Kategorie

Jede Datenquelle bekommt eine Kategorie, bevor sie überhaupt verarbeitet
wird:

| | Kategorie | Grundlage |
|---|---|---|
| A | Amtliche Werke, Rechtstexte | § 5 UrhG o. Ä. |
| B | Frei lizenzierte Regelwerke | Lizenz des Herausgebers |
| C | Vertraglich bezogen | Vertragsreferenz |
| D | Sonstige öffentlich zugänglich | Einzelfallprüfung + § 44b Abs. 3 |

Keine Kategorie zuordenbar heißt: nicht erfassen. Kategorie D wird nie für
kommerziell verwertete Kataloge (DIN Media/Nautos u. Ä.) verwendet — dazu
[ADR-012](../adr/README.md#adr-012-kein-scraping-kommerziell-verwerteter-katalogbestande).

Die Klassifikation gilt **je Rechtsraum**, nicht global — § 5 UrhG gilt nur
in Deutschland. Details: [ADR-011](../adr/README.md#adr-011-internationalisierung-von-beginn-an).

## Getrennte Datenhaltung je Herausgeber

Lizenzierte Bestände (Kategorie C) werden je Herausgeber mit einem eigenen
Datenschlüssel getrennt gespeichert. Das ermöglicht kryptographisches
Löschen bei Vertragsende — auch in Backups, wo selektives Löschen sonst
praktisch nicht durchführbar ist. Details:
[ADR-014](../adr/README.md#adr-014-verschlusselung-kryptographisches-loschen-je-herausgeber).
