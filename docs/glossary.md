# Glossary

Terms from the standards domain keep their German form where there's no
established English equivalent.

**Normenausschuss**
: The body responsible for the content of a standard and its upkeep.

**Reference graph**
: The machine-readable graph of standards, legal texts, and the
  relationships between them (replacement, reference, adoption) —
  normly's central data asset.

**Work**
: A standard as a language-independent node in the reference graph. DIN
  EN ISO 9001 and BS EN ISO 9001 are the same Work; national adoptions and
  translations are relationships and attributes, respectively, not separate
  Works. See
  the "Identifiers" section in `CLAUDE.md`.

**Trägerorganisation**
: Holds the brand, open data, and source code; responsible for the free
  core and relationships with publishers and the community. Separate from
  a future commercial entity — see
  [ADR-001](adr/README.md#adr-001-open-core-model-instead-of-a-white-label-product).

**Normenausschuss vs. publisher**
: The publisher (e.g. DIN, VDI, DGUV) releases a standard; the
  Normenausschuss develops its content. For rights classification, the
  publisher is what counts.

**Category A–D**
: Rights classification per source, see
  [License Model](concepts/license-model.md#rights-classification-by-category).

**Norm**
: A document issued by a standardization body (German *Norm*), for
  example DIN EN ISO 9001. In this repository "norm" always means this,
  never a social convention.

**Standards**
: The collective term for all rule sets normly covers (German
  *Regelwerk*, plural *Regelwerke*): norms, but also legal texts and
  rules from bodies such as DGUV or BAuA. "Norm" and "standard" are
  separate terms here: a norm is one kind of standard.

**Lineage**
: The chain of derivation from a source delivery to every artifact
  built from it (section, segment, embedding, graph edge, export file).
  Makes withdrawal possible. Not the same as provenance.

**Provenance**
: Where a piece of content comes from (publisher, retrieval path, legal
  basis, jurisdiction, check date). An attribute of a record, kept in
  the source register.

**Source delivery**
: One batch of content received from a source, the unit that lineage
  refers back to and that can be withdrawn as a whole.

**Withdrawal**
: Removing a source delivery and everything derived from it, for example
  at the end of a contract or after a takedown request. Distinct from
  a deployment *rollback*.

**Edition**
: The issue state of a Work (German *Ausgabestand*); part of its
  identifier together with publisher, number and part number.

**Processing chain**
: The single pipeline from source to output that all content passes
  through, regardless of provenance (German *Verarbeitungskette*).

**Contribution facade**
: Historical term from ADR-004: a public GitHub presence for issues and
  pull requests in front of a primary code platform elsewhere.
  Superseded by ADR-021.

## Terminology (binding)

This table is binding for all translation and all new text in this
repository; a term missing here is decided by the maintainers and then
added here.

| German | English |
|---|---|
| abgelöst durch / ersetzt / ergänzt (ADR status) | superseded by / replaces / amends |
| Abnahmekriterium (SRS field, a concrete acceptance test) | Acceptance test |
| Abstammung | lineage |
| Akzeptanzkriterium (SRS field, a list) | Acceptance criteria |
| Alterung (of tombstones) | expiry |
| anerkannter Stand der Technik | recognized state of the art |
| Anmeldung | sign-in |
| Attributionserfassung | attribution capture (recording attribution data per answer; see Erfassen → capture) |
| Aufbewahrung | retention |
| Aufräumbefehl | cleanup command |
| Auftraggeber (the project owner) | owner |
| Ausgabestand | edition |
| ausliefern (content shown in the display, not as a file, REQ-DRM-004) | serve |
| Auslieferung (shipping software to operators) | shipping (software to operators) |
| Auslieferung (of a file to an end user), ausgeliefert, Dateiauslieferung | handed out, file download (distinct from shipping software to operators) |
| Ausspielung (output to users at the end of the processing chain) | output |
| baut auf (ADR status) | builds on |
| Befund, Befunde (review) | finding(s) |
| Begründung / Entscheidung / Konsequenz | Rationale / Decision / Consequence |
| Beitragsfassade | contribution facade (explained at first mention) |
| Beitragsweg | contribution path |
| Beobachtungsliste | watchlist |
| beschlossen / favorisiert / offen (ADR status) | accepted / preferred / open |
| Bestand, Bestände | collection, collections (content); data stores (in the sense of storage: database, object storage, indexes, logs, backups) |
| Betreiber | operator |
| Betriebsguide | operations guide |
| Bezeichner (of a norm, e.g. "DIN EN ISO 9001") | designation (code: `DocumentDesignation`) |
| Bezeichner (programming sense) | identifier |
| Bezugsquelle (des Herausgebers) | (publisher's) point of purchase |
| Datenbestand | collection (not "data collection", which reads as the act of collecting) |
| Datenlizenz | data license |
| Datenstand, Datenstände | data state (point in time, e.g. rollback); data version(s) (versioned knowledge base dump) |
| Drittsoftware, Drittsysteme | third-party software, third-party systems |
| Editionshistorie | edition history |
| Entscheidungsdokumentation | architecture decision records |
| Erfassen, Erfassung (recording usage, attribution, billing data or delivery metadata, REQ-PART-001/002) | capture |
| Erfassung, Datenerfassung (taking in sources and data, processing chain, REQ-PIPE) | acquisition, data acquisition |
| Ersetzung | replacement (matches the graph edge `REPLACES`; the existing "supersession" in the README stays) |
| Expertensysteme | expert systems |
| Fassung, Fassungen (of a norm) | version(s) (edition stays for Ausgabestand) |
| Folgearbeit, Folgeaufgabe | follow-up work, follow-up task |
| führend (platform, registry) | primary |
| gekennzeichnet (plain labeling, e.g. als bezahlt, als Zitat) | labeled as paid, marked as quotations (plain sense, not the DRM marking) |
| Hauptzweig | main branch |
| Herausgeber | publisher |
| Herkunft (attribute) | provenance |
| Herkunftsadresse | client IP address |
| (sachliche) Herkunftsangabe | (factual) statement of origin |
| hinfällig (status) | obsolete |
| Identifikator, Identifikatorschema | identifier, identifier scheme |
| Identitätsauflösung | identity resolution |
| Implementierungsplan | implementation plan |
| Inhaltepartnerschaft | content partnership |
| Inhaltezulieferung | content supply |
| Kennung (record ID, e.g. "Google-Kennung") | ID |
| Kennungen (in the export, ADR-027) | readable document IDs (export uses publisher/number/edition/part) |
| Kennzeichnung (of displays/copies, ADR-015, REQ-DRM-003) | marking |
| Kennzeichnung (source-register attribute, REQ-PIPE-008), gekennzeichnet als … | flag, flagged as … |
| kommunizierbarer Prototyp | presentable prototype |
| Kontingent | quota |
| Konto-, Kontolöschung | account deletion |
| Kontobezug | account reference |
| Kontopflicht | account requirement |
| Kopierschutz | copy protection |
| kryptographisches Löschen | cryptographic erasure |
| Lizenzklassifikation | license classification (distinct from rights classification) |
| Löschprotokoll | deletion log |
| Mandantenfähigkeit | multi-tenancy |
| Markieren (von Text) | selecting (text) (not "marking") |
| Massenextraktion | bulk extraction |
| Modellherkunft, Modellherkunftsregel | model origin, model-origin rule |
| Nachfolgestandard, Nachfolgenorm (successor of a norm, e.g. a harmonized EN) | successor norm |
| Nachtrag | addendum |
| Nachverfolgbarkeit | traceability |
| Neu gefasst durch (SRS status) | revised by |
| Neulieferung | re-delivery |
| Nicht betroffen (ADR label) | Not affected |
| Norm, Normen | norm, norms |
| Normen und Regelwerke / Normen- und Regelwerkswissen | norms and standards / knowledge about norms and standards |
| Normenanbieter (sellers of norms, e.g. DIN Media/Nautos) | norm vendor(s) |
| Normenausschuss, Trägerorganisation | unchanged (German loanwords, see above) |
| normengebende / normgebende Vereine | norm-setting associations |
| Normungsorganisation | standardization body |
| Nutzerwunsch, Nutzerentscheidung (the project owner) | at the owner's request, owner decision |
| Nutzungsvorbehalt | rights reservation |
| Offene Punkte | Open items |
| Partnerschaftsleiter / Volltext-Sprung (ADR-013) | partnership ladder / full-text leap |
| Quellenangabe, Quellenanzeige (in chat answers) | citation(s) (code: citations) |
| Quellenattribution (partner billing, REQ-PART-002) | source attribution |
| Quellenregister | source register |
| Quelllieferung | source delivery |
| Ratenbegrenzung | rate limiting |
| Rechteklassifikation | rights classification |
| Rechtetor | rights gate |
| Rechtsraum | jurisdiction |
| Referenzgraph | reference graph |
| Regelwerk, Regelwerke | standards |
| Richtlinie(n); EU-Richtlinie(n) | guideline(s); EU directive(s) |
| Rollback (deployment) | rollback |
| Rücknahme | withdrawal |
| Rückzug | withdrawal (same concept as Rücknahme, REQ-PIPE-005) |
| Schlüssel, Datenschlüssel je Herausgeber | data key per publisher |
| Schlüsselzeremonie | key ceremony |
| Selbsthoster | self-hosters |
| Sicherung | backup |
| Sicherungs-Stand / -Stände | backup(s) |
| Stand (date, as a label) | As of |
| Teilprojekt | sub-project |
| Tombstone | tombstone |
| Trägerschaft | stewardship |
| Umsatzbeteiligung | revenue share |
| Umsetzung (ADR label) | Implementation |
| Verarbeitungskette | processing chain |
| Vergütung | remuneration |
| Verläufe (chat) | histories |
| Verworfen (ADR label) | Rejected |
| Weitere Informationen (SRS field) | Further information |
| Wichtig (SRS label) | Important |
| Widerruf | revocation (code: `revoked_at`) |
| Wissensbasis, Wissensbestand | knowledge base |
| Zugang (countable, an individual user's access) | user access (uncountable access and anonymous access stay "access") |
| Zugangsweg | access path |
| zurückgezogen (documents/edges kept as tombstones), zurückgezogene Kennungen | retired, retired IDs (code: `retired_at`; the process stays "withdrawal") |
| Zurückziehung (of a norm by its standardization body), Zurückziehungskette | withdrawn (norm status), chains of withdrawn norms |
| Zusatzdienste | add-on services |

**Compounds follow their stem.** Rechtsnorm → legal norm, EU-Normen → EU
norms, Regelwerkswissen → knowledge about standards, Regelwerksreihen →
standards series, Regelwerksverzeichnisse → standards registers. If a
compound has no obvious reading under this rule, the maintainers decide.

**Norm vs. standard.** "Norm" and "standard" are separate terms here and
are never interchangeable: *norm* is the German *Norm*, *standard* is the
German *Regelwerk*. "Standard" in its ordinary technical sense ("standard
library", "standard output") is untouched.

**Statutes.** Names of German statutes stay German, with an English
gloss at first mention per file: "UrhG (German Copyright Act)". EU
regulations use their official English name, with the German short name
at first mention per file: "GDPR (DSGVO)"; afterwards "GDPR".

**Withdrawal vs. retired vs. withdrawn.** Three separate terms:

- The act of a publisher or source pulling content (Rücknahme, Rückzug,
  "zieht … zurück") is **withdraw / withdrawal**: the removal of a source
  delivery and all artifacts derived from it. Deliveries carry
  `withdrawn_at`.
- The resulting database state of a tombstoned document or edge is
  **retired** (`retired_at`), e.g. "retired IDs".
- A norm withdrawn by its standardization body is **withdrawn**: a norm
  status, recorded in the graph as the edge `WITHDRAWN_BY`.
