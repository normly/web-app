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
  [ADR-001](adr/README.md#adr-001-open-core-modell-statt-white-label-produkt).

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
| Abstammung | lineage |
| Akzeptanzkriterium, Abnahmekriterium | acceptance criterion (both; the SRS uses them as synonyms) |
| anerkannter Stand der Technik | recognized state of the art |
| Attributionserfassung | attribution capture (exception to Erfassung → acquisition: recording attribution data per answer) |
| Ausgabestand | edition |
| Auslieferung (shipping software to operators) | shipping |
| Ausspielung (output to users at the end of the processing chain) | output |
| Begründung / Entscheidung / Konsequenz | Rationale / Decision / Consequence |
| Beitragsfassade | contribution facade (explained at first mention) |
| Bestand, Bestände | collection, collections |
| Erfassung, Datenerfassung | acquisition, data acquisition |
| Ersetzung | replacement (matches the graph edge `REPLACES`; the existing "supersession" in the README stays) |
| Herausgeber | publisher |
| Herkunft (attribute) | provenance |
| (sachliche) Herkunftsangabe | (factual) statement of origin |
| kommunizierbarer Prototyp | presentable prototype |
| Konto-, Kontolöschung | account deletion |
| Lizenzklassifikation | license classification (distinct from rights classification) |
| Nachtrag | addendum |
| Norm, Normen | norm, norms |
| Normen und Regelwerke / Normen- und Regelwerkswissen | norms and standards / knowledge about norms and standards |
| Normenausschuss, Trägerorganisation | unchanged (German loanwords, see above) |
| Nutzungsvorbehalt | rights reservation |
| Quellenregister | source register |
| Quelllieferung | source delivery |
| Rechteklassifikation | rights classification |
| Rechtsraum | jurisdiction |
| Referenzgraph | reference graph |
| Regelwerk, Regelwerke | standards |
| Rollback (deployment) | rollback |
| Rücknahme | withdrawal |
| Rückzug | withdrawal (same concept as Rücknahme, REQ-PIPE-005) |
| Schlüssel, Datenschlüssel je Herausgeber | data key per publisher |
| Sicherung | backup |
| Tombstone | tombstone |
| Trägerschaft | stewardship |
| Verarbeitungskette | processing chain |
| Wissensbasis, Wissensbestand | knowledge base |

**Compounds follow their stem.** Rechtsnorm → legal norm, EU-Normen → EU
norms, Regelwerkswissen → knowledge about standards, Regelwerksreihen →
standards series, Regelwerksverzeichnisse → standards registers. If a
compound has no obvious reading under this rule, the maintainers decide.

**Norm vs. standard.** "Norm" and "standard" are separate terms here and
are never interchangeable: *norm* is the German *Norm*, *standard* is the
German *Regelwerk*. "Standard" in its ordinary technical sense ("standard
library", "standard output") is untouched.

**Withdrawal vs. withdrawn.** *Withdrawal* is the removal of a source
delivery and all artifacts derived from it; a norm that is *withdrawn* is
one its publisher has withdrawn, a status recorded in the graph as the edge
`WITHDRAWN_BY`.
