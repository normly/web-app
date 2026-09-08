# Design: Work-Entität (Normtracker-Grundgerüst, Teil 1/5)

## Kontext

Der Nutzer plant, mit "Suche & Dokument-Detail" (bisher Plan 6 des
shadcn-Frontend-Redesigns, siehe
`docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`)
tatsächlich das erste Grundgerüst des Normtrackers zu bauen — nicht nur ein
Re-Theming. Bevor das Frontend angefasst wird, soll das Backend-Datenmodell
stehen. Dieser Spec ist der erste von fünf geplanten Teilprojekten:

1. **Work-Entität** (dieser Spec) — Grundlage für alle folgenden.
2. Semantische Suche (Embedding-basiert, ersetzt heutiges ILIKE).
3. Dokument-Detail-Seite (Editionshistorie, nationale Fassungen,
   Referenzen, Rechteklassifikation je Rechtsraum).
4. Watchlist/Notification (Favoriten, Änderungs-Trigger, E-Mail-Versand).
5. Frontend (führt 1–4 zusammen, letzter Zyklus).

**Ausgangslage:** ADR-011 und `CLAUDE.md` fordern "Ein Regelwerk = ein
Knoten, sprachunabhängig" — DIN EN ISO 9001 und BS EN ISO 9001 seien
dasselbe Dokument. Der tatsächlich implementierte `Document`-Typ
(`core/src/normly_core/graph/domain.py`) ist jedoch über
`(origin_issuer, origin_number, edition, part)` geschlüsselt: jede
Ausgabe/nationale Fassung ist eine eigene Zeile mit eigener UUID, nur über
`Edge` (`REPLACES`, `WITHDRAWN_BY`, `ADOPTED_FROM`) verknüpft. REQ-GRAPH-005
verlangt zusätzlich explizit ein Abnahmekriterium, das damit heute nicht
erfüllt ist: "Ein Regelwerk mit Übernahmen durch mindestens drei nationale
Gremien wird als ein Knoten mit zugeordneten Übernahmen dargestellt."

Ein während dieser Session zur Prüfung vorgelegter alternativer
Modellentwurf (`Norm`/`NormVersion`/`NormWatchlist`/`Notification`/
`ImportBatch`) wurde geprüft und verworfen, weil er das bestehende Modell
nicht erweitert, sondern ersetzen würde und dabei mehrere bereits
beschlossene Anforderungen zurückstufen würde: globale statt
rechtsraumabhängige Lizenzklassifikation (widerspricht REQ-GRAPH-006), ein
einzelnes `successor_norm_id`-Feld statt des typisierten Referenzgraphen
(widerspricht REQ-GRAPH-001, ADR-007), keine Abstammungskette zu einzelnen
Feldern (widerspricht der nicht verhandelbaren `CLAUDE.md`-Regel
"Abstammung mitführen"), und keine Mehrsprachigkeit je Knoten (widerspricht
REQ-GRAPH-005). Zwei Ideen aus diesem Entwurf sind aber eigenständig gut und
fließen in spätere Teilprojekte ein: eine Änderungs-Zusammenfassung je
Edition (Teilprojekt 3) und Watchlist/Notification (Teilprojekt 4).

## Ziel dieses Teilprojekts

Eine neue `Work`-Entität einführen, die die logische Identität eines
Regelwerks über alle Ausgaben und nationalen Übernahmen hinweg abbildet,
sodass REQ-GRAPH-005 erfüllt ist und spätere Teilprojekte (Suche,
Dokument-Detail, Watchlist) auf "ein Regelwerk" statt "eine Dokumentzeile"
referenzieren können.

## Nicht-Ziele

- Keine Änderung an `RightsClassification` (bleibt je Document/Rechtsraum).
- Keine Umstellung der Suche auf Work-Gruppierung (Teilprojekt 2).
- Kein UI/API-Workflow für den Normalfall der Ingestion über das hinaus,
  was zur Work-Zuordnung nötig ist.
- Kein automatisiertes Nummern-Ähnlichkeits-Matching (siehe Abschnitt
  "Zuordnungslogik").

## Architektur

### Datenmodell

