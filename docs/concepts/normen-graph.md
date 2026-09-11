# Graph zuerst, Modell nur bei Bedarf

Anfragen werden zuerst gegen den Referenzgraph aufgelöst. Ein Sprachmodell
wird nur aufgerufen, wenn Synthese über Fließtext nötig ist — nicht für
Strukturfragen.

**Warum:** Fragen wie „was ersetzt Norm X" oder „welche Vorschrift verweist
auf Norm Y" sind aus dem Graph exakt beantwortbar — deterministisch, in
Millisekunden, ohne Tokenkosten. Ein Modellaufruf wäre hier teurer,
langsamer und fehleranfälliger. Gerade bei Gültigkeits- und
Ersetzungsfragen sind Halluzinationen besonders folgenschwer.

Details und Abwägung: [ADR-008](../adr/README.md#adr-008-graph-first-anfrageverarbeitung).

## Datenhaltung

Der Graph liegt in PostgreSQL mit pgvector — Graph und Embeddings in
derselben Datenbank, derselben Transaktion, demselben Backup, statt zweier
Systeme, die synchron gehalten werden müssten. Der Datenbankzugriff läuft
ausschließlich über die Repository-Schicht; welche Speichertechnologie
dahintersteckt, bleibt austauschbar.

Details: [ADR-006](../adr/README.md#adr-006-postgresql-statt-neo4j-fur-den-referenzgraph).

## Offen und geschichtet zugleich

Der Referenzgraph selbst ist offen (ODbL) — geschichtet in einen freien und
einen kommerziellen Teil, nicht zurückgehalten. Was frei ist, steht in
[Lizenzmodell](lizenzmodell.md).
