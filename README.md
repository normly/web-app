# normly

**KI-unterstützte Normen und Standards, offen für jeden.**

normly macht Wissen über Normen und Regelwerke so weit frei zugänglich, wie es
rechtlich zulässig ist — und baut darauf einen offenen, maschinenlesbaren
Referenzgraph: welche Regelwerke aufeinander verweisen, was durch was ersetzt
wurde, und welche Rechtsvorschrift auf welche Norm verweist.

> ⚠️ **Frühe Entwicklungsphase.** Dieses Repository befindet sich im Aufbau.
> Es gibt noch keine lauffähige Version und keine stabile API.

## Warum

Wer wissen will, welche Norm für eine Aufgabe gilt, ob sie noch gültig ist und
was sie ersetzt hat, findet darauf heute keine gute Antwort. Die Regelwerke
liegen verstreut bei verschiedenen Herausgebern, ihre Verweise untereinander
sind nirgends maschinenlesbar erfasst, und viele frei verfügbare Texte —
Unfallverhütungsvorschriften, technische Regeln, EU-Richtlinien — sind zwar
öffentlich, aber praktisch kaum auffindbar.

normly richtet sich an die Menschen, die täglich damit arbeiten: Handwerk,
Planung, Arbeitssicherheit und kleine bis mittlere Unternehmen.

## Was frei ist und was nicht

normly folgt einem **Open-Core-Modell**. Die Trennlinie verläuft am Inhalt,
nicht am Zugangsweg.

**Frei** — der Kern, der Referenzgraph und alle Inhalte, die frei weitergegeben
werden dürfen: amtliche Werke, DGUV-Regeln, BAuA-Technische Regeln,
EU-Richtlinien über EUR-Lex, offene Standards. Nutzbar ohne Konto, ohne Entgelt,
selbst hostbar.

**Kostenpflichtig** — Managed Hosting mit SLA, Compliance-Instanzen mit
Audit-Trail, Integrationen in CAD- und ERP-Systeme, sowie Instanzen mit
vertraglich lizenzierten Normenvolltexten.

Urheberrechtlich geschützte Volltexte werden **nicht** frei weitergegeben.
Wo sie verarbeitet werden, geschieht das auf vertraglicher Grundlage — mit
Umsatzbeteiligung der Herausgeber.

Was normly ausdrücklich **nicht** tut: keine personalisierte Werbung, keine
Nutzerprofile zu Werbezwecken, kein Abgreifen kommerziell verwerteter
Normenkataloge.

## Lizenzen

| Bestandteil | Lizenz |
|---|---|
| Kern (Server, Anwendung) | AGPL-3.0 |
| Client-SDKs, API-Spezifikation | Apache-2.0 |
| Daten und Referenzgraph | ODbL |
| Marke `normly` | siehe [TRADEMARK.md](TRADEMARK.md) |

Die AGPL greift, wenn jemand den Server selbst verändert und betreibt. Ein
Drittsystem, das über die HTTP-API mit einer normly-Instanz spricht, ist ein
getrenntes Programm und nicht betroffen — Integrationen sind ausdrücklich
erwünscht.

## Mitwirken

Beiträge laufen über das **Developer Certificate of Origin** (DCO), nicht über
eine Rechteübertragung. Jeder Commit braucht eine `Signed-off-by`-Zeile:

```bash
git commit -s -m "feat: kurze Beschreibung"
```

Details in [CONTRIBUTING.md](CONTRIBUTING.md). Sicherheitslücken bitte **nicht**
als Issue melden — siehe [SECURITY.md](SECURITY.md).

## Wo der Code liegt

Alleinige Plattform für Quellcode, Beiträge, Build und Deployment ist
**STACKIT Git** (Forgejo, Rechenzentren in Deutschland) — keine externe
Beitragsfassade mehr (ADR-019). Issues und Pull Requests finden dort statt,
Betrieb und Daten bleiben in Deutschland.

## Dokumentation

| | |
|---|---|
| [docs/srs/](docs/srs/) | Anforderungen (SRS/SDD), 78 Requirements |
| [docs/adr/](docs/adr/) | Architekturentscheidungen mit Begründung |
| [docs/normly_Verarbeitungskette.svg](docs/normly_Verarbeitungskette.svg) | Von der Quelle bis zur Ausspielung |
| [docs/normly_Entwicklungsphasen.svg](docs/normly_Entwicklungsphasen.svg) | Phasenplan |
| [CLAUDE.md](CLAUDE.md) | Arbeitsanweisungen für KI-gestützte Entwicklung |

Wenn du verstehen willst, **warum** etwas so ist, wie es ist: `docs/adr/` ist
der richtige Einstieg.

## Status

Erster lauffähiger Prototyp: Dezember 2026. Der Referenzgraph entsteht dabei
aus frei zugänglichen Quellen — er braucht keinen Lizenzvertrag.

---

<sub>normly ist ein unabhängiges Projekt und steht in keiner Verbindung zu DIN,
VDI, ISO, CEN oder anderen Normungsorganisationen.</sub>
