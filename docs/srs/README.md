# SRS / SDD — normly

Software Requirements Specification und Software Design Description.
Nach Kapiteln aufgeteilt, damit gezielt gelesen werden kann statt des ganzen Dokuments.

## Kapitel

| Datei | Inhalt |
|---|---|
| [01-einfuehrung.md](01-einfuehrung.md) | Zweck des Dokuments, Produktvision, Definitionen |
| [02-produktueberblick.md](02-produktueberblick.md) | Produktperspektive, Funktionen, Beschränkungen, Nutzergruppen, Annahmen |
| [03-anforderungen.md](03-anforderungen.md) | Sämtliche Anforderungen, Kapitel 3.1–3.16 |
| [05-verifikation.md](05-verifikation.md) | Verifikation |
| [06-anhaenge.md](06-anhaenge.md) | Anhänge |

## Kapitelgliederung der Anforderungen

| | Kapitel | Gruppe |
|---|---|---|
| 3.1 | Externe Interfaces | `REQ-UI`, `REQ-INT` |
| 3.2 | Funktionale Anforderungen | `REQ-FUNC` |
| 3.3 | Nicht-funktionale Anforderungen | `REQ-PERF` |
| 3.4 | Compliance | — |
| 3.5 | Design und Implementierung | `REQ-INST`, `REQ-BUILD`, `REQ-DIST` |
| 3.6 | AI/ML | — |
| 3.7 | Open Source und Governance | `REQ-OSS` |
| 3.8 | Quellcodeverwaltung und Git-Workflow | `REQ-GIT` |
| 3.9 | Referenzgraph | `REQ-GRAPH` |
| 3.10 | Inhaltepartnerschaften und Vergütung | `REQ-PART` |
| 3.11 | Kommerzielle Zusatzdienste | `REQ-COM` |
| 3.12 | Datenerfassung und Verarbeitungskette | `REQ-PIPE` |
| 3.13 | Verschlüsselung und Schutz lizenzierter Inhalte | `REQ-SEC` |
| 3.14 | Geschützte Anzeige und Offline-Nutzung | `REQ-DRM` |
| 3.15 | Mobile Bereitstellung | `REQ-MOB` |
| 3.16 | Zugang und Kontopflicht | `REQ-ACC` |

## Verwandte Dokumente

- [../adr/](../adr/) — Architekturentscheidungen mit Begründung
- [../normly_Verarbeitungskette.svg](../normly_Verarbeitungskette.svg) — Pipeline von der Quelle bis zur Ausspielung
- [../normly_Entwicklungsphasen.svg](../normly_Entwicklungsphasen.svg) — Phasenplan

## Requirement-Index

78 Anforderungen in 17 Gruppen. Alle in [03-anforderungen.md](03-anforderungen.md).