```
Work (neu)
  id: UUID (PK, surrogate — kein natürlicher Schlüssel, da ein Work
      bewusst mehrere Herausgeber/Nummern überspannen kann)
  status: enum(active, merged)
  merged_into_work_id: UUID | None (FK → Work, self-ref; nur bei
      status=merged gesetzt)
  created_at: datetime
  created_via: enum(auto_matched, manual)

Document (bestehend, erweitert)
  + work_id: UUID (FK → Work, NOT NULL)
```

`Work` trägt bewusst **keine** Titel-, Designations- oder sonstigen
Metadatenfelder. Anzeigedaten (Titel, aktueller Status) werden zur Laufzeit
aus der primären Designation/Titel des aktuellsten, nicht zurückgezogenen
`Document` des Works abgeleitet — keine Datenduplizierung, kein
Sync-Problem zwischen Work und den zugrundeliegenden Documents.
`RightsClassification` bleibt unverändert auf `Document`-Ebene, weil sich
Lizenzbedingungen zwischen Herausgebern/Ausgaben desselben Works
unterscheiden können.

### Zuordnungslogik bei der Ingestion

Bei jedem neu eingelesenen `Document` prüft die Ingestion, ob die Lieferung
selbst eine explizite Ableitungsangabe zu einem bereits bekannten Document
enthält (z.B. "diese Ausgabe ersetzt X", "diese nationale Fassung übernimmt
X"):

- **Signal vorhanden und eindeutig auflösbar:** das neue Document erhält
  `work_id` des Ziel-Documents; zusätzlich wird wie bisher die konkrete
  `Edge` (`REPLACES`, `WITHDRAWN_BY` oder `ADOPTED_FROM`) zwischen beiden
  Documents angelegt.
- **Kein Signal, oder Signal verweist auf kein bekanntes Document:** das
  neue Document bekommt ein **neues** Work (1:1). Kein Rateversuch über
  Nummern-Ähnlichkeit — textbasiertes Matching (Teilnummern,
  Bindestrich-Varianten) ist fehleranfällig; eine falsche automatische
  Verknüpfung im offenen, share-alike-lizenzierten Graph wiegt schwerer als
  ein zusätzlicher Fall in der Warteschlange.
- **Signal vorhanden, aber uneindeutig** (z.B. mehrdeutige Zielangabe):
  `IdentityResolutionCase` wie heute (siehe unten), das Document bekommt
  vorübergehend ein eigenes neues Work, bis die Queue-Entscheidung fällt.

**Nur `REPLACES`, `WITHDRAWN_BY` und `ADOPTED_FROM` lösen eine gemeinsame
Work-Zuordnung aus.** `REFERENCES` und `BASED_ON_LAW` verbinden erkennbar
unterschiedliche Regelwerke (eine Norm, die eine andere zitiert; ein
Gesetz, das auf eine Norm verweist) und dürfen niemals dasselbe Work
ergeben.

### Erweiterung von IdentityResolutionCase

`IdentityResolutionCase` (bestehend) bekommt einen zweiten Fall-Typ:

```
IdentityResolutionCase (erweitert)
  ...
  case_type: enum(new_document, work_merge)
  # bei case_type=work_merge:
  source_work_id: UUID | None
  target_work_id: UUID | None
```

- `new_document`: wie heute — ein neu geliefertes Document wartet auf
  Zuordnung zu einem bestehenden `resolved_document_id` (und damit dessen
  Work).
- `work_merge`: ein Kurator stellt fest, dass zwei bereits **bestehende,
  unabhängig entstandene** Works dasselbe Regelwerk sind (z.B. wurden
  DIN- und BS-Fassung anfangs mangels Signal getrennt angelegt, eine
  spätere Lieferung belegt den Zusammenhang doch). Bei Auflösung: alle
  `Document.work_id` des `source_work_id` werden auf `target_work_id`
  umgeschrieben, `source_work_id` wird auf `status=merged` gesetzt mit
  `merged_into_work_id=target_work_id` — nie gelöscht, wegen
  Nachvollziehbarkeit/Abstammung.

## Migration & Backfill

Für bestehende Daten wird `work_id` per Alembic-Migration befüllt: über die
transitive Hülle bestehender `REPLACES`/`WITHDRAWN_BY`/`ADOPTED_FROM`-Kanten
(Union-Find) — jede zusammenhängende Gruppe bestehender Documents bekommt
ein gemeinsames neues Work, jedes unverbundene Document bekommt sein
eigenes neues Work. Das ist deterministisch und nutzt exakt die Kanten, die
heute schon die Zusammengehörigkeit ausdrücken — keine manuelle Nacharbeit
nötig.

## Fehlerbehandlung

- `work_id` ist `NOT NULL` — ein Document ohne auflösbares Work darf nie
  committet werden. Die Ingestion muss vor dem Commit ein Work zugeordnet
  haben (neu erzeugt oder bestehend), analog zur bestehenden Regel
  "fehlende Klassifikation heißt nicht verarbeiten, nicht vorläufig
  erlaubt".
- Zugriff auf ein Document, dessen Work `status=merged` ist, wird
  transparent auf `merged_into_work_id` umgeleitet (nie ein toter Link).
- Ein `work_merge`-Case mit widersprüchlichen/zyklischen Zielen (A merge→B,
  B merge→A) wird beim Auflösen abgelehnt, nicht committet.

## Testkonzept

- Unit: Union-Find-Backfill-Logik gegen ein Fixture-Set bekannter Ketten
  (Edition A→B→C via `REPLACES`, nationale Fassung D via `ADOPTED_FROM` von
  B) — erwartet ein gemeinsames Work für alle vier.
- Unit: Ingestion mit eindeutigem Signal → korrekte `work_id`-Übernahme;
  ohne Signal → neues Work; mehrdeutig → `IdentityResolutionCase`.
- Integration: `work_merge`-Case-Resolution verschiebt alle Documents
  korrekt und markiert die Quelle als `merged`.
- Repository-Test: Zugriff auf ein Document eines `merged`-Works liefert
  transparent das Ziel-Work.
- Repository-Test: `REFERENCES`/`BASED_ON_LAW`-Kanten lösen nachweislich
  **keine** gemeinsame Work-Zuordnung aus.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-GRAPH-005 | Abnahmekriterium ("ein Knoten mit zugeordneten Übernahmen") wird durch `Work` erstmals erfüllt — bisher unerfüllt, da `Document` diese Aggregation nicht abbildete. SRS wird um einen Verweis auf `Work` ergänzt. |
| ADR-011 | "Ein Regelwerk = ein Knoten" wird um einen Nachtrag ergänzt, der die konkrete Umsetzung dokumentiert (Work-Entität als logische Identität über mehrere Document-Zeilen, nicht ein einzelner DB-Row im wörtlichen Sinn). |
| REQ-GRAPH-001/002/006 | Unverändert — Referenzgraph-Kantentypen, Schichtung frei/kommerziell und Rechtsraum-Klassifikation bleiben wie bisher auf `Document`/`Edge`-Ebene. |
| CLAUDE.md "Abstammung mitführen" | `Work` selbst hat keine eigene Abstammung (trägt keine Inhalte); jedes `Document` behält seine bestehende `created_via_delivery_id`. `merged`-Works bleiben aus Nachvollziehbarkeitsgründen erhalten statt gelöscht. |

## Offene Punkte / Folgearbeiten

- **Semantische Suche** (Teilprojekt 2): Suchtreffer sollen künftig pro
  Work gruppiert werden (ein Treffer = ein Regelwerk, Editionen/nationale
  Fassungen aufklappbar) — hängt direkt an diesem Spec, ist aber nicht Teil
  davon.
- **Dokument-Detail-Seite** (Teilprojekt 3): zeigt Editionshistorie,
  nationale Fassungen, Referenzen und Rechteklassifikation je Rechtsraum
  für ein Work.
- **Watchlist/Notification** (Teilprojekt 4): Nutzer verfolgen ein Work
  (nicht eine einzelne Document-Edition); Änderungs-Trigger hängt an neu
  entstehenden `REPLACES`/`WITHDRAWN_BY`-Kanten innerhalb eines Works.
- **Frontend** (Teilprojekt 5, letzter Zyklus): führt 1–4 zusammen.
- **Work-Merge-Admin-Oberfläche.** Dieser Spec legt nur das
  Datenmodell/die Case-Resolution-Logik für `work_merge` fest; eine
  eigene Kuratierungs-UI dafür ist nicht Teil dieses Zyklus.
