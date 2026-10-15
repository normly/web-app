# Glossary

Terms from the standards domain keep their German form where there's no
established English equivalent.

**Normenausschuss**
: The body responsible for the content of a standard and its upkeep.

**Reference graph**
: The machine-readable graph of regulations, legal texts, and the
  relationships between them (replacement, reference, adoption) —
  normly's central data asset.

**Work**
: A regulation as a language-independent node in the reference graph. DIN
  EN ISO 9001 and BS EN ISO 9001 are the same Work; national adoptions and
  translations are relationships or attributes, not separate Works. See
  the "Identifikatoren" section in `CLAUDE.md`.

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
  [License Model](concepts/lizenzmodell.md#rights-classification-by-category).

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
: The single pipeline from source to delivery that all content passes
  through, regardless of provenance (German *Verarbeitungskette*).

**Contribution facade**
: Historical term from ADR-004: a public GitHub presence for issues and
  pull requests in front of a primary code platform elsewhere.
  Superseded by ADR-021.
