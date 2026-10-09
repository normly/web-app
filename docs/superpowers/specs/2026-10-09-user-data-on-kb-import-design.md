# Design: Nutzerdaten beim Import des Wissensbestands

Stand: 2026-10-09 · Status: Entwurf, wartet auf Review. Folgt auf TP4
(`docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`,
ADR-025). Teil B (Lebenszyklus der Nutzerdaten insgesamt) ist ein eigener,
späterer Entwurf.

## Ziel und Anlass

Der Import eines Wissensbestand-Dumps (`replace_knowledge_base`) bricht heute
mit `ImportBlockedError` ab, sobald Nutzerdaten noch auf eine Zeile zeigen, die
der neue Dump nicht mehr enthält (ADR-025, offener Punkt). Das ist falsch für
eine **rechtlich gebotene Rücknahme** (Lieferung zurückgezogen, Klassifikation
widerrufen): Ein Verweis in `watchlist`, `notification` oder
`chat_message_citation` darf die Rücknahme nie verhindern (CLAUDE.md:
„Abstammung mitführen … zugesagte Rücknahme“). Gleichzeitig dürfen
Nutzerdaten nicht verloren gehen, nur weil sich der Wissensbestand ändert.

**Befund aus dem Code:** Keine Nutzerdaten-Tabelle speichert urheberrechtlich
geschützten Inhalt. Es sind Verweise (`work_id`, `edge_id`, `document_id`,
`segment_id`). Der Text eines Zitats wird erst beim Lesen aus `segment`
geholt. Bei einer Rücknahme entstehen daher keine Textreste in Nutzerdaten,
nur Verweise auf Zeilen, die es nicht mehr geben darf oder soll.

## Entscheidung (vom Nutzer gewählt: Tombstones für Kennungen, Löschen für Inhalt)

**Eine Rücknahme gewinnt immer; ein Nutzerverweis blockiert nie einen Import.**
Wissensbestand-Zeilen, die ein Dump nicht mehr enthält, werden je nach Klasse
behandelt:

| Klasse | Tabellen | Behandlung |
|---|---|---|
| Tombstone (Kennung, kein Inhalt) | `work`, `document`, `edge`; mit dem Dokument `document_designation`, `document_title` | Zeile bleibt; Spalte `retired_at` wird gesetzt. Nutzerverweise bleiben gültig. Kommt die Zeile später wieder im Dump vor, wird `retired_at` wieder `NULL`. |
| Herkunft | `delivery`, `source` | Bleibt (Tombstones verweisen darauf). Eine im Dump fehlende Lieferung erhält `withdrawn_at`, falls noch leer. |
| Inhalt/Ableitung | `segment`, `embedding`, `document_embedding`, `rights_classification` | Wird **physisch gelöscht**. Zitate (`chat_message_citation`) verlieren dabei die `segment_id` (bereits nullable); das Dokument bleibt als Tombstone. |

Damit kann ein zurückgezogener Text nirgends mehr gelesen werden (auch nicht aus
Sicherungen nach deren Ablauf), und kein Nutzerverweis geht verloren.

### Warum `retired_at` keine neue Filterpflicht ist

Alle Lesezugriffe laufen über die Rechteklassifikation (das einzige Tor,
CLAUDE.md). Wird die Klassifikation gelöscht, verschwindet das Dokument aus
jeder tor-gebundenen Abfrage. `retired_at` unterscheidet nur „zurückgezogen“
von „nie klassifiziert“ und dient der Wiederkehr und späteren Anzeige („nicht
mehr verfügbar“). Es entsteht kein zweiter Prüfpfad.

## Umsetzung

**Schema:** Migration `0033` fügt `retired_at timestamptz NULL` zu `work`,
`document` und `edge` hinzu (ORM entsprechend). `retired_at` ist **keine
Austauschspalte**: Der Dump enthält sie nicht, das Austauschformat und
`EXCHANGE_SCHEMA_VERSION` bleiben unverändert. Sie ist Zustand der
importierenden Instanz und wird beim Export ausgeschlossen
(`exchange_columns`/`iter_exportable_rows`).

**`replace_knowledge_base`** (ersetzt die drei Durchläufe aus der
TP4-Umsetzung):

1. Einfügen/Aktualisieren in FK-Reihenfolge; für Zeilen der Tombstone-Klassen
   aus dem Dump wird `retired_at` auf `NULL` gesetzt (Wiederkehr).
2. `chat_message_citation.segment_id` wird auf `NULL` gesetzt für Segmente, die
   der Dump nicht mehr enthält.
3. Löschen der Inhalts-/Ableitungsklasse in umgekehrter FK-Reihenfolge
   (`document_embedding`, `embedding`, `segment`, `rights_classification`) für
   alle Schlüssel, die nicht im Dump stehen.
4. Tombstones: `retired_at = Importzeit` für fehlende, noch nicht
   zurückgezogene `work`/`document`/`edge`; fehlende `delivery` erhält
   `withdrawn_at`.
5. Importvermerk schreiben; der Aufrufer committet wie bisher.

