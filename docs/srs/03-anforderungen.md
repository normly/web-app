# 3. Anforderungen

Dieses Kapitel beschreibt alle Anforderungen an normly. Alle Anforderungen sind eindeutig identifizierbar, überprüfbar und so formuliert, dass sie direkt in Entwicklung, Test und Abnahme überführt werden können. Die Anforderungen berücksichtigen den MVP-Status (quelloffene, eigenständige Webanwendung mit Open-Source-LLM) sowie die spätere Skalierung und die Trennung zwischen freiem Kern und kommerzieller Schicht.

## 3.1 Externe Interfaces

Dieses Kapitel beschreibt alle externen Schnittstellen von normly, über die das System mit Nutzern, Websites, Fremdsystemen und externen Diensten interagiert. Ziel ist es, alle Ein- und Ausgabepunkte so zu spezifizieren, dass Integration, Betrieb und Test eindeutig möglich sind.

### 3.1.1 User Interfaces

Dieses Kapitel beschreibt die logischen Benutzeroberflächen von normly sowie die grundlegenden Interaktionsmuster, Bedienkonzepte und Standards, die für alle Nutzeroberflächen verbindlich einzuhalten sind, unabhängig von der konkreten visuellen Gestaltung.

#### REQ-UI-001 — Chat-Oberfläche der eigenständigen Webanwendung

**Statement:** Das System muss eine eigenständige Chat-Oberfläche als Bestandteil der quelloffenen Webanwendung bereitstellen. Eine Einbettung per Browser-Plugin oder Skript in Websites von Normenanbietern ist nicht vorgesehen.  
**Rationale:** normly ist eine eigenständige Anwendung; Betreiber einer eigenen Instanz sollen Erscheinungsbild und Konfiguration anpassen können.  
**Akzeptanzkriterium:**

- Erscheinungsbild (Farben, Typografie, Logo) ist per Konfiguration anpassbar

- Die Oberfläche ist ohne externe Abhängigkeiten in einer eigenen Instanz lauffähig

**Abnahmekriterium:** Eine selbst betriebene Instanz stellt die Chat-Oberfläche mit eigener Konfiguration bereit.

**Weitere Informationen:** Ersetzt den früheren White-Label-Ansatz, siehe ADR-001.

#### REQ-UI-002 — Chat-basierte Interaktion

**Statement:** Das UI muss eine Chat-basierte Interaktion mit dem Sprachmodell ermöglichen, inklusive Texteingabe, Antwortanzeige und Ladezuständen.  
**Rationale:** Chat ist das primäre Interaktionsparadigma für LLM-basierte Systeme.  
**Akzeptanzkriterium:**

- Texteingabe mit Absenden per Button oder Enter

- Visueller Ladeindikator während Modellantwort

- Mindestens ein vollständiger Frage-Antwort-Zyklus im Browser

**Weitere Informationen:** Anlehnung an ChatGPT / Perplexity UX

#### REQ-UI-003 — Quellenanzeige und Verlinkung

**Statement:** Das UI muss für jede Antwort die verwendeten Regelwerke als Quelle anzeigen. Bei frei verfügbaren Inhalten wird auf die Originalfundstelle verlinkt, bei kostenpflichtigen Regelwerken auf die Bezugsquelle des Herausgebers.  
**Rationale:** Nachvollziehbarkeit der Antwort, rechtliche Absicherung sowie Weiterleitung an den Herausgeber als Erlösquelle (Affiliate, siehe Kapitel 3.4).  
**Akzeptanzkriterium:**

- Jede Antwort enthält mindestens eine Quellenreferenz

- Der Verweis führt bei freien Inhalten zur Originalfundstelle, bei kostenpflichtigen zur Bezugsquelle des Herausgebers

**Abnahmekriterium:** Für beide Quellenarten führt der Verweis nachweislich zum korrekten Ziel.

**Weitere Informationen:** Siehe Kapitel 3.4 Compliance und REQ-PART-002 (Attribution).

#### REQ-UI-004 — WCAG-Konformität

**Statement:** Das User Interface muss mindestens WCAG 2.1 AA konform sein.  
**Rationale:** Barrierefreiheit ist rechtlich und ethisch erforderlich.  
**Akzeptanzkriterium:**

- Tastaturbedienbarkeit

- Screenreader-Kompatibilität

- Kontraste gemäß WCAG

**Weitere Informationen:** Gilt für alle UI-Komponenten

#### REQ-UI-005 — Anzeige und Verwaltung der Chat-Historie

**Statement:** Das User Interface muss es Nutzern ermöglichen, ihre bisherigen Chat-Unterhaltungen einzusehen, erneut aufzurufen und zwischen mehreren Chat-Sitzungen zu wechseln, vergleichbar mit der Chat-Historienfunktion moderner KI-Chat-Anwendungen.

**Rationale:** Nutzer erwarten bei der Arbeit mit komplexen normativen Inhalten die Möglichkeit, frühere Fragestellungen und Antworten erneut nachzuvollziehen, fortzuführen oder zu referenzieren.

**Akzeptanzkriterium:**

- Eine übersichtliche Liste vergangener Chats ist im UI verfügbar

- Chats werden nach Erstellungsdatum sortiert

- Ein ausgewählter Chat kann erneut geöffnet und fortgeführt werden (Ausnahme, wenn Dokumente hochgeladen wurden - siehe Anforderung REQ-INT-002C)

- Die Anzeige ist auch bei einer größeren Anzahl an Chats performant nutzbar

**Abnahmekriterium:** Ein Nutzer kann mindestens drei getrennte Chat-Sitzungen erstellen, diese schließen, später erneut öffnen und den Dialog fortsetzen.

**Weitere Informationen:**

- Die Persistenz der Chat-Historie kann nutzer- oder mandantenspezifisch konfigurierbar sein

- Datenschutz- und Löschkonzepte sind gemäß Sicherheits- und Compliance-Anforderungen zu berücksichtigen

### 3.1.2 Hardware Interfaces

Dieses Kapitel beschreibt etwaige Anforderungen an Hardware-Schnittstellen. Für normly sind aktuell keine expliziten Hardware-Integrationen vorgesehen.

### 3.1.3 Software Interfaces

Dieses Kapitel spezifiziert alle softwareseitigen Schnittstellen zu externen Systemen, darunter Website-Integrationen, Authentifizierungsdienste, Datenquellen für Normen sowie die Anbindung an Sprachmodelle und weitere Drittsysteme.

Normly unterstützt zwei Integrationsmodi für Normendokumente:

1.  Anbieterbasierte Vorab-Integration kompletter Normenbestände

2.  Nutzerbasierte, temporäre Dokumenten-Uploads zur sitzungsbezogenen Modellanreicherung

#### REQ-INT-001 — Öffentliche API zur Integration in Drittsoftware

**Statement:** Das System muss ein **dokumentiertes, öffentliches HTTP-API** bereitstellen, über das Drittsysteme (z. B. CAD-, ERP- und Expertensysteme) Anfragen an normly stellen können. Die API ist Bestandteil des freien Kerns und unter Apache-2.0 spezifiziert; die fertigen Integrationen in konkrete Drittsysteme gehören zur kommerziellen Schicht.  
**Rationale:** Die Integration in bestehende Fachsoftware ist der zentrale USP der kommerziellen Schicht. Eine offene, stabile API stellt sicher, dass Zusatzdienste ohne Fork des Kerns andocken können und keine Abhängigkeit von Browser-Erweiterungen entsteht.

**Akzeptanzkriterium:**

- Die API ist vollständig als OpenAPI-Spezifikation dokumentiert und versioniert

- Ein Drittsystem kann ohne Kenntnis der internen Implementierung Anfragen stellen und Antworten mit Quellenangabe verarbeiten

- Keine Installation von Browser-Erweiterungen oder Skripten durch Endnutzer erforderlich

**Abnahmekriterium:** Ein Referenzclient spricht die API gegen zwei aufeinanderfolgende Versionen erfolgreich an.

**Weitere Informationen:** Spezifikation unter Apache-2.0, siehe REQ-OSS-001 und REQ-COM-001.

#### REQ-INT-002 — Schnittstelle zu Normen-Datenbanken

**Statement:** Das System muss Normendokumente (PDF, XML) automatisiert aus den Datenbanken der Herausgeber übernehmen können, sofern hierfür eine vertragliche Grundlage nach Kategorie C des Quellenregisters besteht.  
**Rationale:** Skalierbare Datenpflege ohne manuelle Uploads. Die Beschränkung auf vertraglich bezogene Bestände folgt aus REQ-PIPE-008.  
**Akzeptanzkriterium:**

- Import über API oder SFTP

- Metadatenübernahme (Titel (DE und ENG), Version, Ausgabedatum, Gültigkeit)

**Abnahmekriterium:** Automatisierter Import eines Normenbestands über das Partnerportal.

**Weitere Informationen:** Siehe Kapitel 3.6.2 Datenmanagement, 3.12 Verarbeitungskette sowie REQ-PART-001.

#### REQ-INT-002A — Nutzerbasierter Dokumenten-Upload und temporäre Modellanreicherung

**Statement:** Das System muss einen Integrationsmodus unterstützen, bei dem Normendokumente nicht vorab vollständig durch den Normenanbieter bereitgestellt werden, sondern vom Endnutzer selbst hochgeladen werden können, um das Sprachmodell **temporär und sitzungs- bzw. nutzerspezifisch** für die Beantwortung von Fragen anzureichern.

**Rationale:** Nicht alle Normenanbieter stellen ihre vollständigen Normenbestände zur Vorabverarbeitung zur Verfügung. Um dennoch einen Mehrwert zu bieten, muss normly es Nutzern ermöglichen, ausschließlich mit den von ihnen rechtmäßig erworbenen und hochgeladenen Dokumenten zu interagieren, vergleichbar mit dem Ansatz von NotebookLM.

**Akzeptanzkriterium:**

- Nutzer können Normendokumente (z. B. PDF, XML) über die Anwendung hochladen

- Die hochgeladenen Dokumente werden ausschließlich für den jeweiligen Nutzer oder die jeweilige Sitzung verarbeitet

- Das Sprachmodell beantwortet Fragen nur auf Basis der hochgeladenen Inhalte

- Es erfolgt kein persistentes Training des globalen Modells mit diesen Dokumenten

**Abnahmekriterium:** Ein Nutzer lädt eine gekaufte Norm hoch und kann unmittelbar danach in einem Chat Fragen stellen, deren Antworten ausschließlich auf dem hochgeladenen Dokument basieren.

**Weitere Informationen:**

- Funktional vergleichbar mit Google NotebookLM

- Technische Umsetzung z. B. über temporäre Vektorisierung / Retrieval-Augmented Generation (RAG)

- Relevante Abgrenzung zu REQ-INT-002 (anbieterzentrierte Vorab-Integration)

#### REQ-INT-002B — Isolation nutzerspezifischer Dokumente

**Statement:** Das System muss sicherstellen, dass von Nutzern hochgeladene Dokumente strikt von anderen Nutzern und vom globalen Datenbestand isoliert verarbeitet werden.

**Rationale:** Vermeidung von Datenlecks und Urheberrechtsverletzungen.

**Akzeptanzkriterium:**

- Kein Nutzer kann Inhalte anderer Uploads abfragen

- Sicherheitsaudit bestätigt Isolation

#### REQ-INT-002C — Zeitlich begrenzte Speicherung hochgeladener Dokumente

**Statement:** Das System muss eine konfigurierbare zeitliche Begrenzung für die Speicherung nutzerhochgeladener Dokumente unterstützen, um Serverspeicherplatz zu reduzieren.  
**Rationale:** Reduzierung rechtlicher Risiken und Speicherbedarf.

**Akzeptanzkriterium:**

- Automatische Löschung nach definierter Frist

- Dokument ist nach Ablauf nicht mehr abrufbar

**Weitere Informationen:** Default 7 Tage

#### REQ-INT-003 — SSO-Authentifizierung

**Statement:** Das System muss Single-Sign-On mit bestehenden Mitgliederbereichen von Organisationen unterstützen. SSO ist optional und darf nicht Voraussetzung für die Nutzung frei verfügbarer Inhalte sein.  
**Rationale:** Nahtlose Nutzererfahrung ohne zusätzliche Logins für Organisationen, die eine eigene Nutzerverwaltung betreiben. Die Optionalität folgt aus REQ-ACC-001.  
**Akzeptanzkriterium:**

