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

**Nachtrag 2026-10-09 (ADR-025):** Die Aussage oben, STACKIT Git sei als
Plattform für das künftige Hosting der Normen-Wissensbasis vorgesehen, ist
überholt. Die Wissensbasis wird als signierter Dump in einem öffentlich
lesbaren STACKIT-Object-Storage-Bucket verteilt (ADR-025); die Trennung von
Code und Daten aus ADR-010 bleibt davon unberührt. Das Repository
`jwokittel/normly-webapp` hat damit keine Aufgabe mehr. **Entschieden
(2026-10-09): Das Repository wird gelöscht**, nicht archiviert; der Betreiber
führt das im STACKIT-Portal aus. Der Git-Remote `stackit` ist damit hinfällig.
Der ursprüngliche Wortlaut bleibt als Entscheidungsverlauf stehen.

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

## ADR-023 — Image-Pipeline: GHCR, keyless Signatur, eine Version, Lock-Datei

**Status:** beschlossen (2026-10-08)

**Entscheidung:**

1. **Veröffentlichung:** Die fünf Container-Images (`api`, `chat`,
   `accounts`, `pipeline`, `frontend`) werden in GitHub Actions gebaut
   und als öffentliche Pakete unter `ghcr.io/normly/web-app/` abgelegt
   (bestätigt ADR-021). Gebaut wird bei Push auf `main` (Tags `edge`,
   `sha-<kurz>`), bei Git-Tags `vX.Y.Z` (`X.Y.Z`, `X.Y`, `latest`) und
   manuell — nie bei Pull Requests.
2. **Signatur:** cosign keyless über GitHub-OIDC. Kein Schlüsselmaterial
   wird erzeugt oder verwahrt; das kurzlebige Zertifikat bindet die
   Signatur an Repository, Workflow und Commit. Dazu je Image
   SLSA-Provenance und SBOM aus BuildKit (REQ-GIT-005).
3. **Versionierung:** Eine Version für alle fünf Images; der annotierte
   Git-Tag `vX.Y.Z` ist die einzige Quelle. Die Versionsfelder der
   Pakete werden im Release-Commit auf denselben Wert gesetzt, der
   Workflow prüft die Übereinstimmung.
4. **Reproduzierbarkeit:** Die vier Python-Pakete bilden einen
   uv-Workspace mit einer `uv.lock`; Torch kommt ausschließlich aus dem
   CPU-Wheel-Index; Basis-Images sind per Digest, Modellgewichte (e5,
   Docling) per Commit gepinnt und liegen in einer eigenen Build-Stufe
   (REQ-BUILD-001). Bewusst offen bleiben Zeitstempel in den Schichten
   und die apt-Pakete der Basisschicht; bit-identische Images sind damit
   noch nicht erreicht.

**Begründung:** Der Vertrauensanker der keyless Signatur — die öffentliche
Sigstore-Infrastruktur (Fulcio, Rekor) — wird von der **Linux Foundation
betrieben, einer Non-Profit-Organisation.** Das unterscheidet ihn
qualitativ von den kommerziellen US-Diensten in der Build-Kette, die
ADR-021 für den freien Kern erlaubt, und wiegt leichter als
Schlüsselpflege, Rotation und Neusignierung bei Verlust. Die gemeinsame
Version bildet ab, was tatsächlich getestet wird: die Dienste nur in
Kombination, `api` und `chat` sogar aus einem Basis-Image; ein Rollback
ist damit ein Handgriff. Der Verzicht auf PR-Builds hält die Pipeline
schlank; ein kaputtes Dockerfile fällt nach dem Merge laut und ohne
Schaden auf (`edge` bleibt stehen, der Release-Tag schlägt fehl). Ohne
gepinnte Gewichte könnte derselbe Git-Tag andere Embeddings erzeugen als
der Datenstand, den TP4 importiert.

**Verworfen:** eigenes cosign-Schlüsselpaar (Schlüsselpflege, Ablage
außerhalb von GitHub, Neusignierung bei Verlust); Version je Paket
(getestete Kombination nicht mehr ablesbar, ein Tag je Paket je Release);
Image-Build bei Pull Requests (voller Build je PR, Pfadfilter übersieht
Codeänderungen); pip-tools (vier Lock-Dateien mit möglicher Drift, keine
saubere Index-Trennung für Torch).