`ImportBlockedError` bleibt als letzte Sicherung für einen **unerwarteten**
Fremdschlüssel bestehen, wird im regulären Betrieb nicht mehr ausgelöst.
Idempotenz bleibt: ein zweiter Import derselben Version ändert nichts
(insbesondere nicht `retired_at`).

**Fail-closed-Test:** Ein Test geht alle Fremdschlüssel von Tabellen außerhalb
des Wissensbestands auf Wissensbestand-Tabellen durch. Jedes Ziel muss zur
Tombstone- oder Herkunftsklasse gehören oder in der Löschliste mit einer
ausdrücklichen Löseregel stehen (heute nur `chat_message_citation.segment_id`).
Eine neue Tabelle mit Verweis auf den Wissensbestand ohne Regel lässt den
Test fehlschlagen. Das gilt auch für `identity_resolution_case`
(Pipeline-Zustand), das auf `work` und `document` zeigt.

## Tests

- Rücknahme: Ein Dokument verschwindet aus dem Dump → Segmente, Einbettungen
  und Klassifikation sind gelöscht; Dokument und Work bleiben mit
  `retired_at`; Beobachtung und Benachrichtigung bestehen weiter; das Zitat
  verliert nur die `segment_id`.
- Wiederkehr: Das Dokument kehrt zurück → `retired_at` ist wieder `NULL`, der
  Inhalt ist neu eingespielt.
- Nach der Rücknahme erscheint das Dokument in keiner tor-gebundenen Abfrage
  (Dokumentliste, Suche, Export).
- Idempotenz (zweiter Import ändert nichts).
- Nutzerdaten blockieren den Import nicht mehr (ersetzt den bisherigen
  Blockier-Test).
- Der Export enthält `retired_at` nicht; ein Export-Import-Export ist
  zeilengleich.
- Rollback-Pfad: Nach einem Rollback (Import der früheren Version) bleiben
  Nutzerverweise gültig.

## Dokumentation

- **ADR-026** „Umgang mit Nutzerdaten beim Wissensbestand-Import“:
  Tombstone-/Herkunfts-/Inhaltsklassen, Begründung, Verworfenes (Blockieren
  mit Bereinigungswerkzeug; Anpassen/Löschen von Nutzerverweisen; reine
  Tombstones auch für Inhalt, weil die Rücknahme dann nur logisch wäre).
- **ADR-025:** Blockierregel und der zugehörige offene Punkt entfallen mit
  Verweis auf ADR-026; Beschreibung des Imports (drei Durchläufe) wird
  angepasst.
- **TP4-Spec** Teil 3, `docs/guide/operations.md`: Importverhalten
  (Tombstones, Wiederkehr) beschreiben; ADR-Register aktualisieren.

## Meldung „nicht mehr verfügbar“ (Erweiterung)

Weil ein Widerruf in Produktion die Klassifikation löscht (der Rechteänderungs-
Pfad von `notify-watchers` sieht dann nichts mehr), melden Tombstones den
Verlust selbst. Entscheidungen des Nutzers:

- Neuer Benachrichtigungstyp `no_longer_available`.
- **Pro zurückgezogenem Dokument eine Meldung** (nicht pro Work und Lauf).
- Gemeldet wird nur, was **nach dem Beginn der Beobachtung** zurückgezogen
  wurde (wie bei Kanten).
- Kein Link: Das Dokument ist durch das Rechtetor nicht mehr abrufbar.
- Gedächtnis gegen Doppelmeldungen: neue Tabelle `notified_retirement`
  (Konto, Work, Dokument, `retired_at`; der Zeitstempel gehört zum
  Schlüssel, damit eine Rücknahme nach einer Rückkehr neu gemeldet wird).
  Die Tabelle gehört zu den Nutzerdaten; sie zeigt nur auf Tombstone-Klassen.
- E-Mail: Betreff „Ein beobachtetes Regelwerk ist nicht mehr verfügbar“,
  Rumpf wie bei den anderen Typen.
- Oberfläche: Eintrag „Nicht mehr verfügbar“ / „No longer available“ in der
  Glocke mit eigenem Icon.
- Schema: Migration `0034` (Tabelle, Erweiterung der CHECK-Beschränkung für
  `trigger_type`); `Document` im Domänenmodell erhält `retired_at`.

Nicht enthalten: Detailseite oder Link für zurückgezogene Dokumente,
Alterung von Tombstones. Der Rechteänderungs-Pfad bleibt für den Produzenten
unverändert.

## Nicht-Ziele

- Alterung und Aufräumen von Tombstones.
- Anzeige „nicht mehr verfügbar“ in der Oberfläche.
- Lebenszyklus der Nutzerdaten insgesamt (Aufbewahrung, Kontolöschung,
  Auskunft/Export, Wirkung in Sicherungen): eigener Entwurf, Teil B.
- Änderung des Austauschformats oder der Exportregeln.

## Offene Punkte

- Aufbewahrung von Tombstones (heute unbegrenzt; Identifikatoren, kein
  Inhalt): wird in Teil B mitentschieden.
- Ob Tombstones in der Oberfläche sichtbar werden sollen (Benachrichtigung
  „Dokument nicht mehr verfügbar“): Produktentscheidung, nicht Teil dieser
  Änderung.
