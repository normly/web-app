# Design: Dokument-Detail-Seite (Normtracker-Grundgerüst, Teil 3/5)

## Kontext

Sub-project 1 ([[docs/superpowers/specs/2026-09-06-normtracker-work-entity-design.md]])
und Sub-project 2 ([[docs/superpowers/specs/2026-09-07-normtracker-semantic-search-design.md]]),
beide gemergt, haben die `Work`-Entität und eine Work-gruppierte Suche gebracht.
Dieses Teilprojekt macht die dritte, in der ursprünglichen Work-Entität-Spec
skizzierte Erweiterung: die Dokument-Detail-Seite zeigt Editionshistorie,
nationale Fassungen, Referenzen und Rechteklassifikation je Rechtsraum für
ein Work.

Eine Dokument-Detail-Seite existiert bereits
(`frontend/src/app/documents/[id]/document-detail-content.tsx`), gebaut
gegen die vorhandenen Endpunkte `GET /v1/documents/{id}`, `GET
/v1/documents/{id}/edges` und `GET /v1/documents/{id}/validity`. Sie ist
funktional, aber vollständig ohne Work-Bezug (rein dokumentzentriert), zeigt
alle Kantentypen ungruppiert in einer Liste und zeigt keine
Rechteklassifikation. Rechteklassifikation ist aktuell überhaupt nicht über
HTTP erreichbar — nur `RightsRepository.get_classification` existiert auf
Repository-Ebene.

## Ziel dieses Teilprojekts

1. Editionshistorie (vollständige REPLACES/WITHDRAWN_BY-Kette, nicht nur
   der direkte Vorgänger/Nachfolger) und nationale Fassungen (vollständige
   ADOPTED_FROM-Kette) für das Work eines Dokuments über einen neuen
   Endpunkt bereitstellen.
2. Rechteklassifikation je (aktuell gewähltem) Rechtsraum über einen neuen
   Endpunkt bereitstellen.
3. Die bestehende Dokument-Detail-Seite so erweitern, dass sie diese neuen
   Informationen korrekt anzeigt.

## Nicht-Ziele

- **Kein visuelles Redesign.** Kein Tab-Layout, keine neue Komponentenwahl
  über das bereits verwendete Set hinaus. Das bestehende, schlichte Styling
  bleibt — die Tab-Ansicht mit durchdachtem Design ist explizit
  Teilprojekt 5 vorbehalten.
- **Keine KI-generierte Änderungs-Zusammenfassung** zwischen Editionen.
  Braucht Volltextzugriff beider Editionen plus LLM-Anbindung (ähnlich der
  Chat-Infrastruktur) — ein eigenständiges, späteres Teilprojekt.
- **Keine Mehrfach-Rechtsraum-Ansicht.** Rechteklassifikation wird nur für
  den aktuell gewählten Rechtsraum gezeigt, konsistent mit jedem anderen
  Endpunkt dieser App (Suche, Edges, Validity nehmen alle genau einen
  `jurisdiction`-Parameter). Eine "zeige alle Rechtsräume"-Ansicht wäre ein
  neues UI-Konzept, das sonst nirgends vorkommt.
- **Kein neuer/geänderter `/edges`-Endpunkt.** Bleibt unverändert — nach der
  Lektion aus Teilprojekt 2 (eine geänderte Response-Form brach eine
  bestehende Seite, deren eigener Test es nicht bemerkte) wird hier bewusst
  kein bestehender, produktiv genutzter Endpunkt verändert, wenn eine
  rein clientseitige Neugruppierung ausreicht.

## Architektur

### Zwei neue Endpunkte

Beide angehängt an die bestehende Dokument-Detail-Route (`/v1/documents/{id}/...`),
wie `/edges` und `/validity` es bereits tun.

**`GET /v1/documents/{id}/work?jurisdiction=X`** — liefert die Work-Struktur
des Dokuments:

```
WorkStructureEntry
  document_id: UUID
  origin_issuer: str
  origin_number: str
  edition: str
  designation: str | None   # primäre Designation, falls vorhanden
  status: "valid" | "replaced" | "withdrawn"

WorkStructureResponse
  work_id: UUID
  editions: list[WorkStructureEntry]
  national_adoptions: list[WorkStructureEntry]
```

Innerhalb der (begrenzten) Menge aller Documents desselben `work_id` werden
zwei Teilgraphen gebildet, je nach Kantentyp:

- **`editions`**: alle Documents, die mit dem betrachteten Dokument über
  eine Kette aus **nur** REPLACES/WITHDRAWN_BY-Kanten verbunden sind
  (typischerweise derselbe Herausgeber über die Zeit). Jede Edition bekommt
  einen Status, berechnet genauso wie im bestehenden `/validity`-Endpunkt
  (eingehende Kanten prüfen: zeigt eine neuere Edition per REPLACES/
  WITHDRAWN_BY auf diese, ist sie `replaced`/`withdrawn`), nur für jedes
  Element der Kette statt nur für ein Dokument.
- **`national_adoptions`**: alles andere im selben Work — jedes Document,
  das nicht Teil der Editionskette ist, mit eigenem Herausgeber/Bezeichnung/
  Status. Zusammen decken beide Listen immer die komplette
  Work-Dokumentmenge ab, keine Überschneidung, kein Dokument, das in keiner
  Liste auftaucht.