**Konsequenz:** `docker compose up -d` zieht veröffentlichte Images,
`--build` bleibt der lokale Weg; `docs/guide/self-hosting.md` beschreibt
Bezug und Signaturprüfung, `docs/guide/releasing.md` den Release-Ablauf,
`CONTRIBUTING.md` die uv-Entwicklungsumgebung. REQ-BUILD-001,
REQ-DIST-004 und REQ-GIT-005 verweisen hierher. Die Signaturprüfung als
Pflichtschritt vor dem Start auf der VM folgt mit dem Rollout-Skript
(TP4). Details:
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`.

---

## ADR-024 — Rollout, Rollback und Sicherung auf der Einzel-VM

**Status:** beschlossen (2026-10-09); baut auf ADR-010, ADR-014 und ADR-023

**Kontext:** Die Produktions-VM baut ihre Images heute aus dem Quellcode; es
gibt keinen Rollback-Punkt. Nutzerdaten sind nur durch die Flex-Sicherung
gesichert (täglich, 30 Tage, anbieterintern). STACKIT-Zugangsdaten dürfen
nicht auf GitHub liegen (ADR-021), ein Push-Rollout aus der CI scheidet also
aus. Die Signaturen aus ADR-023 nützen erst etwas, wenn die VM sie vor dem
Start prüft (REQ-GIT-005).

**Entscheidung:**

1. **Auslöser:** Rollout manuell per SSH: `normly-deploy deploy vX.Y.Z`. Das
   Skript ist timerfähig gehalten, einen Timer gibt es nicht.
2. **Prüfung vor dem Start:** `cosign verify` aller fünf Images gegen die
   Identität `images.yml@refs/tags/vX.Y.Z` des Release-Workflows. Compose-Datei
   und Skript-Assets reisen im signierten `pipeline`-Image und werden aus dem
   geprüften `pipeline@<digest>` entnommen. Die geprüften Digests werden
   festgehalten (Digest-Pinning); nach `compose pull` müssen die gezogenen
   Digests den geprüften entsprechen, sonst startet nichts.
3. **Ablauf:** aktuellen Tag und Wissensbestand-Version lesen,
   Pre-Rollout-Sicherung (ohne bestätigten Upload kein Rollout), `pull`,
   `up -d --wait`. Der aktuelle Tag wird abgelehnt; solange ein
   fehlgeschlagener Rollout vermerkt ist (`state/failed_rollout`), startet
   kein neuer `deploy` (bewusstes Übergehen: die Markierungsdatei entfernen).
   Es gibt keinen automatischen Rückweg.
4. **Rollback stellt Images und Daten auf den Stand vor dem Rollout zurück.**
   Weil Alembic-Migrationen nur vorwärts laufen, wird das Schema neu
   aufgebaut: Dienste stoppen, alle Tabellen des Schemas `public` verwerfen
   (Liste aus der Datenbank, das Schema bleibt, damit pgvector erhalten
   bleibt), `migrate` mit dem vorherigen Image, Wissensbestand in der
   damals aktiven Dump-Version importieren (vor den Nutzerdaten, wegen der
   Fremdschlüssel), die zurückgezogenen Kennungen der Sicherung
   (`exchange import-tombstones`, siehe ADR-026), Nutzerdaten mit
   `pg_restore --data-only`, vorheriges Release starten. Vorab prüft das
   Skript, dass die Alembic-Revision der Sicherung dem Alembic-Head des
   vorherigen Images entspricht, dass der aufgezeichnete Wissensbestand-Dump
   abrufbar und prüfbar ist (Signatur, Modell, Prüfsummen; ohne nutzbaren
   öffentlichen Schlüssel Abbruch, bevor etwas verändert wird) und dass die
   Tombstone-Datei der Sicherung abrufbar, entschlüsselbar und gültig ist
   (eine Sicherung, deren `meta.json` die Datei zusagt, der sie aber fehlt,
   gilt als beschädigt: Abbruch; eine ältere Sicherung ohne Zusage führt zu
   einer Warnung, der Rollback läuft weiter), und verlangt
   die Eingabe des Ziel-Tags (oder `--yes`). Der private Schlüssel wird nur
   für den Lauf bereitgestellt (`--age-identity FILE`). Scheitert der
   Rollback nach dem Verwerfen, gibt das Skript Hinweise zur Wiederherstellung;
   ein erneuter Aufruf ist gefahrlos.
5. **Sicherung:** die Nutzerdaten-Tabellen (`exchange tables user`) und, als
   zweite verschlüsselte Datei, die zurückgezogenen Kennungen
   (`<base>.tombstones.age`, ADR-026; nie Inhalt, Rechte oder Nutzerdaten).
   Beide `age`-verschlüsselt auf der VM mit dem öffentlichen Schlüssel, Upload
   per `rclone` in einen privaten STACKIT-Object-Storage-Bucket. Der private
   Schlüssel liegt nie auf der VM. Reihenfolge des Uploads: `meta.json`,
   `dump.age`, `tombstones.age`, `.sha256`; die Prüfsumme deckt beide
   verschlüsselten Dateien ab und ist die Commit-Markierung, erst mit ihr
   zählt eine Sicherung. `meta.json` trägt `"tombstones": true`.
6. **Aufbewahrung:** 7 tägliche, 2 monatliche (jeweils der neueste tägliche
   Stand der beiden jüngsten Kalendermonate), 3 Pre-Rollout-Stände. Die
   Aufbewahrung gilt für beide Dateien einer Sicherung: die Bereinigung löscht
   `.sha256`, `meta.json`, `tombstones.age`, `dump.age` in dieser Reihenfolge
   und überspringt Objekte, die nicht im Bucket liegen (ältere Sicherungen
   ohne Tombstone-Datei). Sie zählt nur committete Sicherungen und löscht
   Waisen (ohne `.sha256`, auch eine einzelne `tombstones.age`) erst nach
   einem Tag. Zusätzlich bleibt die 30-Tage-Sicherung
   der Gesamtdatenbank durch Flex das Betriebsnetz.
7. **Restore-Test:** manuell und dokumentiert (`docs/guide/operations.md`),
   nach dem Bau einmal, danach monatliche Erinnerung.

**Begründung:**

- *Manueller Auslöser:* Ein Mensch entscheidet über das Migrationsfenster.
  Migrationen liefen sonst unbeaufsichtigt, und ein Timer bräuchte eine
  „höchster Tag“-Logik und ein Stabilitätsfenster.
- *Rollback = Neuaufbau:* Migrationen sind nur vorwärts. Ein reiner
  Image-Rollback verlangte eine Expand/Contract-Disziplin, die es nicht gibt;
  ein reiner Datenrestore ließe das neue Schema stehen.
- *Nur Nutzerdaten sichern:* Der Wissensbestand ist über den Dump
  (ADR-025) reproduzierbar; ein täglicher Gesamtdump wäre bei zweistelligen GB
  verschwendet, die Nutzerdaten sind dagegen klein und unersetzlich.
- *Schlüsseltrennung:* Die VM kann Sicherungen schreiben, aber nicht
  entschlüsseln (der Bucket-Zugang der VM umfasst Lesen, weil der Rollback
  die Sicherung herunterlädt; der private Schlüssel fehlt).
  Auch bei kompromittierter VM bleiben die Sicherungen geschützt, anders als
  bei serverseitiger Verschlüsselung, deren Schlüssel beim Anbieter neben den
  Daten liegt (CLAUDE.md: Schlüssel nie neben den Daten).
- *Digest-Pinning:* `cosign verify` prüft, worauf das Tag in diesem Moment
  zeigt. Ein zwischen Prüfung und `pull` umgesetztes Tag würde sonst die
  Prüfung umgehen.
- *Commit-Markierung:* Ein abgebrochener Upload darf weder als Sicherung
  zählen noch eine ältere, gültige verdrängen.

**Verworfen:** Timer mit Auto-Rollout; reiner Image-Rollback mit
Expand/Contract-Disziplin; ausschließlich serverseitige Verschlüsselung;
täglicher Gesamtdump; nur Pre-Rollout-Dumps; wöchentliche Stände (Nutzen
jenseits von 7 Tagen klein).

**Folgen:**

- Ein Rollback verwirft alle Änderungen seit der Pre-Rollout-Sicherung
  (Konten, Chats, Watchlists). Das Skript warnt und verlangt Bestätigung.
- Die Rollback-Dauer wächst mit dem Wissensbestand (Neu-Import).
- Voraussetzung: Der Wissensbestand in Produktion ändert sich nur durch
  Dump-Import, nie durch Ingestion auf der VM (zugleich Voraussetzung für die
  Verkleinerung der VM, TP1a).
- `pg_dump`, `psql` und `pg_restore` laufen auf dem Host; `NORMLY_DATABASE_URL`
  muss dort auflösbar sein (verwaltete Datenbank, nicht das gebündelte Profil).
  Das Datenbankpasswort steht in den Prozessargumenten (Annahme: Einzelmandant-VM;
  Härtung zurückgestellt). Es braucht Docker Compose ab 2.20 (`--wait-timeout`).
- Offen: Kryptographisches Löschen bei Vertragsende (ADR-014) für lizenzierte
  Bestände ist Aufgabe der kommerziellen Schicht; sie müssen von Sicherungen
  ausgenommen oder je Herausgeber verschlüsselt werden. Der Secrets-Fluss per
  AppRole (TP3) liegt außerhalb. Eine Objektsperre im Backup-Bucket sowie PITR
  und Verschlüsselung der Flex-Sicherungen sind zu klären. Das Zusammenspiel
  von `docker compose up --wait` mit dem einmaligen `migrate`-Dienst und die
  Abfrage des Alembic-Heads sind bislang nur gegen Attrappen geprüft, bis
  zur Live-Abnahme.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`,
