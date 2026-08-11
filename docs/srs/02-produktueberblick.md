# 2. Produkt Überblick

Im Folgenden soll ein Überblick über das Produkt gegeben werden.

## 2.1 Produkt Perspektive

Wir unterscheiden den Produktstatus in verschiedenen Phasen.

normly folgt einem Open-Core-Modell. Der freie Kern und die kommerzielle Schicht sind organisatorisch und technisch getrennt: Der Kern enthält keine Abhängigkeit auf proprietäre Bestandteile und bleibt ohne diese vollständig lauffähig.

<img src="media/media/image1.png" style="width:6.27014in;height:8.24375in" />

Figure 1: Entwicklungsphasen

**Freier Kern (Open Source)  
**Die frei verfügbare Wissensbasis, der Referenzgraph und die Anwendung selbst sind quelloffen, selbst hostbar und ohne Lizenzkosten nutzbar. Zusätzlich können Nutzer eigene, rechtmäßig erworbene Dokumente temporär hochladen, um sitzungsbezogen darauf zu arbeiten.

**Kommerzielle Schicht  
**Auf dem freien Kern setzen kostenpflichtige Dienste auf: Managed Hosting mit SLA, Compliance-Instanzen mit Audit-Trail, Integrationen in Drittsoftware, Auswertungsberichte für Normenanbieter sowie Instanzen, in denen vertraglich lizenzierte Normenbestände eines Anbieters vorab verarbeitet sind.

<u>Information:</u> Es ist vorgesehen, die kommerzielle Schicht in eine eigene Gesellschaft (GmbH) auszugründen, während der freie Kern, die Daten und die Marke von einer nicht gewinnorientierten Trägerorganisation gehalten werden. Diese Ausgründung ist derzeit favorisiert, aber noch nicht beschlossen. Die Lizenzierung zwischen Trägerorganisation und GmbH muss zu marktüblichen Konditionen erfolgen.

Im MVP-Status wird der freie Kern als eigenständige Webanwendung bereitgestellt.

normly wird weder als Browser-Plugin für Endnutzer noch als in Anbieter-Websites einzubettendes Web Widget umgesetzt, sondern als eigenständige, selbst hostbare Webanwendung mit öffentlicher API. Die Integration in Drittsoftware (z. B. CAD- und Expertensysteme) erfolgt über diese API und ist Bestandteil der kommerziellen Schicht.