### REQ-UI — Benutzeroberfläche

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-UI-001`](03-anforderungen.md#req-ui-001-chat-oberflache-der-eigenstandigen-webanwendung) | Chat-Oberfläche der eigenständigen Webanwendung | 3.1.1 |
| [`REQ-UI-002`](03-anforderungen.md#req-ui-002-chat-basierte-interaktion) | Chat-basierte Interaktion | 3.1.1 |
| [`REQ-UI-003`](03-anforderungen.md#req-ui-003-quellenanzeige-und-verlinkung) | Quellenanzeige und Verlinkung | 3.1.1 |
| [`REQ-UI-004`](03-anforderungen.md#req-ui-004-wcag-konformitat) | WCAG-Konformität | 3.1.1 |
| [`REQ-UI-005`](03-anforderungen.md#req-ui-005-anzeige-und-verwaltung-der-chat-historie) | Anzeige und Verwaltung der Chat-Historie | 3.1.1 |

### REQ-INT — Integration und Schnittstellen

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-INT-001`](03-anforderungen.md#req-int-001-offentliche-api-zur-integration-in-drittsoftware) | Öffentliche API zur Integration in Drittsoftware | 3.1.3 |
| [`REQ-INT-002`](03-anforderungen.md#req-int-002-schnittstelle-zu-normen-datenbanken) | Schnittstelle zu Normen-Datenbanken | 3.1.3 |
| [`REQ-INT-002A`](03-anforderungen.md#req-int-002a-nutzerbasierter-dokumenten-upload-und-temporare-modellanreicherung) | Nutzerbasierter Dokumenten-Upload und temporäre Modellanreicherung | 3.1.3 |
| [`REQ-INT-002B`](03-anforderungen.md#req-int-002b-isolation-nutzerspezifischer-dokumente) | Isolation nutzerspezifischer Dokumente | 3.1.3 |
| [`REQ-INT-002C`](03-anforderungen.md#req-int-002c-zeitlich-begrenzte-speicherung-hochgeladener-dokumente) | Zeitlich begrenzte Speicherung hochgeladener Dokumente | 3.1.3 |
| [`REQ-INT-003`](03-anforderungen.md#req-int-003-sso-authentifizierung) | SSO-Authentifizierung | 3.1.3 |
| [`REQ-INT-004`](03-anforderungen.md#req-int-004-llm-schnittstelle) | LLM-Schnittstelle | 3.1.3 |

### REQ-FUNC — Funktionale Anforderungen

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-FUNC-001`](03-anforderungen.md#req-func-001-beantwortung-normbasierter-fragen) | Beantwortung normbasierter Fragen | 3.2 |
| [`REQ-FUNC-002`](03-anforderungen.md#req-func-002-paraphrasierung-statt-volltext) | Paraphrasierung statt Volltext | 3.2 |
| [`REQ-FUNC-003`](03-anforderungen.md#req-func-003-fehler-und-fallback-antworten) | Fehler- und Fallback-Antworten | 3.2 |

### REQ-PERF — Performance

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-PERF-001`](03-anforderungen.md#req-perf-001-antwortzeit-chat) | Antwortzeit Chat | 3.3.1 |

### REQ-INST — Installation und Deployment

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-INST-001`](03-anforderungen.md#req-inst-001-deployment-auf-deutscher-stackit-infrastruktur) | Deployment auf deutscher StackIT-Infrastruktur | 3.5.1 |
| [`REQ-INST-002`](03-anforderungen.md#req-inst-002-automatisiertes-deployment) | Automatisiertes Deployment | 3.5.1 |
| [`REQ-INST-003`](03-anforderungen.md#req-inst-003-konfigurationsmanagement-uber-umgebungsvariablen) | Konfigurationsmanagement über Umgebungsvariablen | 3.5.1 |
| [`REQ-INST-004`](03-anforderungen.md#req-inst-004-rollback-fahigkeit) | Rollback-Fähigkeit | 3.5.1 |

### REQ-BUILD — Build und Auslieferung

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-BUILD-001`](03-anforderungen.md#req-build-001-reproduzierbare-builds) | Reproduzierbare Builds | 3.5.2 |
| [`REQ-BUILD-002`](03-anforderungen.md#req-build-002-eu-basierte-build-und-cicd-infrastruktur) | EU-basierte Build- und CI/CD-Infrastruktur | 3.5.2 |
| [`REQ-BUILD-003`](03-anforderungen.md#req-build-003-automatisierte-qualitatssicherung-im-build) | Automatisierte Qualitätssicherung im Build | 3.5.2 |

### REQ-DIST — Distribution

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-DIST-001`](03-anforderungen.md#req-dist-001-klare-trennung-von-umgebungen) | Klare Trennung von Umgebungen | 3.5.3 |
| [`REQ-DIST-002`](03-anforderungen.md#req-dist-002-skalierbare-verteilung-der-systemkomponenten) | Skalierbare Verteilung der Systemkomponenten | 3.5.3 |
| [`REQ-DIST-003`](03-anforderungen.md#req-dist-003-optionale-mandantenfahigkeit-fur-managed-hosting) | Optionale Mandantenfähigkeit für Managed Hosting | 3.5.3 |
| [`REQ-DIST-004`](03-anforderungen.md#req-dist-004-versionierte-auslieferung-der-anwendung) | Versionierte Auslieferung der Anwendung | 3.5.3 |

### REQ-OSS — Open Source und Governance

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-OSS-001`](03-anforderungen.md#req-oss-001-lizenzmodell-des-freien-kerns) | Lizenzmodell des freien Kerns | 3.7 |
| [`REQ-OSS-002`](03-anforderungen.md#req-oss-002-trennung-von-freiem-kern-und-kommerzieller-schicht) | Trennung von freiem Kern und kommerzieller Schicht | 3.7 |
| [`REQ-OSS-003`](03-anforderungen.md#req-oss-003-beitragsmodell-dco) | Beitragsmodell (DCO) | 3.7 |
| [`REQ-OSS-004`](03-anforderungen.md#req-oss-004-community-governance-und-sicherheitsprozess) | Community-Governance und Sicherheitsprozess | 3.7 |
| [`REQ-OSS-005`](03-anforderungen.md#req-oss-005-lizenzkonformitat-der-abhangigkeiten) | Lizenzkonformität der Abhängigkeiten | 3.7 |
| [`REQ-OSS-006`](03-anforderungen.md#req-oss-006-markenrechte) | Markenrechte | 3.7 |

### REQ-GIT — Quellcodeverwaltung und Git-Workflow

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-GIT-001`](03-anforderungen.md#req-git-001-github-als-fuhrende-plattform-fur-den-kern-quellcode) | GitHub als führende Plattform für den Kern-Quellcode (ADR-021) | 3.8 |
| [`REQ-GIT-002`](03-anforderungen.md#req-git-002-beitragsweg-uber-github) | Beitragsweg über GitHub (ADR-021) | 3.8 |
| [`REQ-GIT-003`](03-anforderungen.md#req-git-003-branch-und-release-strategie) | Branch- und Release-Strategie | 3.8 |
| [`REQ-GIT-004`](03-anforderungen.md#req-git-004-merge-request-richtlinie) | Merge-Request-Richtlinie | 3.8 |
| [`REQ-GIT-005`](03-anforderungen.md#req-git-005-integritat-der-lieferkette) | Integrität der Lieferkette | 3.8 |

### REQ-GRAPH — Referenzgraph

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-GRAPH-001`](03-anforderungen.md#req-graph-001-offener-normen-referenzgraph) | Offener Normen-Referenzgraph | 3.9 |
| [`REQ-GRAPH-002`](03-anforderungen.md#req-graph-002-schichtung-von-freiem-und-kommerziellem-graphanteil) | Schichtung von freiem und kommerziellem Graphanteil | 3.9 |
| [`REQ-GRAPH-003`](03-anforderungen.md#req-graph-003-graph-first-anfrageverarbeitung) | Graph-First-Anfrageverarbeitung | 3.9 |
| [`REQ-GRAPH-004`](03-anforderungen.md#req-graph-004-technologieoffenheit-der-graphhaltung) | Technologieoffenheit der Graphhaltung | 3.9 |
| [`REQ-GRAPH-005`](03-anforderungen.md#req-graph-005-internationalisierung-des-referenzgraphen) | Internationalisierung des Referenzgraphen | 3.9 |
| [`REQ-GRAPH-006`](03-anforderungen.md#req-graph-006-rechtsraumabhangige-lizenzklassifikation) | Rechtsraumabhängige Lizenzklassifikation | 3.9 |

### REQ-PART — Inhaltepartnerschaften und Vergütung

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-PART-001`](03-anforderungen.md#req-part-001-partnerportal-zur-inhaltezulieferung) | Partnerportal zur Inhaltezulieferung | 3.10 |
| [`REQ-PART-002`](03-anforderungen.md#req-part-002-quellenattribution-je-antwort) | Quellenattribution je Antwort | 3.10 |
| [`REQ-PART-003`](03-anforderungen.md#req-part-003-umsatzbeteiligung-und-pruffahige-abrechnung) | Umsatzbeteiligung und prüffähige Abrechnung | 3.10 |
| [`REQ-PART-004`](03-anforderungen.md#req-part-004-schutz-und-trennung-lizenzierter-volltextbestande) | Schutz und Trennung lizenzierter Volltextbestände | 3.10 |

### REQ-COM — Kommerzielle Zusatzdienste

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-COM-001`](03-anforderungen.md#req-com-001-erweiterungsschnittstelle) | Erweiterungsschnittstelle | 3.11 |
| [`REQ-COM-002`](03-anforderungen.md#req-com-002-integration-in-drittsoftware) | Integration in Drittsoftware | 3.11 |
| [`REQ-COM-003`](03-anforderungen.md#req-com-003-nutzungsbasierte-abrechnung) | Nutzungsbasierte Abrechnung | 3.11 |
| [`REQ-COM-004`](03-anforderungen.md#req-com-004-nachweisfahige-antworten-und-audit-trail) | Nachweisfähige Antworten und Audit-Trail | 3.11 |
| [`REQ-COM-005`](03-anforderungen.md#req-com-005-ausschluss-personalisierter-werbung) | Ausschluss personalisierter Werbung | 3.11 |

### REQ-PIPE — Datenerfassung und Verarbeitungskette

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-PIPE-001`](03-anforderungen.md#req-pipe-001-einheitliche-verarbeitungskette) | Einheitliche Verarbeitungskette | 3.12 |
| [`REQ-PIPE-002`](03-anforderungen.md#req-pipe-002-quellenregister) | Quellenregister | 3.12 |
| [`REQ-PIPE-003`](03-anforderungen.md#req-pipe-003-prufung-von-nutzungsvorbehalten) | Prüfung von Nutzungsvorbehalten | 3.12 |
| [`REQ-PIPE-004`](03-anforderungen.md#req-pipe-004-rechteklassifikation-als-verarbeitungstor) | Rechteklassifikation als Verarbeitungstor | 3.12 |
| [`REQ-PIPE-005`](03-anforderungen.md#req-pipe-005-abstammung-und-kaskadierende-rucknahme) | Abstammung und kaskadierende Rücknahme | 3.12 |
| [`REQ-PIPE-006`](03-anforderungen.md#req-pipe-006-wiederholbarkeit-und-inhaltsadressierung) | Wiederholbarkeit und Inhaltsadressierung | 3.12 |
| [`REQ-PIPE-008`](03-anforderungen.md#req-pipe-008-ausschluss-kommerziell-verwerteter-katalogbestande) | Ausschluss kommerziell verwerteter Katalogbestände | 3.12 |
| [`REQ-PIPE-009`](03-anforderungen.md#req-pipe-009-erstbestand-aus-frei-zuganglichen-quellen) | Erstbestand aus frei zugänglichen Quellen | 3.12 |
| [`REQ-PIPE-007`](03-anforderungen.md#req-pipe-007-manuelle-prufung-der-identitatsauflosung) | Manuelle Prüfung der Identitätsauflösung | 3.12 |

### REQ-SEC — Verschlüsselung und Sicherheit

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-SEC-001`](03-anforderungen.md#req-sec-001-verschlusselung-ruhender-daten) | Verschlüsselung ruhender Daten | 3.13 |
| [`REQ-SEC-002`](03-anforderungen.md#req-sec-002-schlusselverwaltung) | Schlüsselverwaltung | 3.13 |
| [`REQ-SEC-003`](03-anforderungen.md#req-sec-003-herausgeberspezifische-datenschlussel-und-kryptographisches-loschen) | Herausgeberspezifische Datenschlüssel und kryptographisches Löschen | 3.13 |
| [`REQ-SEC-004`](03-anforderungen.md#req-sec-004-schutz-vor-massenextraktion) | Schutz vor Massenextraktion | 3.13 |

### REQ-DRM — Geschützte Anzeige und Offline-Nutzung

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-DRM-001`](03-anforderungen.md#req-drm-001-anzeige-ohne-herausgebbare-datei) | Anzeige ohne herausgebbare Datei | 3.14 |
| [`REQ-DRM-002`](03-anforderungen.md#req-drm-002-offline-nutzung-mit-befristeter-berechtigung) | Offline-Nutzung mit befristeter Berechtigung | 3.14 |
| [`REQ-DRM-003`](03-anforderungen.md#req-drm-003-nutzerbezogene-kennzeichnung) | Nutzerbezogene Kennzeichnung | 3.14 |
| [`REQ-DRM-004`](03-anforderungen.md#req-drm-004-zuordnung-der-schutzkomponenten-zur-kommerziellen-schicht) | Zuordnung der Schutzkomponenten zur kommerziellen Schicht | 3.14 |

### REQ-MOB — Mobile Bereitstellung

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-MOB-001`](03-anforderungen.md#req-mob-001-progressive-web-app-als-primarer-mobiler-zugang) | Progressive Web App als primärer mobiler Zugang | 3.15 |
| [`REQ-MOB-002`](03-anforderungen.md#req-mob-002-native-anwendung-fur-lizenzierte-offline-inhalte) | Native Anwendung für lizenzierte Offline-Inhalte | 3.15 |
| [`REQ-MOB-003`](03-anforderungen.md#req-mob-003-abstrahierte-offline-schicht) | Abstrahierte Offline-Schicht | 3.15 |
| [`REQ-MOB-004`](03-anforderungen.md#req-mob-004-vertriebswege-und-lizenzvertraglichkeit) | Vertriebswege und Lizenzverträglichkeit | 3.15 |

### REQ-ACC — Zugang und Kontopflicht

| ID | Titel | Kapitel |
|---|---|---|
| [`REQ-ACC-001`](03-anforderungen.md#req-acc-001-anonyme-basisnutzung) | Anonyme Basisnutzung | 3.16 |
| [`REQ-ACC-002`](03-anforderungen.md#req-acc-002-inhaltliche-begrenzung-anonymer-zugange) | Inhaltliche Begrenzung anonymer Zugänge | 3.16 |
| [`REQ-ACC-003`](03-anforderungen.md#req-acc-003-kontingent-fur-anonyme-nutzung) | Kontingent für anonyme Nutzung | 3.16 |
| [`REQ-ACC-004`](03-anforderungen.md#req-acc-004-kontopflichtige-funktionen) | Kontopflichtige Funktionen | 3.16 |