Betrieb: `docs/guide/operations.md`.

---

## ADR-025 — Wissensbestand-Dump als Austauschformat

**Status:** beschlossen (2026-10-09); ergänzt ADR-010, ändert die Aussage zur
Wissensbasis in ADR-021 (siehe Nachtrag dort)

**Kontext:** ADR-010 trennt Code und Daten, REQ-DIST-004 verlangt einen
eigenständig versionierten Dump, der beim ersten Start bezogen wird. Bisher
entsteht der Wissensbestand per Ingestion auf der VM; weder Selbsthoster noch
ein Rollback können ihn reproduzieren.

**Entscheidung:**

1. **Format:** Parquet je Tabelle plus `manifest.json` und die Ed25519-Signatur
   `manifest.json.sig`. Das Manifest führt Austauschschema-Version
   (unabhängig von Alembic), Dump-Version und Zeitpunkt, Einbettungsmodell mit
   Name und gepinnter Revision, Vektordimension (1024), Quelllieferungen und
   Prüfsumme samt Zeilenzahl je Datei.
2. **Zugriff:** Export und Import laufen über die Repository-Schicht
   (`KnowledgeExchangeRepository`), nicht über Postgres-Werkzeuge.
3. **Signatur:** Ed25519 in Python (`cryptography`), im Kern geprüft. Der
   öffentliche Schlüssel liegt im Repository. Die Schlüsselzeremonie steht noch
   aus; bis dahin muss der Schlüssel angegeben werden. Er wird in dieser
   Reihenfolge aufgelöst: `--public-key`, Umgebungsvariable
   `NORMLY_KB_PUBLIC_KEY_FILE`, mitgepackter Schlüssel.
