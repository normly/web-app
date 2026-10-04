# normly — Entscheidungsdokumentation (ADR)

Stand: 10.08.2026 · Bezug: SRS/SDD v0.2 (Redline)

Dieses Dokument hält fest, **was** entschieden wurde und **warum**. Die
Umsetzung steht in der SRS/SDD; hier stehen die Begründungen, die dort
keinen Platz haben und die erfahrungsgemäß als erstes vergessen werden.

Status je Eintrag: `beschlossen` · `favorisiert` · `offen`

---

## ADR-001 — Open-Core-Modell statt White-Label-Produkt

**Status:** beschlossen

**Entscheidung:** Ein quelloffener, selbst hostbarer Kern trägt die frei
verfügbare Wissensbasis und den Referenzgraph. Kommerzielle Zusatzdienste
setzen darauf auf und sollen in eine eigene Gesellschaft ausgegründet werden.

**Begründung:** Die ursprüngliche Vision („Normenwissen für jeden") und das
White-Label-Geschäftsmodell widersprachen sich. Der Rechtsformwechsel allein
löst das Urheberrechtsproblem nicht — auch eine gemeinnützige Organisation,
die DIN-/VDI-/DVGW-Volltexte weitergibt, bleibt für diese Häuser ein
Wettbewerber. Tragfähig ist nur die Trennung: frei ist, was frei sein darf;
bezahlt wird für Prozess, Haftungssicherheit und Integration.

**Konsequenz:** Der Kern darf keine Abhängigkeit auf proprietäre Bestandteile
haben (REQ-OSS-002). Verworfen wurde die Variante „alles in einer GmbH".

---

## ADR-002 — Lizenzmodell: AGPL-3.0 / Apache-2.0 / ODbL

**Status:** beschlossen

**Entscheidung:** Kern unter AGPL-3.0. Client-SDKs und API-Spezifikation unter
Apache-2.0. Daten und Referenzgraph unter offener Datenlizenz mit
Share-Alike-Wirkung (ODbL).

**Begründung:** Die AGPL schließt über § 13 die Lücke der Netzwerknutzung —
wer den Kern als gehosteten Dienst betreibt, muss Änderungen offenlegen. Das
ist der Schutz gegen einen Fork durch eine Normungsorganisation oder einen
großen Softwarehersteller. Apache-2.0 für SDKs und API-Spezifikation sichert
maximale Verbreitung dort, wo keine schützenswerte Logik liegt.

**Verworfen:** Apache-2.0 als alleinige Kernlizenz (gibt den Code ohne
Gegenleistung an potenzielle Wettbewerber). MPL-2.0 (dateibasiertes Copyleft
ist durch Auslagern in neue Dateien umgehbar, SaaS-Lücke bleibt offen —
kombiniert die Nachteile beider Seiten).

**Wichtig:** Die AGPL blockiert die Drittsoftware-Integration nicht. Ein
Plugin, das über HTTP mit einer normly-Instanz spricht, ist ein getrenntes
Programm. Die AGPL greift erst, wenn jemand den Server selbst modifiziert und
betreibt.

---

## ADR-003 — Beitragsmodell: DCO statt CLA

**Status:** beschlossen

**Entscheidung:** Externe Beiträge über das Developer Certificate of Origin.
Jeder Commit trägt eine `Signed-off-by`-Zeile. Keine Rechteübertragung.

**Begründung:** Das DCO senkt die Hürde für Beitragende und passt zum Anspruch
auf frei zugängliches Normenwissen.

**Bewusst in Kauf genommen:** Damit ist **Dual-Licensing dauerhaft
ausgeschlossen.** Sobald der erste externe Beitrag im Kern liegt, sind die
Rechte verteilt und niemand kann mehr eine kommerzielle Ausnahmelizenz zur
AGPL verkaufen. Diese Einnahmequelle entfällt.

**Verworfen:** CLA (hätte Dual-Licensing ermöglicht, wurde zugunsten der
Community-Offenheit abgelehnt). Ebenfalls verworfen: DCO mit permissiver
Inbound-Lizenz (Beiträge unter Apache-2.0, Auslieferung unter AGPL) — hätte
die Relizenzierung offengehalten.

**Offen:** Wer ist Rechteinhaber im LICENSE- und Copyright-Header — Person,
künftige Trägerorganisation oder GmbH? Vor dem ersten externen Beitrag klären.

---

## ADR-004 — STACKIT Git als führende Plattform, GitHub als Beitragsfassade

**Status:** war teilweise abgelöst durch ADR-019 (2026-09-05), das die
Beitragsfassade auf GitHub verwarf. Seit ADR-021 (2026-09-14) gilt für
Quellcode, CI und Registry wieder die hier ursprünglich getroffene
GitHub-Aufteilung, allerdings mit GitHub als führend statt als reiner
Beitragsfassade — siehe ADR-021 für den aktuellen Stand.

**Entscheidung:** STACKIT Git (Forgejo) mit STACKIT Pipelines ist führend für
Quellcode, Build, Artefakte, Zugangsdaten und Deployment. GitHub dient als
öffentliche Beitragsfassade: Issues, Pull Requests, Sichtbarkeit. Dort keine
Zugangsdaten, Runner, Build-Artefakte oder Deployment-Rechte.

**Begründung:** Ein öffentliches Image und öffentlicher Quellcode sind
souveränitätsrechtlich unkritisch — schützenswert sind Betrieb, Daten und
Credentials. Der Split gibt Sichtbarkeit ohne Souveränitätsverlust und ist
gegenüber Normungspartnern sogar das stärkere Argument: der Code ist offen und
prüfbar, Daten und Betrieb liegen in Deutschland.

**Praktisch:** STACKIT Pipelines sind weitgehend GitHub-Actions-kompatibel,
ein späterer Wechsel der Workflows ist billig. Beiträge werden nur an **einer**
Stelle entgegengenommen — zwei parallele Issue-Tracker wirken wie ein totes
Projekt.

**Verworfen:** GitHub + Vercel als Ursprung (hätte eine Ausnahmeklausel gegen
die eigene Spezifikation erfordert). Reines STACKIT ohne öffentliche Fassade
(Verlust an Sichtbarkeit und externen Beiträgen).

---

## ADR-005 — Kein Vercel, Deployment durchgängig auf STACKIT

**Status:** beschlossen

**Entscheidung:** Kein Vercel. Next.js als Container (`standalone`-Output) über
die STACKIT Container Registry, Betrieb zunächst auf VM mit Compose, später
SKE.

**Begründung:** Vercel bindet automatische Deployments nur an GitHub, GitLab
und Bitbucket — Forgejo ist nicht dabei, der Komfortvorteil entfällt also
ohnehin. Der Mehraufwand ist zu Projektbeginn am kleinsten, und die
US-Ausnahmeklausel in der SRS entfällt vollständig.

**Nebenbedingung:** LLM-Inferenz und Vektorsuche laufen ohnehin nicht auf
Serverless-Plattformen (Laufzeitgrenzen, keine GPUs). Der Kern ist daher als
eigenständiger Dienst mit HTTP-API konzipiert.

---

## ADR-006 — PostgreSQL statt Neo4j für den Referenzgraph

**Status:** beschlossen

**Entscheidung:** PostgreSQL Flex mit pgvector. Graphzugriff hinter einer
abstrahierten Schnittstelle gekapselt (REQ-GRAPH-004), Speichertechnologie
austauschbar.

**Begründung:**

1. STACKIT bietet kein Managed Neo4j. Neo4j müsste selbst auf SKE betrieben
   werden — Backup, Failover, Updates inklusive. PostgreSQL Flex bringt das mit.
2. Neo4j Community (GPLv3) hat kein Clustering und keine Hot Backups; Enterprise
   ist proprietär und teuer. Beides untergräbt das Self-Hosting-Versprechen aus
   REQ-OSS-002.
3. Die Abfragen sind flach (ein bis drei Sprünge, begrenzte Ersetzungsketten).
   Rekursive CTEs reichen. Neo4j spielt seine Stärke bei tiefen, variabel langen
   Traversierungen aus — nicht das Muster hier.
4. Graph und Embeddings liegen in derselben Datenbank, derselben Transaktion,
   demselben Backup. Zwei Systeme synchron zu halten ist eine dauerhafte
   Fehlerquelle.

**Auch bei weltweiter Abdeckung gültig:** Bei geschätzt 2–4 Mio. Dokumenten und
50–200 Mio. Kanten bleibt das für PostgreSQL unkritisch. Neo4j skaliert nicht
horizontal durch Sharding; Postgres lässt sich nach Herausgeber oder Rechtsraum
partitionieren.

**Das eigentliche Skalierungsrisiko** ist der Vektorindex, nicht der Graph.
Bei weltweiter Abdeckung sind mehrere Milliarden Textabschnitte zu erwarten —
dort wird pgvector deutlich früher zum Engpass. Retrieval-Schicht daher ebenso
kapseln.

---

## ADR-007 — Referenzgraph bleibt offen

**Status:** beschlossen

**Entscheidung:** Der Referenzgraph wird nicht zurückgehalten, sondern unter
ODbL veröffentlicht — geschichtet in einen freien und einen kommerziellen Teil.

**Begründung:** Offen heißt nicht schutzlos. Das Datenbankherstellerrecht
(§§ 87a ff. UrhG) schützt die wesentliche Investition in Beschaffung und
Aufbereitung und macht die Share-Alike-Klausel durchsetzbar: Wer den Graph in
ein eigenes Produkt einbaut, muss die abgeleitete Datenbank unter denselben
Bedingungen offenlegen. Das ist bei Daten der Gegenpart zur AGPL beim Code.

Geheimhaltung wäre der schwächere Schutz — der Graph ist aus den Quelldokumenten
rekonstruierbar. Ohne den Graph bliebe vom freien Kern ein Chatbot über
DGUV-/BAuA-Dokumente übrig; die Trägerorganisation hätte keine
Existenzberechtigung.

**Trennlinie:**

| Frei (ODbL) | Kommerziell |
|---|---|
| Schema, Identifikatoren | Aktualitätsgarantie mit SLA |
| Verweise zwischen öffentlichen Regelwerken | Verweise auf Abschnittsebene in lizenzierten Normen |
| Ersetzungsketten, Gültigkeitsstände | Konfidenzangaben, Belegstellen für Audits |
| Verweise Gesetz → Norm | Branchenspezifische Anreicherungen |
| Periodischer Dump | SLA-API mit Änderungsbenachrichtigung |

Der letzte Punkt ist der wirtschaftlich entscheidende: **Ein monatlicher Dump
und eine garantiert aktuelle API mit Haftungszusage sind verschiedene Produkte.
Firmen zahlen für Verlässlichkeit, nicht für Daten.**

---

## ADR-008 — Graph-First-Anfrageverarbeitung

**Status:** beschlossen

**Entscheidung:** Anfragen werden zuerst gegen den Referenzgraph aufgelöst. Ein
Sprachmodell wird nur aufgerufen, wenn Synthese über Fließtext nötig ist.

**Begründung:** Strukturfragen („was ersetzt X", „welche Vorschrift verweist auf
Y") sind aus dem Graph exakt beantwortbar — deterministisch, in Millisekunden,
ohne Tokenkosten. Ein Modellaufruf wäre teurer, langsamer und fehleranfälliger.
Gerade bei Gültigkeits- und Ersetzungsfragen sind Halluzinationen besonders
folgenschwer.

**Doppelter Gewinn:** geringere Inferenzkosten *und* höhere Verlässlichkeit
genau dort, wo Fehler am teuersten wären. Ergänzend: Caching gleicher Anfragen,
kleines Modell für Routing, großes nur für komplexe Synthesen, Kontingente in
der freien Nutzung.

---

## ADR-009 — Keine personalisierte Werbung

**Status:** beschlossen

**Entscheidung:** Personalisierte Werbung auf Basis von Suchanfragen,
Chatverläufen oder Nutzerprofilen ist ausgeschlossen. Zulässig: kontextfreie
Verzeichniseinträge, Affiliate auf Shoplinks, bezahlte Einträge im
Konformitätsverzeichnis.

**Begründung:**

- *Rechnerisch:* Eine Chat-Sitzung erzeugt kaum Werbeplätze, verbraucht aber
  mehrere LLM-Aufrufe mit langen Kontexten. Kleine, deutschsprachige
  Fachzielgruppe bei hohen Kosten pro Anfrage — strukturell die schlechteste
  Kombination für Werbefinanzierung.
- *Datenschutz:* Die Fragen sind ungewöhnlich sensibel — ein
  Sicherheitsbeauftragter nach einem Unfall, ein Mittelständler vor einer
  Produkteinführung. Das ist Wettbewerbsinformation und teils haftungsrelevant.
- *Neutralität:* Wer sagt, was der anerkannte Stand der Technik ist, kann nicht
  gleichzeitig Produkte bewerben. Gegenüber DIN und VDI ein unnötiger
  Angriffspunkt.

**Der bessere Hebel ist die Kostenseite** — siehe ADR-008.

---

## ADR-010 — Auslieferung als Container, Daten getrennt vom Image

**Status:** beschlossen

**Entscheidung:** Signierte, versionierte Container-Images plus lauffähiges
Compose-Setup. Der freie Wissensbestand ist **nicht** Teil des Images, sondern
ein eigenständig versionierter Dump, der beim ersten Start bezogen wird.

**Begründung:** Ein AGPL-Kern, den außer dem Projekt selbst niemand betreiben
kann, ist praktisch nicht offen. Das Image ist der Nachweis der
Selbst-Hostbarkeit — und dasselbe Artefakt, das im Managed Hosting läuft.
Die Trennung von Code und Daten ist nötig, weil sich Normenstände deutlich
häufiger ändern als der Code; sonst wächst das Image und jede Datenaktualisierung
erzwingt einen Neubau.

**Registry:** **Nachtrag 2026-09-14 (ADR-021):** GitHub Container Registry
(GHCR) im Repository `normly/web-app` ist die führende Registry für den
freien Kern — löst den vorherigen Nachtrag vom 2026-09-05 (ADR-019, STACKIT
Container Registry alleinig) wieder ab. STACKIT Container Registry bleibt
für Artefakte der kommerziellen Schicht bzw. spätere Normen-Datenprojekte
verfügbar, ist aber nicht mehr die Registry des Kern-Images. Docker Hub
allenfalls später als eigenständiger Spiegel, falls Pull-Limits für anonyme
Zugriffe zum echten Problem werden.

---

## ADR-011 — Internationalisierung von Beginn an

**Status:** beschlossen

**Entscheidung:** Der Referenzgraph wird von Anfang an für weltweite Abdeckung
ausgelegt: global kollisionsfreies Identifikatorschema, sprachunabhängige
Knotenidentität, nationale Übernahmen als Beziehungen, mehrsprachige
Bezeichnungen. Lizenzklassifikation **je Rechtsraum**, nicht global.

**Begründung:** Ein nachträglicher Umbau des Identifikatorschemas ist die
teuerste denkbare Altlast. DIN EN ISO 9001 und BS EN ISO 9001 sind dasselbe
Dokument — ohne sprachunabhängige Identität entstehen Dubletten, die
Verweisketten unbrauchbar machen.

Der frei veröffentlichbare Anteil ist **nicht** global einheitlich: § 5 UrhG
gilt nur in Deutschland; in den USA ist die Lage über die
Edicts-of-Government-Doktrin tendenziell großzügiger; für harmonisierte
EU-Normen ist EuGH C-588/21 (2024) gesondert zu bewerten. Eine globale
Klassifikation wäre entweder rechtswidrig oder unnötig restriktiv.

**Folgeaufgabe:** Die rechtliche Bewertung je Rechtsraum ist eine laufende
Aufgabe, keine einmalige Klärung. Braucht später eine Rolle oder einen Prozess.

---

## ADR-012 — Kein Scraping kommerziell verwerteter Katalogbestände

**Status:** beschlossen

**Entscheidung:** Katalog- und Metadatenbestände von Herausgebern, die diese
selbst kommerziell verwerten (insbesondere DIN Media / Nautos, vormals
Perinorm), werden **ausschließlich vertraglich** bezogen. Automatisierte
Erfassung ist ausgeschlossen — auch dann, wenn die Bestände öffentlich
zugänglich sind. Umgesetzt als Positivliste im Quellenregister (Kategorien
A–D, REQ-PIPE-002) mit technischer Sperre (REQ-PIPE-008).

**Begründung:**

1. *Der Katalog ist das Produkt.* Nautos umfasst rund 2,35 Mio. Datensätze aus
   29 Ländern inklusive monatlicher Aktualisierung durch die
   Normungsorganisationen — also genau den Katalog samt Änderungsverfolgung, den
   normly bräuchte. Ihn nachzubauen heißt, das Umsatzprodukt genau der
   Organisationen anzugreifen, mit denen verhandelt werden soll.
2. *Rechtlich.* Ein Normenkatalog ist eine geschützte Datenbank. § 87b UrhG
   untersagt neben der Entnahme wesentlicher Teile auch die **wiederholte und
   systematische** Entnahme unwesentlicher Teile, soweit sie der normalen
   Auswertung zuwiderläuft — das beschreibt periodisches Scraping mit Abgleich
   exakt. Die TDM-Schranke des § 44b greift bei maschinenlesbarem
   Nutzungsvorbehalt nicht.
3. *Strategisch — der schwerste Punkt.* normly verhandelt darüber, dass
   Herausgeber Inhalte **freiwillig** bereitstellen und dafür beteiligt werden
   (ADR-013). Paralleles Abgreifen ist das exakte Gegenteil dieser Erzählung und
   würde die Verhandlungen beschädigen.

**Konsequenz:** Der Erstbestand kommt aus frei zugänglichen Quellen
(REQ-PIPE-009): EU-Amtsblatt via EUR-Lex (Listen harmonisierter Normen, datiert
und maschinenlesbar), Verweise aus Gesetzen und Verordnungen, DGUV- und
BAuA-Verzeichnisse, Arbeitsprogramme von CEN/CENELEC, Katalogdaten von ISO/IEC.
Das ist zugleich der für den Referenzgraph wertvollste Teil, weil dort die
Verweise **aus dem Recht** stehen.

**Verworfen:** Nautos-Lizenz als Datenquelle für den eigenen Bestand — solche
Lizenzen schließen die Weiterverwendung in einem eigenen Produkt typischerweise
aus. Vor einer solchen Lizenz wären die Vertragsbedingungen genau zu prüfen.

**Nicht regelbar durch Vorsatz:** Die Sperre ist bewusst *technisch* formuliert
(Adapter der Kategorie D lassen sich auf gekennzeichnete Quellen nicht
konfigurieren), nicht als Richtlinie. Sobald Werkstudenten oder externe
Beitragende Adapter schreiben, entscheidet die Spezifikation, nicht das
Bauchgefühl.

---

## ADR-013 — Metadaten zuerst: Partnerschaftsleiter statt Volltext-Sprung

**Status:** beschlossen

**Entscheidung:** Gegenüber Herausgebern wird zuerst um **Katalogmetadaten**
gebeten, nicht um Volltexte. Volltextzulieferung ist die zweite Stufe, gestützt
auf reale Attributionszahlen aus der ersten.

**Begründung:** Metadaten kosten einen Herausgeber fast nichts und bringen ihm
Sichtbarkeit und Verkäufe über Weiterleitung. Volltext ist die große Hürde,
Metadaten die kleine. Ein Herausgeber, der monatliche Metadaten-Deltas ohnehin
an Nautos liefert, hat mit einer zweiten Lieferung keinen zusätzlichen Aufwand.

Sobald die erste Stufe läuft, liegen prüffähige Attributionszahlen vor
(REQ-PART-002/003). Damit verändert sich das Volltextgespräch grundlegend: Es
geht dann um einen Prozentsatz auf belegbaren Zahlen statt um die Frage, ob man
normly überhaupt glaubt.

**Kernaussage für Verhandlungen:** normly tritt nicht als Wettbewerber auf, der
Verkaufserlöse verdrängt, sondern als Kanal, der neue Erlöse erschließt und
nachvollziehbar zurückführt.

**Erster Gesprächspartner:** Austrian Standards (Volltextbereitstellung
angekündigt).

---

## ADR-014 — Verschlüsselung: kryptographisches Löschen je Herausgeber

**Status:** beschlossen

**Entscheidung:** Verschlüsselung ruhender Daten für **alle** Bestände
(Datenbank, Objektspeicher, Indizes, Protokolle, Sicherungen). Schlüssel im
STACKIT Secrets Manager, getrennt von den Daten, mit Rotation und
Zugriffsprotokoll. **Ein eigener Datenschlüssel je Herausgeber.** Dazu Schutz
vor Massenextraktion (Ratenbegrenzung, Kontingente, Anomalieerkennung).
→ REQ-SEC-001…004

**Begründung — der eigentliche Punkt sind die Backups:** REQ-PART-001 sagt zu,
dass ein Herausgeber Bestände **jederzeit** zurückziehen kann. REQ-PIPE-005
löst das über die Abstammungskette für Datenbank, Index und Exporte — aber
**nicht für Sicherungskopien.** Bestehende Backups enthalten die Inhalte
weiterhin, und selektive Bereinigung ist praktisch nicht durchführbar.

Ein Schlüssel je Herausgeber schließt die Lücke: Vertragsende → Schlüssel
vernichten → Inhalte sind überall unlesbar, auch in Backups, ohne dass ein Byte
gelöscht werden muss.

**Verhandlungsargument:** nicht „wir löschen zuverlässig", sondern „wir *können*
es danach technisch nicht mehr lesen". Das ist qualitativ etwas anderes und in
einem Lizenzgespräch deutlich belastbarer.

**Nebenbefund:** Kapitel 3.3.2 deckte nur Transportverschlüsselung ab. Die
Formulierung „Vaults oder Env-Variablen" war sachlich schief — Umgebungsvariablen
sind kein Secrets-Manager. Korrigiert.

---

## ADR-015 — Kopierschutz: Nachverfolgbarkeit statt Verhinderung

**Status:** beschlossen

**Entscheidung:** Lizenzierte Volltexte werden nie als vollständige Datei
ausgeliefert. Offline-Nutzung über verschlüsselte, an Nutzer und Gerät
gebundene, befristete lokale Ablage. Nutzerbezogene Kennzeichnung jeder Anzeige.
Alle drei Komponenten gehören zur **kommerziellen Schicht**, nicht zum Kern.
→ REQ-DRM-001…004

**Begründung:** Absoluter Schutz ist bei Text nicht erreichbar — Bildschirmfoto
plus Texterkennung liefert in Sekunden eine brauchbare Kopie. Wer das anders
verspricht, verspricht Unhaltbares. Erreichbar und ausreichend sind:

1. *Keine Datei ausliefern.* Der Schaden entsteht durch weitergegebene PDFs,
   nicht durch Lesen.
2. *Offline trotzdem ermöglichen.* Ohne Offline-Fähigkeit bleibt die PDF-Kopie
   für Leute auf der Baustelle praktischer — dann verfehlt der Ansatz seinen
   Zweck.
3. *Zurechenbarkeit.* Verhindert das Abfotografieren nicht, macht es aber
   nachverfolgbar. Genau das ist der Mehrwert gegenüber heute, wo eine
   kursierende PDF-Kopie keiner Quelle zuzuordnen ist.

**Warum kommerzielle Schicht:** Ein Schutzmechanismus mit offenliegendem
Quellcode ist kein Schutz — die Umgehung wäre direkt ablesbar. Das ist der
einzige Punkt, an dem AGPL und Kopierschutz wirklich kollidieren; die Trennung
löst ihn. Frei verfügbare Inhalte unterliegen den Beschränkungen ohnehin nicht.

**Verhandlungsargument:** normly verdrängt illegale Kopien nicht durch besseren
Schutz, sondern durch **besseren Zugang.** Eine durchsuchbare, verlinkte,
offline verfügbare Norm ist nützlicher als ein herumgereichtes PDF — und
zurückverfolgbar.

---

## ADR-016 — Mobil: PWA zuerst, nativ nur für lizenzierte Inhalte

**Status:** beschlossen

**Entscheidung:** Phase 0–1 ausschließlich **PWA** auf derselben Codebasis wie
Desktop, Offline über Service Worker für freie Inhalte. **Native App ab Phase
2/3**, ausschließlich für lizenzierte Offline-Volltexte, als Teil der
kommerziellen Schicht. F-Droid später für den freien Client.
→ REQ-MOB-001…004

**Begründung:** Der Treiber ist **nicht** das Sprachmodell, sondern der
Kopierschutz. REQ-DRM-002 verlangt eine an Nutzer und Gerät gebundene,
verschlüsselte lokale Ablage. Im Browser gibt es keinen Ort, an dem ein
Schlüssel geschützt liegen könnte — IndexedDB ist einsehbar. Native Plattformen
bieten Keychain bzw. Keystore, teils hardwaregestützt, dazu `FLAG_SECURE` gegen
Screenshots unter Android.

Damit fällt die Grenze PWA/nativ mit der Grenze frei/kommerziell zusammen.

**Lizenzkonflikt gelöst:** Die Nutzungsbedingungen des Apple App Store gelten
als unvereinbar mit AGPL/GPL (vgl. VLC-Entfernung). Die kommerzielle App ist
deshalb ein **eigenständiger Client**, der nur über die Apache-2.0-spezifizierte
API mit dem Server spricht — ein getrenntes Programm, nicht AGPL-pflichtig.

**F-Droid** verlangt vollständig quelloffene, reproduzierbare Builds ohne
proprietäre Bestandteile; die DRM-Komponenten schließen die kommerzielle App
dort aus. Für den freien Client passend — als Positionierung, nicht als
Reichweitenkanal.

**Korrigiert:** Kapitel 3.5.6 koppelte die native App an die Verfügbarkeit eines
eigenen normlyLLM. Diese Kopplung war sachlich falsch.

**Jetzt schon beachten:** Offline-Schicht hinter einer Abstraktion (REQ-MOB-003)
— später nur mit erheblichem Aufwand nachrüstbar.

**Wichtige Abgrenzung — kommerzielle Schicht ≠ kostenpflichtiger Zugang:** Die
Zuordnung der nativen App zur kommerziellen Schicht betrifft **Eigentum,
Lizenzierung und Wartung**, nicht den Nutzerzugang. Die App ist kostenfrei in
den Stores, frei verfügbare Inhalte sind darin ohne Konto und ohne Entgelt
abrufbar. Entgelte fallen ausschließlich für lizenzierte Volltexte und deren
geschützte Offline-Bereitstellung an.

Gründe: Eine App, die vor der ersten Nutzung Geld verlangt, wird nicht
installiert und nicht ausprobiert. Und die kostenlose Nutzung ist der Kanal in
die Zielgruppe — wer auf der Baustelle eine DGUV-Regel nachschlägt, ist später
derjenige, der im Betrieb nach einem Zugang zu den DIN-Volltexten fragt.

**Abgrenzung PWA/App:** Beide zeigen dieselben freien Inhalte. Um doppelte
Pflege für dieselbe Nutzergruppe zu vermeiden, bleibt die PWA der Standardweg
für Gelegenheitsnutzer; die native App wird gezielt dort beworben, wo
Offline-Nutzung gebraucht wird.

---

## ADR-017 — Anonyme Basisnutzung mit Kontingent statt Kontopflicht

**Status:** beschlossen

**Entscheidung:** Suche, Referenzgraph und frei verfügbare Inhalte sind **ohne
Konto** nutzbar, begrenzt durch ein serverseitig gezähltes Anfragekontingent.
Konto erforderlich für: höhere Kontingente, Verläufe und Merklisten, eigene
Uploads, lizenzierte Inhalte, Offline-Nutzung, kostenpflichtige Dienste — die
Aufzählung ist **abschließend**. → REQ-ACC-001…004

**Begründung gegen durchgehende Kontopflicht:**

- Sie ist die höchste Hürde in der Nutzerreise; wer erst ein Konto anlegen soll,
  geht zu Google zurück.
- Sie widerspricht „offen für jeden" — und das fällt Fördergebern und
  Normungspartnern auf.
- Betreiber eigener Instanzen (z. B. eine Innung) müssten eine Nutzerverwaltung
  betreiben, nur um freie Regelwerke anzuzeigen.
- Ohne Konto entstehen keine personenbezogenen Daten — einfachste Form der
  Datensparsamkeit.

Praktisch entstehen dadurch **mehr** Konten, nicht weniger: Wer das Produkt erst
erlebt, meldet sich freiwillig und mit erkennbarem Gegenwert an.

**Zur Sorge vor Massenextraktion über anonyme Zugänge:** Die Trennlinie ist der
**Inhalt**, nicht der Zugangsweg. Anonym erreichbar ist ausschließlich, was
nach REQ-PIPE-004 frei lizenzierbar ist — und das darf ohnehin jeder abziehen.
Lizenzierte Volltexte sind anonym **strukturell** nicht erreichbar
(REQ-PART-004 Berechtigungsprüfung, REQ-DRM-001 keine Dateiauslieferung,
REQ-DRM-003 Kennzeichnungspflicht). Das ist keine Einstellung, sondern folgt
aus der Architektur.

**Wichtig richtig einzuordnen:** Ein Konto ist **kein** Schutz vor
Massenextraktion — es macht sie nur zurechenbar. Auch angemeldete Nutzer können
systematisch abziehen, und zwar mit mehr Rechten. Der eigentliche Schutz ist
REQ-SEC-004 (Ratenbegrenzung, Anomalieerkennung, Sperrung). Ebenso ist die
adressbasierte Kontingentzählung durch Adresswechsel umgehbar; sie dient der
Kostenbegrenzung, nicht der Sicherheit.

**Umsetzung:** Zählung serverseitig über Sitzungsmerkmal plus Herkunftsadresse,
nicht über Cookies oder Browser-Speicher (beides in zwei Klicks zurückgesetzt).
Gemeinsame Infrastruktur mit REQ-SEC-004 — eine Stelle statt zwei.

**Verworfen:** Künstliche Verzögerung anonymer Antworten. Schadet dem Eindruck
mehr, als sie an Kosten spart.

---

## ADR-018 — ML-gestützte Struktur-Erkennung in der Ingestion-Pipeline (Docling)

**Status:** beschlossen

**Entscheidung:** Die Ingestion-Pipeline nutzt ab sofort
[Docling](https://github.com/docling-project/docling) statt pdfplumber zur
PDF-Extraktion, einschließlich dessen ML-gestützter Layout- und
Tabellenstruktur-Erkennung (Standard-Pipeline: Layout-Modell + TableFormer).
Damit wird der bisher im Ingestion-Spec explizit festgehaltene Nicht-Ziel-
Punkt "kein generisches Dokumentenverständnis" aufgehoben.

**Begründung:** Die ersten beiden Quellen (DGUV, EUR-Lex) kommen mit
regelbasierter Extraktion zufriedenstellend aus, aber deutlich mehr Quellen
mit unbekannten, teils komplexeren Layouts folgen. Docling liefert dafür in
jedem Fall eine sauberere, layoutbewusste Textsegmentierung als
pdfplumbers reine Zeilenausgabe, sowie eine nachweislich zuverlässige
Tabellenstruktur-Erkennung (TableFormer, gegen die echte EUR-Lex-Fixture
verifiziert).

**Wichtig, empirisch korrigiert:** Die ursprüngliche Erwartung, Docling
würde Überschriften/Abschnittsstruktur für *jede* künftige Quelle
automatisch erkennen und damit quellenspezifische Regeln überflüssig
machen, hält nicht für schlicht formatierte Dokumente ohne optische
Überschriften-Merkmale — bei der DGUV-Fixture kommen `§ N`-Überschriften
als `ListItem` zurück, nicht als `SectionHeaderItem` (siehe
`docs/superpowers/specs/2026-08-30-docling-migration-design.md`). Für
solche Quellen bleibt die Grenzerkennung musterbasiert, jetzt angewendet
auf Doclings sauber segmentierte Elemente statt auf rohem Text. Der
Gewinn ist real (bessere Segmentierung, zuverlässige Tabellen, künftig
auch Nicht-PDF-Formate ohne Zusatzaufwand), aber kleiner als ursprünglich
erhofft — jede neue Quelle muss weiterhin empirisch gegen eine echte
Beispieldatei geprüft werden, ob Doclings native Klassifikation für sie
zuverlässig funktioniert.

**Abgrenzung zu ADR-008:** ADR-008 verbietet den Einsatz eines
Sprachmodells zur **Anfragezeit** für Strukturfragen — aus Kosten-, Latenz-
und Halluzinationsgründen bei jeder einzelnen Nutzeranfrage. Diese
Entscheidung betrifft einen anderen Zeitpunkt und eine andere Modellart:
Doclings Layout-/Tabellenmodell läuft **einmalig zur Ingestion-Zeit**, ist
**diskriminativ** (erkennt Struktur in vorhandenem Inhalt), nicht
**generativ** (erfindet keinen Inhalt, kein Halluzinationsrisiko im
eigentlichen Sinn) und ist bei gleicher Eingabe deterministisch
reproduzierbar. Das Ergebnis fließt als normaler, deterministischer Inhalt
in den Referenzgraph ein — jede spätere Anfrage wird weiterhin ausschließlich
graphbasiert beantwortet, ganz ohne Modellaufruf. ADR-008 bleibt in seinem
eigentlichen Geltungsbereich unverändert.

**Umsetzung:** Modellgewichte werden einmalig beim Container-Image-Build
bezogen und gebacken — kein Zugriff auf externe Modell-Repositories zur
Laufzeit, passend zur STACKIT-only-Vorgabe für den Betrieb. Empirisch
bestätigt: Doclings Standard-Pipeline führt automatisch OCR aus (auch ohne
Bildinhalte) und lädt dafür bei aktivierter OCR zusätzliche Modelle von
modelscope.cn nach — einer zweiten, ursprünglich nicht bedachten externen
Quelle neben Hugging Face (dem Layout-/TableFormer-Modell). OCR wird daher
explizit deaktiviert (`do_ocr=False`), wodurch dieser zweite Modellbezug
vollständig entfällt, statt ihn ebenfalls ins Image backen zu müssen.
Details siehe
`docs/superpowers/specs/2026-08-30-docling-migration-design.md`.

**Verworfen:** Doclings VLM-Pipeline (generatives Vision-Language-Modell)
als Standard-Extraktionsweg — deutlich schwereres Abhängigkeits- und
Betriebsprofil ohne aktuellen Bedarf; das diskriminative Standard-Layout-
Modell reicht für die heutigen Anforderungen.

---

## ADR-019 — Kein GitHub mehr als Beitragsfassade

**Status:** abgelöst durch ADR-021 (2026-09-14) — Quellcode, CI und
Registry liegen wieder auf GitHub. Eintrag bleibt als Begründungshistorie
stehen.

**Entscheidung:** GitHub entfällt als Ziel für jede künftige Automatisierung.
Es wird kein Push-Mirror von STACKIT Git nach GitHub eingerichtet und keine
Beitragsannahme (Issues, Pull Requests) dort mehr vorgesehen. STACKIT Git
ist von Anfang an die alleinige Plattform für Quellcode, Beiträge, Build und
Betrieb — nicht nur führend neben einer öffentlichen Fassade. Der
bestehende GitHub-Spiegel (`Sn4kez/normly-app`, Remote `origin`) bleibt als
historischer Schnappschuss stehen, wird aber nicht mehr aktiv bespielt.

**Begründung:** Zwei Plattformen parallel zu pflegen — Push-Mirror,
doppelte Issue-Tracker-Disziplin, Sync-Aufwand — steht in keinem Verhältnis
zum bislang ausgebliebenen externen Beitragsvolumen über GitHub. Eine
Plattform ist einfacher und passt besser zur ohnehin STACKIT-zentrierten
Betriebsrealität.

**Konsequenz:** Löst ADR-004 teilweise ab (STACKIT-Git-Teil bleibt
unverändert bestehen, der GitHub-Beitragsfassade-Teil entfällt). REQ-GIT-002
(„Öffentliche Beitragsfassade") ist damit hinfällig und in
`docs/srs/03-anforderungen.md` entsprechend markiert. Der in
`docs/superpowers/specs/2026-09-02-ci-pipeline-design.md` /
`docs/superpowers/plans/2026-09-02-ci-pipeline.md` dokumentierte
Push-Mirror-Schritt wird nicht umgesetzt.

**Verworfen:** Beibehaltung von GitHub als reine, weiterhin manuell
gepflegte Beitragsfassade ohne Automatisierung (löst das
Pflegeaufwand-Problem nicht, verzögert die Entscheidung nur).

---

## ADR-020 — Dokumentation auf Englisch statt Deutsch

**Status:** beschlossen

**Entscheidung:** Neue Dokumentation (`docs/`-Inhalte, Code-Referenz,
Guides) wird ab sofort auf Englisch verfasst statt auf Deutsch. Ursprünglich
nicht rückwirkend gedacht; die Migration des bestehenden deutschen Contents
ist inzwischen teilweise erfolgt (siehe Nachtrag 2026-09-14 unten).
`docs/superpowers/` fällt nicht unter diese Regel — die Specs, Pläne und
Ledger dort sind Arbeitsdokumente des KI-gestützten Entwicklungsprozesses,
keine Dokumentation für Leser von außen, und bleiben wie CLAUDE.md auf
Deutsch.

**Begründung:** Englisch ist der De-facto-Standard für
Open-Source-Dokumentation. Er ermöglicht internationalen Beitragenden
Teilnahme, unabhängig vom deutschsprachigen Kernteam — passend zum
Open-Core-Modell (ADR-001) und dem Anspruch, dass der freie Kern von
außen mitgetragen werden kann. Die ursprüngliche Regel (Dokumentation auf
Deutsch) stand dem im Weg.

**Nicht betroffen:** Code, Bezeichner und Commits waren schon vorher
Englisch (unverändert). Die App-eigene Sprachumschaltung
(`LocaleProvider`, Deutsch/Englisch für Endnutzer) ist eine
Laufzeit-Funktion, keine Projektdokumentation, und bleibt unverändert.
Die Fachbegriffs-Ausnahme für Normenwesen-Begriffe ohne etablierte
englische Entsprechung (z. B. `Normenausschuss`) gilt unabhängig von der
Sprache weiter.

**Konsequenz:** CLAUDE.md's Abschnitt „Sprache" ist entsprechend
angepasst. Der bereits offene, noch nicht gemergte Merge Request für die
Zensical-Dokumentations-Site
(`docs/superpowers/plans/2026-09-11-zensical-documentation-site.md`)
wird vor dem Merge auf Englisch umgeschrieben, da er als „ab jetzt"
zählt.

**Nachtrag 2026-09-14 — Migration teilweise begonnen:** Auf Nutzerwunsch ins
Englische übersetzt: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`. Die ursprüngliche „nicht rückwirkend"-Regel gilt damit
nicht mehr uneingeschränkt für alle acht ursprünglich genannten Dateien,
sondern nur noch für die verbliebenen: `docs/adr/` (dieses Dokument),
`docs/srs/`, `GOVERNANCE.md`, `TRADEMARK.md` — deren Migration bleibt ein
eigenes, späteres Projekt, insbesondere `docs/adr/` und `docs/srs/` wegen
ihres Umfangs. Keine inhaltliche Änderung an den vier übersetzten Dateien,
nur Sprachwechsel.

---

## ADR-021 — Rückkehr zu GitHub für Quellcode, CI und Registry

**Status:** beschlossen

**Entscheidung:** GitHub (Organisation `normly`, Repository
`github.com/normly/web-app`) ist ab dem 14.09.2026 wieder die führende
Plattform für Quellcode, CI/CD und Container-Registry (GitHub Actions,
GitHub Container Registry). Das löst ADR-019 vollständig ab — nicht nur den
Beitragsfassade-Teil, sondern die gesamte Festlegung „STACKIT Git ist die
alleinige Plattform für Quellcode, Beiträge, Build und Betrieb". STACKIT
Git (`jwokittel/normly-webapp`) wird nicht mehr für Quellcode, CI oder
Registry verwendet. Es bleibt bestehen und ist als Plattform für das
künftige Hosting der Normen-Wissensbasis vorgesehen, sobald lizenzierte
Bestände hinzukommen — das ist ein Datenprojekt, kein Code-Projekt, und
folgt weiter der Trennung aus ADR-010 (Code und Daten getrennt versioniert).

**Begründung:** Nutzerentscheidung. Die Kollaboration — externe wie interne
— ist auf GitHub spürbar einfacher als auf dem selbst gehosteten
Forgejo-Setup: Tooling, Reviewer-Ökosystem und Beitragsfreundlichkeit waren
schon der ursprüngliche Grund für ADR-004, bevor ADR-019 sie zugunsten der
Souveränität einer einzigen STACKIT-Plattform verworfen hatte. Der
Kollaborationsnachteil hat sich in der Praxis stärker ausgewirkt als
erwartet; die Souveränitätsanforderung selbst bleibt bestehen, gilt aber ab
sofort für Betrieb, Nutzerdaten, die Normen-Wissensbasis und Secrets — nicht
mehr für den quelloffenen Kern-Quellcode, dessen CI und dessen
Image-Registry.

**Konsequenz:**

- Löst ADR-019 vollständig ab und ändert ADR-004 (STACKIT statt GitHub
  führend) sowie den Registry-Nachtrag in ADR-010 (STACKIT Container
  Registry statt GHCR) auf ihren jeweiligen Kernpunkt.
- CLAUDE.md's nicht-verhandelbare US-Dienste-Regel gilt unverändert für
  Betrieb, Nutzerdaten, Normen-Wissensbasis, Secrets-Management und
  Produktions-Deployment — dafür bleibt STACKIT ohne Ausnahme. Für
  Quellcode, CI/CD und Container-Registry des freien Kerns gilt ab jetzt
  die hier getroffene Ausnahme.
- `docs/srs/03-anforderungen.md` ist entsprechend zu aktualisieren:
  REQ-GIT-001 (führende Plattform), REQ-GIT-002 (Beitragsweg), REQ-BUILD-002
  (CI/CD-Infrastruktur), REQ-INST-001 (Ausnahme im Fließtext) und
  REQ-DIST-004 (Registry-Verweis).
- Der bisherige GitHub-Spiegel `Sn4kez/normly-app` (lokaler Remote
  `github-old`) war ein reiner, nicht mehr gepflegter Schnappschuss aus der
  ADR-004-Ära und ist vom neuen Repository `normly/web-app` zu
  unterscheiden — kein automatischer Zusammenhang zwischen beiden.
- Offen als technische Folgearbeit, nicht Teil dieser Entscheidung selbst:
  Port von `.forgejo/workflows/ci.yml` nach `.github/workflows/`,
  GHCR-Zugangsdaten und Secrets-Einrichtung in den GitHub-Repository-
  Einstellungen. Bis dahin läuft auf GitHub keine CI.

**Verworfen:** STACKIT Git als alleinige Plattform beibehalten (Status quo
aus ADR-019) — der Kollaborationsnachteil wiegt für den Kern-Quellcode
schwerer als der Souveränitätsgewinn, während dieser für Betrieb und Daten
weiterhin überwiegt und dort unangetastet bleibt.

---

## ADR-022 — Betriebsumgebung Phase 1 und Modellherkunftsregel

**Status:** beschlossen (2026-09-23, ergänzt 2026-10-03)

**Entscheidung:**

1. **Zielumgebung:** eine STACKIT-VM (`g1a.4d`) mit Docker Compose, Caddy
   für TLS, PostgreSQL Flex (Einzelinstanz, pgvector), Secrets Manager,
   später Object Storage. Kein SKE, kein Load Balancer. Bestätigt ADR-005.
2. **LLM-Inferenz:** STACKIT AI Model Serving (OpenAI-kompatible API,
   Region eu01), Startmodell `google/gemma-4-31B-it`. Ollama bleibt für
   lokale Entwicklung und Self-Hosting.
3. **Modellherkunftsregel:** Produktiv eingesetzte Sprachmodelle sind
   Open-Weight-Modelle unter OSI-anerkannter Lizenz, betrieben
   ausschließlich auf STACKIT-Infrastruktur; keine Anfrage erreicht den
   Modellhersteller. Europäische Herkunft ist Präferenz, nicht Pflicht.
   Wiedervorlage: sobald STACKIT ein europäisches Modell in passender
   Größe anbietet, wird der Wechsel geprüft.
4. **DNS:** die Zone `normly.ai` liegt vollständig bei STACKIT DNS
   (Registrar bleibt Strato); kein Cloudflare mehr. App unter
   `app.normly.ai`.
5. **Mailversand:** SMTP aus dem bestehenden Strato-Mailpaket
   (`noreply@normly.ai`), SPF und DKIM in der STACKIT-Zone.
6. **Umgebungen:** zunächst nur eine Produktionsumgebung auf STACKIT; das
   lokale Compose-Setup übernimmt die Rolle der Staging-Umgebung.
   Bewusste, befristete Abweichung von REQ-DIST-001, aufzuheben, sobald es
   Nutzer gibt, die ein fehlerhaftes Deployment treffen würde.
7. **Images:** ein gemeinsames Python-Basis-Image mit allen
   `core`-Abhängigkeiten und eingebackenen Embedding-Gewichten; keine
   Aufteilung der Abhängigkeiten.

**Begründung:** Die VM mit Compose ist die günstigste Umgebung und zugleich
das Self-Hosting-Artefakt aus ADR-010. AI Model Serving liefert
GPU-Inferenz pro Token ohne Dauerkosten; die Daten gehen an STACKIT, nicht
an den Modellhersteller — Gewichte sind eine Datei, kein Dienst. Die
Herkunftsregel schließt die bisher ungeregelte Lücke, dass das
Standardmodell (Llama, Meta-Lizenz) weder offen lizenziert noch
geregelt war; europäische Pflicht hätte nur eine eigene GPU-VM übrig
gelassen, da der STACKIT-Katalog kein europäisches Chat-Modell führt.
Cloudflare als DNS wäre ein US-Dienst in der Betriebskette gewesen. Die
Mail der Domain lag bereits bei Strato; ein zweiter Anbieter hätte einen
MX-Wechsel bedeutet.

**Verworfen:** Ollama auf CPU in Produktion (Antwortzeiten), eigene GPU-VM
(Dauerkosten), europäische Modellherkunft als Pflicht (kein Angebot),
Subzonen-Delegation nur für `app` (Cloudflare bliebe autoritativ), IONOS
als zweiter Mailanbieter (MX-Konflikt), Aufteilung der
`core`-Abhängigkeiten in Extras (Nutzerentscheidung zugunsten der
Einfachheit).

**Konsequenz:** CLAUDE.md erhält einen Satz zur Modellherkunft; REQ-DIST-001
und Kapitel 3.5.9 der SRS verweisen hierher; `docs/guide/self-hosting.md`
beschreibt den Compose-Weg. Folgearbeiten: Embedding-Modell nur einmal
laden und VM auf `g1a.2d` verkleinern (TP1a), Image-Pipeline (TP2),
Secrets-Bezug per AppRole (TP3), Rollout/Rollback/Datenstand (TP4). Details:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

---

## Offene Punkte

| Thema | Status | Nächster Schritt |
|---|---|---|
| Ausgründung GmbH | favorisiert, nicht beschlossen | Steuer- und vereinsrechtliche Prüfung vor Gründung |
| Rechtsform Trägerorganisation (e.V. / eG / Alternative) | offen | eG könnte Normungsorganisationen als Mitglieder statt Gegner einbinden |
| Rechteinhaber im Copyright-Header | offen | vor erstem externen Beitrag klären |
| Lizenzvertrag Trägerorganisation → GmbH | offen | muss zu marktüblichen Konditionen erfolgen, sonst Risiko für die Gemeinnützigkeit |
| RDF-/JSON-LD-Export mit SKOS | vorgeschlagen | Speicherformat und Veröffentlichungsformat sind trennbar |
| Gewichtungsmodell Attribution bei Graph-Antworten | offen | Steht einem Herausgeber etwas zu, wenn ohne Volltext geantwortet wurde? Als eigene Kategorie erfasst, vertraglich zu klären |
| Nutzungsvorbehalte je Quelle (§ 44b Abs. 3 UrhG) | laufende Aufgabe | Prüfung datiert und belegt im Quellenregister, mit Wiedervorlage |
| Rechtliche Bewertung je Rechtsraum | laufende Aufgabe | Braucht mittelfristig eine zuständige Rolle, keine einmalige Klärung |
| Apple-Provision bei digitalen Abos | offen | In der EU inzwischen Alternativen über externe Zahlungswege — vor Store-Release prüfen |
| Aufbewahrungsfristen der Sicherungskopien | offen | Bestimmt, wie lange ein vernichteter Schlüssel vorgehalten werden muss, bevor Backups auslaufen |

**Hinweis:** Die rechtlichen Einschätzungen in diesem Dokument sind
Arbeitsgrundlage, keine Rechtsberatung. Insbesondere die Konstruktion
Trägerorganisation/GmbH, die Lizenzvertragsgestaltung und die
Urheberrechtsbewertung je Rechtsraum gehören vor eine fachkundige Prüfung.