- Unterstützung gängiger Standards (OAuth2, SAML)

- Login über externes Identitätssystem erfolgreich

**Weitere Informationen:** Weitere Anmeldemöglichkeiten wie EMail, mit Google müssen ebenfalls möglich sein.

#### REQ-INT-004 — LLM-Schnittstelle

**Statement:** Das System muss über eine klar definierte Schnittstelle mit einem externen LLM (z. B. Llama 3.1) kommunizieren.  
**Rationale:** Austauschbarkeit des Modells und spätere Migration auf eigenes LLM.  
**Akzeptanzkriterium:**

- Abstraktionsschicht vorhanden

- Modellwechsel ohne UI-Anpassung

- LLM kann ausgetauscht werden, ohne Funktionseinbußen

**Weitere Informationen:** Siehe Kapitel 3.6

## 3.2 Funktionale Anforderungen

Dieses Kapitel beschreibt die funktionalen Fähigkeiten von normly aus Sicht externer Beobachter. Es definiert, welche Funktionen das System bereitstellt, welche Eingaben verarbeitet werden, wie darauf reagiert wird und welche Ausgaben oder Fehlerzustände entstehen können.

### REQ-FUNC-001 — Beantwortung normbasierter Fragen

**Statement:** Das System muss Nutzerfragen ausschließlich auf Basis der verfügbaren Normen beantworten.  
**Rationale:** Vermeidung von Halluzinationen und Rechtsrisiken.

**Akzeptanzkriterium:**

- Antwort enthält nur Inhalte aus referenzierten Normen

**Weitere Informationen:** AI-Safety relevant

### REQ-FUNC-002 — Paraphrasierung statt Volltext

**Statement:** Das System darf urheberrechtlich geschützte Normtexte nicht als Volltext wiedergeben. Zulässig sind Paraphrasen sowie kurze, als Zitat gekennzeichnete Auszüge, soweit ein Lizenzvertrag mit dem Rechteinhaber dies ausdrücklich erlaubt. Für Inhalte, die frei weitergegeben werden dürfen (z. B. amtliche Werke nach § 5 UrhG), gilt diese Beschränkung nicht.  
**Rationale:** Urheberrechtsschutz. Ohne diese Präzisierung widerspricht die Anforderung den Output-Rechten aus den vorgesehenen Lizenzverträgen.  
**Akzeptanzkriterium:** Antworten sind eindeutig paraphrasiert

**Abnahmekriterium:**

- Plagiatsprüfung ohne Treffer

- Zwingend für alle Antworten

### REQ-FUNC-003 — Fehler- und Fallback-Antworten

**Statement:** Das System muss bei unklaren oder nicht beantwortbaren Fragen eine erklärende Fallback-Antwort liefern.  
**Rationale:** Vertrauen und Transparenz.

**Akzeptanzkriterium:**

- Kein erfundener Inhalt bei fehlender Datenbasis

- Test mit absichtlich unbeantwortbaren Fragen

**Weitere Informationen:** Human-in-the-Loop relevant, je nach Umsetzungsaufwand ist diese Funktion für den MVP in Frage zu stellen.

## 3.3 Nicht-Funktionale Anforderungen

Dieses Kapitel beschreibt die qualitativen Eigenschaften, die das System erfüllen muss, um ein zuverlässiges, sicheres und skalierbares Nutzererlebnis zu gewährleisten. Diese Anforderungen beschränken oder qualifizieren das funktionale Verhalten.

### 3.3.1 Performance

Dieses Kapitel definiert Anforderungen an Antwortzeiten, Durchsatz und Reaktionsverhalten des Systems unter normalen und erwarteten Lastbedingungen.

#### REQ-PERF-001 — Antwortzeit Chat

**Statement:** Das System muss innerhalb von 2–4 Sekunden nach Datenverfügbarkeit eine erste Antwort liefern.  
**Rationale:** Erwartung an modernes Chat-UX.  
**Akzeptanzkriterium:** 95 % der Anfragen \<4 Sekunden

**Abnahmekriterium:**

- Lasttest mit definiertem Datensatz

**Weitere Informationen:** Gilt für MVP

### 3.3.2 Sicherheit

Dieses Kapitel beschreibt die sicherheitsrelevanten Anforderungen an Authentifizierung, Autorisierung, Datenverarbeitung, Kommunikation und Entwicklungsprozesse, um Nutzer- und Systemdaten angemessen zu schützen.

Die Sicherheit wird auf verschiedenen Ebene unterschiedlich gewährleistet:

**Authentifizierung & Autorisierung**

- Passwort-Hashing (z. B. bcrypt) und Multi-Faktor-Authentifizierung (MFA).

- Prinzip Least Privilege: Benutzer erhalten nur minimale notwendige Rechte.

- Magic-Link-Login (OTP) denkbar

**Eingabevalidierung & Ausgabe-Encoding**

- Parametrisierte Queries/Prepared Statements gegen SQL-Injection.

- Input-Sanitization und Output-Encoding (z. B. HTML-escaping) gegen XSS/CSRF.

**Verschlüsselung & Datenübertragung**

- TLS 1.3 für alle Kommunikationen (HTTPS only), einschließlich der Verbindungen zwischen internen Diensten und zur Datenbank. Verschlüsselung ruhender Daten gemäß Kapitel 3.13.

- Secrets-Management: Zugangsdaten werden ausschließlich im STACKIT Secrets Manager gehalten, nicht im Quellcode, nicht in Konfigurationsdateien und nicht dauerhaft in Umgebungsvariablen. Repositories und Build-Artefakte werden automatisiert auf versehentlich enthaltene Zugangsdaten geprüft.

**Entwicklungsprozesse**

- Secure Coding Standards, automatisierte SAST/DAST-Tests in CI/CD-Pipeline.

- Regelmäßige Pen-Tests, Threat Modeling und Dependency-Scanning (SCA).

### 3.3.3 Zuverlässigkeit und Beobachtbarkeit

Dieses Kapitel definiert Anforderungen an die Stabilität des Systems sowie an Logging, Monitoring und Fehlerbehandlung, um einen sicheren Betrieb und eine effektive Fehleranalyse zu ermöglichen.

Um eine konsistente Überwachung der Software und des Nutzerverhaltens zu haben, sollten alle Anfragen, Ergebnisse, Ereignisse usw. systemtechnisch protokolliert werden.

Sollten Fehler auftreten, die direkt mit dem Nutzer (z.B. fehlerhafte Eingaben) zu tun haben, sollen diese dem Benutzer mitgeteilt werden.

### 3.3.4 Verfügbarkeit

Dieses Kapitel beschreibt Anforderungen an die zeitliche Verfügbarkeit des Systems sowie an Maßnahmen zur Sicherstellung einer definierten Mindest-Uptime.

Die Software (und somit die zugehörigen Server) soll eine **Uptime von 99%** haben.

## 3.4 Compliance

Die Entwicklung von normly orientiert sich maßgeblich an den zur Verfügung stehenden Normen und Richtlinien. Je nach Vertragssituation mit den normengebenden Vereinen, können diese vorab in das Sprachmodell geladen (da sie und komplett zur Verfügung stehen) oder nur situativ hochgeladen werden.

Es ist bei der Ausgabe von Chat Antworten darauf zu achten, dass nie eine originale 1:1 Wiedergabe des Quellmaterials stattfindet, um eine Urheberrechtsverletzung zu vermeiden. Die verwendeten (zitierten) Quellen sind jeweils aufzuführen und auf die Originalform zu verlinken.

**Wichtig:** Die Verlinkung auf die Original-Norm erfolgt immer auf den jeweiligen Shoplink des Anbieters. Eine Vergütung dieser Weiterleitung (Affiliate-Modell) kann an dieser Stelle in Betracht gezogen werden. Personalisierte Werbung ist ausgeschlossen.

## 3.5 Design und Implementierung

Dieses Kapitel beschreibt verbindliche Anforderungen und Rahmenbedingungen für das Design, die Implementierung, den Build-, Deployment- und Distributionsprozess von normly.

Die hier definierten Anforderungen stellen sicher, dass das System sicher, wartbar, skalierbar und konform mit den Zielen der Daten- und Technologiesouveränität betrieben werden kann.

Sie gelten für alle Umgebungen (Entwicklung, Test, Staging und Produktion) und ergänzen die funktionalen sowie nicht-funktionalen Anforderungen der vorangegangenen Kapitel um konkrete Vorgaben zur technischen Umsetzung und zum Betrieb.

### 3.5.1 Installation (Deployment)

Dieses Kapitel definiert Anforderungen an die Bereitstellung, Konfiguration und Wiederherstellung der normly-Software in allen Zielumgebungen.

#### REQ-INST-001 — Deployment auf deutscher StackIT-Infrastruktur

**Statement:** Das System muss in allen Umgebungen (Produktiv-, Test-, Staging- und Entwicklungsumgebung) ausschließlich auf **Serverinfrastruktur der StackIT (Schwarz Gruppe) mit Standort in Deutschland** betrieben werden.

**Rationale:** Sicherstellung von Datenhoheit, rechtlicher Souveränität und Unabhängigkeit von nicht-europäischen Cloud-Anbietern.

**Akzeptanzkriterium:**

- Alle Compute-, Storage- und Netzwerkressourcen stammen von StackIT

- Serverstandorte befinden sich in Deutschland

**Abnahmekriterium:** Infrastruktur- und Vertragsprüfung bestätigt ausschließliche Nutzung von STACKIT-Services in Deutschland.

**Weitere Informationen:** Gilt auch für LLM-Inferenz, Vektordatenbanken, Logging und Monitoring. Einzige Ausnahme ist die Veröffentlichung des ohnehin öffentlichen Quellcodes und der Container-Images auf einer externen Plattform als Beitragsfassade, siehe REQ-GIT-002.

#### REQ-INST-002 — Automatisiertes Deployment

**Statement:** Das System muss vollständig automatisiert deploybar sein, ohne manuelle Eingriffe in Zielumgebungen.

**Rationale:** Reduzierung von Fehlern, schnellere Releases und reproduzierbare Umgebungen.

**Akzeptanzkriterium:**

- Deployment erfolgt per Skript oder Pipeline

- Kein manuelles Server-Setup erforderlich

**Abnahmekriterium:** Neues System kann aus leerer Umgebung automatisiert bereitgestellt werden.

**Weitere Informationen:** Infrastructure as Code empfohlen.

#### REQ-INST-003 — Konfigurationsmanagement über Umgebungsvariablen

**Statement:** Umgebungsspezifische Konfigurationen (z. B. Endpunkte, Feature-Flags) müssen über Umgebungsvariablen oder zentrale Konfigurationsdienste erfolgen. Zugangsdaten und Schlüsselmaterial werden ausschließlich im STACKIT Secrets Manager gehalten, nicht in Umgebungsvariablen.

**Rationale:** Trennung von Code und Konfiguration erhöht Sicherheit und Wartbarkeit.

**Akzeptanzkriterium:**

- Keine secrets im Quellcode

- Unterschiedliche Umgebungen ohne Codeänderung betreibbar

**Abnahmekriterium:** Code-Review zeigt keine hartkodierten Konfigurationswerte.

**Weitere Informationen:** Siehe Kapitel 3.3.2 sowie REQ-SEC-002.

#### REQ-INST-004 — Rollback-Fähigkeit

**Statement:** Das System muss die Möglichkeit bieten, ein Deployment automatisiert auf eine vorherige stabile Version zurückzusetzen.

**Rationale:** Minimierung von Ausfallzeiten bei fehlerhaften Releases.

**Akzeptanzkriterium:**

- Mindestens eine vorherige Version ist jederzeit wiederherstellbar

**Abnahmekriterium:** Rollback wird erfolgreich in Testumgebung durchgeführt.

**Weitere Informationen:** Blue-Green oder vergleichbare Strategien zulässig.

### 3.5.2 Build and Delivery

Dieses Kapitel definiert Anforderungen an Build-Prozesse, Artefakterstellung, Integrität und Auslieferung der Software.

#### REQ-BUILD-001 — Reproduzierbare Builds

**Statement:** Builds des Systems müssen reproduzierbar sein, sodass derselbe Quellcode unter gleichen Bedingungen identische Artefakte erzeugt.

**Rationale:** Nachvollziehbarkeit, Sicherheit und Debugging-Fähigkeit.