Beide Listen enthalten das gerade betrachtete Dokument selbst mit (an
seiner korrekten Position in der Kette, mit seinem eigenen Status) — nicht
nur seine Geschwister. Das vermeidet eine Sonderbehandlung im Frontend
("ist das die Edition, die ich gerade ansehe?") und liefert eine
vollständige, in sich geschlossene Liste.

Bewusst **keine unbegrenzte Graph-Traversierung**: die zugrundeliegende
DB-Abfrage ist eine einfache, begrenzte Mengenabfrage (alle Documents mit
diesem `work_id`, alle Kanten *zwischen genau diesen* Documents) — die
mehrstufige Ketten-Bildung passiert danach in Python über eine kleine,
bereits geladene Menge. Das bleibt im Sinne von ADR-006 "flach", weil es
die Work-Gruppierung aus Teilprojekt 1 nutzt, um die Menge von vornherein
zu begrenzen, statt rekursiv über den ganzen Graphen zu laufen.

Rechtegating wie überall: nur Documents/Kanten, die in `jurisdiction`
sichtbar sind (`may_process=true`, freie Schicht), fließen ein.

**`GET /v1/documents/{id}/rights?jurisdiction=X`** — dünner Wrapper um das
bereits vorhandene `RightsRepository.get_classification`, liefert
`may_process`, `may_index_fulltext`, `may_cite_passages`, `may_export_free`
und `legal_basis_reference`.

### Frontend

`document-detail-content.tsx` bekommt zwei neue `fetch`-Aufrufe (Work-Struktur,
Rechte) parallel zu den bestehenden. Referenzen werden weiterhin aus den
bestehenden `/edges`-Daten gebaut, aber jetzt clientseitig gefiltert: nur
REFERENCES/BASED_ON_LAW erscheinen in der "Referenzen"-Liste, REPLACES/
WITHDRAWN_BY/ADOPTED_FROM werden dort ausgeblendet (sie erscheinen
stattdessen strukturiert in den neuen Editions-/Fassungen-Listen). Kein
neues Layout — Editionshistorie und nationale Fassungen erscheinen als
einfache, mit den bestehenden Komponenten (`Badge`, `Link`) gebaute Listen,
im gleichen schlichten Stil wie die vorhandenen Abschnitte.

## Fehlerbehandlung

- `/work`: ein Dokument ohne Work-Geschwister liefert beide Listen leer
  (kein Fehler) — die Seite blendet die entsprechenden Abschnitte dann
  einfach aus.
- `/rights`: keine Klassifikation für den angefragten Rechtsraum → 404,
  gleiches Muster wie `/validity` ("kein Dokument" und "nicht klassifiziert"
  bleiben nach außen ununterscheidbar).
- Beide Endpunkte gaten wie überall: nur Documents/Kanten mit
  `may_process=true` im angefragten Rechtsraum werden einbezogen.

## Testkonzept

- Repository/Integration: Editionskette über 3+ Generationen (2010→2015→2018)
  korrekt sortiert mit korrektem Status je Glied; nationale Fassungen
  korrekt von der Editionskette abgegrenzt; ein Work ohne Geschwister
  liefert leere Listen; Rechtegating schließt nicht-sichtbare
  Work-Mitglieder aus den Ergebnissen aus.
- API: `/rights` liefert 404 bei fehlender Klassifikation, sonst die
  korrekten Felder; `/work` liefert das korrekte JSON-Schema inkl. leerer
  Listen für ein Solo-Dokument.
- Frontend: bestehender Test (`document-detail-content.test.tsx` o. ä.,
  falls vorhanden — sonst neu anzulegen) wird um die neuen Abschnitte
  erweitert (Editionsliste, nationale Fassungen, Rechte-Badge); die
  Referenzen-Filterung (Work-interne Kantentypen werden aus der
  Referenzen-Liste ausgeblendet) bekommt einen eigenen Test.

## Bezug zu Requirements und ADRs

| Requirement/ADR | Bezug |
|---|---|
| REQ-GRAPH-005 | Die Editions-/Fassungen-Ansicht ist die zweite nutzerseitig sichtbare Konsequenz der Work-Identität (nach der Suchgruppierung aus Teilprojekt 2) — macht "ein Regelwerk, mehrere Fassungen" für Nutzer direkt sichtbar. |
| REQ-GRAPH-002 | `/work` und `/rights` respektieren dieselbe Schichtung frei/kommerziell wie `/edges` — nur `may_process`-sichtbare, freie Schicht fließt ein. |
| ADR-006 | Die begrenzte Work-Mengenabfrage plus In-Memory-Kettenbildung bleibt konsistent mit "Graph zuerst, flache Abfragen" — keine unbegrenzte rekursive Traversierung. |

## Offene Punkte / Folgearbeiten

- **KI-Änderungs-Zusammenfassung** (eigenes, späteres Teilprojekt): braucht
  Volltextzugriff beider Editionen plus LLM-Anbindung.
- **Tab-Layout und visuelles Redesign**: Teilprojekt 5.
- **Mehrfach-Rechtsraum-Ansicht**: falls später gewünscht, braucht eine
  neue `list_classifications_for_document`-artige Repository-Methode (heute
  nur `get_classification` für genau einen Rechtsraum) und ein neues
  UI-Konzept.
