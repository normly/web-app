# normly

**KI-unterstützte Normen und Standards, offen für jeden.**

normly macht Wissen über Normen und Regelwerke so weit frei zugänglich, wie
es rechtlich zulässig ist — und baut darauf einen offenen, maschinenlesbaren
Referenzgraph: welche Regelwerke aufeinander verweisen, was durch was
ersetzt wurde, und welche Rechtsvorschrift auf welche Norm verweist.

!!! warning "Frühe Entwicklungsphase"
    Dieses Projekt befindet sich im Aufbau. Es gibt noch keine lauffähige
    Version und keine stabile API — diese Doku-Seite wächst mit dem Code.
    Erster lauffähiger Prototyp: Dezember 2026.

## Wo du weiterliest

- **[Guide](guide/getting-started.md)** — Einstieg für Nutzer und Betreiber
- **[Concepts](concepts/normen-graph.md)** — die fachlichen Prinzipien
  dahinter (Graph zuerst, Lizenzmodell)
- **[Architekturentscheidungen](adr/README.md)** — warum es so gebaut ist,
  wie es gebaut ist
- **[Requirements](srs/README.md)** — die 78 Anforderungen (SRS/SDD)
- **[Code-Referenz](reference/core.md)** — automatisch aus den
  Docstrings generiert, für Mitwirkende

## Lizenzen

| Bestandteil | Lizenz |
|---|---|
| Kern (Server, Anwendung) | AGPL-3.0 |
| Client-SDKs, API-Spezifikation | Apache-2.0 |
| Daten und Referenzgraph | ODbL |

Details und Begründung stehen in `README.md` und `GOVERNANCE.md` im
Repository-Wurzelverzeichnis.