**Akzeptanzkriterium:**

- Versionierte Abhängigkeiten

- Build ohne externe, nicht deterministische Einflüsse

**Abnahmekriterium:** Zwei Builds aus identischem Commit erzeugen identische Artefakte.

**Weitere Informationen:** Gilt für Backend, Frontend und ML-Komponenten.

#### REQ-BUILD-002 — EU-basierte Build- und CI/CD-Infrastruktur

**Statement:** Build-, Test- und CI/CD-Prozesse müssen auf **STACKIT Pipelines** oder gleichwertiger, nicht-US-amerikanischer Infrastruktur betrieben werden.

**Rationale:** Schutz von Quellcode, Modellkonfigurationen und Prompts vor extraterritorialem Zugriff.

**Akzeptanzkriterium:**

- Keine Ausführung von Builds, Tests oder Deployments auf US-SaaS-CI-Systemen

- Runner, Container Registry und Secrets Manager werden ausschließlich in STACKIT betrieben

**Abnahmekriterium:** Tooling-Review bestätigt, dass kein Build- oder Deployment-Schritt außerhalb von STACKIT läuft.

**Weitere Informationen:** STACKIT Git (Forgejo) mit STACKIT Pipelines, siehe REQ-GIT-001.

#### REQ-BUILD-003 — Automatisierte Qualitätssicherung im Build

**Statement:** Builds dürfen nur erfolgreich abgeschlossen werden, wenn definierte Qualitätskriterien (Tests, Linting, Security-Checks) erfüllt sind.

**Rationale:** Vermeidung instabiler oder unsicherer Releases.

**Akzeptanzkriterium:**

- Fehlgeschlagene Tests verhindern Auslieferung

**Abnahmekriterium:** Pipeline bricht bei Testfehlern ab.

**Weitere Informationen:** Siehe auch Kapitel 3.5.4 Wartbarkeit.

### 3.5.3 Distribution

Dieses Kapitel beschreibt Anforderungen an die Verteilung, Skalierung und Trennung der Systemkomponenten über mehrere Umgebungen hinweg.

#### REQ-DIST-001 — Klare Trennung von Umgebungen

**Statement:** Produktiv-, Staging-, Test- und Entwicklungsumgebungen müssen strikt voneinander getrennt betrieben werden.

**Rationale:** Vermeidung von Datenlecks und unbeabsichtigten Änderungen im Produktivsystem.

**Akzeptanzkriterium:**

- Getrennte Infrastruktur und Konfigurationen

- Keine gemeinsamen Datenbanken

**Abnahmekriterium:** Architektur-Review bestätigt Umgebungstrennung.

**Weitere Informationen:** Gilt auch für ML-Daten und Logs.

#### REQ-DIST-002 — Skalierbare Verteilung der Systemkomponenten

**Statement:** Das System muss so verteilt sein, dass einzelne Komponenten (z. B. Chat-Backend, LLM-Inferenz, Dokumentenverarbeitung) unabhängig voneinander skaliert werden können.

**Rationale:** Kosteneffizienz und Performance bei wachsender Nutzung.

**Akzeptanzkriterium:**

- Horizontale Skalierung einzelner Services möglich

**Abnahmekriterium:** Lasttest zeigt erfolgreiche Skalierung einzelner Komponenten.

**Weitere Informationen:** Microservice- oder modulare Architektur empfohlen.

#### REQ-DIST-003 — Optionale Mandantenfähigkeit für Managed Hosting

**Statement:** Das System soll optional mehrere Organisationen (Mandanten) logisch getrennt innerhalb derselben Deployment-Struktur betreiben können. Mandantenfähigkeit ist Voraussetzung für das Managed-Hosting-Angebot der kommerziellen Schicht, nicht für den Betrieb einer einzelnen Instanz des freien Kerns.

**Rationale:** Grundvoraussetzung für das Managed-Hosting-Angebot der kommerziellen Schicht. Für den Betrieb einer einzelnen Instanz des freien Kerns ist Mandantenfähigkeit nicht erforderlich und darf keine Voraussetzung sein.

**Akzeptanzkriterium:**

- Trennung von Konfiguration, Erscheinungsbild und Daten je Mandant

- Der freie Kern ist ohne aktivierte Mandantenfähigkeit vollständig lauffähig

**Abnahmekriterium:** Zwei Organisationen können parallel ohne Überschneidungen betrieben werden; eine Einzelinstanz läuft ohne Mandantenkonfiguration.

**Weitere Informationen:** Relevanz für UI, Datenmanagement und Abrechnung. Trennung lizenzierter Bestände siehe REQ-PART-004 und REQ-SEC-003.

#### REQ-DIST-004 — Versionierte Auslieferung der Anwendung

**Statement:** Die Anwendung muss als versionierte, signierte Container-Images ausgeliefert werden, ergänzt um ein lauffähiges Compose-Setup, das Anwendung, Datenbank und Grundkonfiguration in einem Aufruf startet. Der freie Wissensbestand ist nicht Bestandteil des Images, sondern wird als eigenständig versionierter Dump bereitgestellt und beim ersten Start bezogen. Code- und Datenstand sind getrennt versioniert und unabhängig voneinander aktualisierbar.

**Rationale:** Ein quelloffener Kern, den außer dem Projekt selbst niemand betreiben kann, ist praktisch nicht offen. Das Container-Image ist der Nachweis der Selbst-Hostbarkeit und zugleich Grundlage der eigenen Deployments und des Managed-Hosting-Angebots. Die Trennung von Code und Daten ist erforderlich, weil sich Normenstände deutlich häufiger ändern als der Anwendungscode.

**Akzeptanzkriterium:**

- Ein Compose-Aufruf startet eine lauffähige Instanz ohne manuelle Nacharbeit; Image-Größe bleibt unabhängig vom Umfang des Wissensbestands; Datenstände sind einzeln referenzierbar und austauschbar; Images sind signiert und über einen öffentlich lesbaren Weg beziehbar.

**Abnahmekriterium:** Eine leere Umgebung wird ohne Vorkenntnisse allein anhand der Dokumentation in Betrieb genommen; ein Wechsel des Datenstands erfolgt ohne Neubau des Images.

**Weitere Informationen:** Führende Registry ist die STACKIT Container Registry. Für den öffentlichen Bezug ist ein Spiegel auf der bereits als Beitragsfassade genutzten Plattform vorzusehen. Helm-Charts für den Betrieb auf Kubernetes können ergänzend folgen. Cache-Strategien sind zu berücksichtigen.

### 3.5.4 Wartbarkeit

Um das Onboarding von weiteren Entwicklern zu erleichtern, die Zeit für Fehlerbehebungen zu reduzieren und um die Entwicklung zu beschleunigen ist auf folgende Entwicklungsgrundsätze zu achten:

**Bereich**

**Vorgabe**

**Modulare Architektur**

Code in unabhängige, austauschbare Module unterteilen für einfache Wartung und Erweiterung.

**Niedrige Code-Komplexität (Cyclomatic Complexity \<10)**

Begrenzt Verzweigungen in Funktionen, um Code lesbar und testbar zu halten.

**Coding Standards (z.B. PSR-12)**

Einheitliche Formatierungsregeln für konsistenten, teamfähigen Code.

**Schnittstellen**

Klare, standardisierte APIs/Contracts zwischen Modulen definieren.

**Developer Observability (Logging, Monitoring, Tracing)**

Strukturierte Logs, Metriken und Spuren für schnelle Fehlerdiagnose.

**Dokumentation**

Vollständige Beschreibung von Komponenten, APIs und Algorithmen.

Dokumentation erfolgt als "Docs as Code" im Git-Repository mit Markdown-Templates und automatisierter Generierung (z. B. MkDocs/Sphinx). Jede Komponente erhält READMEs mit Architektur, APIs, Algorithmen und Beispielen; API-Docs via OpenAPI/Swagger.

Eine Swagger Instanz zur Dokumentation der API ist zwingend.

**Automatisierte Tests (\>80% Coverage)**

Unit-/Integrationstests decken den Großteil des Codes ab.

**CI/CD-Pipelines**

Automatisierte Builds/Tests/Deployments für schnelle Releases.

**Technical Debt Management**

Regelmäßiges Refactoring und Debt-Tracking verhindern Akkumulation

**Open Source**

Der Code soll Open Source verfügbar sein - auf einem öffentlich einsehbaren Repository.

Verwendete Open Source Frameworks sind gesondert und sauber aufzulisten und zu verlinken.

### 3.5.5 Wiederverwendbarkeit