4. **Verteilung:** öffentlich lesbarer STACKIT-Object-Storage-Bucket mit
   Kalenderversion `kb/<version>/` und `kb/latest`. Eine Version ist
   unveränderlich. `fetch` lädt nur von `NORMLY_KB_BASE_URL` (https, für
   localhost auch http) und prüft Version und Pfade.
5. **Import:** atomar und idempotent; der Aufrufer committet, die
   importierte Version wird in der Datenbank festgehalten. Was die neue Version
   nicht mehr enthält, wird nach ADR-026 behandelt, nie blockiert durch
   Nutzerdaten: Zitate lösen, Inhalt löschen, Tombstones setzen, Lieferungen
   zurückziehen, dann einfügen oder aktualisieren. Ein Dump ohne Dokumente
   wird abgelehnt, solange die Datenbank Dokumente hält, es sei denn
   `--allow-empty` ist gesetzt.
6. **Prüfungen beim Import:** Signatur, Austauschschema-Version, Modellname
   **und** Modellrevision (`NORMLY_EMBEDDING_MODEL_REVISION`), Dimension,
   Prüfsummen. Bei Abweichung Abbruch, keine stillen falschen Einbettungen.
   Dieselben Prüfungen laufen ohne Datenbank als Unterbefehl `verify
   (--from DIR | --fetch VERSION)`; der Rollback ruft ihn vor dem ersten
   destruktiven Schritt auf, damit ein nicht prüfbarer Dump nicht erst nach
   dem Verwerfen der Tabellen auffällt.