**Beispiel für die Einbettung des White Label LM:** Die [<u>Normenverwaltungssoftware Nautos</u>](https://nautos.de/login) des DIN hat über 20.000 Accounts. Je nach Abo-Status der Kunden, können diese die Software in ihrem Browser nutzen.

**Beispiel für die Einbettung des White Label GPT:** Der [<u>VDI hat für jedes seiner Mitglieder</u>](https://www.vdi.de/) einen eigenen Benutzerbereich (Mein VDI). Je nach Status, sollen die Mitglieder das Plugin in ihrem Mitgliederbereich nutzen können, um mit allen VDI Normen interagieren zu können. Dabei werden nur paraphrasierte Antworten erzeugt, da der Volltext zunächst nicht dargestellt werden darf.

Ist der MVP-Status erfolgreich validiert und im Einsatz, wird die nächste Entwicklungsstufe gezündet. Hierzu gehört die Erschließung von Einnahmequellen über die kommerzielle Schicht. Personalisierte Werbung ist ausgeschlossen: Sie ist mit der Neutralität der Trägerorganisation und mit dem Datenschutzversprechen des freien Kerns nicht vereinbar. Werbung darf nur kontextbezogen ausgeschaltet werden, d.h. zum Beispiel über den Kontext einer Norm, die für Antworten genutzt wurde, aber nicht auf Basis der persönlichen Chateingaben.

## 2.2 Produkt Funktionen

In diesem Abschnitt werden high-level die Kernfunktionen des Produkts beschrieben. Detaillierte Anforderungen werden in Abschnitt 3 behandelt.

**WICHTIG:** <u>Für den Start (MVP Status) werden noch nicht alle Funktionen benötigt!</u> Der Vollständigkeit halber, und um ein besseres Verständnis des Zielstatus zu erhalten, werden hier trotzdem alle Funktionen aufgeführt.  
Einen ersten Eindruck, wie die Zielversion aussehen kann, kann man bereits unter [<u>app.normly.ai</u>](http://app.normly.ai/) erhalten.  
MVP-spezifische Funktionen werden daher speziell hervorgehoben.

**Sprachmodell**

- Es ist für den Start ein Open Source Sprachmodell auszuwählen.

- Durch isolierten Betrieb des Modells kann ein Abfließen von Informationen ausgeschlossen werden.

- Zur Vision von normly gehört es, dass später ein eigenes, auf Rechtstexte spezialisiertes Sprachmodell entwickelt wird.

**Benutzerverwaltung**

- Wenn normgebende Vereine einen existierenden Mitgliederbereich haben (z.B. VDI, VDE oder DIN) dann wird voraussichtlich SSO zum Einsatz kommen.

- Für die spätere Skalierung ist anzumerken, dass Nutzer sich auch selbst registrieren können, um einen Account anzulegen.

- Subscription Modell: In Phase 2 wird ein Abo-Modell für die kommerzielle Schicht implementiert (Managed Hosting, SLA, Integrationen). Die Nutzung des freien Kerns bleibt davon unberührt und kostenfrei.

**Interfaces**

- Die Haupt-Interfaces werden zu den Weboberflächen der Vereine bestehen (Mitgliederbereich).

- Die Übermittlung von Normen (Dokumenten) beim White Label LM ist zentral und im Detail zu spezifizieren, wie das geschehen kann.

- Bezahlfunktion Stripe: Um ab Phase 2 ein Abomodell implementieren zu können, wird dann ein Interface zu Stripe gebraucht, um automatisiert Zahlungen entgegennehmen zu können.

**Auswertung und Berichte (kommerzielle Schicht)**

- Ab Phase 2 werden Auswertungs- und Berichtsfunktionen als kostenpflichtiger Dienst angeboten. Diese sind vollständig Teil der kommerziellen Schicht und nicht Bestandteil des freien Kerns.

- Ergänzend ist ein Verzeichnis konformitätsrelevanter Produkte vorgesehen, in dem Hersteller, Dienstleister kostenpflichtige Einträge buchen können. Personalisierte Werbung auf Basis von Suchanfragen oder Chatverläufen ist ausgeschlossen.

**Normen Insights**

- Für Auswertungsberichte ist das Erfassen aggregierter Nutzungsdaten erforderlich. Die Erhebung erfolgt ausschließlich in der kommerziellen Schicht, ist im freien Kern deaktivierbar und darf keine personenbezogenen Profile erzeugen. Anonyme Nutzungsdaten dürfen erhoben werden, um zum Beispiel aussagen zu können, wie viele Nutzer eine spezielle Norm aufrufen, oder welcher Teil einer Norm besonders oft genutzt wird und damit sehr relevant ist.

- Normen-Anbietern soll außerdem ein weiterer (kostenpflichtiger) Service angeboten werden. Sie können detaillierte Berichte kaufen, die ihnen sehr detailliert zeigen, wie und von welcher Nutzergruppe ihre Normen genutzt werden.

- Ein weiterer kostenpflichtiger Service an Endnutzer basiert auf AI-unterstützen Empfehlungen, wie Normen im Betrieb angewendet werden sollten, oder welche praxisnahen Empfehlungen aufgrund von Novellierungen empfohlen wird.

**Normen Management**

- In späteren Phasen sollen Nutzer in der Lage sein, ihre favorisierten Normen zu überwachen. Dies bedeutet auf Aktualisierungen hingewiesen zu werden usw.

**Third-Party Integrationen**

- In Phase 3 soll dann eine Third-Party Integration erfolgen. Dies bedeutet, dass Nutzer in Expertensystemen, wie z.B. Autodesk, direkt mit normlyGPT interagieren können, ohne die Software verlassen zu müssen. Die Abrechnung erfolgt nutzungsbasiert über API Calls. **Dieser Schritt stellt das größte Umsatzwachstum dar und ist der zentrale USP der kommerziellen Schicht (auszugründende GmbH). Die Integration erfolgt über die öffentliche API des freien Kerns, ohne dessen Quelloffenheit einzuschränken.** Ein eigenes Sprachmodell ist dafür nicht zwingend Voraussetzung; die Integration ist auch auf Basis des Open-Source-Modells des freien Kerns möglich.

## 2.3 Produkt Beschränkungen

Dieses Kapitel beschreibt verbindliche Rahmenbedingungen und Einschränkungen, die das Design, die Implementierung und den Betrieb von normly beeinflussen.

**Technologische Beschränkungen**

- normly muss als eigenständige, selbst hostbare, webbasierte Anwendung umgesetzt werden. Ein in Anbieter-Websites einzubettendes White-Label-Web-Widget ist nicht Bestandteil des Produkts; die Integration in Drittsysteme erfolgt ausschließlich über die öffentliche API.

- Die Nutzung von Browser-Plugins für Endnutzer ist nicht vorgesehen.  
  Für den MVP-Status wird ein Open-Source-Sprachmodell eingesetzt; ein eigenes normlyLLM ist nicht Bestandteil der initialen Entwicklungsphase.

**Infrastruktur- und Hosting-Beschränkungen**

- Das Hosting aller Systemkomponenten (Produktiv-, Test-, Staging- und Entwicklungsumgebungen) ist ausschließlich auf Serverinfrastruktur der StackIT (Schwarz Gruppe) mit Standort in Deutschland zulässig.

- Der Einsatz von US-amerikanischen Cloud- oder SaaS-Anbietern (z. B. AWS, Azure, Google Cloud) für Betrieb, Build, Datenhaltung, Zugangsdaten oder Deployment ist nicht erlaubt. Zulässig ist ausschließlich die Veröffentlichung des ohnehin öffentlichen Quellcodes auf einer externen Plattform (GitHub) als reine Beitragsfassade. Dort werden keine Zugangsdaten, Build-Artefakte, Runner oder Deployment-Rechte vorgehalten.

**Rechtliche und vertragliche Beschränkungen**

- Normen und Richtlinien unterliegen urheberrechtlichen Einschränkungen und dürfen nicht wortgleich wiedergegeben werden.

- Je nach Vertragssituation mit Normenanbietern dürfen Inhalte entweder vollständig vorab verarbeitet oder ausschließlich nutzerbasiert und temporär hochgeladen werden.

- normly stellt keine rechtsverbindliche Beratung dar.

**Funktionale Beschränkungen (MVP)**

- Monetarisierungsfunktionen (Abonnements, Abrechnung, Berichte) sind Bestandteil der kommerziellen Schicht und im MVP nicht vollständig umgesetzt. Personalisierte Werbung ist dauerhaft ausgeschlossen.

- Drittanbieter-Integrationen (z. B. CAD- oder Expertensysteme) sind nicht Bestandteil des MVP.

## 2.4 Benutzer Charakteristika

Dieses Kapitel beschreibt die primären Benutzergruppen von normly sowie deren Eigenschaften, Bedürfnisse und Nutzungskontexte, die Einfluss auf die Anforderungen haben.

**Endnutzer (Fachanwender)**

- Typische Nutzer sind Ingenieure, Techniker, Sicherheitsbeauftragte, Qualitätsmanager und Studierende.

- Die Nutzer verfügen über fachliches Domänenwissen, jedoch nicht zwingend über tiefgehende Kenntnisse der jeweiligen Normenstruktur.

- Nutzung erfolgt situativ zur Klärung konkreter fachlicher Fragestellungen.

- Erwartet werden schnelle, verständliche, paraphrasierte Antworten mit klarer Quellenangabe.

**Administrierende Nutzer (Normenanbieter)**

- Mitarbeitende von Normenanbietern oder Verbänden, die normly in ihre Website integrieren.

- Technische Kenntnisse sind vorhanden, jedoch soll die Integration mit minimalem Implementierungsaufwand möglich sein.

- Erwartet werden Konfigurationsmöglichkeiten (Branding, Zugriffssteuerung) sowie **perspektivisch Nutzungs- und Analyseberichte** (wie wir sie im normly-Dummy bereits gezeigt haben).

**Barrierefreiheit und Internationalisierung**

- Nutzer können unterschiedliche körperliche oder kognitive Einschränkungen aufweisen; daher sind barrierefreie UI-Konzepte erforderlich.

- normly richtet sich perspektivisch an ein internationales Publikum; Mehrsprachigkeit ist daher ein zentrales Nutzungsszenario. Das Frontend ist per default englisch – deutsch von Beginn an möglich. Nutzer werden später in ihrer Muttersprache mit normly interagieren können müssen, auch wenn die Quellinhalte nicht in der Muttersprache zur Verfügung stehen.

## 2.5 Annahmen und Abhängigkeiten

Dieses Kapitel beschreibt Annahmen und externe Abhängigkeiten, auf denen die Planung, Entwicklung und der Betrieb von normly basieren.

**Annahmen**

- Normenanbieter sind grundsätzlich bereit, normly in ihre bestehenden Metadaten zur Verfügung zu stellen, sofern rechtliche und vertragliche Rahmenbedingungen erfüllt sind.

- Endnutzer besitzen die rechtliche Berechtigung, Normen hochzuladen, sofern diese nicht zentral durch den Anbieter bereitgestellt werden.

- Open-Source-Sprachmodelle erreichen eine ausreichende Qualität für den MVP-Einsatz.

**Technische Abhängigkeiten**

- Verfügbarkeit und Stabilität der StackIT-Infrastruktur.

- Verfügbarkeit geeigneter Open-Source-LLMs mit kommerzieller Nutzungslizenz.

- Leistungsfähigkeit von Retrieval- und Vektorisierungsmechanismen für große Dokumentenmengen.

**Organisatorische Abhängigkeiten**

- Vertragsverhandlungen mit Normenanbietern beeinflussen Umfang und Art der verfügbaren Inhalte.

- Rechtliche Bewertungen (Urheberrecht, Haftung, Datenschutz) können Einfluss auf Funktionsumfang und UI-Gestaltung haben.

**Risiken bei falschen Annahmen**

- Verzögerungen oder Einschränkungen bei Vertragsabschlüssen können den Funktionsumfang reduzieren.

- Änderungen in der Lizenzierung von Open-Source-LLMs können technische Anpassungen erforderlich machen.

- Unerwartete Skalierungsanforderungen können zu Performance- oder Kostenrisiken führen.