Die Software soll durch modulare, lose gekoppelte Komponenten wiederverwendbar sein. Die Implementierung von DRY-Prinzipien (Don't Repeat Yourself), ein zentrales Repository für Code und Anforderungen mit Versionskontrolle in STACKIT Git sowie standardisierte APIs/Schnittstellen sind vorzusehen.

### 3.5.6 Portabilität

normly wird als Webanwendung designt, um in allen üblichen Browserversionen zu laufen. Responsive Design ist jederzeit einzuhalten. Die Anwendung ist zugleich als Progressive Web App installierbar und ermöglicht Push-Benachrichtigungen.

Rückwärtskompatibilität ist bis zu folgenden Versionen sicherzustellen:

|                 |                                     |
|-----------------|-------------------------------------|
| **Browser**     | **Rückwärtskompatibel bis Version** |
| Google Chrome   | 143                                 |
| Microsoft Edge  | 142                                 |
| Mozilla Firefox | 145                                 |
| Apple Safari    | 26                                  |
| Opera           | 125                                 |

Die mobile Bereitstellung erfolgt zunächst als Progressive Web App (PWA) auf derselben Codebasis wie die Desktop-Anwendung. Eine native App ist erst erforderlich, sobald lizenzierte Volltexte offline bereitgestellt werden — nicht in Abhängigkeit von der Verfügbarkeit eines eigenen Sprachmodells. Näheres regelt Kapitel 3.15.

### 3.5.7 Kosten

Das Ziel ist es zu Beginn eine MVP-Lösung zu haben, deren freier Kern öffentlich nutzbar ist und auf deren Basis erste kommerzielle Dienste (Managed Hosting, Integrationen, Berichte) verkauft werden können, um ersten ARR vorweisen zu können.

### 3.5.8 Deadline

Die Entwicklung eines ersten testbaren Prototypen ist bis Mai/Juni 2026 abgeschlossen. Ein erstes, verkaufsfähiges MVP Produkt ist Ende Q2, Anfang Q3 2026 zu erreichen.

### 3.5.9 Physische Anforderungen

Um als USP eine 100%ige Unabhängig von amerikanischen oder chinesischen Angeboten sicherstellen zu können, ist das komplette Deployment auf Server-Infrastruktur von [<u>Stack IT</u>](https://stackit.com/de) sicherzustellen. Dies gilt auch für Entwicklungs-, Build- und Deployment-Umgebungen. Als Quell- und Build-Plattform wird STACKIT Git (Forgejo) mit STACKIT Pipelines eingesetzt.

### 3.5.10 Design Anforderungen

Um die Entwicklungskosten für Design auf ein Minimum zu beschränken, werden wir uns auf frei verfügbare Quellen stützen und Anwenden. Hierzu zählen:

- Frontend-Design: [<u>Shadcn</u>](https://ui.shadcn.com/), [Github-Repo von Shadcn-ui](https://github.com/shadcn-ui/ui)

Als Inspiration für die Darstellung an den Endnutzer dienen vor allem:

- Perplexity

- ChatGPT

- NotebookLM

## 3.6 AI/ML

Dieser Abschnitt definiert Anforderungen, die speziell für Systeme gelten, deren Kern aus maschinellem Lernen oder datengesteuerten Komponenten besteht. Diese Anforderungen ergänzen die in den vorangegangenen Abschnitten behandelten funktionalen, nicht-funktionalen und qualitativen Aspekte. Sie befassen sich jedoch mit ML-spezifischen Überlegungen hinsichtlich Lebenszyklus und Datenqualität.

### 3.6.1 Modell Spezifikationen

Um eine schnelle und kostengünstige Entwicklung sicherstellen zu können, werden wir zu Beginn auf Open Source LLM setzen. Es ist sicherzustellen, dass Deutsch und Englisch vorrangig unterstützt werden. Gefolgt von Französisch, Spanisch und Italienisch.

- Sprachmodell: [<u>Llama 3.1</u>](https://ai.meta.com/blog/meta-llama-3-1/) (Open Source und erlaubt die kommerzielle Nutzung für eigene Produkte). Derzeit führend, aber kann ersetzt werden.

### 3.6.2 Daten Management

Das Daten Management ist für normly von zentraler Bedeutung. Mit steigender Skalierung ist von vielen zehntausend Dokumenten auszugehen, dessen Informationen verarbeitet werden müssen. Zudem werden Dokumente (Normen) aktualisiert, erweitert oder für unfülgitg erklärt. Die Sicherstellung der Datenintegrität ist daher entscheidend!

Die aktuelle ungefähre Anzahl an Normen und damit verbunden (geschätzten Textseiten) ist wie folgt:

|                |                          |
|----------------|--------------------------|
| **Land**       | **Gesamtbestand Normen** |
| Deutschland    | 38.000+                  |
| Italien        | 48.000+                  |
| China          | 200.000+                 |
| Japan          | 25.000+                  |
| USA            | 40.000+                  |
| Frankreich     | 30.000+                  |
| Großbritannien | 27.000+                  |
| Indien         | 20.000+                  |
| Russland       | 30.000+                  |

Es ist also mit knapp einer halben Millionen Normen zu rechnen. Bei einer durchschnittlichen Anzahl von 40 Seiten pro Norm entspricht das über 20 Mio Seiten an technischen Informationen (zuzüglich Graphen, Tabellen, Zeichnungen und Formeln).

Diese Zahlen bilden ausschließlich den deutschsprachigen Raum ab. Zielhorizont von normly ist die weltweite Abdeckung. Weltweit ist von einer Größenordnung von mehreren Millionen Normendokumenten auszugehen, entsprechend einem mittleren dreistelligen Millionenbereich an Textseiten und mehreren Milliarden Textabschnitten für das Retrieval. Das Datenmanagement ist daher von Beginn an auf diese Zielgröße auszulegen. Insbesondere sind Graph- und Metadatenhaltung einerseits und Vektorindex andererseits so zu kapseln, dass sie unabhängig voneinander skaliert und ausgetauscht werden können.

### 3.6.3 Human-in-the-Loop

Das Sprachmodell gibt nur Zusammenfassungen und antwortet auf die gestellten Fragen anhand der zur Verfügung stehenden Normen. normly stellt keine gesetzlich basierte Rechtsberatung. Der Mensch muss die Antworten immer noch verifizieren.

### 3.6.4 Model Lifecycle und Operations

Die Sprachmodelle sind fortwährend den neuesten zur Verfügung stehenden Versionen anzupassen. Im Zuge der Internationalisierung sind neben deutsch und englisch (Start Sprachen) zudem weitere Sprachen erforderlich.

## 3.7 Open Source und Governance

Dieses Kapitel definiert Anforderungen an Lizenzierung, Rechteordnung und Governance des quelloffenen Kerns sowie an die Abgrenzung zur kommerziellen Schicht.

### REQ-OSS-001 — Lizenzmodell des freien Kerns

**Statement:** Der Quellcode des Kerns steht unter der GNU Affero General Public License 3.0 (AGPL-3.0). Client-SDKs und die API-Spezifikation stehen unter Apache-2.0. Die frei verfügbaren Inhalte und der Referenzgraph stehen unter einer offenen Datenlizenz (ODbL oder CC-BY-SA).

**Rationale:** Die AGPL schließt die Lücke der Netzwerknutzung und verhindert, dass Dritte den Kern als geschlossenen Dienst betreiben. Die permissive Lizenz für SDKs und API-Spezifikation sichert maximale Verbreitung.

**Akzeptanzkriterium:** LICENSE-Datei je Repository vorhanden; Lizenzhinweis in allen Quelldateien; Datenlizenz in der Veröffentlichung ausgewiesen.

**Abnahmekriterium:** Lizenz-Review bestätigt konsistente Auszeichnung aller Bestandteile.

### REQ-OSS-002 — Trennung von freiem Kern und kommerzieller Schicht

**Statement:** Der freie Kern darf keine Abhängigkeit auf proprietäre Bestandteile besitzen und muss ohne diese vollständig lauffähig sein. Kommerzielle Module docken ausschließlich über dokumentierte Erweiterungspunkte an.

**Rationale:** Ohne diese Trennung ist das Open-Core-Modell weder lizenzrechtlich noch gegenüber der Community belastbar.

**Akzeptanzkriterium:** Der Kern lässt sich ohne kommerzielle Module bauen, testen und betreiben; keine Importe aus proprietären Paketen im Kern.

**Abnahmekriterium:** Build des Kerns ohne kommerzielle Repositories erfolgreich; Abhängigkeitsprüfung in der Pipeline ohne Befund.

### REQ-OSS-003 — Beitragsmodell (DCO)

**Statement:** Externe Beiträge werden über das Developer Certificate of Origin (DCO) angenommen. Jeder Commit trägt eine Signed-off-by-Zeile. Eine Übertragung von Rechten (CLA) findet nicht statt.

**Rationale:** Das DCO senkt die Hürde für Beitragende und stützt den Anspruch auf frei zugängliches Normenwissen. Die Konsequenz, dass eine spätere kommerzielle Ausnahmelizenz zur AGPL damit ausgeschlossen ist, wurde bewusst in Kauf genommen.

**Akzeptanzkriterium:** DCO-Prüfung als verpflichtender Schritt in der Pipeline; CONTRIBUTING-Datei beschreibt das Verfahren.

**Abnahmekriterium:** Ein Merge Request ohne Signed-off-by wird automatisiert abgelehnt.

### REQ-OSS-004 — Community-Governance und Sicherheitsprozess

**Statement:** Das Projekt führt einen dokumentierten Maintainer-Kreis, einen Verhaltenskodex sowie eine Sicherheitsrichtlinie mit definiertem Meldeweg und Reaktionsfrist.

**Rationale:** Nachvollziehbare Governance ist Voraussetzung für Vertrauen und für die Mitwirkung Dritter.

**Akzeptanzkriterium:** CODE_OF_CONDUCT, SECURITY und GOVERNANCE im Repository vorhanden; Meldeweg für Schwachstellen benannt.

**Abnahmekriterium:** Ein Testbericht über den Meldeweg wird innerhalb der definierten Frist beantwortet.

### REQ-OSS-005 — Lizenzkonformität der Abhängigkeiten

**Statement:** Für jeden Release wird eine Software Bill of Materials (SBOM) erzeugt und die Lizenzen aller Abhängigkeiten automatisiert geprüft. Mit der AGPL unvereinbare Lizenzen führen zum Abbruch des Builds.

**Rationale:** Vermeidung von Lizenzverstößen und von Rechtsunsicherheit bei Nachnutzern.

**Akzeptanzkriterium:** SBOM je Release als Artefakt; Lizenz-Scan als Pflichtschritt in der Pipeline.

**Abnahmekriterium:** Ein eingeschleuster inkompatibler Abhängigkeitseintrag lässt den Build fehlschlagen.

### REQ-OSS-006 — Markenrechte

**Statement:** Die Marke normly ist nicht Bestandteil der Open-Source-Lizenz. Für die Nutzung der Marke durch Dritte gilt eine gesonderte Markenrichtlinie.

**Rationale:** Die Marke ist der Vermögenswert, über den Qualität und Herkunft gesteuert werden; sie muss unabhängig von der Codelizenz kontrollierbar bleiben.

**Akzeptanzkriterium:** Markenrichtlinie im Repository veröffentlicht; Hinweis in der LICENSE-Datei.

**Abnahmekriterium:** Rechtliche Prüfung bestätigt die Trennung von Code- und Markenlizenz.

## 3.8 Quellcodeverwaltung und Git-Workflow

Dieses Kapitel definiert Anforderungen an Plattform, Ablauf und Absicherung der Quellcodeverwaltung.

### REQ-GIT-001 — STACKIT Git als führende Plattform

**Statement:** Führende Plattform für Quellcode, Build, Artefakte, Zugangsdaten und Deployment ist STACKIT Git (Forgejo) mit STACKIT Pipelines. Runner, Container Registry und Secrets Manager werden ausschließlich dort betrieben.

**Rationale:** Daten- und Technologiesouveränität; Erfüllung der Beschränkung aus Kapitel 2.3.

**Akzeptanzkriterium:** Alle Repositories, Pipelines und Registries liegen in STACKIT; keine Build- oder Deployment-Rechte außerhalb.

**Abnahmekriterium:** Infrastruktur-Review bestätigt, dass kein Build- oder Deployment-Schritt außerhalb von STACKIT läuft.

### REQ-GIT-002 — Öffentliche Beitragsfassade

**Statement:** Der quelloffene Kern wird zusätzlich auf einer öffentlich zugänglichen Plattform (GitHub) als Beitragsfassade gespiegelt. Dort finden Issues und Pull Requests statt. Der Spiegel enthält keine Zugangsdaten, Runner, Build-Artefakte oder Deployment-Rechte.

**Rationale:** Sichtbarkeit und niedrige Beitragshürde für externe Mitwirkende, ohne Betrieb und Daten aus der souveränen Umgebung zu verlagern.

**Akzeptanzkriterium:** Automatisierter Push-Mirror nach jedem Merge; Beiträge werden ausschließlich an einer Stelle entgegengenommen; DCO-Prüfung aktiv.

**Abnahmekriterium:** Ein externer Pull Request durchläuft den definierten Weg bis in die STACKIT-Pipeline.

### REQ-GIT-003 — Branch- und Release-Strategie

**Statement:** Es gilt ein dokumentierter Branching-Ablauf mit geschütztem Hauptzweig, semantischer Versionierung (SemVer), einheitlichem Commit-Format und signierten Release-Tags.

**Rationale:** Nachvollziehbarkeit von Änderungen und verlässliche Versionsstände für Nachnutzer.

**Akzeptanzkriterium:** Direkte Pushes auf den Hauptzweig sind unterbunden; jeder Release trägt ein signiertes Tag.

**Abnahmekriterium:** Ein Versuch, direkt auf den Hauptzweig zu pushen, wird abgewiesen.

### REQ-GIT-004 — Merge-Request-Richtlinie

**Statement:** Änderungen gelangen ausschließlich über Merge Requests in den Hauptzweig. Voraussetzung sind mindestens eine fachliche Freigabe, eine erfolgreiche Pipeline und die Zustimmung der zuständigen Codeverantwortlichen.

**Rationale:** Qualitätssicherung und Vier-Augen-Prinzip; Schutz vor unbeabsichtigten Regressionen.

**Akzeptanzkriterium:** Merge ohne Freigabe oder mit fehlgeschlagener Pipeline ist technisch nicht möglich.

**Abnahmekriterium:** Ein Merge Request mit rotem Pipeline-Status lässt sich nicht zusammenführen.

### REQ-GIT-005 — Integrität der Lieferkette

**Statement:** Commits und Build-Artefakte werden signiert. Für jeden Release werden Herkunftsnachweis und SBOM veröffentlicht.

**Rationale:** Schutz vor Manipulation und Voraussetzung für die Nachvollziehbarkeit in regulierten Umgebungen.

**Akzeptanzkriterium:** Signaturprüfung als Pflichtschritt in der Pipeline; Artefakte in der STACKIT Container Registry signiert abgelegt.

**Abnahmekriterium:** Ein unsigniertes Artefakt wird von der Auslieferung abgewiesen.

## 3.9 Referenzgraph

Dieses Kapitel definiert Anforderungen an Aufbau, Lizenzierung und Nutzung des Normen-Referenzgraphen.

### REQ-GRAPH-001 — Offener Normen-Referenzgraph

**Statement:** Das System führt einen maschinenlesbaren Referenzgraph über Regelwerke. Erfasst werden stabile Identifikatoren, Verweise zwischen Regelwerken, Ersetzungs- und Zurückziehungsketten, Ausgabestände sowie Verweise aus Gesetzen und Verordnungen auf Normen. Schema und Inhalte des freien Teils werden unter einer offenen Datenlizenz mit Share-Alike-Wirkung (ODbL) veröffentlicht.

**Rationale:** Der Referenzgraph ist das eigentliche Alleinstellungsmerkmal von normly. Seine Offenheit ist kein Verzicht auf Schutz: Das Datenbankherstellerrecht nach §§ 87a ff. UrhG in Verbindung mit der Share-Alike-Klausel verhindert, dass Dritte den Graph in ein geschlossenes Produkt überführen. Zugleich begründet die Offenheit die Rolle als neutrale Infrastruktur gegenüber den Normungsorganisationen.

**Akzeptanzkriterium:** Vollständiger Dump in einem offenen, dokumentierten Format; Schema versioniert und öffentlich; Lizenzhinweis maschinenlesbar mitgeführt.

**Abnahmekriterium:** Ein Dritter kann den veröffentlichten Dump ohne Rückfrage einlesen und Verweisketten reproduzieren.

### REQ-GRAPH-002 — Schichtung von freiem und kommerziellem Graphanteil

**Statement:** Frei veröffentlicht werden Schema, Identifikatoren, Verweise zwischen öffentlich zugänglichen Regelwerken, Ersetzungsketten und Gültigkeitsstände. Der kommerziellen Schicht vorbehalten sind: Aktualitätsgarantie mit SLA und Änderungsbenachrichtigung, Verweise bis auf Abschnittsebene innerhalb lizenzierter Normen, Konfidenzangaben und Belegstellen für Auditzwecke sowie branchenspezifische Anreicherungen.

**Rationale:** Verweise, die die interne Gliederung geschützter Normen abbilden, dürfen je nach Lizenzvertrag nicht frei veröffentlicht werden. Zugleich zahlen gewerbliche Kunden für Verlässlichkeit und Aktualität, nicht für den Datenbestand als solchen; ein periodischer Dump und eine SLA-gestützte API sind unterschiedliche Produkte.

**Akzeptanzkriterium:** Jede Kante und jeder Knoten des Graphen trägt eine Herkunfts- und Lizenzklassifikation je Rechtsraum gemäß REQ-GRAPH-006; der freie Export enthält je Rechtsraum ausschließlich dort frei lizenzierbare Elemente.

**Abnahmekriterium:** Ein Export des freien Anteils enthält nachweislich keine lizenzpflichtigen Abschnittsverweise.

### REQ-GRAPH-003 — Graph-First-Anfrageverarbeitung

**Statement:** Anfragen werden zuerst gegen den Referenzgraph aufgelöst. Ein Sprachmodell wird nur aufgerufen, wenn die Anfrage eine Synthese über Fließtext erfordert. Strukturfragen (Ersetzung, Gültigkeit, Verweisbeziehungen) sind deterministisch und ohne Modellaufruf zu beantworten.

**Rationale:** Strukturfragen sind aus dem Graph exakt beantwortbar. Ein Modellaufruf wäre hier teurer, langsamer und fehleranfälliger; gerade bei Gültigkeits- und Ersetzungsfragen sind Halluzinationen besonders folgenschwer.

**Akzeptanzkriterium:** Klassifikation jeder Anfrage vor der Verarbeitung; deterministische Antwort mit Quellenangabe für Strukturfragen; Zwischenspeicherung wiederkehrender Anfragen.

**Abnahmekriterium:** Ein definierter Satz von Strukturfragen wird vollständig ohne Modellaufruf und mit korrekter Quellenangabe beantwortet.

### REQ-GRAPH-004 — Technologieoffenheit der Graphhaltung

**Statement:** Der Zugriff auf den Referenzgraph erfolgt ausschließlich über eine abstrahierte Schnittstelle innerhalb der Anwendung. Die konkrete Speichertechnologie ist austauschbar und darf nicht in die Fachlogik durchschlagen. Für den Start wird eine bei STACKIT betreibbare, quelloffene Datenbank eingesetzt.

**Rationale:** Betreiber eigener Instanzen sollen den freien Kern ohne zusätzliche Lizenzkosten und ohne fremdgehostete Spezialdatenbank betreiben können. Eine spätere Migration auf eine dedizierte Graphdatenbank muss ohne Eingriff in die Fachlogik möglich bleiben.

**Akzeptanzkriterium:** Keine datenbankspezifischen Abfragen außerhalb der Zugriffsschicht; Austausch der Speichertechnologie ist durch Tests abgedeckt.

**Abnahmekriterium:** Architektur-Review bestätigt, dass die Fachlogik keine Kenntnis der konkreten Graphtechnologie besitzt.

### REQ-GRAPH-005 — Internationalisierung des Referenzgraphen

**Statement:** Der Referenzgraph ist von Beginn an für weltweite Abdeckung auszulegen. Erforderlich sind: ein global kollisionsfreies Identifikatorschema, das Herausgeber, Dokumentnummer, Ausgabestand und Teilnummer getrennt abbildet; eine sprachunabhängige Knotenidentität, bei der ein Regelwerk einen Knoten bildet und nationale Übernahmen sowie Übersetzungen als Beziehungen bzw. Attribute geführt werden; mehrsprachige Bezeichnungen je Knoten.

**Rationale:** Ein nachträglicher Umbau des Identifikatorschemas ist die teuerste denkbare Altlast. Ein Regelwerk wie EN ISO 9001 wird von mehreren nationalen Gremien in unterschiedlichen Sprachen übernommen; ohne sprachunabhängige Identität entstehen Dubletten, die Verweisketten unbrauchbar machen.

**Akzeptanzkriterium:** Identifikatorschema dokumentiert und versioniert; nationale Übernahmen sind als Beziehung zum Ursprungsdokument abgebildet; je Knoten sind Bezeichnungen in mehreren Sprachen führbar.

**Abnahmekriterium:** Ein Regelwerk mit Übernahmen durch mindestens drei nationale Gremien wird als ein Knoten mit zugeordneten Übernahmen dargestellt.

### REQ-GRAPH-006 — Rechtsraumabhängige Lizenzklassifikation

**Statement:** Die Lizenz- und Veröffentlichungsfähigkeit von Knoten und Kanten wird je Rechtsraum klassifiziert und geführt. Exporte und API-Antworten werden anhand des jeweils maßgeblichen Rechtsraums gefiltert.

**Rationale:** Der frei veröffentlichbare Anteil ist nicht global einheitlich: § 5 UrhG gilt nur in Deutschland, die Lage bei per Verweis in Gesetze aufgenommenen Normen ist je Rechtsordnung unterschiedlich, und für harmonisierte europäische Normen ist die Rechtslage durch die Entscheidung des EuGH in der Rechtssache C-588/21 gesondert zu bewerten. Eine globale Klassifikation wäre entweder rechtswidrig oder unnötig restriktiv.

**Akzeptanzkriterium:** Klassifikation je Rechtsraum am Datenmodell hinterlegt; Exportfilter wählbar; Herkunft der rechtlichen Bewertung dokumentiert und mit Datum versehen.

**Abnahmekriterium:** Zwei Exporte für unterschiedliche Rechtsräume liefern nachweislich unterschiedliche, jeweils zulässige Umfänge.

## 3.10 Inhaltepartnerschaften und Vergütung

Dieses Kapitel definiert Anforderungen an die Zulieferung lizenzierter Normeninhalte durch herausgebende Organisationen sowie an deren nachvollziehbare Vergütung.

### REQ-PART-001 — Partnerportal zur Inhaltezulieferung

**Statement:** Für herausgebende Organisationen wird ein Portal mit zugehöriger Schnittstelle bereitgestellt, über das Normeninhalte im Volltext zugeliefert werden. Unterstützt werden gängige Austauschformate (mindestens PDF und XML). Je Lieferung werden Herausgeber, Dokumentidentifikator, Ausgabestand, Sprache, Rechtsraum sowie die vertraglich eingeräumten Nutzungsrechte als Metadaten erfasst. Lieferungen sind versioniert; ein Zurückziehen einzelner Dokumente oder ganzer Bestände muss jederzeit möglich sein und wirkt unmittelbar auf die Beantwortung von Anfragen.

**Rationale:** Die Zulieferung von Volltexten ist die Voraussetzung für den entscheidenden Sprung im Datenbestand. Ein definierter, nachvollziehbarer Zulieferweg senkt die Hürde für Herausgeber und ist Bestandteil der Verhandlungsposition. Die jederzeitige Rückziehbarkeit ist Voraussetzung dafür, dass Herausgeber die Kontrolle über ihre Werke behalten, und damit Bedingung für den Vertragsabschluss.

**Akzeptanzkriterium:** Zulieferung, Statusverfolgung und Rückzug sind über das Portal ohne technische Unterstützung durch normly durchführbar; jede Lieferung ist einem Vertrag zugeordnet; Rechte-Metadaten sind Pflichtfelder.

**Abnahmekriterium:** Ein Herausgeber liefert einen Bestand ein, ruft dessen Verarbeitungsstatus ab und zieht ein Dokument zurück; das zurückgezogene Dokument wird ab diesem Zeitpunkt nicht mehr zur Beantwortung herangezogen.

### REQ-PART-002 — Quellenattribution je Antwort

**Statement:** Für jede erzeugte Antwort wird protokolliert, welche Quellen herangezogen wurden und mit welchem Anteil sie zur Antwort beigetragen haben. Der Anteil bemisst sich nach der Anzahl der tatsächlich in die Antwort eingegangenen Passagen je Quelle im Verhältnis zur Gesamtzahl der eingegangenen Passagen. Passagen, die abgerufen, aber nicht verwendet wurden, bleiben unberücksichtigt. Wird eine Anfrage vollständig aus dem Referenzgraph beantwortet, wird dies als eigene Kategorie erfasst.

**Rationale:** Die Attributionsdaten sind die Grundlage jeder Umsatzbeteiligung und lassen sich nachträglich nicht rekonstruieren. Sie müssen daher ab Inbetriebnahme erhoben werden, unabhängig davon, ob bereits ein Vergütungsvertrag besteht. Die Erfassung gehört in den freien Kern, weil sie ohnehin für die Quellenangabe erforderlich ist; nur die Auswertung ist kommerziell.

**Akzeptanzkriterium:** Je Antwort liegt ein Attributionsdatensatz mit Quelle, Passagenanzahl und resultierendem Anteil vor; die Anteile je Antwort summieren sich auf 100 Prozent; die Erfassung ist unabhängig von bestehenden Verträgen aktiv.

**Abnahmekriterium:** Für eine Antwort, die Passagen aus drei verschiedenen Herausgebern verwendet, wird die Verteilung korrekt und nachvollziehbar ausgewiesen.

### REQ-PART-003 — Umsatzbeteiligung und prüffähige Abrechnung

**Statement:** Auf Basis der Attributionsdaten wird je Abrechnungszeitraum und Herausgeber ein anteiliger Vergütungsbetrag ermittelt. Grundlage ist der vertraglich vereinbarte Anteil am zurechenbaren Umsatz, verteilt nach dem Attributionsanteil gemäß REQ-PART-002. Herausgeber erhalten einen Abrechnungsbericht, der Zeitraum, Anfragevolumen, Attributionsanteil, Berechnungsgrundlage und resultierenden Betrag ausweist und maschinenlesbar exportierbar ist.

**Rationale:** Ein Herausgeber, der eine Umsatzbeteiligung erwartet, wird die Zahlen prüfen wollen. Ohne unabhängig nachvollziehbare Berechnung wird über Vertrauen verhandelt statt über einen Prozentsatz. Eine prüffähige Abrechnung verbessert die Verhandlungsposition erheblich und entschärft den Konflikt, dass normly als Wettbewerber um Verkaufserlöse wahrgenommen wird.

**Akzeptanzkriterium:** Abrechnungsberichte sind aus den protokollierten Einzeldatensätzen vollständig herleitbar; die Berechnungsvorschrift ist dokumentiert und versioniert; eine Stichprobe einzelner Antworten ist bis in den Bericht nachverfolgbar.

**Abnahmekriterium:** Eine externe Prüfung rechnet einen Abrechnungszeitraum aus den Rohdaten nach und kommt zum selben Ergebnis.

### REQ-PART-004 — Schutz und Trennung lizenzierter Volltextbestände

**Statement:** Lizenzierte Volltextbestände werden je Herausgeber logisch getrennt gehalten und ausschließlich im Rahmen der hinterlegten Nutzungsrechte verarbeitet. Ein Bestand darf nicht für Instanzen oder Mandanten herangezogen werden, für die keine entsprechende Berechtigung vorliegt. Der freie Kern und die frei veröffentlichten Exporte enthalten keine lizenzierten Volltextinhalte.

**Rationale:** Ohne belastbare Trennung ist kein Herausgeber bereit, Volltexte bereitzustellen. Die Trennung ist zugleich Voraussetzung dafür, dass der freie Kern quelloffen und frei verteilbar bleibt, während lizenzierte Bestände nur in berechtigten Instanzen wirksam werden.

**Akzeptanzkriterium:** Berechtigungsprüfung bei jedem Zugriff auf lizenzierte Bestände; Zugriffe werden protokolliert; freie Exporte werden gegen lizenzierte Inhalte automatisiert geprüft.

**Abnahmekriterium:** Eine Instanz ohne Berechtigung erhält nachweislich keine Inhalte aus einem lizenzierten Bestand; ein freier Export enthält nachweislich keine lizenzpflichtigen Volltextpassagen.

## 3.11 Kommerzielle Zusatzdienste

Dieses Kapitel definiert Anforderungen an die kommerzielle Schicht, die auf dem freien Kern aufsetzt und deren Ausgründung in eine eigene Gesellschaft vorgesehen ist.

### REQ-COM-001 — Erweiterungsschnittstelle

**Statement:** Der Kern stellt eine stabile, versionierte Erweiterungsschnittstelle bereit, über die kommerzielle Module ohne Fork angebunden werden können.

**Rationale:** Voraussetzung dafür, dass Kern und kommerzielle Schicht getrennt weiterentwickelt werden können.

**Akzeptanzkriterium:** Erweiterungspunkte dokumentiert und versioniert; ein Beispielmodul lässt sich ohne Änderung am Kern einbinden.

**Abnahmekriterium:** Ein Referenzmodul wird gegen zwei aufeinanderfolgende Kernversionen erfolgreich betrieben.

### REQ-COM-002 — Integration in Drittsoftware

**Statement:** Für CAD-, ERP- und Expertensysteme werden Integrationen bereitgestellt, die über die öffentliche API des Kerns arbeiten.

**Rationale:** Zentraler USP der kommerziellen Schicht und größter erwarteter Umsatzträger.

**Akzeptanzkriterium:** Mindestens eine Integration in ein verbreitetes Fachsystem ist lauffähig und dokumentiert.

**Abnahmekriterium:** Ein Endnutzer kann eine Anfrage aus dem Drittsystem heraus stellen und erhält eine Antwort mit Quellenangabe.

### REQ-COM-003 — Nutzungsbasierte Abrechnung

**Statement:** Kommerzielle API-Zugänge werden über Schlüssel authentifiziert, mit Kontingenten begrenzt und nutzungsbasiert abgerechnet.

**Rationale:** Tragfähiges Erlösmodell für Integrationen ohne Einschränkung des freien Zugangs.

**Akzeptanzkriterium:** Schlüsselverwaltung, Kontingentprüfung und prüffähige Abrechnungsdaten vorhanden.

**Abnahmekriterium:** Eine Testperiode wird vollständig und nachvollziehbar abgerechnet.

### REQ-COM-004 — Nachweisfähige Antworten und Audit-Trail

**Statement:** Für Compliance-Instanzen werden Anfrage, herangezogene Quellen, Modellversion und Zeitpunkt revisionssicher protokolliert und exportierbar gemacht.

**Rationale:** Haftungssicherheit ist der eigentliche Zahlungsgrund gewerblicher Kunden, nicht der Wissenszugang.

**Akzeptanzkriterium:** Vollständiger Audit-Datensatz je Antwort; Export in maschinenlesbarem Format.

**Abnahmekriterium:** Ein Audit-Export lässt sich einer konkreten Antwort eindeutig zuordnen.

### REQ-COM-005 — Ausschluss personalisierter Werbung

**Statement:** Personalisierte Werbung auf Basis von Suchanfragen, Chatverläufen oder Nutzerprofilen ist ausgeschlossen. Zulässig sind kontextfreie Verzeichniseinträge und Verweise auf Bezugsquellen der Originaldokumente.

**Rationale:** Personalisierte Werbung ist mit der Neutralität der Trägerorganisation und dem Datenschutzversprechen des freien Kerns unvereinbar.

**Akzeptanzkriterium:** Keine Profilbildung zu Werbezwecken; Verzeichniseinträge sind als bezahlt gekennzeichnet.

**Abnahmekriterium:** Datenschutz-Review bestätigt, dass keine werbebezogenen Nutzerprofile entstehen.

## 3.12 Datenerfassung und Verarbeitungskette

Dieses Kapitel beschreibt den Weg, auf dem Inhalte unterschiedlicher Herkunft — frei verfügbare Quellen, lizenzierte Partnerlieferungen und Bestände ohne geklärte Rechtslage — in einen einheitlichen Datenbestand überführt werden.

### REQ-PIPE-001 — Einheitliche Verarbeitungskette

**Statement:** Inhalte aller Herkunftsarten durchlaufen dieselbe Verarbeitungskette. Die Herkunftsart ist eine Eigenschaft des Datensatzes, nicht ein eigener Verarbeitungsweg. Die Kette gliedert sich in: Quellenregister, Ingest-Adapter, Identitätsauflösung, Rechteklassifikation, Strukturextraktion, Verweisextraktion, Segmentierung und Einbettung, Ausspielung.

**Rationale:** Getrennte Verarbeitungswege je Herkunftsart driften auseinander, und die Rechteprüfung säße an mehreren Stellen. Eine einzige Kette mit herkunftsabhängiger Steuerung ist prüfbar und erweiterbar.

**Akzeptanzkriterium:** Neue Quellen werden ausschließlich über einen Adapter angebunden; ab der Identitätsauflösung ist die Verarbeitung von der Herkunftsart unabhängig.

**Abnahmekriterium:** Eine neue Quelle wird angebunden, ohne dass Schritte hinter dem Adapter angepasst werden müssen.

### REQ-PIPE-002 — Quellenregister

**Statement:** Jede Quelle wird vor der ersten Verarbeitung registriert. Der Eintrag umfasst Herausgeber, Abrufweg, Rechtsgrundlage der Nutzung, Rechtsraum, Prüfdatum und die für die Prüfung verantwortliche Person. Ohne Registereintrag findet keine Erfassung statt. Die Rechtsgrundlage ist einer der folgenden abschließend definierten Kategorien zuzuordnen: (A) amtliche Werke und Rechtstexte, deren Nutzung sich aus § 5 UrhG oder einer entsprechenden Regelung des jeweiligen Rechtsraums ergibt; (B) Regelwerke unter einer freien Lizenz des Herausgebers; (C) vertraglich bezogene Daten, unter Angabe der Vertragsreferenz; (D) sonstige öffentlich zugängliche Quellen, ausschließlich nach dokumentierter Einzelfallprüfung einschließlich Prüfung nach REQ-PIPE-003 und unter Benennung einer verantwortlichen Person. Quellen, die keiner dieser Kategorien zugeordnet werden können, werden nicht erfasst.

**Rationale:** Das Register ist die Nachweisführung über die Herkunft und die rechtliche Grundlage des gesamten Bestands. Es ist Voraussetzung dafür, gegenüber Herausgebern und Aufsichtsstellen auskunftsfähig zu sein.

**Akzeptanzkriterium:** Registereintrag ist Pflichtvoraussetzung jedes Ingest-Laufs; Änderungen sind historisiert; die Kategoriezuordnung ist Pflichtfeld und ohne gültigen Wert nicht speicherbar.

**Abnahmekriterium:** Ein Erfassungslauf ohne gültigen Registereintrag oder ohne Kategoriezuordnung wird abgewiesen.

### REQ-PIPE-003 — Prüfung von Nutzungsvorbehalten

**Statement:** Vor der automatisierten Erfassung frei zugänglicher Quellen wird geprüft, ob ein maschinenlesbarer Nutzungsvorbehalt im Sinne des § 44b Abs. 3 UrhG vorliegt. Das Ergebnis wird mit Datum und Fundstelle im Quellenregister protokolliert und in festzulegenden Abständen erneut geprüft.

**Rationale:** Text- und Data-Mining ist nur zulässig, solange kein Nutzungsvorbehalt erklärt ist. Eine nicht dokumentierte Prüfung schwächt die Verhandlungsposition gegenüber genau den Organisationen, mit denen Lizenzverträge angestrebt werden.

**Akzeptanzkriterium:** Prüfergebnis je Quelle vorhanden, datiert und belegt; Wiedervorlage eingerichtet.

**Abnahmekriterium:** Für jede aktive Quelle lässt sich das Prüfergebnis mit Datum und Fundstelle abrufen.

### REQ-PIPE-004 — Rechteklassifikation als Verarbeitungstor

**Statement:** Nach der Identitätsauflösung wird je Dokument und Rechtsraum bestimmt, welche Verarbeitungsschritte zulässig sind: Verarbeitung, Volltextindexierung, Zitierung von Passagen, freier Export. Dokumente ohne Klassifikation werden nicht weiterverarbeitet. Eine fehlende Klassifikation gilt nicht als vorläufige Erlaubnis.

**Rationale:** Die Rechteklassifikation ist der einzige Punkt, an dem über die zulässige Nutzung entschieden wird. Eine zentrale Prüfung ist belastbarer als verteilte Prüfungen in einzelnen Schritten.

**Akzeptanzkriterium:** Jeder nachgelagerte Schritt prüft die Klassifikation; nicht klassifizierte Dokumente verbleiben in einem Wartezustand.

**Abnahmekriterium:** Ein Dokument ohne Klassifikation erreicht nachweislich weder Index noch Export.

### REQ-PIPE-005 — Abstammung und kaskadierende Rücknahme

**Statement:** Jedes abgeleitete Artefakt — Abschnitt, Segment, Einbettung, Graphkante, Exportdatei — führt eine Referenz auf die Quelllieferung, aus der es entstanden ist. Wird eine Lieferung zurückgezogen oder eine Rechteklassifikation eingeschränkt, werden alle abgeleiteten Artefakte automatisch entfernt oder gesperrt.

**Rationale:** Ohne durchgängige Abstammungskette ist die in REQ-PART-001 zugesagte Rückziehbarkeit nicht einlösbar. Nachträglich lässt sich eine solche Kette nicht herstellen; sie muss von Beginn an mitgeführt werden.

**Akzeptanzkriterium:** Abstammungsreferenz an allen abgeleiteten Artefakten; Rücknahme läuft als nachvollziehbarer Vorgang mit Protokoll.

**Abnahmekriterium:** Nach Rückzug eines Dokuments sind dessen Segmente, Einbettungen, Graphkanten und Exportanteile nachweislich entfernt.

### REQ-PIPE-006 — Wiederholbarkeit und Inhaltsadressierung

**Statement:** Alle Verarbeitungsschritte sind idempotent und beliebig wiederholbar. Rohdateien werden inhaltsadressiert abgelegt, sodass unveränderte Neulieferungen erkannt und nicht erneut verarbeitet werden.

**Rationale:** Extraktionsverfahren werden sich weiterentwickeln; der Bestand muss neu verarbeitet werden können, ohne abweichende Ergebnisse oder Dubletten zu erzeugen.

**Akzeptanzkriterium:** Ein wiederholter Lauf über denselben Eingangsstand erzeugt kein abweichendes Ergebnis; unveränderte Lieferungen werden übersprungen.

**Abnahmekriterium:** Eine vollständige Neuverarbeitung des Bestands liefert ein identisches Ergebnis.

### REQ-PIPE-008 — Ausschluss kommerziell verwerteter Katalogbestände

**Statement:** Katalog- und Metadatenbestände von Herausgebern, die diese selbst kommerziell verwerten, werden ausschließlich über Kategorie C des Quellenregisters bezogen, also auf vertraglicher Grundlage. Eine automatisierte Erfassung solcher Bestände über Kategorie D ist ausgeschlossen. Dies gilt unabhängig davon, ob die Bestände öffentlich zugänglich sind.

**Rationale:** Ein Normenkatalog ist eine geschützte Datenbank; § 87b UrhG untersagt neben der Entnahme wesentlicher Teile auch die wiederholte und systematische Entnahme unwesentlicher Teile, soweit sie der normalen Auswertung zuwiderläuft. Systematisches Abgreifen mit periodischem Abgleich erfüllt dieses Merkmal. Schwerer wiegt die strategische Seite: normly verhandelt mit denselben Organisationen über freiwillige Bereitstellung gegen Umsatzbeteiligung. Ein Zugriff ohne Vertrag widerspricht dieser Position unmittelbar und gefährdet die Verhandlungen.

**Akzeptanzkriterium:** Adapter der Kategorie D können technisch nicht auf Quellen konfiguriert werden, die als kommerziell verwerteter Katalogbestand gekennzeichnet sind; die Kennzeichnung ist im Quellenregister geführt.

**Abnahmekriterium:** Der Versuch, eine als kommerziell verwertet gekennzeichnete Quelle über Kategorie D anzubinden, wird abgewiesen und protokolliert.

### REQ-PIPE-009 — Erstbestand aus frei zugänglichen Quellen

**Statement:** Der Erstaufbau von Katalog und Referenzgraph erfolgt aus Quellen der Kategorien A und B. Dazu zählen insbesondere die Listen harmonisierter Normen im Amtsblatt der Europäischen Union über EUR-Lex, Verweise aus Gesetzen und Verordnungen, die Regelwerksverzeichnisse von DGUV und BAuA, die Arbeitsprogramme der europäischen Normungsorganisationen sowie frei verfügbare Katalogdaten internationaler Gremien.

**Rationale:** Diese Quellen tragen einen belastbaren Erstbestand ohne Rechtsrisiko und enthalten zugleich den für den Referenzgraph wertvollsten Teil: die Verweise aus dem Recht auf Normen. Der Graph ist damit vor dem ersten Lizenzvertrag aufbaubar und stärkt die Verhandlungsposition, statt sie zu belasten.

**Akzeptanzkriterium:** Katalog und Graph sind ohne Quellen der Kategorien C und D in Betrieb nehmbar; Herkunft je Eintrag nachweisbar.

**Abnahmekriterium:** Ein Erstbestand wird ausschließlich aus Quellen der Kategorien A und B aufgebaut und ist auswertbar.

### REQ-PIPE-007 — Manuelle Prüfung der Identitätsauflösung

**Statement:** Für Fälle, in denen die automatische Zuordnung eines Dokuments zu einem Knoten nicht eindeutig gelingt, steht eine Prüfoberfläche zur Verfügung. Ungeklärte Fälle blockieren die Weiterverarbeitung des betroffenen Dokuments, nicht die des übrigen Bestands.

**Rationale:** Herausgeber schreiben Normnummern uneinheitlich; eine vollständige Automatisierung der Zuordnung ist nicht erreichbar. Falsche Zuordnungen machen Verweisketten unbrauchbar und sind schwer zu entdecken.

**Akzeptanzkriterium:** Unklare Fälle werden zur Prüfung vorgelegt statt heuristisch entschieden; Entscheidungen sind protokolliert und rückgängig machbar.

**Abnahmekriterium:** Ein mehrdeutiger Fall wird vorgelegt, entschieden und die Entscheidung ist nachvollziehbar dokumentiert.

<img src="media/media/image3.png" style="width:6.27014in;height:7.89583in" />

Figure 2: Verarbeitungskette

## 3.13 Verschlüsselung und Schutz lizenzierter Inhalte

Dieses Kapitel ergänzt die allgemeinen Sicherheitsanforderungen aus Kapitel 3.3.2 um Vorgaben zur Verschlüsselung ruhender Daten, zur Schlüsselverwaltung sowie zum Schutz vertraglich bezogener Volltextbestände.

### REQ-SEC-001 — Verschlüsselung ruhender Daten

**Statement:** Alle persistierten Daten werden verschlüsselt abgelegt: Datenbankinhalte, Objektspeicher, Suchindizes, Protokolldaten und sämtliche Sicherungskopien. Dies gilt unabhängig davon, ob es sich um frei verfügbare oder um lizenzierte Inhalte handelt.

**Rationale:** Die bisherigen Anforderungen decken ausschließlich die Transportverschlüsselung ab. Sobald lizenzierte Volltexte im Bestand liegen, ist die Verschlüsselung ruhender Daten Gegenstand jeder Vertragsprüfung durch die Herausgeber. Eine einheitliche Behandlung aller Bestände vermeidet zudem, dass die Schutzwirkung von einer korrekten Klassifikation abhängt.

**Akzeptanzkriterium:** Verschlüsselung ist für alle Speicherorte nachweisbar aktiv; unverschlüsselte Ablagen sind technisch ausgeschlossen; Sicherungskopien sind einbezogen.

**Abnahmekriterium:** Ein Sicherheitsaudit weist für jeden Speicherort den aktiven Verschlüsselungszustand nach.

### REQ-SEC-002 — Schlüsselverwaltung

**Statement:** Schlüssel werden im STACKIT Secrets Manager verwaltet und niemals gemeinsam mit den durch sie geschützten Daten abgelegt. Es gelten dokumentierte Rotationsfristen, eine Trennung der Zugriffsrechte zwischen Betrieb und Anwendung sowie eine vollständige Protokollierung jedes Zugriffs auf Schlüsselmaterial. Der Verlust einzelner Schlüssel darf nicht zum Verlust des Gesamtbestands führen.

**Rationale:** Verschlüsselung ohne belastbares Schlüsselkonzept ist eine Zusage ohne Substanz. Die Trennung von Schlüssel und Daten sowie die Protokollierung sind Voraussetzung dafür, gegenüber Herausgebern und Auditoren nachweisfähig zu sein.

**Akzeptanzkriterium:** Rotationsfristen dokumentiert und technisch durchgesetzt; Zugriffe auf Schlüsselmaterial protokolliert; Rollentrennung wirksam.

**Abnahmekriterium:** Eine Schlüsselrotation wird ohne Betriebsunterbrechung durchgeführt und ist im Protokoll nachvollziehbar.

### REQ-SEC-003 — Herausgeberspezifische Datenschlüssel und kryptographisches Löschen

**Statement:** Vertraglich bezogene Volltextbestände werden je Herausgeber mit einem eigenen Datenschlüssel verschlüsselt. Bei Beendigung eines Vertrages oder beim Rückzug eines Bestandes nach REQ-PART-001 wird der zugehörige Schlüssel vernichtet. Die betroffenen Daten sind damit auch in bestehenden Sicherungskopien dauerhaft unlesbar. Die Vernichtung wird protokolliert und dem Herausgeber bestätigt.

**Rationale:** Die in REQ-PART-001 zugesagte Rückziehbarkeit lässt sich für Sicherungskopien nicht durch Löschen einlösen: Bestehende Sicherungen enthalten die Inhalte weiterhin, und ihre selektive Bereinigung ist praktisch nicht durchführbar. Das kryptographische Löschen schließt diese Lücke und ist zugleich das stärkste Argument in Lizenzverhandlungen — nach Vertragsende sind die Inhalte technisch nicht mehr lesbar, nicht lediglich als gelöscht markiert.

**Akzeptanzkriterium:** Ein Datenschlüssel je Herausgeber; kein Bestand ist mit einem gemeinsamen Schlüssel verschlüsselt; Vernichtung ist ein protokollierter Vorgang mit Bestätigung.

**Abnahmekriterium:** Nach Vernichtung eines Schlüssels sind die zugehörigen Inhalte weder im Produktivbestand noch in einer Sicherungskopie lesbar; die Bestätigung liegt dem Herausgeber vor.

### REQ-SEC-004 — Schutz vor Massenextraktion

**Statement:** Zugriffe auf lizenzierte Bestände werden durch Ratenbegrenzung, Kontingente und Anomalieerkennung geschützt. Auffällige Zugriffsmuster, die auf eine systematische Extraktion hindeuten, führen zu Drosselung oder Sperrung und werden protokolliert. Zugriffsprotokolle sind je Herausgeber auswertbar.

**Rationale:** Herausgeber sorgen sich weniger um unbefugten Zugriff von außen als darum, dass berechtigte Nutzer den Bestand systematisch abziehen. Ohne wirksamen Schutz gegen Massenextraktion ist die Zusage aus REQ-PART-004 nicht belastbar und eine Volltextbereitstellung nicht verhandelbar.

**Akzeptanzkriterium:** Ratenbegrenzung und Kontingente je Zugang aktiv; Anomalieerkennung mit definierten Schwellwerten; Auswertung je Herausgeber möglich.

**Abnahmekriterium:** Ein simulierter Extraktionsversuch wird erkannt, gedrosselt und protokolliert.

## 3.14 Geschützte Anzeige und Offline-Nutzung

Dieses Kapitel definiert Anforderungen an die Anzeige lizenzierter Volltexte. Ziel ist, dass Inhalte innerhalb der Anwendung vollständig nutzbar sind — auch offline — ohne dass daraus weitergebbare Kopien entstehen. Der Schutz wirkt abschreckend und nachverfolgbar, nicht absolut; diese Einschränkung ist bewusst und gegenüber Herausgebern offen zu benennen.

### REQ-DRM-001 — Anzeige ohne herausgebbare Datei

**Statement:** Lizenzierte Volltexte werden ausschließlich innerhalb der Anwendung angezeigt. Es wird keine vollständige, eigenständig verwendbare Dokumentdatei an den Endnutzer ausgeliefert. Die Anzeige erfolgt abschnittsweise und bedarfsgesteuert; ein Export als PDF oder gleichwertiges Format ist für lizenzierte Inhalte nicht vorgesehen. Ebenso ist das markieren von Text in den Volltexten nicht möglich, um copy&paste zu vermeiden.

**Rationale:** Der wirtschaftliche Schaden für die Herausgeber entsteht nicht durch das Lesen, sondern durch die Weitergabe vollständiger Dateien. Wer keine Datei erhält, kann keine weitergeben. Dies ist zugleich das Argument, mit dem normly den Herausgebern hilft, die Verbreitung nicht lizenzierter PDF-Kopien zurückzudrängen: ein bequemer legaler Zugang ist wirksamer als jede Rechtsverfolgung.

**Akzeptanzkriterium:** Kein Endpunkt liefert lizenzierte Inhalte als vollständige Datei aus; die Anzeige erfolgt in Teilabrufen; Abrufe sind protokolliert.

**Abnahmekriterium:** Ein Prüfversuch zeigt, dass sich aus den ausgelieferten Daten keine vollständige Dokumentdatei rekonstruieren lässt, ohne die Anwendung zu umgehen.

### REQ-DRM-002 — Offline-Nutzung mit befristeter Berechtigung

**Statement:** Nutzer können lizenzierte Inhalte für die Offline-Nutzung vorhalten. Die lokale Ablage erfolgt verschlüsselt, gebunden an Nutzer und Gerät, mit befristeter Gültigkeit. Nach Ablauf der Frist ist eine erneute Berechtigung erforderlich. Endet die Lizenz des Nutzers oder wird der Bestand nach REQ-PART-001 zurückgezogen, verliert die lokale Ablage ihre Gültigkeit.

**Rationale:** Offline-Verfügbarkeit ist für die Zielgruppe wesentlich — auf Baustellen und in Werkshallen ist keine verlässliche Verbindung gegeben. Ohne Offline-Fähigkeit bleibt die PDF-Kopie für die Nutzer die praktischere Lösung, und der Zweck der Anforderung wird verfehlt.

**Akzeptanzkriterium:** Lokale Ablage verschlüsselt und an Nutzer und Gerät gebunden; Gültigkeitsdauer konfigurierbar; Entzug der Berechtigung wirkt bei der nächsten Verbindung.

**Abnahmekriterium:** Ein offline vorgehaltener Inhalt ist nach Ablauf der Frist ohne erneute Berechtigung nicht mehr lesbar und außerhalb der Anwendung zu keinem Zeitpunkt lesbar.

### REQ-DRM-003 — Nutzerbezogene Kennzeichnung

**Statement:** Angezeigte lizenzierte Inhalte tragen eine nutzerbezogene Kennzeichnung, sichtbar sowie in nicht ohne Weiteres entfernbarer Form. Anhand einer aufgefundenen Kopie muss sich der Zugang bestimmen lassen, über den sie entstanden ist.

**Rationale:** Bildschirmfotos, Abfotografieren und Texterkennung lassen sich technisch nicht verhindern. Erreichbar ist Nachverfolgbarkeit: Wer weiß, dass eine Weitergabe auf ihn zurückfällt, gibt seltener weiter. Für Herausgeber ist gerade dies der Mehrwert gegenüber der heutigen Situation, in der eine kursierende PDF-Kopie keiner Quelle zuzuordnen ist.

**Akzeptanzkriterium:** Kennzeichnung je Zugang eindeutig; in der Anzeige nicht abschaltbar; Zuordnung aus einer Kopie reproduzierbar.

**Abnahmekriterium:** Aus einem Bildschirmfoto einer Anzeige lässt sich der zugehörige Zugang eindeutig bestimmen.

### REQ-DRM-004 — Zuordnung der Schutzkomponenten zur kommerziellen Schicht

**Statement:** Die geschützte Anzeige, die verschlüsselte Offline-Ablage und die Kennzeichnung sind Bestandteil der kommerziellen Schicht und nicht des quelloffenen Kerns. Der Kern stellt hierfür ausschließlich Schnittstellen bereit. Frei verfügbare Inhalte unterliegen diesen Beschränkungen nicht und bleiben ohne Einschränkung exportierbar.

**Rationale:** Ein Schutzmechanismus, dessen Quellcode vollständig offenliegt, bietet keinen wirksamen Schutz — die Umgehung wäre aus dem Quelltext unmittelbar ableitbar. Die Zuordnung zur kommerziellen Schicht löst diesen Widerspruch, ohne die Quelloffenheit des Kerns einzuschränken. Zugleich stellt sie sicher, dass der freie Kern nicht durch Beschränkungen belastet wird, die für seine Inhalte gar nicht erforderlich sind.
**Akzeptanzkriterium:** Der Kern ist ohne die Schutzkomponenten vollständig lauffähig; frei verfügbare Inhalte sind ohne Beschränkung abrufbar und exportierbar.
**Abnahmekriterium:** Eine Instanz des freien Kerns läuft ohne die Schutzkomponenten und liefert frei verfügbare Inhalte uneingeschränkt aus.

## 3.15 Mobile Bereitstellung

Dieses Kapitel definiert, über welche Wege normly auf mobilen Geräten bereitgestellt wird. Die Aufteilung folgt der Grenze zwischen freiem Kern und kommerzieller Schicht: Frei verfügbare Inhalte werden über eine Progressive Web App bereitgestellt, lizenzierte Volltexte erfordern eine native Anwendung.

### REQ-MOB-001 — Progressive Web App als primärer mobiler Zugang

**Statement:** Die Anwendung wird als installierbare Progressive Web App bereitgestellt, auf derselben Codebasis wie die Desktop-Anwendung. Frei verfügbare Inhalte sind über einen Service Worker offline nutzbar. Die PWA ist Bestandteil des freien Kerns.

**Rationale:** Eine gemeinsame Codebasis vermeidet doppelten Aufwand und deckt den gesamten Bedarf bis zum ersten Volltextvertrag ab. Für frei verfügbare Inhalte bestehen keine Schutzanforderungen, die über die Möglichkeiten des Browsers hinausgehen.

**Akzeptanzkriterium:** Installierbar auf Android und iOS; frei verfügbare Inhalte offline abrufbar; keine getrennte mobile Codebasis.

**Abnahmekriterium:** Die Anwendung wird auf einem mobilen Gerät installiert und im Flugmodus mit frei verfügbaren Inhalten genutzt.

### REQ-MOB-002 — Native Anwendung für lizenzierte Offline-Inhalte

**Statement:** Die Offline-Bereitstellung lizenzierter Volltexte nach REQ-DRM-002 erfolgt ausschließlich über eine native Anwendung für Android und iOS. Diese nutzt die hardwaregestützte Schlüsselablage des Betriebssystems und die verfügbaren Mechanismen zur Einschränkung von Bildschirmaufnahmen. Die native Anwendung ist Bestandteil der kommerziellen Schicht. Diese Zuordnung betrifft Eigentum, Lizenzierung und Wartung, nicht den Zugang für Nutzer: Die Anwendung ist kostenfrei beziehbar und nutzbar. Frei verfügbare Inhalte sind darin ohne Anmeldung und ohne Entgelt abrufbar. Kostenpflichtig sind ausschließlich lizenzierte Volltexte und deren geschützte Offline-Bereitstellung.

**Rationale:** Im Browser existiert kein Ort, an dem ein Schlüssel geschützt abgelegt werden kann; lokale Speicher sind einsehbar. Die in REQ-DRM-002 geforderte Bindung an Nutzer und Gerät ist dort nicht umsetzbar. Native Plattformen bieten mit Keychain und Keystore eine belastbare Grundlage.

**Akzeptanzkriterium:** Schlüsselablage über die Plattformmechanismen; Bindung an Nutzer und Gerät nachweisbar; freier Kern bleibt ohne native Anwendung vollständig nutzbar; die Anwendung ist ohne Konto und ohne Zahlung installier- und nutzbar.

**Abnahmekriterium:** Ein lizenzierter Inhalt ist offline ausschließlich innerhalb der nativen Anwendung lesbar.

### REQ-MOB-003 — Abstrahierte Offline-Schicht

**Statement:** Der Zugriff auf lokal vorgehaltene Inhalte erfolgt über eine einheitliche Abstraktion, deren Implementierung je Plattform ausgetauscht wird. Die Anwendungslogik unterscheidet nicht zwischen Browser- und nativer Ablage.

**Rationale:** Ohne diese Trennung müsste die Offline-Logik für die native Anwendung vollständig neu gebaut werden. Die Abstraktion ist zu Beginn nahezu kostenlos und später nur mit erheblichem Aufwand nachrüstbar. Sie ist zugleich Voraussetzung dafür, dass beide Anwendungen dieselben frei verfügbaren Inhalte gleichwertig bereitstellen.

**Akzeptanzkriterium:** Keine plattformspezifischen Speicherzugriffe außerhalb der Abstraktionsschicht; Austausch durch Tests abgedeckt.

**Abnahmekriterium:** Architektur-Review bestätigt, dass die Anwendungslogik keine Kenntnis der konkreten Ablageform besitzt.

### REQ-MOB-004 — Vertriebswege und Lizenzverträglichkeit

**Statement:** Die native Anwendung der kommerziellen Schicht wird kostenfrei über die Plattform-Stores von Apple und Google vertrieben; Entgelte fallen ausschließlich für den Zugang zu lizenzierten Inhalten an. Sie ist ein eigenständiger Client, der ausschließlich über die unter Apache-2.0 spezifizierte API mit dem Server kommuniziert, und unterliegt nicht der AGPL. Ergänzend kann ein quelloffener Client des freien Kerns über F-Droid bereitgestellt werden.

**Rationale:** Die Nutzungsbedingungen des Apple App Store gelten als unvereinbar mit den Bedingungen von AGPL und GPL. Die Trennung in einen eigenständigen Client über eine permissiv lizenzierte Schnittstelle löst diesen Konflikt, ohne die Quelloffenheit des Kerns einzuschränken. F-Droid setzt vollständig quelloffene, reproduzierbare Builds voraus und kommt daher nur für den freien Client in Betracht.

**Akzeptanzkriterium:** Keine AGPL-lizenzierten Bestandteile in der Store-Anwendung; Kommunikation ausschließlich über die öffentliche API; Lizenzprüfung dokumentiert.

**Abnahmekriterium:** Eine Lizenzprüfung bestätigt die Trennung von freiem Kern und Store-Anwendung.

## 3.16 Zugang und Kontopflicht

Dieses Kapitel regelt, welche Funktionen ohne Konto nutzbar sind und ab wann eine Anmeldung erforderlich wird. Maßgeblich ist nicht der Zugangsweg, sondern die Lizenzklassifikation der Inhalte.

### REQ-ACC-001 — Anonyme Basisnutzung

**Statement:** Suche, Abfrage des Referenzgraphen und Anzeige frei verfügbarer Inhalte sind ohne Konto und ohne Anmeldung nutzbar. Eine Registrierung ist für den Kernzweck der Anwendung nicht erforderlich. Dies gilt für alle Zugangswege gleichermaßen: Webanwendung, Progressive Web App und native Anwendung.

**Rationale:** Eine Registrierungspflicht ist die höchste Hürde in der Nutzerreise und steht im Widerspruch zur Vision eines frei zugänglichen Normenwissens. Zudem sollen Betreiber eigener Instanzen keine Nutzerverwaltung vorhalten müssen, um frei verfügbare Regelwerke bereitzustellen. Ohne Konto entstehen zugleich keine personenbezogenen Daten, die geschützt werden müssten.

**Akzeptanzkriterium:** Vollständiger Frage-Antwort-Zyklus ohne Anmeldung durchführbar; keine Registrierungsaufforderung vor der ersten Nutzung.

**Abnahmekriterium:** Eine frisch installierte Instanz beantwortet eine Anfrage zu einem frei verfügbaren Regelwerk ohne Anmeldung.

### REQ-ACC-002 — Inhaltliche Begrenzung anonymer Zugänge

**Statement:** Anonyme Zugänge erreichen ausschließlich Inhalte, die nach REQ-PIPE-004 als frei lizenzierbar klassifiziert sind. Lizenzierte Volltexte sind ohne authentifizierten und berechtigten Zugang technisch nicht erreichbar. Die Antwortlänge ist begrenzt; ein systematischer Abruf aufeinanderfolgender Abschnitte ist ausgeschlossen.

**Rationale:** Gegenüber Herausgebern muss belegbar sein, dass lizenzierte Inhalte über anonyme Zugänge grundsätzlich nicht erreichbar sind — unabhängig von Kontingenten oder Ratenbegrenzung. Diese strukturelle Zusage ist in Verhandlungen belastbarer als eine reine Registrierungspflicht, die den Zugriff lediglich zurechenbar machen würde.

**Akzeptanzkriterium:** Kein anonymer Zugriffspfad auf lizenzierte Bestände; Antwortlänge konfigurierbar begrenzt; keine Abrufreihenfolge über zusammenhängende Abschnitte.

**Abnahmekriterium:** Ein Prüfversuch belegt, dass lizenzierte Inhalte über keinen anonymen Zugang erreichbar sind.

### REQ-ACC-003 — Kontingent für anonyme Nutzung

**Statement:** Anonyme Zugänge unterliegen einem begrenzten Anfragekontingent je Zeitfenster. Die Zählung erfolgt serverseitig anhand eines vergebenen Sitzungsmerkmals in Verbindung mit der Herkunftsadresse, nicht über clientseitig gespeicherte Werte. Bei Erreichen des Kontingents wird auf die Anmeldung verwiesen.

**Rationale:** Das Kontingent begrenzt die Inferenzkosten der anonymen Nutzung und schafft einen sachlichen Anlass zur Registrierung, ohne sie zu erzwingen. Eine clientseitige Zählung wäre durch Zurücksetzen des Browsers wirkungslos. Da eine adressbasierte Begrenzung durch Adresswechsel umgehbar bleibt, ist sie kein Schutzmechanismus gegen Massenextraktion; diese Aufgabe erfüllt REQ-SEC-004.

**Akzeptanzkriterium:** Kontingent konfigurierbar; Zählung serverseitig; Zurücksetzen clientseitiger Daten hebt die Begrenzung nicht auf; gemeinsame Infrastruktur mit REQ-SEC-004.

**Abnahmekriterium:** Nach Ausschöpfung des Kontingents führt das Löschen der Browserdaten nicht zu weiteren freien Anfragen.

### REQ-ACC-004 — Kontopflichtige Funktionen

**Statement:** Ein Konto ist erforderlich für: erhöhte Anfragekontingente, gespeicherte Verläufe und Merklisten, das Hochladen eigener Dokumente, den Zugang zu lizenzierten Inhalten, die Offline-Nutzung nach REQ-DRM-002 sowie sämtliche kostenpflichtigen Dienste. Diese Aufzählung ist abschließend; weitere Funktionen dürfen nicht ohne Anpassung dieser Anforderung mit einer Kontopflicht versehen werden.

**Rationale:** Eine abschließende Aufzählung verhindert, dass die Kontopflicht schrittweise auf Funktionen ausgeweitet wird, die sie nicht benötigen. Alle genannten Funktionen setzen eine zurechenbare Identität voraus — sei es für Kontingente, Abrechnung, Gerätebindung oder die nutzerbezogene Kennzeichnung nach REQ-DRM-003.

**Akzeptanzkriterium:** Keine Kontopflicht außerhalb der genannten Funktionen; die Zuordnung ist im Berechtigungsmodell abgebildet.

**Abnahmekriterium:** Eine Prüfung der Zugriffspfade bestätigt, dass keine weitere Funktion eine Anmeldung erzwingt.