7. **Export-Gate:** die Rechteklassifikation als einziges Tor, über alle
   Rechtsräume hinweg ausgewertet. Exportiert wird, was eine nicht
   widerrufene Klassifikation mit `may_process` und `may_export_free` hat,
   dessen Lieferung nicht zurückgezogen ist und dessen Quelle Kategorie A, B
   oder D hat und kein kommerziell verwerteter Katalog ist. Fehlende
   Klassifikation heißt nicht exportieren. Zusammengeführte Werke werden samt
   Ziel exportiert, damit die Weiterleitung erhalten bleibt. Nutzerdaten und
   lizenzierte Bestände sind nie enthalten.
8. **Erster Start:** der Compose-Dienst `kb-import` (Profil `tools`) führt
   `import --fetch latest` aus.

**Begründung:**

- *Parquet statt `pg_dump` (Nutzerentscheidung, gegen die ursprüngliche
  Empfehlung):* ADR-006 und CLAUDE.md verlangen Datenbankzugriff nur über die
  Repository-Schicht, damit die Speichertechnologie austauschbar bleibt;
  `pg_dump` ist ein Postgres-Artefakt und umgeht sie.
- *Öffentliches Produkt (REQ-DIST-004):* Ein Format ohne Bindung an unsere
  Alembic-Revision überlebt Schemaänderungen. Bei `pg_dump` müsste jeder
  Selbsthoster die passende Anwendungsversion finden.
- *Abstammung:* Ein tabellenweiser Export mit Quelllieferung je Zeile hält die
  Rücknahme einer Lieferung auch im Dump nachvollziehbar.
- *Parquet statt NDJSON:* Einbettungen (1024 Floats, etwa 4 KB je Abschnitt)
  wären sonst unhandlich.
- *Preis:* mehr Code (Export, Import, Austauschschema), langsamerer Import,
  Idempotenz selbst herzustellen. Das nehmen wir in Kauf.
- *Ed25519 im Kern statt cosign/minisign:* Der Import läuft im
  `pipeline`-Image und beim Selbsthoster; ein zusätzliches Binary vergrößerte
  das Image und schüfe eine zweite Installationshürde. Keyless-Signatur geht
  nicht, weil der Dump lokal entsteht, nicht in der CI.
- *Object Storage statt Git:* große Binärdateien und anonymer Zugriff sind in
  einem Git-Repository unhandlich; die Wissensbasis bleibt damit auf STACKIT
  (CLAUDE.md).
- *Import mit Tombstones statt Blockieren:* siehe ADR-026.

**Verworfen:** `pg_dump` des Wissensbestands; Delta-Dumps (das Format lässt
sie offen, gebaut werden sie nicht); STACKIT Git als Ablage; ein zusätzliches
Git-Manifest als Verlauf (zweites System); NDJSON.

**Folgen:**

- ADR-021 erhält einen Nachtrag; CLAUDE.md und REQ-GIT-005 sind angepasst.
- `docs/guide/self-hosting.md` beschreibt den Import, `docs/guide/operations.md`
  Export, Signatur und Veröffentlichung.
- Das Export-Gate liest die Rechteklassifikation und führt keinen zweiten
  Prüfpfad ein.

**Personennamen (entschieden 2026-10-09):** Der Export ersetzt Personennamen
durch die Rolle `normly maintainers`. Betroffen sind
`source.responsible_person` und `rights_classification.classified_by`; beide
Spalten tragen in jeder exportierten Zeile die Konstante `PUBLISHED_ROLE`. Die
Ersetzung geschieht im Export-Statement der Repository-Schicht, also an der
Stelle des Export-Gates, und ändert weder Manifest noch Austauschschema (keine
Versionserhöhung). Der Dump trägt nie einen Namen; die Quellenregistrierung im Code enthält nur
einen Platzhalter, und Namen, die ein Ingestion-Betreiber einträgt, liegen nur
in dessen eigener Datenbank. Ein Import überschreibt die beiden Spalten mit dem
Rollenlabel: Produktion, die den öffentlichen Dump einspielt, trägt daher das
Label, nie Namen; ein erneuter Export eines importierten Stands ist zeilengleich.
Einen Dump nie in die Ingestion-Datenbank importieren: der Upsert überschreibt
dort die Namen unwiderruflich. Maskiert wird auch
`classified_by="pipeline:automatic"`; der öffentliche Dump unterscheidet damit
nicht zwischen automatischer und menschlicher Klassifikation (bewusster
Kompromiss, das Label ist eine Rolle und keine Aussage über menschliche
Prüfung).
Ein Test sucht einen eindeutigen Namen in allen Zeilen, allen Parquet-Dateien
und im Manifest.

**Offene Punkte:**

- **Delta-Dumps** sind nicht gebaut.
- **Schlüsselzeremonie:** Erzeugung, Verwahrung und Veröffentlichung des
  Signaturschlüssels stehen aus.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`.

---

## ADR-026 — Umgang mit Nutzerdaten beim Wissensbestand-Import

**Status:** beschlossen (2026-10-09); ersetzt die Blockierregel des Imports
aus ADR-025

**Kontext:** Der Import eines Wissensbestand-Dumps brach mit
`ImportBlockedError` ab, sobald Nutzerdaten (`watchlist`, `notification`,
`notified_edge`, `chat_message_citation`) auf eine Zeile verwiesen, die der neue
Dump nicht mehr enthält. Für eine rechtlich gebotene Rücknahme (Lieferung
zurückgezogen, Klassifikation widerrufen) ist das falsch: Sie darf nicht an
Nutzerdaten scheitern (CLAUDE.md, „Abstammung mitführen“). Befund aus dem Code:
Keine Nutzerdaten-Tabelle speichert urheberrechtlich geschützten Inhalt, es
sind nur Verweise (`work_id`, `edge_id`, `document_id`, `segment_id`); der Text
eines Zitats wird erst beim Lesen aus `segment` geholt.

**Entscheidung:** Eine Rücknahme gewinnt immer; ein Nutzerverweis blockiert nie
einen Import. Was der Dump nicht mehr enthält, wird nach Klasse behandelt:

| Klasse | Tabellen | Behandlung |
|---|---|---|
| Tombstone (Kennung, kein Inhalt) | `work`, `document`, `edge` | Zeile bleibt, `retired_at` wird gesetzt; Kanten werden zusätzlich widerrufen (`revoked_at`). Nutzerverweise bleiben gültig. |
| Herkunft | `source`, `delivery` | Werden nie gelöscht; eine fehlende Lieferung erhält `withdrawn_at`. |
| Inhalt/Ableitung | `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` | Werden physisch gelöscht. |

Ablauf in `replace_knowledge_base`, in dieser Reihenfolge: Schlüssel des Dumps
laden; Zitate lösen (`chat_message_citation.segment_id` wird `NULL` für Segmente,
die der Dump nicht enthält); fehlenden Inhalt in umgekehrter
Fremdschlüssel-Reihenfolge löschen; fehlende Tombstones zurückziehen; fehlende
Lieferungen mit `withdrawn_at` versehen; den Dump einfügen oder aktualisieren
(Zeilen der Tombstone-Klassen aus dem Dump erhalten `retired_at = NULL`:
Wiederkehr); Importvermerk schreiben. Löschen und Zurückziehen laufen **vor**
dem Einfügen, damit eine Neulieferung mit neuen IDs nicht an natürlichen
Eindeutigkeitsschlüsseln kollidiert (Bezeichner, Titel, partieller Index aktiver
Kanten). `ImportBlockedError` (mit `.step`) bleibt nur als letzte Sicherung für
einen unerwarteten Fremdschlüssel.

- `retired_at` (Migration 0033; `work`, `document`, `edge`) ist keine
  Austauschspalte: Dumpformat und `EXCHANGE_SCHEMA_VERSION` bleiben unverändert.
- `retired_at` ist keine Filterpflicht. Ein zurückgezogenes Dokument hat keine
  Rechteklassifikation mehr; jede tor-gebundene Lesestelle (das einzige Tor)
  schließt es damit aus. Es entsteht kein zweiter Prüfpfad.
- Schutz vor leerem Dump: Ein Dump ohne Dokumente wird abgelehnt, solange die
  Datenbank Dokumente hält (`allow_empty` bzw. `--allow-empty` hebt das auf).
- Ein Test geht alle Fremdschlüssel jeder Tabelle außerhalb des Wissensbestands
  auf den Wissensbestand durch (fail-closed), nicht nur die der
  Nutzerdaten-Tabellen, also auch `identity_resolution_case`: Jedes Ziel muss
  zu einer Klasse gehören oder eine ausdrückliche Löseregel haben.
- Meldung: Ein Widerruf löscht in Produktion die Klassifikation, der
  Rechteänderungs-Pfad von `notify-watchers` sähe also nichts. Neuer
  Benachrichtigungstyp `no_longer_available` (Migration 0034, Tabelle
  `notified_retirement`, `trigger_type` auf VARCHAR(19)): `notify-watchers`
  erzeugt eine Meldung je zurückgezogenem Dokument eines beobachteten Werks, nur
  für Rücknahmen nach Beginn der Beobachtung; Dedup-Schlüssel enthält
  `retired_at` (eine erneute Rücknahme nach Wiederkehr wird neu gemeldet). Kein
  Link; E-Mail-Betreff „Ein beobachtetes Regelwerk ist nicht mehr verfügbar“;
  Glocke „Nicht mehr verfügbar“ / „No longer available“. `delete_account`
  entfernt die `notified_retirement`-Zeilen des Kontos.

**Begründung:** Die zugesagte Rücknahme darf nie von einem Menschen oder von
Nutzerdaten abhängen. Gelöschter Inhalt ist auch in Produktion und nach Ablauf
der Sicherungen nicht mehr lesbar; Tombstones tragen nur Kennungen. Kein
Nutzerverweis geht verloren, weil sich der Wissensbestand ändert.

**Verworfen:**

- Blockieren mit Bereinigungswerkzeug: Die Rücknahme wartete auf einen Menschen.
- Nutzerverweise anpassen oder löschen: Datenverlust ohne Nutzen, da nur
  Verweise betroffen sind.
- Reine Tombstones auch für Inhalt: Die Rücknahme wäre nur logisch, der Text
  bliebe in Datenbank und Sicherungen lesbar.
- Bezeichner und Titel als Teil des Tombstones: Sie kollidieren bei einer
  Neulieferung mit den natürlichen Eindeutigkeitsschlüsseln (Befund im Review);
  das Dokument behält Herausgeber, Nummer, Ausgabe und Teil als Kennung.

**Rollback und Sicherung (Erweiterung 2):** `normly-deploy rollback` (ADR-024)
baut die Datenbank neu auf und importiert die ältere Dump-Version. Tombstones
stehen in keinem Dump; Nutzerzeilen, die auf sie zeigen, verletzten beim
Einspielen den Fremdschlüssel. Deshalb enthält jede Sicherung eine zweite,
`age`-verschlüsselte Datei `<base>.tombstones.age`:

- *Inhalt:* JSON (`format` 1, `created_at`, `rows` je Tabelle in
  Fremdschlüssel-Reihenfolge) mit allen Zeilen aus `work`, `document` und
  `edge`, deren `retired_at` gesetzt ist, plus dem Abschluss über die
  Fremdschlüssel-Eltern innerhalb von `source`, `delivery`, `work`, `document`,
  `edge`. Der Abschluss wird aus den ORM-Fremdschlüsseln berechnet, nicht
  hartverdrahtet, und nimmt nur Eltern auf, nie Kinder. Alle Spalten, auch
  `retired_at` und `revoked_at`. Nie Inhalt, Rechte oder Nutzerdaten.
  `source.responsible_person` kann enthalten sein; in Produktion ist es die
  veröffentlichte Rollenbezeichnung (Importe überschreiben es), ein Klarname
  nur in einer Datei aus einer Ingestion-Datenbank. Er liegt nur in der
  verschlüsselten Sicherung.
- *Erzeugung und Prüfung:* im Container (`exchange export-tombstones`, stdout),
  auf dem Host vor dem Verschlüsseln geprüft (JSON-Objekt, `format` 1, `rows`
  mit genau den fünf Tabellen, je eine Liste). Eine ungültige Ausgabe bricht
  die Sicherung ab.
- *Einspielen:* im Rollback nach dem Wissensbestand-Import und **vor**
  `pg_restore` (`exchange import-tombstones`, JSON auf stdin, im Image des
  vorherigen Release). Einfügen in Fremdschlüssel-Reihenfolge mit
  `ON CONFLICT DO NOTHING`; vorhandene Zeilen bleiben unverändert;
  `work.merged_into_work_id` wird aufgeschoben. Eingefügte Zeilen aus `work`,
  `document`, `edge` erhalten `retired_at` (gesicherter Wert, bei lebenden
  Eltern `created_at` der Datei) und gelten damit als zurückgezogen. Sie haben
  keine Klassifikation, jede tor-gebundene Lesestelle schließt sie aus. Ein
  späterer normaler Import, der die Zeile enthält, setzt `retired_at` wieder
  auf `NULL`.
- *Vorabprüfung:* Der Rollback lädt und entschlüsselt beide Objekte und
  prüft die Datei, bevor Banner, Bestätigung, Stopp oder `DROP` kommen. Sagt
  `meta.json` `"tombstones": true`, fehlt aber die Datei, gilt die Sicherung als
  beschädigt (Abbruch). Eine ältere Sicherung ohne Zusage bleibt nutzbar: Der
  Rollback warnt deutlich (ein Fremdschlüsselfehler ist möglich, wenn
  Nutzerdaten auf zurückgezogene Dokumente zeigen) und läuft weiter.
- *Nicht wiederhergestellt:* Inhalt und Rechte zurückgezogener Dokumente; nur
  Kennungen. Das ist gewollt, die Rücknahme bleibt wirksam.
- *`revoked_at`:* An einer zurückgezogenen Kante ist `revoked_at` der
  **Importzeitpunkt**, nicht der Zeitpunkt des Widerrufs beim Produzenten. Es
  ist kein Ereignisdatum und so nicht zu lesen.

**Folgen / offen:**

- Ein Tombstone behält nur `origin_issuer`, `origin_number`, `edition` und
  `part`. Jede Oberfläche, die Tombstones auflistet, muss darauf zurückfallen.
- Die Ingestion legt bei Neulieferung nach einem Widerruf einen **neuen**
  Dokumentknoten an (Bezeichner sind gelöscht, `find_by_designation` findet
  nichts). Beobachtungen und Meldungen bleiben am Tombstone und gehen nicht auf
  den neuen Knoten über. Produkt- und Identitätsentscheidung, offen.
- Das Export-Gate des Produzenten lässt ein Dokument aus, dessen erzeugende
  Lieferung widerrufen wurde, auch nach einer Neulieferung. Offen.
- Dumps müssen aus einer Abstammungslinie mit stabilen IDs stammen. Eine neu
  aufgebaute Produzenten-Datenbank mit neuen IDs kann mit stehengebliebenen
  Tombstones kollidieren (partieller Index aktiver Kanten u. a.) und endet in
  `ImportBlockedError`.
- Aufbewahrung und Alterung von Tombstones sind offen (Teil B, Lebenszyklus der
  Nutzerdaten).
- Die Rechteänderungs-Meldung (`RIGHTS_CHANGE`) für reine Änderungen von
  Rechtewerten, ohne dass das Dokument verschwindet, entsteht weiter beim
  Produzenten, nicht in Produktion.
- Der Schutz vor leerem Dump vertraut den Zeilenzahlen des Manifests; das
  Manifest ist signiert.

Details: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`.

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
| STACKIT-Repository `jwokittel/normly-webapp` | entschieden (2026-10-09): löschen | Der Betreiber löscht es im STACKIT-Portal (Nachtrag zu ADR-021); danach den Eintrag streichen |
| Personennamen im öffentlichen Wissensbestand-Dump | entschieden (2026-10-09): Rolle `normly maintainers` | Umgesetzt im Export (ADR-025); Eintrag nach dem ersten öffentlichen Dump streichen |
| Aufbewahrung und Alterung von Tombstones | offen | Wird mit dem Lebenszyklus der Nutzerdaten (Teil B) entschieden (ADR-026) |
| Identität bei Neulieferung nach Widerruf | offen | Neue Dokumentknoten übernehmen Beobachtungen der Tombstones nicht; Produkt- und Identitätsentscheidung (ADR-026) |
| Signaturschlüssel des Wissensbestand-Dumps | offen | Schlüsselzeremonie, öffentlichen Schlüssel ins Repository einchecken (ADR-025) |
| Sicherungen bei lizenzierten Beständen | offen | Kryptographisches Löschen (ADR-014) für die kommerzielle Schicht; Flex-PITR und Objektsperre klären (ADR-024) |

**Hinweis:** Die rechtlichen Einschätzungen in diesem Dokument sind
Arbeitsgrundlage, keine Rechtsberatung. Insbesondere die Konstruktion
Trägerorganisation/GmbH, die Lizenzvertragsgestaltung und die
Urheberrechtsbewertung je Rechtsraum gehören vor eine fachkundige Prüfung.
